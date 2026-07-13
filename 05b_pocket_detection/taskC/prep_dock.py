#!/usr/bin/env python3
"""Task C engine: SMILES -> 3D -> pdbqt (meeko) -> Vina dock into AMP's pocket.
Parallelizes ACROSS ligands (each Vina uses --cpu 1) for HTS throughput.
Usage: prep_dock.py <input.smi/csv> <outdir> <n_workers> [limit]
"""
import sys, os, subprocess, csv, time, tempfile
from pathlib import Path
from multiprocessing import Pool
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')
from meeko import MoleculePreparation, PDBQTWriterLegacy

VINA = os.environ.get("VINA", "vina")   # Vina on PATH (activate the dock env), or set $VINA
REC = str(Path(__file__).resolve().parents[2] / "01_inputs/oplah_receptor.pdbqt")

# AMP's pocket (Task B). Focused box now that the site is known.
CX, CY, CZ = -15.58, -4.55, 17.09
BOX = float(os.environ.get("DOCK_BOX", "20.0"))
EXH = int(os.environ.get("DOCK_EXH", "8"))          # HTS setting (calibrate vs 16 later)
MMFF = os.environ.get("DOCK_MMFF", "1") == "1"

def smiles_to_pdbqt(smi):
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    p = AllChem.ETKDGv3(); p.randomSeed = 42
    if AllChem.EmbedMolecule(mol, p) != 0:
        return None
    if MMFF:
        try:
            AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
        except Exception:
            pass
    try:
        setups = MoleculePreparation().prepare(mol)
        s, ok, _ = PDBQTWriterLegacy.write_string(setups[0])
        return s if ok else None
    except Exception:
        return None

def dock_one(args):
    lig_id, smi, outdir = args
    t0 = time.time()
    pdbqt = smiles_to_pdbqt(smi)
    if pdbqt is None:
        return (lig_id, None, "prep_fail", time.time() - t0)
    lig_path = os.path.join(outdir, f"{lig_id}.pdbqt")
    out_path = os.path.join(outdir, f"{lig_id}_out.pdbqt")
    with open(lig_path, "w") as f:
        f.write(pdbqt)
    cmd = [VINA, "--receptor", REC, "--ligand", lig_path,
           "--center_x", str(CX), "--center_y", str(CY), "--center_z", str(CZ),
           "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX),
           "--exhaustiveness", str(EXH), "--num_modes", "5", "--cpu", "1",
           "--seed", "42", "--out", out_path]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=True, timeout=300)
    except Exception as e:
        return (lig_id, None, f"dock_fail:{type(e).__name__}", time.time() - t0)
    best = None
    for line in open(out_path):
        if line.startswith("REMARK VINA RESULT"):
            best = float(line.split()[3]); break
    os.remove(lig_path)  # keep only poses
    return (lig_id, best, "ok", time.time() - t0)

def load_ligands(path, limit=None):
    ligs = []
    if path.endswith(".csv"):
        for r in csv.DictReader(open(path)):
            smi = r.get("can_smiles") or r.get("smiles")
            lid = r.get("lig_id") or r.get("zinc_id") or f"L{len(ligs)}"
            if smi: ligs.append((lid, smi))
    else:  # .smi : "SMILES ID"
        for line in open(path):
            parts = line.split()
            if len(parts) >= 2:
                ligs.append((parts[1], parts[0]))
            elif parts:
                ligs.append((f"m{len(ligs)}", parts[0]))
    return ligs[:limit] if limit else ligs

if __name__ == "__main__":
    inp, outdir, nw = sys.argv[1], sys.argv[2], int(sys.argv[3])
    limit = int(sys.argv[4]) if len(sys.argv) > 4 else None
    os.makedirs(outdir, exist_ok=True)
    ligs = load_ligands(inp, limit)
    print(f"docking {len(ligs)} ligands with {nw} workers (exh={EXH}, box={BOX})", flush=True)
    t0 = time.time()
    rows = []
    with Pool(nw) as pool:
        for i, res in enumerate(pool.imap_unordered(
                dock_one, [(l, s, outdir) for l, s in ligs], chunksize=4), 1):
            rows.append(res)
            if i % 25 == 0 or i == len(ligs):
                el = time.time() - t0
                print(f"  {i}/{len(ligs)}  {el:.0f}s  {el/i:.2f}s/lig  "
                      f"proj_50k={el/i*50000/3600:.1f}h", flush=True)
    ok = [r for r in rows if r[2] == "ok"]
    with open(os.path.join(outdir, "..", "dock_results.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["lig_id", "best_affinity", "status", "sec"])
        for r in sorted(rows, key=lambda x: (x[1] if x[1] is not None else 0)):
            w.writerow([r[0], r[1], r[2], f"{r[3]:.1f}"])
    print(f"\ndone: {len(ok)}/{len(rows)} ok, {time.time()-t0:.0f}s total")
