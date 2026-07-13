"""M3 — Receptor prep: trim, protonate, convert to PDBQT (Meeko)."""
from __future__ import annotations
import subprocess
from pathlib import Path
from ..config import PipelineConfig
from ..status import ModuleResult, ok, low_confidence, unscreenable


def run(cfg: PipelineConfig, cif_or_pdb: str, low_conf_regions=None) -> ModuleResult:
    pdbqt = cfg.path("m3", "receptor.pdbqt")
    rec_pdb = cfg.path("m3", "receptor.pdb")
    if pdbqt.exists() and rec_pdb.exists():
        n = sum(1 for l in open(pdbqt) if l.startswith("ATOM"))
        return ok("M3_receptor", f"cached receptor ({n} atoms)",
                  data={"pdbqt_atoms": n}, artifacts=[str(pdbqt), str(rec_pdb)])

    src = Path(cif_or_pdb)
    if not src.exists():
        return unscreenable("M3_receptor", "no input structure to prepare")
    # mk_prepare_receptor needs PDB; convert mmCIF -> PDB first if needed.
    if src.suffix.lower() in (".cif", ".mmcif"):
        pdb_in = cfg.path("m3", "input.pdb")
        try:
            subprocess.run(["obabel", str(src), "-O", str(pdb_in)],
                           check=True, capture_output=True, timeout=300)
        except Exception as e:
            return unscreenable("M3_receptor", f"cif->pdb conversion failed: {type(e).__name__}")
        src = pdb_in
    # protonate + PDBQT via meeko CLI (mk_prepare_receptor)
    try:
        subprocess.run(["mk_prepare_receptor.py", "--read_pdb", str(src),
                        "-o", str(cfg.path("m3", "receptor")), "-p", "--allow_bad_res"],
                       check=True, capture_output=True, timeout=600)
    except Exception as e:
        return unscreenable("M3_receptor", f"receptor preparation failed: {type(e).__name__}")
    n = sum(1 for l in open(pdbqt) if l.startswith("ATOM")) if pdbqt.exists() else 0
    if n == 0:
        return unscreenable("M3_receptor", "receptor PDBQT is empty after preparation")
    return ok("M3_receptor", f"prepared receptor ({n} atoms)",
              data={"pdbqt_atoms": n}, artifacts=[str(pdbqt), str(rec_pdb)])
