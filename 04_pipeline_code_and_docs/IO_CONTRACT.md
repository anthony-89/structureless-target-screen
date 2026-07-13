# Module I/O contract

Every module is a function returning a `ModuleResult` (`structure_to_screen/status.py`):

```python
ModuleResult(module, status, reason="", confidence=None,
             data={}, artifacts=[], metrics={}, elapsed_s=None)
# status ∈ {ok, low_confidence, unscreenable};  can_continue = status in {ok, low_confidence}
```

The orchestrator chains them and short-circuits the moment `can_continue` is false.
All file paths are written under `--workdir/<module>/`.

| # | Module | Reads | Writes | `unscreenable` when | `low_confidence` when |
|---|--------|-------|--------|---------------------|-----------------------|
| M1 | `m1_intake` | UniProt acc | `m1/<acc>.fasta`, `_af.cif`, `_pae.json`, `intake.json` | no UniProt seq, or no AlphaFold DB model (→ predict de novo) | — |
| M2 | `m2_qc` | M1 cif | `m2/qc.json` | no structure to QC | mean pLDDT < `min_mean_plddt` (70) |
| M3 | `m3_receptor` | M1 structure | `m3/receptor.pdb`, `receptor.pdbqt` | prep fails / empty PDBQT | — |
| M4 | `m4_site` | M1 fasta, M3 receptor | `m4/binding_site.json`, `m4/homologs/*.pdb` | **no liganded homolog found**, or superposition RMSD > `site_rmsd_low` (4 Å) | superposition RMSD > `site_rmsd_ok` (2.5 Å) |
| M5 | `m5_validate` | M3 receptor, M4 site | `m5/validation.json` | anchor does not dock in the site | anchor engages pocket but pose shifted (overlap < `pose_overlap_ok`) → `pose_trust` |
| M6 | `m6_library` | modulator SMILES | `m6/candidate_library.csv` | no compounds found | < 10 compounds |
| M7 | `m7_screen` | M3 receptor, M4 site, M6 library | `m7/docking_scores.csv` | nothing docked | > half of ligands fail to dock |
| M8 | `m8_prioritize` | M7 scores, M6 library | `m8/shortlist.csv` | nothing to prioritize | inherits upstream low_confidence (→ `interpretation: comparative-within-box`) |

Top-level output: `run_manifest.json` — `{target, modulator, overall_status,
reached_module, results:[ModuleResult...]}`.

## Thresholds
All thresholds live in `PipelineConfig` (`config.py`) and can be overridden per run:
`min_mean_plddt`, `homolog_identity_cutoff`, `homolog_evalue_cutoff`, `site_rmsd_ok`,
`site_rmsd_low`, `pose_overlap_ok`, `pose_contact_jaccard_low`, plus docking box /
screen params (`box_size`, `exhaustiveness`, `num_modes`, `seed`).

## Live vs. cached
Each module is **cache-first**: if its output files already exist under `--workdir`,
it reuses them (resumable runs). Every module also has a live cold-start path (no
`NotImplementedError` stubs remain). The `verified` column records what has actually been
exercised end-to-end so far — an honest distinction, since implemented ≠ tested:

| module | live path | verified in-repo |
|--------|-----------|------------------|
| M1 | UniProt FASTA + AlphaFold DB model fetch | ✅ live (OPLAH, c-Myc) |
| M2 | pLDDT confidence parse | ✅ live (OPLAH, c-Myc) |
| M3 | trim → protonate → PDBQT (mmCIF auto-converted) | ✅ live (c-Myc fresh build) |
| M4 | RCSB liganded-homolog search + superposition transplant (`_homolog.py`) | ✅ live (OPLAH 7HK7, c-Myc) |
| M5 | Meeko ligand prep + Vina dock of the anchor; pose overlap / contact-Jaccard vs the transplanted reference ligand (`_dock.dock_reference`) | ✅ live (5-AMP, −8.1 kcal/mol) |
| M6 | ChEMBL similarity/substructure build, or user-supplied `m6/candidate_library.csv` (`_library.build_library`) | ⚙️ implemented; BYO-CSV path used; live ChEMBL build not yet run end-to-end |
| M7 | parallel Vina screen, per-ligand atomic `.sc` writes + resume-on-restart (`_dock.screen_library`) | ⚙️ implemented + unit-tested; not yet run on a fresh target through the package API |
| M8 | consensus rank + scaffold diversity (`_prioritize.py`) | ✅ live (OPLAH shortlist) |

The M7 screen is designed to be crash-resilient: each ligand's score is written
atomically (`os.replace`) as it finishes and re-running skips completed ligands, so a
killed process loses at most the ligands in flight — the failure mode a multi-hour CPU
screen actually hits. (The standalone validation docker this pattern is ported from *has*
survived multi-hour 1,000+-ligand batches; the packaged `screen_library` wrapper carries
the same logic but has so far been exercised only by the unit tests.) M5/M6/M7 require the
`dock` extra (RDKit, Meeko) and the external `vina` binary on PATH.

See `MCP_TOOLS.md` for the agent-facing tool surface.

## M5 confidence diagnostic (box-contraction sweep)

To distinguish a rigid-receptor artifact from a pocket-mislocalization, M5 can run
a box-contraction sweep: redock the anchor in progressively tighter boxes centered
on the transplanted reference position and watch the affinity.

For OPLAH/5-AMP the affinity **collapses** as the box forces the ligand onto the
reference (−8.8 → −6.0 → −3.7 → **+3.8** kcal/mol as the box edge shrinks 24→10 Å;
a steric clash once the ligand is forced to ~4 Å of the reference), while in the
open box the ligand docks well ~10 Å away in the same Gly-loop/K34/F18 region.

**Verdict: `induced_fit_limited`** — the pocket is correctly localized, but the exact
holo nucleotide pose needs receptor flexibility the apo AlphaFold model lacks. The
diagnostic raises `pose_trust` from 0.41 (geometry only) to 0.59 (site validated as
correct) — still `low_confidence`, because the exact pose is not recovered. Orthogonal
fix: co-folding (Boltz-2) or flexible-loop docking. See `m5_diagnostic.png`.
