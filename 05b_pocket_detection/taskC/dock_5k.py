#!/usr/bin/env python3
"""Dock the AMP-guided 5,000-compound subset (10% of the diverse ZINC library) into
AMP's pocket with local AutoDock Vina. Resumable (skips already-docked). Runs 8-way.
Includes 5'-AMP as a matched control. ~11 h on this Mac (8 s/lig, 8 cores, exh 8)."""
import csv, os, subprocess, time
from pathlib import Path
from multiprocessing import Pool

BASE = Path(__file__).resolve().parent            # 05b_pocket_detection/taskC
REC = str(BASE.parents[1] / "01_inputs/oplah_receptor.pdbqt")
VINA = os.environ.get("VINA", "vina")             # Vina on PATH (activate the dock env), or set $VINA
AMP_LIG = str(BASE / "taskB/ligand/5amp.pdbqt")
OUTDIR = BASE / "dock_5k/poses"; OUTDIR.mkdir(parents=True, exist_ok=True)
RESULTS = BASE / "dock_5k/results.csv"
CENTER = (-15.58, -4.55, 17.09); BOX = 22; EXH = 8

def parse(fp):
    for line in open(fp):
        if line.startswith("REMARK VINA RESULT"):
            try: return float(line.split()[3])
            except Exception: return None
    return None

def dock(lig):
    bn = os.path.basename(lig)[:-6]
    out = OUTDIR / f"{bn}_out.pdbqt"
    if out.exists() and out.stat().st_size > 0:              # resumable
        return (bn, parse(out))
    cmd = [VINA, "--receptor", REC, "--ligand", lig,
           "--center_x", str(CENTER[0]), "--center_y", str(CENTER[1]), "--center_z", str(CENTER[2]),
           "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX),
           "--exhaustiveness", str(EXH), "--num_modes", "1", "--seed", "42", "--cpu", "1",
           "--out", str(out)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return (bn, parse(out) if out.exists() else None)

if __name__ == "__main__":
    ligs = [l.strip() for l in open(BASE / "selected_5k_list.txt") if l.strip()]
    if os.path.exists(AMP_LIG):
        ligs = [AMP_LIG] + ligs                             # AMP control first
    done = set()
    if RESULTS.exists():
        done = {r[0] for r in csv.reader(open(RESULTS)) if r and r[0] != "lig_id"}
    todo = [l for l in ligs if os.path.basename(l)[:-6] not in done]
    print(f"total {len(ligs)} | already done {len(done)} | to dock {len(todo)}", flush=True)

    new = not RESULTS.exists()
    f = open(RESULTS, "a", newline=""); w = csv.writer(f)
    if new: w.writerow(["lig_id", "best_affinity_kcal_mol"]); f.flush()
    t0 = time.time(); n = 0
    with Pool(8) as pool:
        for bn, aff in pool.imap_unordered(dock, todo, chunksize=1):
            w.writerow([bn, aff]); n += 1
            if n % 200 == 0:
                f.flush(); el = time.time() - t0
                eta = el / n * (len(todo) - n) / 3600
                print(f"  {n}/{len(todo)}  {el:.0f}s  {el/n:.1f}s/lig  eta={eta:.1f}h", flush=True)
    f.close()
    print(f"DONE: docked {n} in {time.time()-t0:.0f}s -> {RESULTS}", flush=True)
