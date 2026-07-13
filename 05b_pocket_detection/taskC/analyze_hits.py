#!/usr/bin/env python3
"""Rank a docked library into a shortlist: affinity (#4 better binders) + how well
each reproduces AMP's contact footprint (#3 mimics). Usage:
  analyze_hits.py <run_dir> <library_csv> [top_n_for_footprint]
<run_dir> holds dock_results.csv and poses/<id>_out.pdbqt
"""
import sys, csv, math, os
from pathlib import Path

RUN = Path(sys.argv[1])
LIB = sys.argv[2]
TOPN = int(sys.argv[3]) if len(sys.argv) > 3 else 40
REC = str(Path(__file__).resolve().parents[2] / "01_inputs/oplah_receptor.pdbqt")
AMP_FOOTPRINT = {13,15,16,17,18,20,34, 314,316,317,318,319, 489,490,515,518,519}
CUTOFF = 4.0
AMP_AFFINITY = -8.78   # AMP's own best affinity in this pocket (Task B)

# receptor atoms with residue number
rec = []
for l in open(REC):
    if l.startswith(("ATOM","HETATM")):
        try: rec.append((float(l[30:38]),float(l[38:46]),float(l[46:54]), int(l[22:26])))
        except ValueError: pass

def pose_contacts(pose_path):
    lig = []
    started = False
    for l in open(pose_path):
        if l.startswith("MODEL"):
            if started: break
            started = True; continue
        if started and l.startswith(("ATOM","HETATM")):
            lig.append((float(l[30:38]),float(l[38:46]),float(l[46:54])))
        if l.startswith("ENDMDL"): break
    res = set()
    for (rx,ry,rz,ri) in rec:
        for (lx,ly,lz) in lig:
            if (rx-lx)**2+(ry-ly)**2+(rz-lz)**2 <= CUTOFF*CUTOFF:
                res.add(ri); break
    return res

# names
name = {}
for r in csv.DictReader(open(LIB)):
    lid = r.get("lig_id")
    name[lid] = r.get("pref_name") or r.get("zinc_id") or lid

# affinities
results = []
for r in csv.DictReader(open(RUN/"dock_results.csv")):
    if r["status"] != "ok" or not r["best_affinity"]: continue
    results.append((r["lig_id"], float(r["best_affinity"])))
results.sort(key=lambda x: x[1])

# footprint overlap for the top affinity hits
rows = []
for lid, aff in results[:TOPN]:
    pose = RUN/"poses"/f"{lid}_out.pdbqt"
    if not pose.exists():
        rows.append((lid, aff, None, None)); continue
    c = pose_contacts(pose)
    inter = c & AMP_FOOTPRINT
    jacc = len(inter)/len(c | AMP_FOOTPRINT) if c else 0.0
    rows.append((lid, aff, len(inter), jacc))

# combined shortlist score: normalize affinity + footprint jaccard
def combo(aff, jacc):
    if jacc is None: return aff
    return aff - 2.0*jacc   # reward footprint mimicry (kcal-equivalent nudge)

rows.sort(key=lambda x: combo(x[1], x[3]))
print(f"{'rank':>4} {'lig_id':>8} {'name':<24} {'aff':>7} {'vsAMP':>6} {'fp_hits':>7} {'jaccard':>7}")
better = 0
out_csv = RUN/"shortlist.csv"
with open(out_csv,"w",newline="") as f:
    w = csv.writer(f); w.writerow(["rank","lig_id","name","affinity","delta_vs_AMP","footprint_overlap_residues","footprint_jaccard","beats_AMP"])
    for i,(lid,aff,fph,jac) in enumerate(rows,1):
        d = aff - AMP_AFFINITY
        beats = aff < AMP_AFFINITY
        if beats: better += 1
        nm = name.get(lid, lid)[:24]
        js = f"{jac:.2f}" if jac is not None else "NA"
        print(f"{i:>4} {lid:>8} {nm:<24} {aff:>7.2f} {d:>+6.2f} {str(fph):>7} {js:>7}")
        w.writerow([i, lid, name.get(lid,lid), aff, round(d,2), fph, js, beats])
print(f"\nAMP reference affinity: {AMP_AFFINITY} kcal/mol")
print(f"compounds beating AMP on affinity (top {TOPN}): {better}")
print(f"shortlist -> {out_csv}")
