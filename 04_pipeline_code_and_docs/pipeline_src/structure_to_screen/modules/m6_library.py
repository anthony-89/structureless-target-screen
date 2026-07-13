"""M6 — Candidate library: analogs + mimetics of the modulator scaffold."""
from __future__ import annotations
import json
from pathlib import Path
from ..config import PipelineConfig
from ..status import ModuleResult, ok, low_confidence, unscreenable


def run(cfg: PipelineConfig) -> ModuleResult:
    lib_csv = cfg.path("m6", "candidate_library.csv")
    if lib_csv.exists():
        n = sum(1 for _ in open(lib_csv)) - 1
        return ok("M6_library", f"cached library ({n} compounds)",
                  data={"n_compounds": n}, artifacts=[str(lib_csv)])

    from .._library import build_library
    n, chemotypes = build_library(cfg, lib_csv)   # writes CSV + pdbqt bundle
    if n == 0:
        return unscreenable("M6_library",
            "no candidate compounds found for the modulator scaffold (ChEMBL returned nothing)")
    if n < 10:
        return low_confidence("M6_library",
            f"small library ({n} compounds, {chemotypes} chemotypes): screen will be underpowered",
            confidence=round(min(n / 50, 1.0), 2), data={"n_compounds": n, "chemotypes": chemotypes},
            artifacts=[str(lib_csv)])
    return ok("M6_library", f"{n} compounds, {chemotypes} chemotypes",
              data={"n_compounds": n, "chemotypes": chemotypes}, artifacts=[str(lib_csv)])
