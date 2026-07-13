"""M7 — Virtual screen: dock the library into the defined site (AutoDock Vina)."""
from __future__ import annotations
import json
from ..config import PipelineConfig
from ..status import ModuleResult, ok, low_confidence, unscreenable


def run(cfg: PipelineConfig, receptor_pdbqt: str, site: dict, library_csv: str) -> ModuleResult:
    scores = cfg.path("m7", "docking_scores.csv")
    if scores.exists():
        n = sum(1 for _ in open(scores)) - 1
        return ok("M7_screen", f"cached screen ({n} docked)",
                  data={"n_docked": n}, artifacts=[str(scores)])

    from .._dock import screen_library
    n_ok, n_fail = screen_library(cfg, receptor_pdbqt, site, library_csv, scores)
    if n_ok == 0:
        return unscreenable("M7_screen", "no ligand docked successfully")
    if n_fail > n_ok:
        return low_confidence("M7_screen",
            f"{n_fail} of {n_ok+n_fail} ligands failed to dock; screen is partial",
            confidence=round(n_ok / (n_ok + n_fail), 2),
            data={"n_docked": n_ok, "n_failed": n_fail}, artifacts=[str(scores)])
    return ok("M7_screen", f"{n_ok} ligands docked ({n_fail} failed)",
              data={"n_docked": n_ok, "n_failed": n_fail}, artifacts=[str(scores)])
