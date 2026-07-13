"""Graceful-degradation test: prove the pipeline reports a reasoned, machine-readable
`unscreenable` state (not a crash, not a silent fallback) when the site cannot be
localized — and that the MCP tools surface that state to an agent.

Run:  PYTHONPATH=. python examples/test_degradation.py
"""
import json
import shutil
from pathlib import Path

from structure_to_screen.config import PipelineConfig
from structure_to_screen.orchestrator import run_pipeline
from structure_to_screen.modules import m4_site
from structure_to_screen.status import Status
from structure_to_screen import mcp_server


def _seed_upstream(cfg, ref="examples/oplah_run"):
    """Give the run valid M1/M2/M3 so it reaches M4, where degradation happens."""
    for sub, files in [("m1", ["O14841.fasta", "O14841_af.cif", "intake.json"]),
                       ("m2", ["qc.json"]),
                       ("m3", ["receptor.pdb", "receptor.pdbqt"])]:
        for f in files:
            src = Path(ref) / sub / f
            if src.exists():
                shutil.copy(src, cfg.path(sub, f))


def run_no_homolog_unscreenable():
    # Simulate an orphan target: no liganded homolog in the PDB.
    orig = m4_site._search_liganded_homologs
    m4_site._search_liganded_homologs = lambda cfg, rec: []
    try:
        cfg = PipelineConfig(target="O14841", modulator_smiles="x",
                             modulator_name="orphan", workdir="s2s_runs/degradation_test")
        # remove any cached site so the live (empty) search runs
        site = cfg.path("m4", "binding_site.json")
        if site.exists():
            site.unlink()
        _seed_upstream(cfg)
        man = run_pipeline(cfg, verbose=False)

        assert man.overall_status is Status.UNSCREENABLE, man.overall_status
        m4 = next(r for r in man.results if r.module == "M4_site")
        assert m4.status is Status.UNSCREENABLE
        assert m4.data["pocket_source"] == "none_found"
        assert "next_actions" in m4.data
        # pipeline must NOT have run M5+ after an unscreenable M4
        modules_run = [r.module for r in man.results]
        assert "M5_validate" not in modules_run, modules_run

        # MCP get_shortlist must explain WHY there's no shortlist, not return []
        g = mcp_server.get_shortlist("degradation_test")
        assert g["available"] is False
        assert "M4_site" in g["reason"]
        print("PASS: no-homolog -> unscreenable, short-circuit, reasoned MCP response")
        print("  overall_status :", man.overall_status.value)
        print("  reached_module :", man.last.module)
        print("  M4 pocket_source:", m4.data["pocket_source"])
        print("  get_shortlist   :", json.dumps({k: g[k] for k in ("available", "reason")}))
        return man
    finally:
        m4_site._search_liganded_homologs = orig


if __name__ == "__main__":
    run_no_homolog_unscreenable()
