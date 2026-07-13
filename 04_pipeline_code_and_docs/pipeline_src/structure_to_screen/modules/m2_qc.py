"""M2 — Structure QC: per-residue pLDDT confidence gate.

Below `min_mean_plddt` the model is flagged `low_confidence` (docking proceeds
but the caveat is attached to every downstream result).
"""
from __future__ import annotations
import json
import numpy as np
from ..config import PipelineConfig
from ..status import ModuleResult, ok, low_confidence, unscreenable


def _plddt_from_cif(cif_path):
    vals = []
    for line in open(cif_path):
        if line.startswith(("ATOM", "HETATM")):
            parts = line.split()
            # mmCIF atom_site: pLDDT is the B-iso column; grab CA rows
            if " CA " in f" {parts[3] if len(parts)>3 else ''} " or (len(parts) > 5 and parts[3] == "CA"):
                try:
                    vals.append(float(parts[14]))
                except (IndexError, ValueError):
                    pass
    return np.array(vals)


def run(cfg: PipelineConfig, m1: ModuleResult) -> ModuleResult:
    cif = next((a for a in m1.artifacts if a.endswith(".cif")), None)
    if cif is None:
        return unscreenable("M2_qc", "no structure to QC (M1 produced no model)")

    plddt = _plddt_from_cif(cif)
    if plddt.size == 0:
        return low_confidence("M2_qc", "could not parse pLDDT from model; proceeding without confidence gate",
                              confidence=None)
    mean = float(plddt.mean())
    frac70 = float((plddt >= 70).mean())
    out = {"mean_plddt": round(mean, 2), "frac_ge_70": round(frac70, 3),
           "n_residues": int(plddt.size), "min": round(float(plddt.min()), 2)}
    cfg.path("m2", "qc.json").write_text(json.dumps(out, indent=2))
    conf = round(frac70, 3)

    if mean < cfg.min_mean_plddt:
        return low_confidence("M2_qc",
            f"mean pLDDT {mean:.1f} < {cfg.min_mean_plddt:.0f}: model confidence marginal; docking results carry this caveat",
            confidence=conf, data=out, metrics=out, artifacts=[str(cfg.path('m2','qc.json'))])
    return ok("M2_qc", f"mean pLDDT {mean:.1f}, {frac70*100:.0f}% of residues confident",
              confidence=conf, data=out, metrics=out, artifacts=[str(cfg.path('m2','qc.json'))])
