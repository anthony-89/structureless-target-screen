# OPLAH structure-to-screen — finding a modulator's binding site *without pre-deciding the answer*

**Built with Claude · Life Sciences Hackathon 2026 · Researcher Track**

**Team:** Antonio Esquivel Gaytan

> **How Claude was used.** **Claude Science** grounded the biology — it surfaced the
> OPLAH–heart-failure literature and the 5′-AMP FDA-screen provenance (cited below).
> **Claude Code** drove the computation end-to-end: unbiased pocket detection, catching and
> removing the homolog-transplant bias, blind docking, and a two-arm virtual screen run locally.

> **Why it matters.** Heart failure represses OPLAH (5-oxoprolinase, UniProt
> [O14841](https://www.uniprot.org/uniprotkb/O14841), 1288 aa); the toxic metabolite
> **5-oxoproline** then accumulates and drives the oxidative stress that damages the heart — a
> murine HFpEF model ([van der Pol *et al.*, *Sci Transl Med* 2017](https://pubmed.ncbi.nlm.nih.gov/29118264/);
> [van der Pol *et al.*, *Cardiovasc Res* 2018](https://academic.oup.com/cardiovascres/article-abstract/114/14/1871/5056075)).
> So **activating** OPLAH is a therapeutic goal — and **5′-AMP**, found in a screen of 1,280
> FDA-approved compounds ([*Eur Heart J* 2023](https://academic.oup.com/eurheartj/article/44/Supplement_2/ehad655.3130/7391542)),
> is the activator identified so far.
>
> **The question.** But OPLAH has **no solved 3D structure** and **no known binding site**, so a
> better activator can't be designed. Where does AMP bind — and can we find molecules that mimic
> it or bind better?

> **The finding.** Searching the whole protein *without assuming a site*, three independent
> methods converge on a single pocket — a glycine-rich phosphate cleft with a repeated
> **DxGGT** motif. AMP, docked blind, chooses that exact pocket on its own. Screening it
> recovers known nucleotide mimics and approved antiviral drugs, and — from a diverse ZINC
> screen — novel drug-like scaffolds that out-score AMP *in silico*.

---

## Why this is more than "dock a ligand"

The obvious way to find AMP's site is to **copy it from a homologous protein** that has a
bound nucleotide. We started down that path — and realized it **pre-decides the answer**.
Transplanting a site can only ever *confirm* the assumption; it can never discover that AMP
actually binds somewhere else. (A second, subtler bias: the popular blind-docking tool
DiffDock caps input at 1022 residues, forcing you to **truncate** OPLAH's 1288 — which
physically deletes residues that turn out to *form* the real pocket.)

**So we removed the assumption.** We detect pockets over the entire structure by pure
geometry/ML, then let AMP pick its own site by docking. The result happens to overlap the
old guess — but now it's an *output of unbiased search*, not an *input*. That distinction is
the scientific core of the project.

---

## The pipeline, in one pass

```
AlphaFold model
  → A · detect pockets       P2Rank + fpocket over the FULL structure (unbiased, no truncation)
  → B · place the modulator  dock AMP blind + into every pocket → AMP picks its own site
  → C · screen that site     nucleotide arm (152, local Vina)
                             + diverse arm (5,000 = 10%, AMP-guided similarity+diversity funnel)
  → shortlist                AMP-mimics (#3)  +  novel better binders (#4)
```

Hand it **any** structureless target + one known modulator and it runs the same way — that's
what the packaged pipeline in `04_pipeline_code_and_docs/` is for. The unbiased site-finder
above becomes its module **M4**.

---

## How the two fit together

This repo has **two entry points that share one idea** — not two separate projects:

```
            one idea: don't trust a single site-finder —
       let the known modulator pick its own pocket by docking
                   /                             \
  THE FINDING                            THE TOOL
  05b_pocket_detection/                  04_…/structure_to_screen/
  done by hand on OPLAH                  the same idea, packaged as M1–M8
  → reproduces the science below         → run it on your own target
```

- **`05b_pocket_detection/` — the finding.** The OPLAH study behind every number in this
  README: unbiased detection → AMP picks its site → two-arm screen. Reproduce it with the
  [commands below](#reproduce-it).
- **`04_pipeline_code_and_docs/` — the tool.** The same method packaged as an agent-callable
  pipeline (M1 intake → M2 QC → M3 receptor → **M4 site** → M5 validate → M6 library →
  M7 screen → M8 prioritize), each step returning `ok` / `low_confidence` / `unscreenable`.
  Point it at a UniProt id + a modulator SMILES and it runs end-to-end, and it exposes an
  **MCP server** so an agent (Claude) can drive it. See
  [`04_pipeline_code_and_docs/README.md`](04_pipeline_code_and_docs/README.md).

**The join is M4.** What `05b` did by hand — geometric/ML pocket detection, then the modulator
choosing its site by docking — is exactly what **M4** automates, as a modulator-adjudicated
ensemble of proposers (homolog transplant · fpocket · blind dock). OPLAH is the first target
it was validated on.

---

## The five questions, answered

| # | Question | Answer | Evidence |
|---|----------|--------|----------|
| 1 | Can we predict the structure? | **Yes** | AlphaFold model (full 1288 aa) |
| 5 | What are the pockets? | **21 detected; one dominant** | P2Rank prob **0.98**; detection score **5× the next** (50.7 vs 9.8); fpocket agrees within **1.8 Å** |
| 2 | Where does AMP bind? | **One phosphate cleft, 17 contact residues** | 3 independent methods converge; blind dock lands **2.2 Å** from it |
| 3 | Can we find AMP mimics? | **Yes** | dGMP, cAMP, GMP; approved drugs **entecavir, sofosbuvir** |
| 4 | Are there better binders? | **Yes — 775 of 5,000 (in silico)** | AMP-guided 10% screen; **379 novel** diversity-arm scaffolds beat AMP; top −10.81, median QED 0.75 vs AMP's 0.39 |

*(Question 6 — activator vs inhibitor — is out of scope: docking can't answer it; it needs an assay.)*

### Q2 in detail — AMP's binding site (on OPLAH's own terms)
- **Center** ≈ (−15.6, −4.5, 17.1); best Vina affinity **−8.78 kcal/mol** (−8.79 in the blind whole-protein dock; −8.70 with Task C's smaller box — all within docking noise)
- **Contact residues:** `D13 G15 G16 T17 F18 D20 K34 | D314 G316 G317 T318 S319 | G489 G490 G515 S518 A519`
- **Motif:** the site carries the phosphate-binding loop **D-x-G-G-T** *twice* (res 13–18 and
  314–319) — consistent with OPLAH's two ATP-grasp domains. F18 stacks the adenine; the
  Gly-rich loops + K34 cradle the phosphate.
- **Convergence:** P2Rank geometry, fpocket druggability, a **blind whole-protein dock**, and
  a per-pocket dock all point to the same cavity.

### Q3/Q4 — two-arm virtual screen into AMP's real pocket
- **Nucleotide arm (152 cpds, run locally):** AMP docks mid-pack (self-consistency check).
  Top mimics: **dGMP** (−9.14, 85% footprint overlap), **cAMP** (−9.25, 80%), **SAM** (89%),
  **entecavir** (approved HBV drug), **sofosbuvir** (approved HCV drug). Guanine nucleotides
  edge out adenine.
- **Diverse arm (ZINC20, local Vina):** **5,000 diverse compounds — 10% of the library** —
  selected by an AMP-guided **similarity + diversity funnel** (2,500 by ECFP4 Tanimoto to AMP +
  2,500 MaxMin-diverse), then docked locally into AMP's pocket. **775 out-score the AMP control
  (−8.78)**, and **379 of those are novel, low-similarity scaffolds** from the diversity arm.
  Top hit **ZINC4126706, −10.81 kcal/mol** (Tanimoto to AMP just **0.06** — genuinely new
  chemistry), and the hits are far more drug-like than AMP (**median QED 0.75** vs 0.39; 89% ≥ 0.6).
  The same AMP-guided funnel scales to the full library by widening the selection fraction.

> **Read the scores as hypotheses, not measurements.** Vina affinities rank candidates
> to test — they are not measured binding constants (~1–2 kcal/mol noise; charged polyphosphates
> score artificially well). Every hit is a prioritized lead for assay, not a validated binder.

---

## Reproduce it

Everything runs from public data + open tools. No wet lab, no private assets.

```bash
# 1. environment (conda/mamba)
mamba env create -f 04_pipeline_code_and_docs/environment.yml   # or env below
mamba install -n dock -c conda-forge openjdk=17                 # for P2Rank

# 2. Task A — unbiased pocket detection (full, untruncated model)
prank predict -f 01_inputs/oplah_af.pdb -o 05b_pocket_detection/p2rank_out
fpocket -f 01_inputs/oplah_af.pdb
python 05b_pocket_detection/analyze_pockets.py        # -> pockets_p2rank.csv, comparison

# 3. Task B — let AMP pick its site (blind + per-pocket dock)
python 05b_pocket_detection/taskB/dock_pockets.py     # dock AMP into every pocket
python 05b_pocket_detection/taskB/contacts.py         # AMP's contact residues

# 4. Task C — screen libraries into AMP's pocket
python 05b_pocket_detection/taskC/build_nucleotide_lib.py   # nucleotide arm
python 05b_pocket_detection/taskC/prep_dock.py ...          # dock + rank
# diverse ZINC arm — AMP-guided similarity+diversity funnel, docked locally with Vina:
python 05b_pocket_detection/taskC/build_5k_selection.py     # pick 5,000 = 10% (ECFP4 + MaxMin)
python 05b_pocket_detection/taskC/dock_5k.py                # local Vina dock (resumable)
python 05b_pocket_detection/taskC/analyze_5k.py             # rank + shortlist
```

**Key inputs** (`01_inputs/`): `oplah_af.pdb` (AlphaFold model), `oplah_receptor.pdbqt`
(prepared receptor), `5amp.sdf`, `candidate_library.csv`.
**Key outputs** (`05b_pocket_detection/`): `RESULTS_taskA/B/C_*.md`, `pockets_*.csv`,
`taskC/nucleotide_run/shortlist.csv`, `taskC/diverse_1k_top120_annotated.csv`.

---

## Tools & data (all public)
AlphaFold · **P2Rank 2.5** · **fpocket** · **AutoDock Vina 1.2.7** ·
**Meeko 0.7.1** · **RDKit** · **ChEMBL** · **PubChem** · **ZINC20** (in-stock tranches).
Built and driven with **Claude Code**.

## Repository map
```
01_inputs/                     public inputs (AlphaFold model, receptor, ligands, libraries)
05b_pocket_detection/          ← the unbiased analysis (Tasks A–C) + results + scripts
04_pipeline_code_and_docs/     the modular structure-to-screen pipeline (M1–M8) + docs
03_diffdock_attempt/  05_diffdock_local/   ARCHIVED — the truncation dead-ends we rejected (kept for honesty)
demo/                          showcase — interactive viewer, one-pager, result figures, written summary
```

## License
MIT — see [LICENSE](LICENSE). All code, data pointers, and results are open source.
