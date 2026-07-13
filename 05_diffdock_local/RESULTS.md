# OPLAH structure-to-screen — local DiffDock + fpocket results

The local DiffDock + manual-Vina work (the truncation dead-end we rejected). All work is under `05_diffdock_local/`.
Environment: Apple Silicon (arm64), macOS 26.4, 16 GB RAM, CPU only.

## TL;DR

- **Task A (DiffDock on CPU): DONE.** The Colab blocker is gone. DiffDock ran to
  completion in **57 min** and wrote **40 ranked poses** with **no ESM truncation
  error** — the 1015-residue truncation (res 6–1020) worked exactly as intended.
- **Task C (fpocket): DONE, clean win.** The pocket covering all 7 AMP site residues
  is the **most druggable pocket in the whole protein** (0.62 on the receptor, 0.79 on
  the AlphaFold model), centroid **2.6–2.8 Å** from the AMP-anchored box. Replicated on
  both structures. fpocket also independently recovered the 12 "extra" contact residues,
  showing the site is a **bipartite interdomain groove with two Gly-rich loops**.
- **Task B (DiffDock vs footprint): qualified confirmation.** **37/40** poses drift to
  the AMP-anchored box rather than the original mis-anchored one, and the **top-confidence
  pose engages both motifs** (F18 + the P-loop region). But no single blind pose crisply
  reproduces the full 7-residue footprint (top pose 2/7, best pose 4/7), and DiffDock's
  own confidence is low for all poses. DiffDock **corroborates the site's location**; it
  does not, alone, reproduce it at high confidence.
- **Task D:** not started — it is a build task and was explicitly conditional. A concrete
  design and recommendation are at the bottom; awaiting your go-ahead.

## Environment (differs from the Colab recipe — reusable via `run_diffdock.sh`)

The Colab install recipe does **not** port to Apple Silicon, for reasons that are
features here, not bugs:

| Step | Colab | Here (arm64 CPU) |
|---|---|---|
| PyG companions | prebuilt CUDA wheels from `data.pyg.org` | **source-compiled** `torch_scatter`/`torch_cluster` (no arm64 wheels exist; compiling is correct) |
| `torch_sparse`, `torch_spline_conv` | installed | **skipped** — never imported by the inference path |
| openfold / `fair-esm[esmfold]` | installed | **skipped** — only needed to fold from sequence; we supply a structure |
| torch | 1.13 + cu117 | 2.5.1 CPU |
| model/ESM weight download | just works | needed a **certifi SSL bundle** (`SSL_CERT_FILE`); Python here had no CA bundle wired up |

Python 3.11 venv at `05_diffdock_local/.venv`. One reusable launcher: `run_diffdock.sh`.

## Task A — DiffDock blind dock (CPU)

- Input: truncated receptor `oplah.pdb` (res 6–1020, 1015 residues), AMP SMILES
  `Nc1ncnc2c1ncn2C1OC(COP(=O)(O)O)C(O)C1O`, 40 samples.
- **Verified the truncated receptor is in the identical coordinate frame as
  `oplah_receptor.pdb` (max deviation 0.0000 Å)** — so poses are directly comparable to
  both boxes and the Vina reference. All 7 site residues are present in the truncated file.
- Result: `DiffDock/out/oplah_amp_blind/rank1..40_confidence*.sdf`, exit 0, zero skips,
  **no "Expected size 1254 but got size 1022"**. The handoff's suspicion was right — the
  empty Colab zip was a stale-upload artifact, not a bad truncation.

## Task B — DiffDock poses vs the AMP footprint

Contact = residue within 4.5 Å (min heavy-atom distance) of a ligand heavy atom.
Reference 7-set: F18 (adenine) + D13/G15/G16/T17/D20/K34 (phosphate P-loop).

| metric | value |
|---|---|
| poses drawn to AMP-anchored box over original box | **37 / 40** |
| poses contacting the adenine motif **and** the phosphate motif | 3 / 40 (rank 1, 7, 25) |
| **top-confidence pose (rank1, conf −0.98)** | contacts **F18 + T17**, both motifs, 2/7 exact |
| best-covering pose (rank7, conf −1.98) | both motifs, **4/7** (F18 + 3 phosphate) |
| all pose confidences | negative (DiffDock's low-confidence regime; >0 = confident) |

**Reading:** the blind dock, with no box, preferentially samples the corrected AMP
location and its top pose lands on the bipartite site (adenine end first). But a
phosphosugar in a 1015-residue multidomain protein on CPU is hard for DiffDock: 36/40
poses scatter elsewhere and confidence never goes positive. This is corroboration of
*where* the site is, not a high-confidence reproduction of the full footprint.

## Task C — fpocket (the strong, unambiguous result)

**The reported fpocket "silent failure" was a broken binary, not PDB formatting.** A
freshly built arm64 fpocket 4.0 runs fine on `oplah_receptor.pdb` **and** the raw
`oplah_af.pdb`, producing 83 and 89 pockets respectively.

The pocket covering the AMP site:

| structure | pocket rank by fpocket score | **rank by druggability** | druggability | 7-set coverage | centroid → AMP box |
|---|---|---|---|---|---|
| `oplah_receptor.pdb` | 46 / 83 | **1 / 83** | 0.623 | **7/7** | 2.75 Å |
| `oplah_af.pdb` | 70 / 89 | **1 / 89** | 0.788 | **7/7** | 2.56 Å |

Two things worth carrying into M4:
1. fpocket's **default score buries the real site** (rank 46/70); **druggability score
   surfaces it at #1**. Rank pockets by druggability, not score.
2. This pocket contains **both** Gly-rich motifs — D13-R14-G15-G16-T17-F18…D20 **and**
   D314-G316-G317-T318-S319…D321 — plus every one of the 12 "extra" contacts the Vina
   pose made. The site is one large (~2400 Å³) bipartite interdomain groove, consistent
   with OPLAH's two homologous hydantoinase domains.

## Corrections / notes on the handoff (things that turned out differently)

1. **OPLAH is 1288 aa, not 1254.** 1254 is the residue count of the *prepared* receptor
   (`oplah_receptor.pdb`, spans 6–1259). The FASTA and AlphaFold model are 1288. The
   truncation logic is unaffected (site ≤ 409, cap 1022).
2. **fpocket failure cause was the install, not the PDB.** No reformatting was needed.
3. **The reference pose file is the −7.33 pose, not the −8.68 one.**
   `AMP_docked_pose_L001_out.pdbqt` MODEL 1 = VINA RESULT −7.330 (the original-box pose).
   Its phosphate contacts reproduce the handoff exactly (D13 3.08, D20 2.88, K34 4.30),
   but its **adenine is 8.9–11.8 Å from F18's ring — not a 3.45 Å stack**. I regenerated
   the −8.68 pose (see 3a) rather than relying on this file.
3a. **Regenerated the −8.68 pose (arm64 Vina 1.2.7 + Meeko) — and it overturns the
   "adenine→F18 stack" mechanism.** Re-docking AMP in the AMP-anchored box gives a top pose
   at **−8.815 kcal/mol** (matches −8.68) that reproduces the **exact 7/7 footprint** with
   per-residue distances within ~0.9 Å of the handoff, centroid 2.47 Å from the AMP box.
   But with RDKit perceiving the aromatic ring, **the adenine is 6.7–12.6 Å from F18 at
   42–85° tilt in all 9 modes — never a π-stack** (a stack needs <5 Å, <35°). Instead:
   - **F18's real contact (3.4–3.7 Å) is to the phosphate**, not the adenine.
   - **The adenine ring is recognized by the backbone of *both* Gly-rich loops** —
     G15/G16/T17 (loop 1) and G316/G317/T318/S319 (loop 2). The nearest aromatic ring
     centroid to the adenine is F18 at 8.55 Å; there is no aromatic partner.
   Both independent poses (the −7.33 file and this −8.815 re-dock) put the adenine ≥8.5 Å
   from F18, so the **motif labels in `binding_site_AMP_anchored.json` are inverted**:
   F18 recognizes phosphate; the twin Gly-loops recognize adenine. The contact *footprint*
   (F18 included) is unchanged and screening is unaffected — but M4's mechanistic motif
   definitions should be corrected. Caveat: this is a docking-model result; a solved
   structure is the arbiter. Pose saved at `results/AMP_redocked_-8.815_AMPbox.{sdf,pdbqt}`.
4. **Latent DiffDock bug:** `utils/torus.py` guards on `.p.npy` existing (line 31) but
   loads `.score.npy` (line 33). If the SO(3) precompute is interrupted between the two
   saves, every later run crashes with `FileNotFoundError: .score.npy`. Fix: delete both
   `.p.npy`/`.score.npy` and let them regenerate (~60 s).

## Files

```
05_diffdock_local/
  run_diffdock.sh                 reusable CPU launcher (SSL + threads wired up)
  .venv/                          py3.11 env (torch 2.5.1 CPU, compiled PyG, esm, prody, rdkit)
  bin/fpocket                     arm64 fpocket 4.0
  DiffDock/out/oplah_amp_blind/   40 ranked blind poses (rank1..40_confidence*.sdf)
  fpocket_work/                   fpocket runs on receptor + AlphaFold model
  analysis/footprint.py           shared contact/footprint measurement
  analysis/analyze_diffdock.py    Task B
  analysis/analyze_fpocket.py     Task C
  analysis/validate_reference.py  reproduces the handoff's AMP numbers from coordinates
  results/                        saved text outputs + the two on-site DiffDock poses
```

## Task D — ensemble M4: BUILT and verified

Rewrote M4 as an **open ensemble** adjudicated by the modulator, against the pipeline in
`04_pipeline_code_and_docs/pipeline_src/` (extracted from `s2s_repo_day1.tar.gz`).

**What changed** (`04_pipeline_code_and_docs/pipeline_src/M4_ENSEMBLE.patch`):
- **NEW `structure_to_screen/_site_ensemble.py`** — pluggable proposers + selection:
  - `fpocket_propose` — runs fpocket, keeps top-K pockets **by druggability** (the Task C
    lesson: fpocket's default score buries the real site).
  - `diffdock_propose` — non-blocking by default: reads a completed blind dock
    (`cfg.diffdock_poses_dir`) or the per-run cache `m4/diffdock/<complex>/`, taking the
    top-confidence pose's centroid + 4.5 Å contacts. Opt in with `cfg.diffdock_run=True` +
    `cfg.diffdock_repo` to have M4 launch DiffDock itself (~1 h CPU), cache the poses, and
    reuse them on resume — the same cache-first pattern as every other module.
  - `select_site` — docks the known modulator into a uniform probe box on each candidate and
    ranks by `composite = 0.40·coverage + 0.40·affinity + 0.20·consensus`, where **coverage**
    = fraction of the modulator's contacts inside the proposer's residues (size-robust; plain
    Jaccard unfairly deflates fpocket's large-pocket residue lists — this bit us at first).
- **Rewrote `modules/m4_site.py`** — cache-first path unchanged; cold start assembles proposers
  per `cfg.site_proposers`, calls `select_site`, classifies ok / low_confidence / unscreenable,
  writes `binding_site.json` with `runner_up_sites` (viable/rejected flags), `proposers_run`,
  `proposers_failed`. The homolog RCSB seams stay module-level so existing monkeypatch tests hold.
  Same `ModuleResult` contract; `box_center`/`box_size`/`site_residues` unchanged for M5/M7.
- **`config.py`** — `site_proposers`, `fpocket_bin`, `fpocket_top_k`, `diffdock_poses_dir`,
  `consensus_radius_A`, `site_select_coverage_ok`, `site_select_affinity_ok`.
- **Tests** — updated the no-homolog test to the ensemble contract; added 3 hermetic tests
  (fpocket-rescue → low_confidence; two-method consensus → ok; modulator rejects all →
  unscreenable). `pytest -k "not unknown_target"` → **6 passed** (the excluded one is a
  pre-existing *live-UniProt* M1 test, unrelated to M4).

**Honest contract change:** "no liganded homolog" is no longer automatically unscreenable —
fpocket/DiffDock are now legitimate, *declared* proposers (every one that ran, and every
runner-up, is recorded — an open ensemble, not a silent fallback). The new honest-failure
state is "the modulator engages no proposed box."

**Live OPLAH result (cold M4, real Vina/fpocket/DiffDock):**
- Winner = **fpocket** (no reliable homolog this run): modulator docks at **−8.63 kcal/mol**,
  coverage **0.88**, box centre **2.76 Å** from the hand-found AMP box, fpocket druggability
  rank #1. → **low_confidence** (single strong method).
- DiffDock's blind pose is reported as a runner-up but sits ~9 Å off (its top pose only
  partially engages, per Task B) → flagged **rejected**. This matches the M5
  `induced_fit_limited` verdict: the site is right, high-confidence pose needs receptor flex.

## Files

```
05_diffdock_local/
  run_diffdock.sh                 reusable CPU launcher (SSL + threads wired up)
  .venv/                          py3.11 env (torch 2.5.1 CPU, compiled PyG, esm, prody, rdkit, vina, meeko)
  bin/fpocket, bin/vina           arm64 fpocket 4.0, AutoDock Vina 1.2.7
  DiffDock/out/oplah_amp_blind/   40 ranked blind poses (rank1..40_confidence*.sdf)
  fpocket_work/                   fpocket runs on receptor + AlphaFold model
  vina_work/                      AMP re-dock (−8.815 pose) inputs/outputs
  analysis/footprint.py           shared contact/footprint measurement
  analysis/analyze_diffdock.py    Task B
  analysis/analyze_fpocket.py     Task C
  analysis/verify_ensemble_m4.py  Task D end-to-end verification on OPLAH
  results/                        saved outputs + on-site DiffDock poses + regenerated −8.815 AMP pose
04_pipeline_code_and_docs/pipeline_src/
  structure_to_screen/_site_ensemble.py   NEW ensemble backend
  structure_to_screen/modules/m4_site.py  rewritten (ensemble)
  M4_ENSEMBLE.patch                        unified diff of all pipeline changes
```
