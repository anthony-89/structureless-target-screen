#!/usr/bin/env python3
"""Hybrid AMP-guided selection of 5,000 (10%) from the 50k diverse ZINC library:
  - enrichment half: top 2,500 by ECFP4 Tanimoto to 5'-AMP
  - diversity half : 2,500 MaxMin-diverse picks from the rest
Only compounds already prepared as pdbqt in ligs_50k/ are eligible.
Writes selected_5k.csv + selected_5k_list.txt (pdbqt paths for docking).
"""
import csv, time
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, DataStructs
from rdkit.SimDivFilters import rdSimDivPickers
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

BASE = Path("/Users/antonioesquivel/Desktop/claude_code_handoff/05b_pocket_detection/taskC")
LIB = BASE / "library/zinc_diverse_50k.csv"
LIGDIR = BASE / "ligs_50k"
AMP = "Nc1ncnc2c1ncn2C1OC(COP(=O)(O)O)C(O)C1O"
N_ENRICH, N_DIVERSE = 2500, 2500

t0 = time.time()
rows = [r for r in csv.DictReader(open(LIB)) if (LIGDIR / f'{r["lig_id"]}.pdbqt').exists()]
print(f"eligible (prepped) compounds: {len(rows)}", flush=True)

amp_fp = AllChem.GetMorganFingerprintAsBitVect(Chem.MolFromSmiles(AMP), 2, 2048)
fps, keep = [], []
for r in rows:
    m = Chem.MolFromSmiles(r["can_smiles"])
    if m is None:
        continue
    fps.append(AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048))
    keep.append(r)
sims = DataStructs.BulkTanimotoSimilarity(amp_fp, fps)
print(f"fingerprints + similarity done ({time.time()-t0:.0f}s). "
      f"sim range {min(sims):.2f}..{max(sims):.2f}", flush=True)

order = sorted(range(len(keep)), key=lambda i: -sims[i])
enrich = order[:N_ENRICH]
enrich_set = set(enrich)

rest = [i for i in range(len(keep)) if i not in enrich_set]
rest_fps = [fps[i] for i in rest]
print(f"MaxMin diversity pick: {N_DIVERSE} from {len(rest_fps)} ...", flush=True)
picker = rdSimDivPickers.MaxMinPicker()
picked = picker.LazyBitVectorPick(rest_fps, len(rest_fps), N_DIVERSE, seed=42)
diverse = [rest[i] for i in picked]
print(f"diversity pick done ({time.time()-t0:.0f}s)", flush=True)

sel = [(i, "enrichment") for i in enrich] + [(i, "diversity") for i in diverse]
with open(BASE / "selected_5k.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["lig_id", "zinc_id", "can_smiles", "tanimoto_to_amp", "arm"])
    for i, arm in sel:
        r = keep[i]
        w.writerow([r["lig_id"], r.get("zinc_id", ""), r["can_smiles"], f"{sims[i]:.3f}", arm])
with open(BASE / "selected_5k_list.txt", "w") as f:
    for i, _ in sel:
        f.write(str(LIGDIR / f'{keep[i]["lig_id"]}.pdbqt') + "\n")

import statistics as st
e_sims = [sims[i] for i in enrich]; d_sims = [sims[i] for i in diverse]
print(f"\nSELECTED {len(sel)} compounds:")
print(f"  enrichment arm: {len(enrich)}  Tanimoto to AMP {min(e_sims):.2f}..{max(e_sims):.2f} (median {st.median(e_sims):.2f})")
print(f"  diversity  arm: {len(diverse)}  Tanimoto to AMP {min(d_sims):.2f}..{max(d_sims):.2f} (median {st.median(d_sims):.2f})")
print(f"-> selected_5k.csv + selected_5k_list.txt  ({time.time()-t0:.0f}s total)")
