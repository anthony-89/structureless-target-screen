# Task C — nucleotide-focused arm (results)

Answers **#3 (AMP mimics)** and **#4 (better binders)** from the chemistry we know fits.
Diverse 50k arm runs separately on GPU (Colab notebook).

**Library:** 152 molecules — natural nucleotides/nucleosides + clinical nucleoside/nucleotide
drugs + base analogs (PubChem canonical structures) + adenine-scaffold ChEMBL set.
`taskC/library/nucleotide_focused.csv`.
**Dock:** AutoDock Vina 1.2.7, AMP's pocket (center -15.58,-4.55,17.09, box 20 Å),
exhaustiveness 8, seed 42. Ranked by affinity + contact-footprint overlap (Jaccard) with
AMP's 17-residue footprint. `taskC/nucleotide_run/shortlist.csv`.
**Control:** AMP itself docks at -8.70 kcal/mol, footprint Jaccard 0.70 — mid-pack among
nucleotides, exactly where a self-consistent screen should place it.

## Top findings

**Strong AMP mimics (good affinity AND high footprint overlap — answers #3):**
| Compound | Affinity | vs AMP | Jaccard | Note |
|---|---|---|---|---|
| 2'-deoxyguanosine 5'-MP (dGMP) | -9.14 | -0.36 | 0.85 | best mimic; touches all 17 AMP residues |
| cAMP | -9.25 | -0.47 | 0.80 | |
| S-adenosylmethionine (SAM) | -8.65 | +0.13 | 0.89 | highest overlap (adenosine core) |
| entecavir | -8.78 | 0.00 | 0.79 | **approved HBV antiviral** |
| xanthosine 5'-MP | -9.68 | -0.90 | 0.73 | |
| GMP / guanosine nucleotides | ~-9.3 | ~-0.5 | ~0.70 | guanine series consistently strong |
| sofosbuvir | -9.70 | -0.92 | 0.60 | **approved HCV antiviral** |
| molnupiravir | -8.68 | +0.10 | 0.73 | **antiviral** |

**Pattern:** guanine-based nucleotides (dGMP, GMP, cGMP, xanthosine-MP) edge out the
adenine ones — the pocket tolerates, maybe slightly prefers, guanine. Several **approved
nucleoside drugs** (entecavir, sofosbuvir, molnupiravir, capecitabine) dock as well as AMP —
these are immediately testable.

**Possible stronger-but-different binder (#4):** CHEMBL21930 scores best on raw affinity
(-10.49) but low footprint overlap (0.37) — it binds hard in a *different* sub-pose, not as an
AMP mimic. Flagged for follow-up, not as a mimic.

## Honest caveats — read before trusting any rank
1. **Vina error is ~1–2 kcal/mol.** "23 of top 40 beat AMP" really means *~23 are in AMP's
   league*. Only CHEMBL21930 (-1.7) and a couple others (~-1.0) exceed AMP by more than noise.
2. **Polyanion bias:** tri-/di-phosphates (GTP -9.47, ATP -9.20) get inflated Vina scores from
   size/charge; the pocket is monophosphate-sized. Trust the mono-phosphates/nucleosides more.
3. **Protonation not rigorously assigned** (some RDKit charge warnings). Affects phosphate
   scoring.
4. Docking gives **hypotheses, not affinities.** Real ranking needs rescoring (MM-GBSA) or
   assay. Treat this as a prioritized list to test, not a truth.

## Bottom line
The pocket behaves like a genuine nucleotide-monophosphate site: nucleotide-MPs and several
approved nucleoside antivirals reproduce AMP's binding well. Best mimics = dGMP, cAMP, GMP,
entecavir, SAM. Best actionable leads = entecavir, sofosbuvir, molnupiravir (approved drugs).
No nucleotide is *dramatically* better than AMP — consistent with AMP being a natural ligand.
