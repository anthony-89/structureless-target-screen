"""M5 — Reference-ligand validation: dock the KNOWN modulator as an anchor.

The pipeline must place the known modulator sensibly before novel hits are
trusted. We report a calibrated `pose_trust` rather than a binary pass/fail:

  - anchor recovers the reference position well        -> ok
  - anchor engages the pocket but is spatially shifted -> low_confidence
    (this is the honest OPLAH/5-AMP outcome: right pocket, ~10 A off the
     transplanted nucleotide on a rigid apo model)
  - anchor does not dock in the site at all            -> unscreenable
"""
from __future__ import annotations
import json
from ..config import PipelineConfig
from ..status import ModuleResult, ok, low_confidence, unscreenable


def run(cfg: PipelineConfig, receptor_pdbqt: str, site: dict) -> ModuleResult:
    val_path = cfg.path("m5", "validation.json")
    if val_path.exists():
        v = json.loads(val_path.read_text())
        return _classify(v, cfg, cached=True)

    from .._dock import dock_reference
    v = dock_reference(cfg, receptor_pdbqt, site)   # returns dict with metrics
    val_path.write_text(json.dumps(v, indent=2))
    return _classify(v, cfg, cached=False)


def _classify(v, cfg, cached):
    tag = "cached: " if cached else ""
    aff = v.get("top_affinity_kcal_mol")
    overlap = v.get("pose_overlap_frac_within_3A", 0.0)
    jacc = v.get("max_contact_jaccard", 0.0)
    # geometric agreement of the free-box top pose with the reference
    geom = 0.5 * min(overlap / max(cfg.pose_overlap_ok, 1e-6), 1.0) + 0.5 * min(jacc / 0.5, 1.0)
    # If a box-contraction diagnostic ran, fold its recoverability into the trust
    # score: a shifted top pose is more trustworthy if the ligand CAN reach the
    # reference at reasonable cost (search artifact) than if it clashes there
    # (induced-fit limit). See docs / m5_diagnostic.json.
    recover = v.get("recoverability_score")
    if recover is not None:
        trust = round(0.5 * geom + 0.5 * recover, 2)
    else:
        trust = round(geom, 2)
    data = {**v, "pose_trust": trust, "screen_benchmark_kcal_mol": aff}
    if aff is None:
        return unscreenable("M5_validate", f"{tag}reference modulator did not dock into the site")
    if overlap < 1e-6 and jacc < cfg.pose_contact_jaccard_low:
        return unscreenable("M5_validate",
            f"{tag}anchor dock does not engage the site (overlap 0, Jaccard {jacc:.2f})", data=data)
    if overlap < cfg.pose_overlap_ok:
        return low_confidence("M5_validate",
            f"{tag}anchor engages pocket (Jaccard {jacc:.2f}) but is spatially shifted "
            f"(overlap {overlap:.2f}); pose_trust {trust:.2f}. Scores are comparative-within-box.",
            confidence=trust, data=data, metrics=data, artifacts=[str(cfg.path('m5','validation.json'))])
    return ok("M5_validate",
              f"{tag}anchor recovers reference pose (overlap {overlap:.2f}, Jaccard {jacc:.2f}), pose_trust {trust:.2f}",
              confidence=trust, data=data, metrics=data, artifacts=[str(cfg.path('m5','validation.json'))])
