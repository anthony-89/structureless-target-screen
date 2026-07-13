"""M4 — Binding-site definition by an ENSEMBLE of site proposers, adjudicated by the modulator.

The pipeline's distinguishing idea is that we have a *known modulator*, so we do not
have to trust any single site-finder. M4 runs several independent proposers and lets
the modulator's own docking decide which proposed pocket is real:

  proposers (each pluggable; any may return nothing):
    * homolog   — liganded-homolog transplant (the original method). Search the PDB for
                  a homolog crystallised WITH a ligand of the modulator's chemotype,
                  superpose, transplant the ligand centroid to localise the pocket.
    * fpocket   — ligand-free geometric cavity detection, ranked by DRUGGABILITY.
    * diffdock  — blind DiffDock dock of the modulator; its top pose localises the site.

  adjudication — dock the modulator into each candidate box and keep the one it engages
  best (contact-Jaccard + affinity + cross-method consensus). Runner-up sites are
  reported with a viable/rejected flag, never silently dropped.

Graceful degradation (the agent-facing contract):
  - modulator engages a candidate well, ≥2 methods agree  -> ok
  - modulator engages, but weakly / only one method        -> low_confidence  (+caveat)
  - no proposer yields a box the modulator binds in        -> unscreenable
                                                              {"pocket_source":"none_found", ...}

This is an *open* ensemble, not a silent fallback: every proposer that ran, and every
runner-up, is recorded in binding_site.json. The output stays backward-compatible —
box_center / box_size / site_residues are exactly what M5 and M7 already read.

Which proposers run is controlled by cfg.site_proposers (default: all three). A proposer
whose tool is unavailable (no fpocket binary, no DiffDock poses) simply contributes
nothing and is listed under `proposers_failed`, so on a homolog-only machine M4 reduces
to the original single-method behaviour — now validated by the modulator's own dock.
"""
from __future__ import annotations
import json
from ..config import PipelineConfig
from ..status import ModuleResult, ok, low_confidence, unscreenable
from .. import _site_ensemble as ens


def run(cfg: PipelineConfig, receptor_pdb: str) -> ModuleResult:
    site_path = cfg.path("m4", "binding_site.json")

    # resumable: reuse a previously-defined site (unchanged contract)
    if site_path.exists():
        site = json.loads(site_path.read_text())
        st = site.get("status", "ok")
        src = site.get("pocket_source", site.get("method", "?"))
        msg = f"cached site: {site.get('method','?')} via {src}"
        if st == "ok":
            return ok("M4_site", msg, confidence=site.get("confidence"),
                      data=site, artifacts=[str(site_path)])
        if st == "low_confidence":
            return low_confidence("M4_site", msg, confidence=site.get("confidence"),
                                  data=site, artifacts=[str(site_path)])
        return unscreenable("M4_site", site.get("reason", "no pocket"), data=site)

    # --- live path: run the enabled proposers, let the modulator adjudicate ---
    proposers = _assemble_proposers(cfg)
    result = ens.select_site(cfg, receptor_pdb, proposers)
    proposals = result["proposals"]

    if not proposals or result["winner"] is None:
        return _unscreenable_no_site(cfg, site_path, result)

    winner = result["winner"]
    runners = [p for p in proposals if p is not winner]
    site = {
        "method": "modulator_selected_ensemble",
        "pocket_source": winner.source,
        "box_center": winner.box_center,
        "box_size": winner.box_size or [cfg.box_size] * 3,
        "site_residues": winner.site_residues,
        "confidence": winner.composite,
        "selection": {
            "modulator_affinity_kcal_mol": winner.modulator_affinity_kcal_mol,
            "modulator_coverage": winner.modulator_coverage,
            "modulator_contact_jaccard": winner.modulator_contact_jaccard,
            "consensus_n_methods_agreeing": winner.consensus_n,
            "composite_score": winner.composite,
            "method_conf": winner.method_conf,
            "meta": winner.meta,
        },
        "runner_up_sites": [p.summary() for p in runners],
        "proposers_run": result["proposers_run"],
        "proposers_failed": result["proposers_failed"],
    }

    cov = winner.modulator_coverage or 0.0
    aff = winner.modulator_affinity_kcal_mol
    strong = cov >= cfg.site_select_coverage_ok and aff is not None and aff <= cfg.site_select_affinity_ok
    consensus = winner.consensus_n >= 1
    detail = (f"modulator binds {winner.source} box (affinity {aff:.2f} kcal/mol, "
              f"coverage {cov:.2f}, {winner.consensus_n} other method(s) agree)")

    if strong and consensus:
        site["status"] = "ok"
        site_path.write_text(json.dumps(site, indent=2))
        return ok("M4_site", f"{detail}; site validated by ensemble consensus",
                  confidence=winner.composite, data=site, artifacts=[str(site_path)])

    site["status"] = "low_confidence"
    why = ("only one method localised it" if not consensus else "modulator engages but weakly")
    site_path.write_text(json.dumps(site, indent=2))
    return low_confidence("M4_site", f"{detail}; {why} — site defined with caveat",
                          confidence=winner.composite, data=site, artifacts=[str(site_path)])


def _unscreenable_no_site(cfg, site_path, result) -> ModuleResult:
    """No proposer produced a box the modulator engages. Honest, explicit failure."""
    any_candidate = bool(result["proposals"])
    payload = {
        "status": "unscreenable",
        "pocket_source": "none_found",
        "confidence": "unscreenable",
        "proposers_run": result["proposers_run"],
        "proposers_failed": result["proposers_failed"],
        "runner_up_sites": [p.summary() for p in result["proposals"]],
        "identity_cutoff": cfg.homolog_identity_cutoff,
        "next_actions": ["blind_docking_diffdock_l", "cavity_detection_p2rank",
                         "manual_site_from_literature", "cofold_holo_boltz2"],
        "reason": ("candidate pockets were proposed but the modulator engaged none of them"
                   if any_candidate else
                   "no site proposer produced a candidate pocket (no liganded homolog, "
                   "no fpocket cavity, no DiffDock pose)"),
    }
    site_path.write_text(json.dumps(payload, indent=2))
    return unscreenable("M4_site", payload["reason"], data=payload, artifacts=[str(site_path)])


# --------------------------------------------------------------------------- proposer wiring
def _assemble_proposers(cfg):
    """Build the ordered proposer list from cfg.site_proposers.

    The homolog proposer lives here (not in _site_ensemble) so its RCSB seams
    `_search_liganded_homologs` / `_transplant_and_box` remain module-level and
    monkeypatchable by tests.
    """
    registry = {
        "homolog": _homolog_propose,
        "fpocket": ens.fpocket_propose,
        "diffdock": ens.diffdock_propose,
    }
    return [registry[name] for name in cfg.site_proposers if name in registry]


def _homolog_propose(cfg, receptor_pdb):
    """Liganded-homolog transplant as an ensemble proposer. Returns [] or [SiteProposal]."""
    hits = _search_liganded_homologs(cfg, receptor_pdb)
    if not hits:
        return []
    try:
        best, rmsd, center, residues = _transplant_and_box(cfg, receptor_pdb, hits)
    except Exception:
        return []
    if rmsd > cfg.site_rmsd_low:
        return []  # fold too far to trust this homolog's frame
    # RMSD-based internal confidence, matching the original module's scaling
    conf = max(0.0, min(1.0, (cfg.site_rmsd_low - rmsd) / (cfg.site_rmsd_low - cfg.site_rmsd_ok)))
    return [ens.SiteProposal(
        source="homolog_transplant",
        box_center=center,
        site_residues=residues,
        method_conf=round(conf, 2),
        meta={"homolog": best["pdb_id"], "homolog_identity": best.get("identity"),
              "homolog_ligand": best.get("ligand"), "superposition_rmsd_A": round(rmsd, 2)})]


_homolog_propose.proposer_name = "homolog"


# --- RCSB seams (kept importable at module level for monkeypatching in tests) ---
def _search_liganded_homologs(cfg, receptor_pdb):
    from .._homolog import search_liganded_homologs
    return search_liganded_homologs(cfg, receptor_pdb)


def _transplant_and_box(cfg, receptor_pdb, hits):
    from .._homolog import transplant_and_box
    return transplant_and_box(cfg, receptor_pdb, hits)
