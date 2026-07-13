"""Task C: does any fpocket pocket overlap the AMP binding site?

fpocket is ligand-free, so this is an independent geometric vote on where the
site is. Pockets in *_info.txt are ordered by fpocket score (descending).
"""
import os
import re
import sys
import numpy as np
from footprint import AMP_FOOTPRINT, BOX_AMP_ANCHORED, BOX_ORIGINAL_TRIPHOS, jaccard

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "05_diffdock_local/fpocket_work/oplah_receptor_out")
STEM = OUT.rstrip("/").split("/")[-1].replace("_out", "")


def parse_info(path):
    pockets, cur = {}, None
    for line in open(path):
        m = re.match(r"Pocket (\d+)", line)
        if m:
            cur = int(m.group(1)); pockets[cur] = {}
            continue
        m = re.match(r"\t(.+?) :\s*\t?(-?[\d.]+)", line)
        if m and cur:
            pockets[cur][m.group(1).strip()] = float(m.group(2))
    return pockets


def pocket_residues(path):
    res = set()
    for line in open(path):
        if line.startswith(("ATOM", "HETATM")):
            res.add(int(line[22:26]))
    return res


def alpha_centroid(path):
    pts = [(float(l[30:38]), float(l[38:46]), float(l[46:54]))
           for l in open(path) if l.startswith(("ATOM", "HETATM"))]
    return np.asarray(pts).mean(axis=0) if pts else None


info = parse_info(f"{OUT}/{STEM}_info.txt")
rows = []
for pid in sorted(info):
    res = pocket_residues(f"{OUT}/pockets/pocket{pid}_atm.pdb")
    cen = alpha_centroid(f"{OUT}/pockets/pocket{pid}_vert.pqr")
    shared = res & AMP_FOOTPRINT
    rows.append({
        "pocket": pid,
        "score": info[pid].get("Score", float("nan")),
        "drug": info[pid].get("Druggability Score", float("nan")),
        "vol": info[pid].get("Volume", float("nan")),
        "nres": len(res),
        "shared": len(shared),
        "shared_res": sorted(shared),
        "jaccard": jaccard(res, AMP_FOOTPRINT),
        "d_amp_box": float(np.linalg.norm(cen - BOX_AMP_ANCHORED)) if cen is not None else float("nan"),
        "d_orig_box": float(np.linalg.norm(cen - BOX_ORIGINAL_TRIPHOS)) if cen is not None else float("nan"),
        "centroid": cen,
    })

hits = sorted([r for r in rows if r["shared"]], key=lambda r: (-r["shared"], r["pocket"]))

print(f"fpocket on {STEM}: {len(rows)} pockets")
print(f"AMP reference footprint: {sorted(AMP_FOOTPRINT)}\n")

print("=== pockets containing ANY AMP footprint residue ===")
print(f"{'rank':>4} {'score':>7} {'drug':>6} {'vol':>8} {'nres':>5} {'shared':>7} "
      f"{'Jacc':>5} {'d->AMPbox':>10} {'d->origbox':>11}  shared residues")
for r in hits:
    print(f"{r['pocket']:>4} {r['score']:7.3f} {r['drug']:6.3f} {r['vol']:8.1f} {r['nres']:5} "
          f"{r['shared']:7} {r['jaccard']:5.2f} {r['d_amp_box']:10.2f} {r['d_orig_box']:11.2f}  {r['shared_res']}")
if not hits:
    print("  NONE")

print("\n=== fpocket's own top-5 by score ===")
print(f"{'rank':>4} {'score':>7} {'drug':>6} {'vol':>8} {'nres':>5} {'shared':>7} {'d->AMPbox':>10}")
for r in rows[:5]:
    print(f"{r['pocket']:>4} {r['score']:7.3f} {r['drug']:6.3f} {r['vol']:8.1f} {r['nres']:5} "
          f"{r['shared']:7} {r['d_amp_box']:10.2f}")

print("\n=== top-5 by druggability ===")
for r in sorted(rows, key=lambda r: -r["drug"])[:5]:
    print(f"{r['pocket']:>4} {r['score']:7.3f} {r['drug']:6.3f} {r['vol']:8.1f} {r['nres']:5} "
          f"{r['shared']:7} {r['d_amp_box']:10.2f}")

print("\n=== pocket nearest the AMP-anchored box center ===")
for r in sorted(rows, key=lambda r: r["d_amp_box"])[:5]:
    print(f"pocket {r['pocket']:>3}  d={r['d_amp_box']:6.2f} A  score={r['score']:.3f}  "
          f"drug={r['drug']:.3f}  shared={r['shared']}  {r['shared_res']}")
