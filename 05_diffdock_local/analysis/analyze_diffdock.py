"""Task B: measure DiffDock's blind poses against AMP's known footprint.

The blind dock got no box and no site hint. The question is whether it
independently lands on the bipartite site found by hand.

Metrics per pose
  coverage_7   fraction of the 7 reference residues contacted at <=4.5 A.
               (Over the 7-residue universe this equals the contact-Jaccard,
                since a pose's contacts within that universe are a subset of it.)
  jaccard_full Jaccard of the pose's full 4.5 A contact shell against the
               reference Vina pose's full shell -- a stricter, set-symmetric score.
  adenine_F18  F18 contacted (the adenine-recognition motif).
  phos_n       how many of D13/G15/G16/T17/D20/K34 are contacted.
"""
import glob
import os
import re
import sys
import numpy as np
from footprint import (parse_pdb_heavy, parse_pdbqt_ligand, parse_sdf_heavy,
                       residue_min_distances, footprint, jaccard,
                       AMP_FOOTPRINT, ADENINE_MOTIF, PHOSPHATE_MOTIF,
                       BOX_AMP_ANCHORED, BOX_ORIGINAL_TRIPHOS, CUTOFF)

IN = "/Users/antonioesquivel/Desktop/claude_code_handoff/01_inputs"
OUTDIR = sys.argv[1] if len(sys.argv) > 1 else \
    "/Users/antonioesquivel/Desktop/claude_code_handoff/05_diffdock_local/DiffDock/out/oplah_amp_blind"

REF7 = sorted(AMP_FOOTPRINT)


def conf_from_name(p):
    m = re.search(r"confidence(-?\d+(?:\.\d+)?)", os.path.basename(p))
    return float(m.group(1)) if m else None


def rank_from_name(p):
    m = re.search(r"rank(\d+)", os.path.basename(p))
    return int(m.group(1)) if m else 10**6


prot_xyz, prot_meta = parse_pdb_heavy(f"{IN}/oplah_receptor.pdb")

# reference: AMP's Vina pose (model 1). Same coordinate frame as the truncated receptor.
ref = parse_pdbqt_ligand(f"{IN}/AMP_docked_pose_L001_out.pdbqt", model=1)
ref_shell, _ = footprint(ref, prot_xyz, prot_meta)
ref_cent = ref.mean(axis=0)

# DiffDock also writes a bare rank1.sdf duplicating rank1_confidence*.sdf -- exclude it.
poses = sorted((p for p in glob.glob(f"{OUTDIR}/rank*_confidence*.sdf")), key=rank_from_name)
if not poses:
    poses = sorted(glob.glob(f"{OUTDIR}/rank*.sdf"), key=rank_from_name)
if not poses:
    print(f"NO POSES FOUND in {OUTDIR}")
    sys.exit(1)

print(f"DiffDock blind dock: {len(poses)} poses in {OUTDIR}")
print(f"reference 7-residue footprint : {REF7}")
print(f"reference Vina pose full shell: {sorted(ref_shell)}")
print(f"reference Vina pose centroid  : ({ref_cent[0]:.2f}, {ref_cent[1]:.2f}, {ref_cent[2]:.2f})")
print(f"AMP-anchored box {tuple(BOX_AMP_ANCHORED)} | original box {tuple(BOX_ORIGINAL_TRIPHOS)}")
print(f"contact cutoff: {CUTOFF} A, min heavy-atom distance\n")

rows = []
for p in poses:
    lig = parse_sdf_heavy(p)
    shell, mins = footprint(lig, prot_xyz, prot_meta)
    cent = lig.mean(axis=0)
    hit7 = shell & AMP_FOOTPRINT
    rows.append({
        "rank": rank_from_name(p),
        "conf": conf_from_name(p),
        "cov7": len(hit7) / len(AMP_FOOTPRINT),
        "hit7": sorted(hit7),
        "jfull": jaccard(shell, ref_shell),
        "aden": 18 in shell,
        "phos_n": len(shell & PHOSPHATE_MOTIF),
        "both": (18 in shell) and bool(shell & PHOSPHATE_MOTIF),
        "d_amp": float(np.linalg.norm(cent - BOX_AMP_ANCHORED)),
        "d_orig": float(np.linalg.norm(cent - BOX_ORIGINAL_TRIPHOS)),
        "d_ref": float(np.linalg.norm(cent - ref_cent)),
        "mins": mins,
        "nshell": len(shell),
    })

print("=" * 108)
print(f"{'rank':>4} {'conf':>7} {'cov7':>5} {'F18':>4} {'phos':>5} {'both':>5} "
      f"{'Jfull':>6} {'d->AMPbox':>10} {'d->origbox':>11} {'d->refpose':>11} {'shell':>6}")
print("=" * 108)
for r in rows[:12]:
    print(f"{r['rank']:>4} {r['conf'] if r['conf'] is not None else float('nan'):7.2f} "
          f"{r['cov7']:5.2f} {'Y' if r['aden'] else '.':>4} {r['phos_n']:>5} "
          f"{'Y' if r['both'] else '.':>5} {r['jfull']:6.2f} {r['d_amp']:10.2f} "
          f"{r['d_orig']:11.2f} {r['d_ref']:11.2f} {r['nshell']:>6}")

top = rows[0]
print("\n" + "=" * 60)
print("TOP-CONFIDENCE POSE (rank1)")
print("=" * 60)
print(f"confidence            : {top['conf']}")
print(f"centroid -> AMP box   : {top['d_amp']:.2f} A")
print(f"centroid -> orig box  : {top['d_orig']:.2f} A")
print(f"centroid -> Vina pose : {top['d_ref']:.2f} A")
print(f"contacts 7-set        : {top['hit7']}  ({len(top['hit7'])}/7, coverage {top['cov7']:.2f})")
print(f"adenine motif F18     : {'CONTACTED' if top['aden'] else 'not contacted'}")
print(f"phosphate motif       : {top['phos_n']}/6 of {sorted(PHOSPHATE_MOTIF)}")
print(f"Jaccard vs Vina shell : {top['jfull']:.2f}")
print("\nper-residue min heavy-atom distance (A):")
for r in REF7:
    d, name = top["mins"][r]
    print(f"  {name}{r:<4} {d:6.2f} {'<= contact' if d <= CUTOFF else ''}")

best = max(rows, key=lambda r: (r["cov7"], -r["d_amp"]))
print(f"\nbest-covering pose: rank{best['rank']} (conf {best['conf']}), "
      f"coverage {best['cov7']:.2f}, {len(best['hit7'])}/7, d->AMPbox {best['d_amp']:.2f} A")

n_on_site = sum(1 for r in rows if r["cov7"] >= 0.5)
print(f"\n{n_on_site}/{len(rows)} poses contact >=4 of the 7 reference residues")
print(f"{sum(1 for r in rows if r['d_amp'] < r['d_orig'])}/{len(rows)} poses are closer to the "
      f"AMP-anchored box than to the original triphosphate box")
