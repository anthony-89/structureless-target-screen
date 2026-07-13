# OPLAH structure-to-screen — handoff to Claude Code (v2, corrected plan)

> **This v2 replaces the earlier plan.** The earlier version pushed DiffDock + a
> **truncated receptor**. That was wrong: truncating the C-terminus to fit DiffDock's
> residue limit *pre-decides the answer* by deleting any site outside the N-terminal
> region — exactly the bias this experiment is supposed to remove. **DiffDock and
> truncation are OUT of the critical path.** See §3.

**Project:** modular AI drug-discovery pipeline ("structure-to-screen"). Turns a target
with no solved 3D structure + one known small-molecule modulator into a virtual-screen
shortlist. Reference case: **OPLAH** (5-oxoprolinase, UniProt **O14841**, 1288 aa) +
**5-AMP**, which functionally *enhances* OPLAH activity. No crystal structure exists; the
model is an AlphaFold prediction.

---

## 1. Honest status of the six original questions

The user posed six questions. After review, only #1 is actually answered.

| # | Question | Status |
|---|----------|--------|
| 1 | Can we predict the structure? | **DONE.** AlphaFold model, high confidence (apo, no ligand). |
| 2 | Where does AMP bind? | **NOT answered.** We only ever looked at ONE site — copied from a homolog — never discovered it. |
| 3 | Can we screen for AMP-mimics? | **NOT validly answered.** Ran inside the assumed site. |
| 4 | Are there better binders to similar pockets? | **NOT validly answered.** Same assumed-site bias. |
| 5 | **What are the pockets?** | **NOT answered — THIS IS THE START POINT.** Never ran unbiased pocket detection over the whole protein. |
| 6 | Activator vs inhibitor certainty? | **Out of scope for now** (user's call). Docking cannot answer it anyway; needs an assay. |

**Why everything downstream of #1 is suspect:** the binding site was **transplanted from
homolog 7HK7's ligand ANP (a triphosphate)** — never discovered on OPLAH itself. Every
later result (the re-anchored box, the 73-compound re-dock, the "7 compounds beat AMP",
the whole shortlist) was computed *inside that assumed site*. If the assumed site is wrong
or incomplete, those results don't mean what we thought.

**→ The current shortlist in `02_current_results/` is PROVISIONAL and possibly invalid.
Do not treat it as a result until #5 is answered and AMP's true site is confirmed.**

---

## 2. The real question, and the unbiased experiment

> **How many pockets does OPLAH have across the WHOLE protein, what are they, and which
> one does AMP actually go to — without assuming the ATP/ANP site?**

Three steps. Each uses a tool with **no residue-length limit**, so nothing is truncated,
and each step only proceeds if the previous one holds:

**Step 1 — Detect pockets over all 1288 residues (answers #5).**
Run **P2Rank** (preferred) and/or **fpocket** on the full AlphaFold model. Pure geometry /
ML on geometry — no sequence-length cap, no assumption about where the site is. Output:
a ranked list of ALL candidate pockets with their lining residues and centers.

**Step 2 — Let AMP choose its pocket (answers #2, unbiased).**
Dock 5-AMP into EACH detected pocket with **AutoDock Vina** (Vina has no residue limit).
Whichever pocket gives AMP the best, most consistent pose *wins* — AMP picks its own site.
Critical check: is the winning pocket the old ATP/ANP site, or something else (e.g. an
allosteric site we never screened)?

**Step 3 — Re-screen the library only in AMP's real pocket (re-answers #3, #4).**
Only after Step 2 identifies the true site, re-dock the 73-compound library there and
rank by footprint overlap with AMP. If AMP's real pocket ≠ the assumed ATP site, the
current shortlist gets replaced.

**DiffDock's role:** optional confirmation ONLY, never the step that defines the site.
Its ESM-2 residue cap (1022 < OPLAH's 1288) is what forced the truncation bias, so it
must not be on the critical path. Skip it unless Steps 1–3 leave a specific question it
can settle without truncation.

---

## 3. What NOT to do (the loop we got stuck in)

- **Do NOT truncate the receptor.** The whole point is to search the full protein.
  `03_diffdock_attempt/` and `05_diffdock_local/` are dead ends — ignore them.
- **Do NOT anchor the box on the homolog's ANP ligand.** That is the original bias.
- **Do NOT start from `binding_site_*.json`.** Those encode the assumed ATP site. They are
  kept only for later comparison ("did AMP's real pocket match the old assumption?").
- **Do NOT trust the current shortlist** until Step 2 confirms AMP's site.

---

## 4. Tasks for Claude Code (in order)

**Task A — P2Rank + fpocket on the full model.**
Input: `01_inputs/oplah_af.pdb` (full 1288 aa, raw AlphaFold — do NOT truncate).
- P2Rank: `prank predict -f oplah_af.pdb` (Java; install if needed). This is the primary
  tool.
- fpocket: `fpocket -f <clean pdb>`. NOTE: fpocket **segfaulted (exit 139)** on the
  Claude-Science sandbox — likely low RAM there, may work on your Mac; if it still crashes,
  rely on P2Rank. Consider cleaning the PDB first (`pdb_tools` / `obabel`) if fpocket
  chokes on formatting.
- Deliverable: table of all pockets (rank, score, center xyz, lining residues).

**Task B — Dock AMP into every detected pocket (Vina).**
5-AMP SMILES: `Nc1ncnc2c1ncn2C1OC(COP(=O)(O)O)C(O)C1O` (also `01_inputs/5amp.sdf`).
Receptor: `01_inputs/oplah_receptor.pdbqt`. Build a Vina box on each pocket center from
Task A, dock AMP, record best affinity + pose per pocket.
- Deliverable: which pocket AMP prefers; whether it is the old ATP site (compare to
  `binding_site_ORIGINAL_triphosphate.json` center `(-25.6,-7.46,18.85)` and
  `binding_site_AMP_anchored.json` center `(-16.2,-1.65,15.2)`).

**Task C — Re-screen the 73-compound library in AMP's real pocket.**
Only after B. Dock `01_inputs/candidate_library.csv` (col `can_smiles`; L001 = 5-AMP) in
the winning pocket; rank by contact-footprint overlap with AMP's pose. This produces the
*real* shortlist, replacing the provisional one if the site changed.

**Task D — (optional) fold decision into pipeline M4.**
If the unbiased approach works, replace M4's homolog-transplant site-finder with
"detect pockets (P2Rank) → dock modulator → pick site". Pipeline source is in
`04_pipeline_code_and_docs/pipeline_src/`; keep the `ModuleResult` contract (see
`IO_CONTRACT.md`). There is already an `M4_ENSEMBLE.patch` in pipeline_src — review it
against this plan before applying.

---

## 5. File map

```
01_inputs/                             USE THESE (full-length, untruncated)
  oplah_af.pdb                         AlphaFold model, full 1288 aa  <- Task A input
  oplah_receptor.pdb / .pdbqt          prepared receptor (Vina)       <- Task B input
  oplah_sequence.fasta
  5amp.sdf                             5-AMP ligand
  candidate_library.csv                73 compounds (col can_smiles; L001 = 5-AMP)
  AMP_docked_pose_L001_out.pdbqt       AMP's Vina pose in the ASSUMED site (reference only)
  binding_site_ORIGINAL_triphosphate.json   assumed ATP site (COMPARISON ONLY - biased)
  binding_site_AMP_anchored.json            re-anchored assumed site (COMPARISON ONLY - biased)
02_current_results/                    PROVISIONAL - possibly invalid until #5 answered
  shortlist_amp_anchored.csv           the provisional shortlist
  docking_scores_amp_anchored.csv
  amp_anchored_diagnostic.png, amp_motif_contacts.png
03_diffdock_attempt/  05_diffdock_local/   DEAD ENDS - ignore (truncation bias)
04_pipeline_code_and_docs/
  pipeline_src/                        pipeline source (M1-M8) + M4_ENSEMBLE.patch
  README.md, IO_CONTRACT.md, COMPUTE.md, FAILURE_MODES.md
  environment.yml, requirements-pinned.txt
```

## 6. Environment
`environment.yml` builds conda env `dock`: RDKit 2025.09.5, Meeko 0.7.1, AutoDock Vina
1.2.7, fpocket, openbabel. Add **P2Rank** (Java) for Task A — not in the env yet.

## 7. Reference numbers (mark all PROVISIONAL except the structure)
- OPLAH: UniProt O14841, 1288 aa. AlphaFold model = the one solid result.
- Assumed-site footprint (biased, for comparison): F18 (adenine) + D13/G15/G16/T17/D20/K34
  (phosphate). Assumed-site box centers: ATP `(-25.6,-7.46,18.85)`, re-anchored `(-16.2,-1.65,15.2)`.
- Provisional shortlist top-7 (assumed site): L067, L052, L004(GMP), L056, L003(cAMP), L068, L035.
  **These may not survive an unbiased site.**
