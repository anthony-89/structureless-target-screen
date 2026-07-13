# Failure-mode walkthrough

The pipeline is built to **fail informatively**. Every way it can fall short maps to a
status an agent branches on, with a machine-readable reason. This is the catalogue.

Run the paired demo: `PYTHONPATH=. python examples/demo.py`

## The three states
| status | the pipeline is saying | agent should |
|--------|------------------------|--------------|
| `ok` | trust this result | proceed |
| `low_confidence` | I produced a result, but a quantified check is marginal | proceed **with** the attached caveat |
| `unscreenable` | I cannot produce a usable result here | read `reason`/`next_actions`; try another method or escalate |

## Failure modes by module

### M1 — no structure to start from
- **No UniProt sequence** → `unscreenable`. (Bad accession, or a target not in UniProt.)
- **No AlphaFold DB model** → `unscreenable`, `next_action: run_structure_predictor`.
  This is the hand-off point to a de-novo predictor (ESMFold / Boltz-2) — the tool tells
  the agent to fold first, then come back.

### M2 — model too unreliable to dock
- **mean pLDDT < 70** → `low_confidence`. Docking proceeds but every downstream score
  inherits the caveat. *Seen live on c-Myc: pLDDT 60.4, only 23% of residues confident —
  the intrinsic disorder is caught here.*

### M4 — cannot localize the pocket (the central failure mode)
This is the method's key assumption — a liganded homolog exists and can be trusted — so
it has the richest degradation:
- **No liganded homolog found** → `unscreenable`, `pocket_source: none_found`,
  `next_actions: [blind_docking_diffdock_l, cavity_detection_p2rank, manual_site_from_literature]`.
- **Homolog found but superposition RMSD > 4 Å** → `unscreenable`,
  `pocket_source: homolog_untrustworthy`. *Seen live on c-Myc: a 100%-identity liganded
  structure (8OTS) exists, but superposes at 39.5 Å — the disordered model has no stable
  fold to align to, so the tool refuses to transplant a pocket rather than inventing one.*
- **Superposition RMSD 2.5–4 Å** → `low_confidence`: pocket used, but flagged.

### M5 — anchor validates weakly
- **Anchor does not dock** → `unscreenable` (wrong site, or receptor problem).
- **Anchor docks but pose is shifted** (< 30% atom overlap with the reference) →
  `low_confidence`, with `pose_trust`. *Seen on OPLAH: 5-AMP docks strongly but ~10 Å
  off the crystallographic nucleotide. The box-contraction diagnostic showed this is an
  induced-fit limit of the apo model (affinity collapses to a +3.8 kcal/mol clash when
  the ligand is forced onto the reference), not a mislocalized pocket — pose_trust 0.59.*

### M6 / M7 — thin library or failed docking
- **0 compounds** (M6) / **nothing docked** (M7) → `unscreenable`.
- **< 10 compounds** (M6) / **> half fail to dock** (M7) → `low_confidence`.

### M8 — the shortlist inherits the weakest upstream confidence
If M5 was `low_confidence`, the shortlist is still produced but labelled
`interpretation: comparative-within-box` — it ranks compounds *relative to each other in
the same box*, and is a hypothesis generator, not a set of validated affinities.

## Why this matters for a live demo
A judge who picks their own hard target does not break the tool — they exercise a
documented path. The worst case is a correct, explained refusal (`unscreenable`), never a
crash and never a fabricated shortlist. That is the difference between a demo and a tool.
