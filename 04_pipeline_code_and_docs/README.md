# structure-to-screen

Agent-callable pipeline that turns a **protein target with no experimental 3D structure**
plus **one known small-molecule modulator** into a prioritized virtual-screen shortlist —
orchestrating UniProt, AlphaFold DB, RCSB PDB, ChEMBL and AutoDock Vina.

## What we did, why, and in what order

The reference case: OPLAH has **no solved 3D structure** and no known binding site, but one
molecule (**5-AMP**) is known to activate it. This pipeline goes from that single clue to a
ranked list of new compounds to test. There are **three distinct stages** — keep them separate
when reading the results:

1. **Get a structure.** No experimental structure exists → use the AlphaFold model (1,288 aa).
2. **Find WHERE the modulator binds — without pre-deciding it.** *(Site discovery — NOT a
   compound screen.)* Detect pockets unbiasedly across the whole protein (P2Rank + fpocket),
   then dock 5-AMP blind and let it choose its own site. Three independent methods converge on
   one pocket (a `D-x-G-G-T` phosphate cleft; blind dock lands 2.2 Å away) → we trust the site.
3. **Discovery screen — two arms, into that pocket.** *(This is the screen — it produces the
   hits.)* **Arm 1 (nucleotide/analog):** sanity check — recovers AMP-like mimics (dGMP, cAMP,
   plus approved antivirals entecavir & sofosbuvir). **Arm 2 (diverse ZINC, ~5,000 compounds,
   run locally):** discover *new* chemistry — 775 out-score AMP, 379 genuinely novel; **top hit
   ZINC4126706, −10.81 kcal/mol, Tanimoto to AMP 0.06.**
4. **Validate the method retrospectively.** *(A control, NOT discovery — see "Retrospective
   validation" below.)* Hide 5-AMP in a large library and check the pipeline re-finds it.

> Docking ranks hypotheses, not measured affinities — every hit is a lead to test in an assay.

**Modulator-agnostic.** The pipeline works identically whether your known active is an
inhibitor, an activator, or a mechanism-unknown binder — you anchor the screen on whatever
molecule you have. It was *motivated* by the harder, less-served case (**enhancers /
activators**, where the reference target OPLAH + 5-AMP lives), but nothing in the pipeline
restricts it to that: `modulator_mode` is recorded as provenance, not used to branch behavior.

**Bring your own library.** The candidate set is pluggable. Drop a `candidate_library.csv`
into the run's `m6/` directory and the screen uses it directly — any open collection works
(approved-drug sets, orphan/rare-disease libraries, ChEMBL subsets, metabolite panels, or
your own list). Only the from-scratch ChEMBL analog-builder is invoked when you *don't* supply
one.

## The status contract (why it's agent-callable)
Every module returns a machine-readable status an agent can branch on:

| status | meaning | pipeline behavior |
|--------|---------|-------------------|
| `ok` | trustworthy result | continue |
| `low_confidence` | result produced, a quantified check is marginal | continue, caveat attached |
| `unscreenable` | cannot produce a usable result (e.g. no liganded homolog) | short-circuit, agent told why |

## Quickstart
> The installable package lives in `pipeline_src/` — run the commands in this README from there:
> `cd 04_pipeline_code_and_docs/pipeline_src` first.
```bash
pip install -e .
python -m structure_to_screen \
  --target O14841 \
  --modulator "Nc1ncnc2c1ncn2[C@@H]1O[C@H](COP(=O)([O-])[O-])[C@@H](O)[C@H]1O" \
  --modulator-name 5-AMP --modulator-mode activator \
  --workdir examples/oplah_run
```
Reference run output (OPLAH / 5-AMP), showing the honest low-confidence propagation:
```
[M5_validate]   low_confidence  pose_trust 0.59 :: anchor engages pocket but spatially shifted (induced-fit limited)
[M8_prioritize] low_confidence  :: 15-compound shortlist (comparative-within-box, see M5)
== overall: low_confidence ==
```


## Cold start on your own target
The quickstart above reuses shipped example outputs. Every module also has a live
cold-start path (no stubs), so a **brand-new** target with no cache runs from your UniProt
accession + modulator SMILES. M1–M5 and M8 have been exercised live; the M6 ChEMBL build
and the packaged M7 screen wrapper are implemented and unit-tested but not yet run
end-to-end on a fresh target through the package API (see the `verified` column in
[`docs/IO_CONTRACT.md`](pipeline_src/docs/IO_CONTRACT.md)) — treat a first cold-start screen as a run to
watch, not fire-and-forget:
```bash
pip install -e ".[dock]"          # RDKit + Meeko; also needs `vina` on PATH
python -m structure_to_screen \
  --target <UNIPROT_ID> --modulator "<SMILES>" \
  --modulator-name my_ligand --workdir runs/my_target
```
M1/M2/M4 hit UniProt / AlphaFold DB / RCSB; M5 docks your modulator as the anchor; M6
builds a ChEMBL analog library (or drop your own `m6/candidate_library.csv`); M7 runs the
Vina screen with per-ligand atomic checkpointing (kill it and re-run — it resumes). A CPU
screen of ~1,000–1,500 ligands takes a few hours. See
[`docs/IO_CONTRACT.md`](pipeline_src/docs/IO_CONTRACT.md) for the per-module live/cached contract.

**No big machine? Only M7 is compute-heavy** — M1–M6/M8 run on a laptop in minutes, so you
run everything locally and offload just the screen. The docking step can also run on a free
cloud GPU (e.g. Google Colab or Kaggle) using the same box and scoring, with the scores handed
back for the pipeline to finish locally. See [`COMPUTE.md`](COMPUTE.md) for the step-by-step and
the other cheapest-first options.

## Demo — two targets, two honest outcomes
```bash
PYTHONPATH=. python examples/demo.py
```
Runs OPLAH/5-AMP (→ a `low_confidence` shortlist) and c-Myc/10058-F4 (→ a graceful
`unscreenable` refusal) back-to-back. See [`docs/FAILURE_MODES.md`](pipeline_src/docs/FAILURE_MODES.md)
for the full catalogue of how each module degrades, and
[`examples/STRESS_TEST_myc.md`](pipeline_src/examples/STRESS_TEST_myc.md) for the stress-test writeup.

## Use it as an MCP server (agent-callable)
```bash
python -m structure_to_screen.mcp_server      # stdio transport
```
Three tools, each returning machine-readable status:
- `run_full_pipeline(target, modulator_smiles, modulator_name, modulator_mode, run_id)`
- `check_status(run_id)` — poll without recomputing
- `get_shortlist(run_id, top_n)` — ranked hits, **or** a reasoned "why not"

MCP client config:
```json
{ "mcpServers": {
    "structure-to-screen": {
      "command": "python", "args": ["-m", "structure_to_screen.mcp_server"] } } }
```
Full tool reference: [`docs/MCP_TOOLS.md`](pipeline_src/docs/MCP_TOOLS.md).

## The method — how it works without a crystal structure
The core problem: you have a target with **no experimental 3D structure** and **one known
modulator**, and you want a ranked list of related compounds to test. The pipeline chains
eight modules:

| # | Module | What it does |
|---|--------|--------------|
| M1 | intake | UniProt sequence + AlphaFold DB model (or hand off to a predictor) |
| M2 | QC | pLDDT confidence gate — flags disordered / low-confidence models |
| M3 | receptor | trim, protonate, PDBQT prep |
| M4 | **site** | **the key step** — an *ensemble* of site proposers (liganded-homolog transplant · fpocket cavities · blind DiffDock), with the known modulator's own docking adjudicating which proposed pocket is real |
| M5 | validation | dock the known modulator; a box-contraction diagnostic converts the result into a calibrated `pose_trust` |
| M6 | library | build a candidate set from ChEMBL (similarity + substructure + curated analogs) |
| M7 | screen | dock the library (AutoDock Vina) |
| M8 | prioritize | consensus rank + scaffold diversity → shortlist |

**M4 is the module that carries the science.** It is the packaged, tested implementation of the
unbiased site-finder that the standalone `05b_pocket_detection/` analysis validated by hand on
OPLAH (`verify_ensemble_m4.py` checks it re-selects AMP's pocket). M1–M3 and M5–M8 are the
scaffolding that lets it run end-to-end and agent-callable.

M4 lets the tool work structure-free — and rather than trust any single site-finder, it
lets the known modulator's own docking adjudicate among several proposers, which is why the
status contract centers on it. (The liganded-homolog transplant is one proposer of several — the
original method, now cross-checked instead of trusted blindly.) See
[`docs/IO_CONTRACT.md`](pipeline_src/docs/IO_CONTRACT.md) for the full per-module contract and
[`docs/FAILURE_MODES.md`](pipeline_src/docs/FAILURE_MODES.md) for every degradation path.

## Installation
```bash
# option A — pip (pure-Python path: M1/M2/M4/M8; needs the conda tools below for docking)
pip install -e .

# option B — full environment incl. AutoDock Vina + Open Babel (recommended)
conda env create -f environment.yml
conda activate structure-to-screen
```
Exact versions used for the reference runs are pinned across two files: the Python
packages in [`requirements-pinned.txt`](requirements-pinned.txt) (RDKit 2025.9, Meeko
0.7.1, Biopython 1.87, mcp 1.28.1, …), and the external binaries in
[`environment.yml`](environment.yml) (AutoDock Vina 1.2.7, Open Babel 3.1.0).

## Reproducibility
```bash
pytest -q                              # 4 status-contract tests, offline (~1 s)
python examples/demo.py                # both reference targets, cached, offline
python examples/test_degradation.py    # the no-homolog graceful-degradation path
```
Both reference runs ship as cached module outputs under `examples/`, so every claim in the
docs is reproducible offline; a fresh live run reproduces the OPLAH homolog proposer's transplant
at 1.52 Å RMSD (7HK7/ANP) — one of the several proposers M4's ensemble adjudicates between.

## Results — discovery screen (two arms)
The screen docks candidates **into the AMP-chosen pocket** (stage 3 above). Two arms, two jobs:

| Arm | Purpose | Representative hits (Vina, kcal/mol) |
|-----|---------|--------------------------------------|
| Nucleotide / analog | sanity check — recover AMP-like mimics | dGMP −9.14 · cAMP −9.25 · entecavir (HBV drug) · sofosbuvir (HCV drug) |
| Diverse ZINC (~5,000) | discover *novel* chemistry | **ZINC4126706 −10.81** (novel, Tanimoto to AMP 0.06) |

Diverse arm: 4,998 usable of 4,999 docked (local Vina); AMP control *in this box* −8.78.
**775 beat AMP** → 396 enrichment-arm + **379 genuinely novel** diversity-arm scaffolds, and the
hits are more drug-like than AMP (median QED 0.75 vs 0.39). Full ranked table:
[`../05b_pocket_detection/taskC/dock_5k/shortlist_5k.csv`](../05b_pocket_detection/taskC/dock_5k/shortlist_5k.csv).
Docking ranks hypotheses, not measured affinities — every hit is a lead to test in an assay.

> **Provenance.** These reference-case numbers come from the hand-run analysis in
> `../05b_pocket_detection/` — the method applied to OPLAH — **not** from executing the packaged
> M1–M8 on this target. Module **M4** below is that same site-finding step, generalized and tested.
>
> **This is the discovery result** (new hits). The section below is a *retrospective control* on
> the method — a different question, don't conflate them.

## Retrospective validation
Does docking-alone, no tuning, recover the one experimentally-known modulator (5-AMP) out of
a large library? Tested on **two independent libraries** — full detail in
[`docs/VALIDATION.md`](pipeline_src/docs/VALIDATION.md):

- **Public ChEMBL library (1,431 approved drugs, fully reproducible):** 5-AMP ranks **3/14**
  among nucleoside/purine analogs (−8.36 kcal/mol), beaten only by two close analogs.
- **FDA study library (confidential, numbers only):** 5-AMP global rank **top ~9%**,
  **1/22** among close analogs, false-positive rate **7.4%** vs the −8.43 anchor.

Across both, 5-AMP consistently enriches to the **top of its structural-analog class** — the
exact rank shifts with the competitor set, a more honest claim than "always #1". This is the
ceiling the M5 diagnostic predicts (`pose_trust 0.59`, induced-fit limited): docking-alone
enriches strongly but does not perfectly rank. The FDA library is a confidential experimental
asset and **is not distributed with this repo** (only aggregate numbers are shown); the public
library is open and rebuildable from the shipped recipe.

## Scope & honesty
This is a **hypothesis generator**, not an affinity predictor. Docking scores rank
compounds *within one box*; on the reference target the known modulator's pose is
induced-fit limited (`pose_trust 0.59`), so the shortlist is labelled
`comparative-within-box`. The tool's value is that it says so — and that it refuses
(`unscreenable`) rather than fabricating a screen when it can't trust the pocket.

The **activator/enhancer** framing is the motivating niche (the reference case, OPLAH +
5-AMP, is an enhancer), but the pipeline is modulator-agnostic: it ranks *binding* to a
modulator-adjudicated pocket, which is mechanism-independent. An activator anchor and an inhibitor
anchor run through identical code.

## Modularity — swap one module, keep the rest
Each module (`M1`–`M8`) is an independent function returning a `ModuleResult`; the
orchestrator only chains them and checks status. To adapt the pipeline you replace one module,
not the whole thing:

| want to change | swap this | leave alone |
|----------------|-----------|-------------|
| structure source (e.g. a Boltz-2 co-fold instead of AlphaFold DB) | `modules/m1_intake.py` | M2–M8 |
| binding-site proposers (ensemble already runs homolog + fpocket + DiffDock; add P2Rank, or swap one out) | `modules/m4_site.py` + `_site_ensemble.py` | rest |
| candidate library | supply `m6/candidate_library.csv`, or edit `_library.py` | M7/M8 unchanged |
| docking engine (e.g. smina, GNINA) | `_dock.py` | scoring/prioritization |
| prioritization scheme | `modules/m8_prioritize.py` | screen output |

As long as a replacement returns `ok` / `low_confidence` / `unscreenable` with the same data
keys, the status contract and the agent-facing MCP tools keep working unchanged.

## License
MIT — see [`LICENSE`](../LICENSE). Built open-source for the Built with Claude: Life Sciences
hackathon.
