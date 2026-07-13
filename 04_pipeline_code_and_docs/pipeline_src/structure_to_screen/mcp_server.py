"""MCP server for the structure-to-screen pipeline.

Exposes exactly three tools — the minimal surface an agent needs:

    run_full_pipeline(target, modulator_smiles, modulator_name, modulator_mode, run_id)
        -> runs the pipeline; returns the RunManifest as structured JSON, including
           the per-module ok/low_confidence/unscreenable cascade and overall_status.

    check_status(run_id)
        -> returns the current/last manifest for a run without recomputing; an agent
           polls this to decide whether to trust, retry, or escalate.

    get_shortlist(run_id, top_n)
        -> returns the prioritized shortlist rows IF the run reached M8, else an
           explicit {"available": false, "reason": ...} tied to where the run stopped.

Design intent: an agent never parses prose. Every return carries a `status` field
it can branch on. `run_full_pipeline` on a structure-free / no-homolog target returns
overall_status="unscreenable" with the reason — not an exception.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import PipelineConfig
from .orchestrator import run_pipeline

mcp = FastMCP("structure-to-screen")

# Where runs live. Each run_id is a subdirectory holding the manifest + module outputs.
RUNS_ROOT = Path("s2s_runs")


def _run_dir(run_id: str) -> Path:
    return RUNS_ROOT / run_id


def _load_manifest(run_id: str) -> dict[str, Any] | None:
    p = _run_dir(run_id) / "run_manifest.json"
    return json.loads(p.read_text()) if p.exists() else None


@mcp.tool()
def run_full_pipeline(target: str, modulator_smiles: str,
                      modulator_name: str = "modulator",
                      modulator_mode: str = "unknown",
                      run_id: str | None = None) -> dict[str, Any]:
    """Run the full structure-to-screen pipeline for a target + known modulator.

    Args:
        target: UniProt accession, e.g. "O14841".
        modulator_smiles: SMILES of the known modulator (the validation anchor).
        modulator_name: human label for the modulator.
        modulator_mode: "activator" | "inhibitor" | "unknown" — recorded as provenance only;
            the pipeline is modulator-agnostic and does not branch on this value.
        run_id: optional identifier; defaults to "<target>_<modulator_name>".

    Returns:
        The run manifest as JSON: overall_status (ok|low_confidence|unscreenable),
        reached_module, and the per-module result cascade. On a structure-free or
        no-homolog target this returns overall_status="unscreenable" with a reason —
        it does not raise.
    """
    rid = run_id or f"{target}_{modulator_name}"
    cfg = PipelineConfig(target=target, modulator_smiles=modulator_smiles,
                         modulator_name=modulator_name, modulator_mode=modulator_mode,
                         workdir=str(_run_dir(rid)))
    man = run_pipeline(cfg, verbose=False)
    return {"run_id": rid, **man.to_dict()}


@mcp.tool()
def check_status(run_id: str) -> dict[str, Any]:
    """Return the current status of a run without recomputing.

    Returns the manifest (overall_status, reached_module, per-module cascade) if the
    run exists, else {"found": false}. Use this to poll a run and decide whether to
    trust the result, retry, or escalate.
    """
    man = _load_manifest(run_id)
    if man is None:
        return {"found": False, "run_id": run_id,
                "reason": f"no run named '{run_id}' — call run_full_pipeline first"}
    per_module = [{"module": r["module"], "status": r["status"],
                   "confidence": r.get("confidence"), "reason": r["reason"]}
                  for r in man["results"]]
    return {"found": True, "run_id": run_id,
            "overall_status": man["overall_status"],
            "reached_module": man["reached_module"],
            "modules": per_module}


@mcp.tool()
def get_shortlist(run_id: str, top_n: int = 15) -> dict[str, Any]:
    """Return the prioritized shortlist for a completed run.

    If the run did not reach prioritization (M8) — e.g. it was unscreenable at the
    site-definition step — returns {"available": false, "reason": ...} tied to where
    the run stopped, so the agent knows why there is no shortlist rather than seeing
    an empty list.
    """
    man = _load_manifest(run_id)
    if man is None:
        return {"available": False, "run_id": run_id,
                "reason": f"no run named '{run_id}'"}
    m8 = next((r for r in man["results"] if r["module"] == "M8_prioritize"), None)
    if m8 is None:
        return {"available": False, "run_id": run_id,
                "overall_status": man["overall_status"],
                "reached_module": man["reached_module"],
                "reason": f"run stopped at {man['reached_module']} before prioritization; "
                          f"overall status {man['overall_status']}"}
    shortlist_csv = _run_dir(run_id) / "m8" / "shortlist.csv"
    rows = []
    if shortlist_csv.exists():
        with open(shortlist_csv) as fh:
            rows = list(csv.DictReader(fh))[:top_n]
    return {"available": True, "run_id": run_id,
            "status": m8["status"],  # ok or low_confidence (comparative-within-box)
            "interpretation": m8.get("data", {}).get("interpretation"),
            "n_beat_anchor": m8.get("data", {}).get("n_beat_anchor"),
            "note": m8["reason"],
            "shortlist": rows}


def main():
    mcp.run()


if __name__ == "__main__":
    main()
