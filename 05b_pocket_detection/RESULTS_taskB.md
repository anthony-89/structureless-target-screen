# Task B — Where does 5-AMP bind on OPLAH? (results)

**Question (#2):** where on OPLAH does 5-AMP bind? Answered on OPLAH's own terms — a
location + contact residues — by letting AMP sample the protein. No ATP/homolog reference
defines the answer.

**Method:** 5-AMP prepared at physiological protonation (net charge **−2**, deprotonated
phosphate; 7 rotatable bonds) with Meeko 0.7.1. AutoDock Vina 1.2.7, seed 42.
Two independent searches:
1. **Blind dock** — box enclosing the whole protein (100×92×106 Å), no pocket prior.
2. **Per-pocket dock** — 24 Å box on each of the 21 P2Rank pockets, all treated identically.

## Answer
**AMP binds one site on OPLAH**, centered near **(-16, -3, 17)**, defined by these contacts
(residues within 4.0 Å of AMP's best pose):

> **D13, G15, G16, T17, F18, D20, K34** (N-terminal loop)
> **D314, G316, G317, T318, S319** (middle domain)
> **G489, G490, G515, S518, A519** (third strand)

The site is a **glycine-rich, Thr/Ser/Lys/Asp-lined phosphate-binding cleft** — consistent
with a nucleotide-monophosphate binder. F18 stacks against the adenine; the Gly-rich loops +
K34 coordinate the phosphate.

## Why this is robust — three independent methods converge
| Evidence | Result | Agreement |
|---|---|---|
| P2Rank geometry (Task A) | pocket 1, prob 0.98, 5× next | center (-15.6,-4.5,17.1) |
| fpocket geometry (Task A) | most druggable (0.788) | 1.8 Å from P2Rank |
| **Blind dock** (no prior) | best pose −8.79 kcal/mol | **2.2 Å** from P2Rank pocket 1 |
| **Per-pocket dock** | best = pocket 1, −8.78 kcal/mol | same site, 0.01 kcal/mol from blind |

Geometry, druggability, and two independent docking searches all point to the same cavity.

## Honest read on the docking margin
On docking score alone the win is real but not huge: pocket 1 (−8.78) leads pocket 5 (−8.06,
at (5,-7,28), ~16 Å away) and pocket 19 (−7.98) by ~0.7–0.8 kcal/mol — within Vina's noise if
taken in isolation. **The confidence comes from convergence, not the gap:** the blind dock
(which had no reason to prefer pocket 1) independently landed there, and it is also the
dominant pocket by geometry (5× P2Rank score, top fpocket druggability). No competing site has
that support — the runner-ups are geometrically minor (P2Rank rank 5/19) and 0.7+ kcal/mol
weaker. Full ranking: `taskB/analysis/pocket_dock_ranking.csv`.

## Files
- `taskB/ligand/5amp.pdbqt` — prepared ligand
- `taskB/blind/amp_blind_out.pdbqt` + `.log` — blind dock poses
- `taskB/pockets/amp_pocket01_out.pdbqt` … `21` — per-pocket poses
- `taskB/analysis/pocket_dock_ranking.csv` — AMP affinity per pocket
- `taskB/contacts.py` — contact-residue extraction

## Footnote (NOT the question)
For the record only: this unbiased site happens to reproduce the old assumed footprint
(all of D13/G15/G16/T17/F18/D20/K34) and sits 2–3 Å from the old *AMP-anchored* center. So the
earlier guess was roughly right — but that is now a consequence of the unbiased result, not an
input to it.

## Next: Task C (#3, #4)
Dock the 73-compound library (`01_inputs/candidate_library.csv`, col `can_smiles`, L001=AMP)
into **this** site and rank by how well each reproduces AMP's contact footprint (above).
#3 = mimics of AMP's binding; #4 = compounds that bind the site better than AMP.
