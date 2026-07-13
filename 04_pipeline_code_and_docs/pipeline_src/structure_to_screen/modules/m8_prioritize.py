"""M8 — Prioritization: consensus rank -> scaffold-diverse shortlist.

The final result inherits the *weakest* upstream confidence: if M5 was
low_confidence (shifted anchor pose), the shortlist is emitted but explicitly
labelled comparative-within-box rather than affinity-ranked.
"""
from __future__ import annotations
import json
from ..config import PipelineConfig
from ..status import ModuleResult, ok, low_confidence, unscreenable


def _flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def run(cfg: PipelineConfig, scores_csv: str, library_csv: str,
        upstream_low_confidence: bool = False, anchor_kcal: float | None = None) -> ModuleResult:
    shortlist = cfg.path("m8", "shortlist.csv")
    if shortlist.exists():
        import csv as _csv
        rows = list(_csv.DictReader(open(shortlist)))
        n = len(rows)
        n_beat = None
        if anchor_kcal is not None:
            n_beat = sum(1 for r in rows
                         if _flt(r.get("affinity_kcal_mol")) is not None
                         and _flt(r["affinity_kcal_mol"]) < anchor_kcal)
        interp = "comparative-within-box" if upstream_low_confidence else "site-validated"
        st = low_confidence if upstream_low_confidence else ok
        return st("M8_prioritize", f"cached shortlist ({n} compounds)"
                  + (" — comparative-within-box (see M5)" if upstream_low_confidence else ""),
                  data={"shortlist_n": n, "n_beat_anchor": n_beat, "interpretation": interp},
                  artifacts=[str(shortlist)])

    from .._prioritize import prioritize
    n, n_beat_anchor, top = prioritize(cfg, scores_csv, library_csv, shortlist, anchor_kcal)
    if n == 0:
        return unscreenable("M8_prioritize", "no compounds to prioritize")
    data = {"shortlist_n": n, "n_beat_anchor": n_beat_anchor, "top": top,
            "interpretation": "comparative-within-box" if upstream_low_confidence else "site-validated"}
    msg = f"{n}-compound shortlist; {n_beat_anchor} beat the anchor"
    if upstream_low_confidence:
        return low_confidence("M8_prioritize", msg + " (comparative-within-box; anchor pose was shifted, see M5)",
                              data=data, artifacts=[str(shortlist)])
    return ok("M8_prioritize", msg, data=data, artifacts=[str(shortlist)])
