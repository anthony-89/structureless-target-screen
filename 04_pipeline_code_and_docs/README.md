# structure-to-screen

Agent-callable pipeline that turns a **protein target with no experimental 3D structure**
plus **one known small-molecule modulator** into a prioritized virtual-screen shortlist —
orchestrating UniProt, AlphaFold DB, RCSB PDB, ChEMBL and AutoDock Vina.

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
[`docs/IO_CONTRACT.md`](docs/IO_CONTRACT.md)) — treat a first cold-start screen as a run to
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
[`docs/IO_CONTRACT.md`](docs/IO_CONTRACT.md) for the per-module live/cached contract.

**No big machine? Only M7 is compute-heavy** — M1–M6/M8 run on a laptop in minutes, so you
run everything locally and offload just the screen. There's a ready-to-run
[`examples/colab_screen.ipynb`](examples/colab_screen.ipynb) that docks the library on a free
Colab GPU (Uni-Dock) and hands the scores back for the pipeline to finish locally. See
[`docs/COMPUTE.md`](docs/COMPUTE.md) for that and the other cheapest-first options.

## Demo — two targets, two honest outcomes
```bash
PYTHONPATH=. python examples/demo.py
```
Runs OPLAH/5-AMP (→ a `low_confidence` shortlist) and c-Myc/10058-F4 (→ a graceful
`unscreenable` refusal) back-to-back. See [`docs/FAILURE_MODES.md`](docs/FAILURE_MODES.md)
for the full catalogue of how each module degrades, and
[`examples/STRESS_TEST_myc.md`](examples/STRESS_TEST_myc.md) for the stress-test writeup.

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
Full tool reference: [`docs/MCP_TOOLS.md`](docs/MCP_TOOLS.md).

## The method — how it works without a crystal structure
The core problem: you have a target with **no experimental 3D structure** and **one known
modulator**, and you want a ranked list of related compounds to test. The pipeline chains
eight modules:

| # | Module | What it does |
|---|--------|--------------|
| M1 | intake | UniProt sequence + AlphaFold DB model (or hand off to a predictor) |
| M2 | QC | pLDDT confidence gate — flags disordered / low-confidence models |
| M3 | receptor | trim, protonate, PDBQT prep |
| M4 | **site** | **the key step** — find a crystallographic homolog *with a bound ligand*, superpose it onto the model, and transplant the ligand's position as the binding site |
| M5 | validation | dock the known modulator; a box-contraction diagnostic converts the result into a calibrated `pose_trust` |
| M6 | library | build a candidate set from ChEMBL (similarity + substructure + curated analogs) |
| M7 | screen | dock the library (AutoDock Vina) |
| M8 | prioritize | consensus rank + scaffold diversity → shortlist |

M4 is what lets the tool work structure-free — but it's also the assumption most likely to
break, which is why the status contract centers on it. See
[`docs/IO_CONTRACT.md`](docs/IO_CONTRACT.md) for the full per-module contract and
[`docs/FAILURE_MODES.md`](docs/FAILURE_MODES.md) for every degradation path.

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
docs is reproducible offline; a fresh live run reproduces the OPLAH homolog transplant at
1.52 Å RMSD (7HK7/ANP).

## Retrospective validation
Does docking-alone, no tuning, recover the one experimentally-known modulator (5-AMP) out of
a large library? Tested on **two independent libraries** — full detail in
[`docs/VALIDATION.md`](docs/VALIDATION.md):

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
homolog-anchored pocket, which is mechanism-independent. An activator anchor and an inhibitor
anchor run through identical code.

## Modularity — swap one module, keep the rest
Each module (`M1`–`M8`) is an independent function returning a `ModuleResult`; the
orchestrator only chains them and checks status. To adapt the pipeline you replace one module,
not the whole thing:

| want to change | swap this | leave alone |
|----------------|-----------|-------------|
| structure source (e.g. a Boltz-2 co-fold instead of AlphaFold DB) | `modules/m1_intake.py` | M2–M8 |
| binding-site method (e.g. add P2Rank / blind docking) | `modules/m4_site.py` + `_homolog.py` | rest |
| candidate library | supply `m6/candidate_library.csv`, or edit `_library.py` | M7/M8 unchanged |
| docking engine (e.g. smina, GNINA) | `_dock.py` | scoring/prioritization |
| prioritization scheme | `modules/m8_prioritize.py` | screen output |

As long as a replacement returns `ok` / `low_confidence` / `unscreenable` with the same data
keys, the status contract and the agent-facing MCP tools keep working unchanged.

## License
MIT — see [`LICENSE`](LICENSE). Built open-source for the Built with Claude: Life Sciences
hackathon.
