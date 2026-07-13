#!/usr/bin/env python3
"""Prep ALL 50k ligands to pdbqt on the Mac (8 cores), so Colab only GPU-docks.
Writes ligs_50k/<lig_id>.pdbqt and a zip bundle for upload."""
import os, csv, time, zipfile
from multiprocessing import Pool
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')
from meeko import MoleculePreparation, PDBQTWriterLegacy

BASE = str(Path(__file__).resolve().parent)   # 05b_pocket_detection/taskC
LIB = f"{BASE}/library/zinc_diverse_50k.csv"
OUTDIR = f"{BASE}/ligs_50k"
os.makedirs(OUTDIR, exist_ok=True)

def prep(row):
    lid, smi = row
    out = f"{OUTDIR}/{lid}.pdbqt"
    if os.path.exists(out):          # resumable
        return lid
    m = Chem.MolFromSmiles(smi)
    if m is None: return None
    m = Chem.AddHs(m)
    p = AllChem.ETKDGv3(); p.randomSeed = 42
    if AllChem.EmbedMolecule(m, p) != 0: return None
    try: AllChem.MMFFOptimizeMolecule(m, maxIters=100)
    except Exception: pass
    try:
        s, ok, _ = PDBQTWriterLegacy.write_string(MoleculePreparation().prepare(m)[0])
    except Exception: return None
    if not ok: return None
    open(out, "w").write(s)
    return lid

if __name__ == "__main__":
    rows = [(r["lig_id"], r["can_smiles"]) for r in csv.DictReader(open(LIB))]
    print(f"prepping {len(rows)} ligands on 8 cores ...", flush=True)
    t0 = time.time(); ok = 0
    with Pool(8) as pool:
        for i, r in enumerate(pool.imap_unordered(prep, rows, chunksize=64), 1):
            if r: ok += 1
            if i % 2000 == 0:
                el = time.time() - t0
                print(f"  {i}/{len(rows)}  ok={ok}  {el:.0f}s  eta={el/i*(len(rows)-i)/60:.0f}min", flush=True)
    print(f"prepared {ok}/{len(rows)} in {time.time()-t0:.0f}s", flush=True)
    # zip for upload
    zpath = f"{BASE}/colab/ligs_50k.zip"
    print("zipping ...", flush=True)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in os.listdir(OUTDIR):
            if f.endswith(".pdbqt"):
                z.write(f"{OUTDIR}/{f}", f"ligs_50k/{f}")
    print(f"zip -> {zpath} ({os.path.getsize(zpath)/1e6:.0f} MB)", flush=True)
