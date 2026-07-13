# Task A — Unbiased pocket detection on full OPLAH (results)

**Input:** `01_inputs/oplah_af.pdb` — full 1288-aa AlphaFold model, **untruncated**.
**Tools:** P2Rank 2.5 (primary) + fpocket (cross-validation). Both run on the whole protein,
no residue-length cap, no homolog transplant, no ANP anchoring.
**Date:** 2026-07-10.

## Headline
Two independent detectors agree on **one dominant pocket**, and it is the same region the
old pipeline had *assumed* — but now it is found by unbiased geometry, not copied from a
homolog.

| Detector | Top site | Center (x,y,z) | Strength |
|---|---|---|---|
| P2Rank | pocket 1 | (-15.58, -4.55, 17.09) | score **50.66**, prob **0.98** — **5.2× the #2 pocket** (9.77) |
| fpocket | pocket 70 | (-14.90, -2.84, 17.06) | druggability **0.788** — highest of all pockets |

The two top pockets are **1.8 Å apart** — effectively the same cavity.

## Comparison to the ASSUMED (biased) sites
P2Rank pocket 1:
- **3.5 Å** from the re-anchored AMP site `(-16.2, -1.65, 15.2)`
- **10.6 Å** from the original ATP-triphosphate site `(-25.6, -7.46, 18.85)`
- contains **7/7** assumed-footprint residues: **D13, G15, G16, T17, F18, D20, K34**

So the earlier assumption landed in roughly the right cleft, and the *AMP-anchored* center
was the better of the two guesses. The original ATP-triphosphate center was ~10 Å off.

## Why this vindicates dropping the truncation
Pocket 1's lining residues span **13 → 1288** — it draws walls from the extreme C-terminus
(1280, 1281, 1284, 1287, 1288). DiffDock's ESM-2 cap (1022) would have **deleted part of the
pocket wall**. Truncation wasn't just risky in principle; it physically removes residues that
form this cavity.

## All P2Rank pockets (top 8 of 21)
| rank | score | prob | center | nRes | d_AMP | footprint overlap |
|---|---|---|---|---|---|---|
| 1 | 50.66 | 0.98 | (-15.58,-4.55,17.09) | 46 | 3.5 | D13 G15 G16 T17 F18 D20 K34 |
| 2 | 9.77 | 0.53 | (3.81,-18.09,-5.34) | 22 | 33.0 | — |
| 3 | 8.86 | 0.47 | (-13.19,19.94,14.92) | 23 | 21.8 | — |
| 4 | 7.35 | 0.38 | (-1.75,23.04,-10.05) | 17 | 38.2 | — |
| 5 | 7.35 | 0.38 | (5.01,-6.72,28.06) | 20 | 25.3 | — |
| 6 | 5.75 | 0.28 | (9.04,-23.62,-6.01) | 12 | 39.6 | — |
| 7 | 5.37 | 0.25 | (-4.09,18.62,-1.91) | 13 | 29.2 | — |
| 8 | 4.86 | 0.22 | (4.77,-10.91,12.55) | 15 | 23.1 | — |

Full tables: `pockets_p2rank.csv` (all 21, with lining residues) and `pockets_fpocket.csv`.
Raw P2Rank output: `p2rank_out/` (incl. `visualizations/` PyMOL session).
Raw fpocket output: `fpocket_run/oplah_af_out/`.

## What this does and does NOT establish
- **Establishes (#5):** OPLAH has one clearly dominant, druggable cavity; ~20 minor ones.
  There is **no second strong pocket** competing with it (next best is 5× weaker).
- **Does NOT yet establish (#2):** that *AMP* binds there. Geometry says it's the obvious
  candidate, but AMP has not been docked unbiasedly yet. That is **Task B** — dock 5-AMP into
  each of these pocket centers with Vina and see which it prefers. Only after B confirms the
  site do we re-screen the library (Task C).

## Next: Task B
Dock centers to try (from this table): pocket 1 first, plus pockets 2–5 as negative controls,
plus the two assumed centers for calibration. Receptor `01_inputs/oplah_receptor.pdbqt`,
ligand `01_inputs/5amp.sdf` (SMILES `Nc1ncnc2c1ncn2C1OC(COP(=O)(O)O)C(O)C1O`).
