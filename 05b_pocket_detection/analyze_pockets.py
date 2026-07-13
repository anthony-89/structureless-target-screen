#!/usr/bin/env python3
"""Task A analysis: compile P2Rank + fpocket pockets, compare to the two ASSUMED sites.

Unbiased pocket detection over the full 1288-aa OPLAH AlphaFold model.
No truncation, no homolog transplant. Just geometry/ML on the whole protein.
"""
import csv, json, math, re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]   # repo root
P2 = BASE / "05b_pocket_detection/p2rank_out/oplah_af.pdb_predictions.csv"
FP_INFO = BASE / "05b_pocket_detection/fpocket_run/oplah_af_out/oplah_af_info.txt"
FP_PQR = BASE / "05b_pocket_detection/fpocket_run/oplah_af_out/oplah_af_pockets.pqr"
OUT = BASE / "05b_pocket_detection"

# --- the two ASSUMED (biased) site centers, for COMPARISON ONLY ---
ASSUMED = {
    "ATP_original_triphosphate": (-25.6, -7.46, 18.85),
    "AMP_reanchored":            (-16.2, -1.65, 15.2),
}
# assumed-site footprint residues (biased, from handoff)
ASSUMED_FOOTPRINT = {13, 15, 16, 17, 18, 20, 34}  # D13 G15 G16 T17 F18 D20 K34

def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

# ---------- P2Rank ----------
p2_pockets = []
with open(P2) as f:
    for row in csv.DictReader(f, skipinitialspace=True):
        row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        if not row.get("name"):
            continue
        resids = row["residue_ids"].split()
        resnums = sorted({int(r.split("_")[1]) for r in resids if "_" in r})
        c = (float(row["center_x"]), float(row["center_y"]), float(row["center_z"]))
        p2_pockets.append({
            "rank": int(row["rank"]),
            "score": float(row["score"]),
            "prob": float(row["probability"]),
            "center": c,
            "n_res": len(resnums),
            "resnums": resnums,
            "footprint_overlap": sorted(ASSUMED_FOOTPRINT & set(resnums)),
            "d_ATP": dist(c, ASSUMED["ATP_original_triphosphate"]),
            "d_AMP": dist(c, ASSUMED["AMP_reanchored"]),
        })

# ---------- fpocket: parse druggability from info + centroid from pqr ----------
fp_drug = {}
cur = None
for line in open(FP_INFO):
    m = re.match(r"Pocket (\d+) :", line.strip())
    if m:
        cur = int(m.group(1)); continue
    m = re.search(r"Druggability Score :\s*([\d.]+)", line)
    if m and cur is not None:
        fp_drug[cur] = float(m.group(1))

# pqr: ATOM lines carry pocket id in the residue-sequence column (STP resname)
fp_coords = {}
for line in open(FP_PQR):
    if line.startswith(("ATOM", "HETATM")) and "STP" in line:
        # columns are whitespace-ish; use fixed slices robustly via split fallback
        try:
            x = float(line[30:38]); y = float(line[38:46]); z = float(line[46:54])
            pid = int(line[22:26])
        except ValueError:
            parts = line.split()
            x, y, z = float(parts[6]), float(parts[7]), float(parts[8])
            pid = int(parts[5])
        fp_coords.setdefault(pid, []).append((x, y, z))

fp_pockets = []
for pid, pts in sorted(fp_coords.items()):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    cz = sum(p[2] for p in pts) / len(pts)
    c = (cx, cy, cz)
    fp_pockets.append({
        "pocket": pid,
        "drug_score": fp_drug.get(pid, float("nan")),
        "n_spheres": len(pts),
        "center": c,
        "d_ATP": dist(c, ASSUMED["ATP_original_triphosphate"]),
        "d_AMP": dist(c, ASSUMED["AMP_reanchored"]),
        "d_p2rank1": dist(c, p2_pockets[0]["center"]),
    })

# ---------- write deliverable CSV (P2Rank ranked table) ----------
with open(OUT / "pockets_p2rank.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["rank", "score", "probability", "center_x", "center_y", "center_z",
                "n_lining_res", "dist_to_ATP_site", "dist_to_AMP_site",
                "assumed_footprint_overlap", "lining_residues"])
    for p in p2_pockets:
        w.writerow([p["rank"], f'{p["score"]:.2f}', f'{p["prob"]:.3f}',
                    f'{p["center"][0]:.2f}', f'{p["center"][1]:.2f}', f'{p["center"][2]:.2f}',
                    p["n_res"], f'{p["d_ATP"]:.1f}', f'{p["d_AMP"]:.1f}',
                    "|".join(map(str, p["footprint_overlap"])),
                    " ".join(map(str, p["resnums"]))])

with open(OUT / "pockets_fpocket.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["fpocket_id", "druggability", "n_alpha_spheres",
                "center_x", "center_y", "center_z",
                "dist_to_ATP_site", "dist_to_AMP_site", "dist_to_p2rank_pocket1"])
    for p in sorted(fp_pockets, key=lambda x: -x["drug_score"]):
        w.writerow([p["pocket"], f'{p["drug_score"]:.3f}', p["n_spheres"],
                    f'{p["center"][0]:.2f}', f'{p["center"][1]:.2f}', f'{p["center"][2]:.2f}',
                    f'{p["d_ATP"]:.1f}', f'{p["d_AMP"]:.1f}', f'{p["d_p2rank1"]:.1f}'])

# ---------- console summary ----------
print("=" * 78)
print("P2RANK — top pockets (unbiased, full 1288 aa)")
print("=" * 78)
print(f'{"rank":>4} {"score":>7} {"prob":>5} {"center (x,y,z)":>26} {"nRes":>4} '
      f'{"d_ATP":>6} {"d_AMP":>6}  footprint_overlap')
for p in p2_pockets[:8]:
    c = p["center"]
    print(f'{p["rank"]:>4} {p["score"]:>7.2f} {p["prob"]:>5.3f} '
          f'({c[0]:>7.2f},{c[1]:>7.2f},{c[2]:>7.2f}) {p["n_res"]:>4} '
          f'{p["d_ATP"]:>6.1f} {p["d_AMP"]:>6.1f}  {p["footprint_overlap"]}')

print()
print("=" * 78)
print("fpocket — pockets sorted by druggability (cross-validation)")
print("=" * 78)
print(f'{"id":>3} {"drug":>6} {"nSph":>4} {"center (x,y,z)":>26} '
      f'{"d_ATP":>6} {"d_AMP":>6} {"d_P2R1":>6}')
for p in sorted(fp_pockets, key=lambda x: -x["drug_score"])[:8]:
    c = p["center"]
    print(f'{p["pocket"]:>3} {p["drug_score"]:>6.3f} {p["n_spheres"]:>4} '
          f'({c[0]:>7.2f},{c[1]:>7.2f},{c[2]:>7.2f}) '
          f'{p["d_ATP"]:>6.1f} {p["d_AMP"]:>6.1f} {p["d_p2rank1"]:>6.1f}')

# nearest fpocket to P2Rank pocket1
nearest = min(fp_pockets, key=lambda x: x["d_p2rank1"])
print()
print(f'Nearest fpocket to P2Rank pocket1: fpocket #{nearest["pocket"]} '
      f'(drug={nearest["drug_score"]:.3f}), {nearest["d_p2rank1"]:.1f} A away')

top = p2_pockets[0]
print()
print("=" * 78)
print("VERDICT (Task A)")
print("=" * 78)
print(f'P2Rank pocket1: score {top["score"]:.1f} (prob {top["prob"]:.2f}) — '
      f'{top["score"]/p2_pockets[1]["score"]:.1f}x the #2 pocket ({p2_pockets[1]["score"]:.1f}).')
print(f'  center {tuple(round(x,2) for x in top["center"])}')
print(f'  {top["d_AMP"]:.1f} A from the re-anchored AMP site; {top["d_ATP"]:.1f} A from the ATP site.')
print(f'  contains {len(top["footprint_overlap"])}/{len(ASSUMED_FOOTPRINT)} assumed-footprint residues: '
      f'{top["footprint_overlap"]}')
print(f'  spans residues {min(top["resnums"])}-{max(top["resnums"])} '
      f'(includes C-terminal {max(top["resnums"])} > DiffDock cap 1022 => truncation WOULD have damaged it).')
