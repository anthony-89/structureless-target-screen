"""Sanity check: reproduce the manual Vina AMP footprint numbers from raw coordinates.

If this does not match, no downstream DiffDock measurement can be trusted.
"""
import os
import numpy as np
from footprint import (parse_pdb_heavy, parse_pdbqt_ligand, residue_min_distances,
                       footprint, AMP_FOOTPRINT, BOX_AMP_ANCHORED, BOX_ORIGINAL_TRIPHOS)

IN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "01_inputs")

# reference values from the manual Vina run (Task B)
EXPECTED = {13: 3.08, 15: 4.29, 16: 3.55, 17: 2.06, 18: 3.45, 20: 2.88, 34: 4.30}
EXPECTED_NONCONTACT = {14: 6.72}  # R14: part of the P-loop motif, NOT a direct contact

prot_xyz, prot_meta = parse_pdb_heavy(f"{IN}/oplah_receptor.pdb")
lig = parse_pdbqt_ligand(f"{IN}/AMP_docked_pose_L001_out.pdbqt", model=1)

print(f"receptor heavy atoms : {len(prot_xyz)}")
print(f"AMP pose heavy atoms : {len(lig)}  (model 1)")

cent = lig.mean(axis=0)
print(f"\nAMP pose centroid    : ({cent[0]:.2f}, {cent[1]:.2f}, {cent[2]:.2f})")
print(f"  dist -> AMP-anchored box center {BOX_AMP_ANCHORED}: "
      f"{np.linalg.norm(cent - BOX_AMP_ANCHORED):.2f} A")
print(f"  dist -> original triphosphate box {BOX_ORIGINAL_TRIPHOS}: "
      f"{np.linalg.norm(cent - BOX_ORIGINAL_TRIPHOS):.2f} A")
print(f"  box-to-box separation: {np.linalg.norm(BOX_AMP_ANCHORED - BOX_ORIGINAL_TRIPHOS):.2f} A"
      f"   (reference: 11.6)")

mins = residue_min_distances(lig, prot_xyz, prot_meta)

print("\n--- reported contacts (min heavy-atom distance, A) ---")
print(f"{'res':>6} {'expected':>9} {'measured':>9} {'delta':>7}  ok")
ok_all = True
for r, exp in sorted(EXPECTED.items()):
    got, name = mins[r]
    delta = got - exp
    ok = abs(delta) <= 0.15
    ok_all &= ok
    print(f"{name}{r:<3} {exp:9.2f} {got:9.2f} {delta:+7.2f}  {'OK' if ok else 'MISMATCH'}")

print("\n--- reported NON-contact ---")
for r, exp in EXPECTED_NONCONTACT.items():
    got, name = mins[r]
    delta = got - exp
    ok = abs(delta) <= 0.15
    ok_all &= ok
    print(f"{name}{r:<3} {exp:9.2f} {got:9.2f} {delta:+7.2f}  {'OK' if ok else 'MISMATCH'}")

fp, _ = footprint(lig, prot_xyz, prot_meta)
print(f"\nfootprint @4.5A  : {sorted(fp)}")
print(f"reference footprint: {sorted(AMP_FOOTPRINT)}")
print(f"exact match      : {fp == AMP_FOOTPRINT}")
extra = fp - AMP_FOOTPRINT
if extra:
    print(f"extra residues within 4.5A not in the reference footprint:"
          f"{[(mins[r][1] + str(r), round(mins[r][0], 2)) for r in sorted(extra)]}")

print(f"\nVALIDATION {'PASSED' if ok_all and fp == AMP_FOOTPRINT else 'NEEDS REVIEW'}")
