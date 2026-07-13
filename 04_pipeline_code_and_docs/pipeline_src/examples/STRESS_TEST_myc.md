# Stress-test target: c-Myc (MYC, P01106) + 10058-F4

**Why this target.** c-Myc is a canonical "undruggable" intrinsically disordered
oncoprotein with a known small-molecule modulator (10058-F4, which binds the
bHLH-LZ region). It was chosen deliberately to *stress the failure path*, not to
score a second win — the value is showing the tool reports honest status on a hard
case instead of fabricating a screen.

## What the pipeline did — a layered, honest degradation

| Module | Status | What it means |
|--------|--------|---------------|
| M1 intake | `ok` | 454 aa, AlphaFold model AF-P01106-F1 retrieved |
| M2 QC | **`low_confidence`** | mean pLDDT 60.4, only 23% of residues confident — the intrinsic disorder surfaces exactly where the confidence gate should catch it |
| M3 receptor | `ok` | receptor prepared (4382 atoms) — after a real cif→pdb fix (see below) |
| M4 site | **`unscreenable`** | a liganded homolog (8OTS, ligand PTD; also 5G1X/ADP) *exists*, but superposes at **39.5 Å RMSD** — its fold cannot be aligned to the disordered model, so the tool **refuses to transplant a pocket** |

**Overall: `unscreenable`, reached M4_site.** The pipeline does not produce a
shortlist — and it says precisely why, in machine-readable form:

```json
{ "pocket_source": "homolog_untrustworthy",
  "homolog": "8OTS", "homolog_identity": 1.0, "superposition_rmsd_A": 39.48,
  "next_actions": ["check_model_pLDDT_for_disorder", "restrict_to_folded_domain",
                   "blind_docking_diffdock_l", "manual_site_from_literature"] }
```

This is the demo's strongest claim: **"it ran on a target we picked and correctly
told us it couldn't trust the pocket — and why"** is more valuable than a second
lucky success. It directly answers the live-demo failure mode (a judge picks a hard
target) that the design review flagged.

## Contrast with the reference target
| | OPLAH / 5-AMP | c-Myc / 10058-F4 |
|--|--------------|------------------|
| Model confidence (M2) | pLDDT 87.9, `ok` | pLDDT 60.4, `low_confidence` |
| Homolog superposition (M4) | 1.52 Å (packaged M4 path; the original notebook run of the same 7HK7/ANP transplant reported 1.59 Å), transplant trusted | 39.5 Å, transplant refused |
| Outcome | `low_confidence` shortlist (comparative-within-box) | `unscreenable`, no shortlist |

## A real bug this stress test caught
M3 previously passed the AlphaFold `.cif` straight to `mk_prepare_receptor`, which
needs PDB — OPLAH never hit this because it used a cached prepared receptor. The
stress test exposed it; M3 now converts mmCIF→PDB first. A second target found a
genuine defect the reference run masked — which is the point of running one.
