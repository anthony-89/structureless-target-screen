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
| M4 | `m4_site` | M1 fasta, M3 receptor | `m4/binding_site.json`, `m4/homologs/*.pdb`, `m4/fpocket/*`, `m4/select/*` | **no proposer yields a box the modulator engages** (`pocket_source:"none_found"`) | modulator engages but weakly, or only one method localised the site |
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
| M4 | **ensemble**: homolog transplant (`_homolog.py`) + fpocket (druggability-ranked) + DiffDock blind pose, adjudicated by docking the modulator into each candidate (`_site_ensemble.py`) | ✅ live (OPLAH: fpocket wins, modulator −8.6 kcal/mol, 2.8 Å from hand-found box) |
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

## M4 ensemble site selection (the modulator adjudicates)

M4 no longer trusts a single site-finder. It runs several **pluggable proposers** and
lets the known modulator's own docking decide which proposed pocket is real
(`_site_ensemble.py`). Which proposers run is `cfg.site_proposers` (default all three):

| proposer | signal | notes |
|----------|--------|-------|
| `homolog` | liganded-homolog transplant (the original M4) | RCSB seams stay monkeypatchable in `m4_site` |
| `fpocket` | ligand-free cavity detection, ranked by **druggability** | fpocket's default `Score` buries real sites — rank by druggability (`FAILURE_MODES.md`) |
| `diffdock` | top-confidence blind pose of the modulator | non-blocking by default: reads a completed dock (`cfg.diffdock_poses_dir`) or the per-run cache `m4/diffdock/<complex>/`. Set `cfg.diffdock_run=True` + `cfg.diffdock_repo` to have M4 launch DiffDock itself (~1 h CPU), cache the poses, and reuse them on resume |

**Adjudication.** Each proposer returns candidate box centre(s) + residues (or `[]` on any
failure — a proposer never raises). The modulator is docked into a uniform probe box
(`cfg.box_size`) on every candidate and scored:

```
composite = 0.40*coverage + 0.40*affinity_norm + 0.20*consensus
  coverage      = frac of the modulator's docked contacts that fall in the proposer's
                  residues (size-robust: a large correct pocket is not penalised, unlike Jaccard)
  affinity_norm = (aff − (−4)) / ((−12) − (−4)), clipped to [0,1]
  consensus     = other methods whose box centre is within cfg.consensus_radius_A (8 Å)
```

The best-engaged candidate wins; the rest are written to `runner_up_sites` with a
`viable`/`rejected` flag — never discarded. Status: **ok** when the winner is engaged well
(`coverage ≥ site_select_coverage_ok`, `aff ≤ site_select_affinity_ok`) **and** ≥1 other
method agrees; **low_confidence** when engaged but weak or single-method; **unscreenable**
(`pocket_source:"none_found"`) when the modulator engages no candidate — an honest failure
grounded in the modulator's binding, not merely in homolog availability.

Added `binding_site.json` keys (all backward-compatible; `box_center`/`box_size`/
`site_residues` unchanged): `selection{modulator_affinity_kcal_mol, modulator_coverage,
modulator_contact_jaccard, consensus_n_methods_agreeing, composite_score, meta}`,
`runner_up_sites[]`, `proposers_run[]`, `proposers_failed[]`. Config:
`site_proposers, fpocket_bin, fpocket_top_k, diffdock_poses_dir, consensus_radius_A,
site_select_coverage_ok, site_select_affinity_ok`. The cold-start path needs the `dock`
extra (RDKit/Meeko/Vina) since it docks the modulator to choose; the cache-first path
(reusing `m4/binding_site.json`) has no heavy deps, as before.

**OPLAH result (live):** with no reliable liganded homolog, fpocket wins — the modulator
docks at **−8.6 kcal/mol**, its box centre **2.8 Å** from the hand-found AMP box; DiffDock's
blind pose is reported as a runner-up but sits ~9 Å off, so the site is **low_confidence**
(single strong method), consistent with the M5 `induced_fit_limited` verdict below.

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
