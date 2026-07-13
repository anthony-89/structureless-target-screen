# Running large screens without a big machine

**The key fact: only M7 (the library screen) is compute-heavy.** M1–M6 and M8 — sequence
fetch, AlphaFold download, receptor prep, homolog-transplant pocket finding, ligand prep,
prioritization — all run on a laptop in minutes. CPU docking of a large library is the *only*
step that needs real muscle, and it is embarrassingly parallel and **resumable** (each
ligand's score is written atomically; re-running skips completed ligands).

So the pattern is never "get a bigger machine for the pipeline" — it's **run everything
locally, offload only the screen.** Cheapest options first.

## Tier 0 — shrink the problem (laptop, today)
- **Screen a diverse subset.** M6 already Butina-clusters the library; screen ~150–250
  cluster representatives instead of the full set — same chemotype coverage, a fraction of
  the time. Often the right first-pass choice, not a compromise.
- **Two-pass triage.** Dock everything fast (`--exhaustiveness 6–8`), then re-dock only the
  top ~5% at full settings.
- **Run the resumable docker unattended.** Atomic writes mean you can run it in the
  background across days; it picks up wherever it stopped. Slow, zero babysitting.

## Tier 1 — free cloud GPU (practical sweet spot)
- **Google Colab (free T4)** or **Kaggle (30 GPU-h/week free)**. Run M1–M6 locally, upload the
  prepared `receptor.pdbqt` + ligand PDBQTs, dock M7 on the GPU (minutes for ~1,500 ligands),
  pull the scores back, run M8 locally. No cost.
- **Ready-to-run notebook: [`examples/colab_screen.ipynb`](../examples/colab_screen.ipynb)** —
  a self-contained upload → GPU-dock (Uni-Dock) → download loop. Reads the same box M4 defines
  and writes the same `.sc` score format the CPU path uses, so the results drop straight into
  `m7/scores/` and the pipeline finishes locally.

## Tier 2 — GPU docking engines (the real fix)
Drop-in replacements for Vina using the **identical box and parameters**, 100×+ faster on one
consumer GPU:
- **Uni-Dock** — highest throughput, Vina-compatible scoring.
- **AutoDock-GPU** — mature, widely used.
- **gnina** — GPU + CNN rescoring (better ranking, somewhat slower).

Point M7 at one of these instead of the CPU `vina` binary; nothing else in the pipeline
changes. Turns ~11 CPU-hours into minutes.

## Tier 3 — institutional / paid
- **SLURM cluster** (most academics have one): the resumable docker maps cleanly to an array
  job — one ligand per task, atomic writes collate the results.
- **Cloud spot GPU** (~$0.20–0.50/hr): finishes any realistic library for pocket change.

## The split in practice
```bash
# on your laptop — minutes:
structure-to-screen --target <UNIPROT> --modulator "<SMILES>" --workdir runs/mytarget
#   ... runs M1–M6, stops with the prepared receptor + ligand library in runs/mytarget/

# copy runs/mytarget/m3/receptor.pdbqt + runs/mytarget/m6/ligands_pdbqt/ to GPU/cluster,
# run the screen there (Uni-Dock / AutoDock-GPU / resumable dock script), then copy
# runs/mytarget/m7/scores/ back and finish locally:
structure-to-screen --target <UNIPROT> --modulator "<SMILES>" --workdir runs/mytarget
#   ... M7 sees the scores are present, M8 prioritizes → shortlist
```
Because every module is cache-first, re-running after dropping in the M7 scores just completes
the pipeline — no re-computation of the light steps.
