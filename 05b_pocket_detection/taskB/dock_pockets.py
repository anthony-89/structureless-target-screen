#!/usr/bin/env python3
"""Task B (per-pocket): dock 5-AMP into EVERY detected pocket, treated identically.
AMP ranks the pockets itself by affinity. No pocket is privileged going in.
"""
import csv, subprocess, os, sys
from pathlib import Path

BASE = Path("/Users/antonioesquivel/Desktop/claude_code_handoff")
DOCK = Path("/Users/antonioesquivel/.claude-science/conda/envs/dock")
VINA = str(DOCK / "bin" / "vina")
REC = str(BASE / "01_inputs" / "oplah_receptor.pdbqt")
LIG = str(BASE / "05b_pocket_detection/taskB/ligand/5amp.pdbqt")
POCKETS = BASE / "05b_pocket_detection/pockets_p2rank.csv"
OUTDIR = BASE / "05b_pocket_detection/taskB/pockets"
OUTDIR.mkdir(parents=True, exist_ok=True)

BOX = 24.0          # cubic box side (A) — big enough for AMP (7 torsions)
EXH = 16            # exhaustiveness
NMODES = 9
SEED = 42

pockets = []
with open(POCKETS) as f:
    for row in csv.DictReader(f):
        pockets.append({
            "rank": int(row["rank"]),
            "cx": float(row["center_x"]), "cy": float(row["center_y"]), "cz": float(row["center_z"]),
        })

results = []
for p in pockets:
    r = p["rank"]
    out = OUTDIR / f"amp_pocket{r:02d}_out.pdbqt"
    log = OUTDIR / f"amp_pocket{r:02d}.log"
    cmd = [VINA, "--receptor", REC, "--ligand", LIG,
           "--center_x", f'{p["cx"]}', "--center_y", f'{p["cy"]}', "--center_z", f'{p["cz"]}',
           "--size_x", f"{BOX}", "--size_y", f"{BOX}", "--size_z", f"{BOX}",
           "--exhaustiveness", f"{EXH}", "--num_modes", f"{NMODES}", "--seed", f"{SEED}",
           "--out", str(out)]
    print(f"[pocket {r:02d}] center ({p['cx']:.1f},{p['cy']:.1f},{p['cz']:.1f}) ...", flush=True)
    with open(log, "w") as lf:
        subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, check=True)
    # parse best affinity (mode 1) from output pdbqt REMARK VINA RESULT
    best = None
    for line in open(out):
        if line.startswith("REMARK VINA RESULT"):
            best = float(line.split()[3]); break
    results.append({**p, "best_affinity": best, "out": str(out)})
    print(f"           best affinity = {best} kcal/mol", flush=True)

results.sort(key=lambda x: (x["best_affinity"] if x["best_affinity"] is not None else 0))
with open(OUTDIR.parent / "analysis" / "pocket_dock_ranking.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["pocket_rank", "center_x", "center_y", "center_z", "best_affinity_kcal_mol"])
    for r in results:
        w.writerow([r["rank"], f'{r["cx"]:.2f}', f'{r["cy"]:.2f}', f'{r["cz"]:.2f}', r["best_affinity"]])

print("\n==== AMP per-pocket ranking (most negative = best) ====")
for i, r in enumerate(results, 1):
    print(f'{i:>2}. pocket{r["rank"]:>2}  {r["best_affinity"]:>6.2f} kcal/mol  '
          f'center ({r["cx"]:.1f},{r["cy"]:.1f},{r["cz"]:.1f})')
