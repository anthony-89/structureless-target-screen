"""Live-path candidate library builder (M6).

Two sources, in priority order:
  1. If the user drops `m6/candidate_library.csv` into the run dir, M6 uses it directly
     (handled in the module, before this function is called) — "bring your own library".
  2. Otherwise this builds a library from ChEMBL: similarity + substructure search around
     the known modulator, standardised and size-filtered with RDKit.

The ChEMBL REST API (https://www.ebi.ac.uk/chembl/api) is queried directly so the package
does not depend on any MCP host. Network failures degrade gracefully to (0, 0) so M6 emits
`unscreenable` rather than crashing.
"""
from __future__ import annotations
import csv
import time
import urllib.parse
import urllib.request
import json as _json

CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"


def _get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return _json.loads(r.read().decode())
        except Exception:
            time.sleep(1.0 * (i + 1))
    return None


def _similarity(smiles, threshold, limit=200):
    q = urllib.parse.quote(smiles)
    url = f"{CHEMBL}/similarity/{q}/{threshold}.json?limit={limit}"
    d = _get(url)
    out = []
    if d:
        for m in d.get("molecules", []):
            cs = (m.get("molecule_structures") or {})
            smi = cs.get("canonical_smiles")
            if smi:
                out.append((m.get("molecule_chembl_id"), smi))
    return out


def build_library(cfg, out_csv):
    """Build + standardise a candidate library around the modulator. Returns (n, n_chemotypes)."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, AllChem
    from rdkit.Chem.MolStandardize import rdMolStandardize
    from rdkit.ML.Cluster import Butina
    from rdkit import DataStructs

    lo, hi = cfg.library_similarity if len(cfg.library_similarity) >= 2 else (70, 80)
    raw = {}
    for thr in (hi, lo):
        for cid, smi in _similarity(cfg.modulator_smiles, thr, limit=cfg.library_max * 3):
            if cid and cid not in raw:
                raw[cid] = smi
    # always include the modulator itself as the anchor
    raw.setdefault("MODULATOR", cfg.modulator_smiles)

    lc = rdMolStandardize.LargestFragmentChooser()
    keep, seen = [], set()
    for cid, smi in raw.items():
        m = Chem.MolFromSmiles(smi)
        if m is None:
            continue
        m = rdMolStandardize.Cleanup(lc.choose(m))
        can = Chem.MolToSmiles(m)
        if can in seen:
            continue
        mw, heavy = Descriptors.MolWt(m), m.GetNumHeavyAtoms()
        if cid != "MODULATOR" and not (120 <= mw <= 600 and 8 <= heavy <= 45):
            continue
        seen.add(can)
        keep.append((cid, can, round(mw, 1), heavy, m))
    if not keep:
        return 0, 0

    # Butina cluster (Morgan r2) to count chemotypes
    fps = [AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048) for *_, m in keep]
    n = len(fps)
    dists = []
    for i in range(1, n):
        sims = DataStructs.BulkTanimotoSimilarity(fps[i], fps[:i])
        dists.extend(1 - s for s in sims)
    clusters = Butina.ClusterData(dists, n, 0.4, isDistData=True) if n > 1 else ((0,),)

    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["lig_id", "chembl_id", "smiles", "mw", "heavy_atoms"])
        for i, (cid, can, mw, heavy, _m) in enumerate(keep):
            w.writerow([f"L{i:04d}", cid, can, mw, heavy])
    return n, len(clusters)
