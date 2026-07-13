#!/usr/bin/env python
"""structure-to-screen demo — the 90-second judge walkthrough.

Runs BOTH stories back-to-back, driving the exact functions the MCP tools expose:

  1. OPLAH / 5-AMP  -> a prioritized shortlist, flagged `low_confidence`
                       (comparative-within-box; the anchor pose is induced-fit limited).
  2. c-Myc / 10058-F4 -> graceful `unscreenable`: a liganded homolog exists but cannot
                       be trusted (39.5 A superposition), so NO shortlist is fabricated.

Both runs are cache-first and read from examples/, so the demo is offline and fast.
It exercises the SAME code path as the live pipeline — the cached module outputs were
produced by that path on OPLAH (and by a live run on c-Myc through M4).

    PYTHONPATH=. python examples/demo.py
"""
from __future__ import annotations
import sys
from pathlib import Path

from structure_to_screen import mcp_server
from structure_to_screen.mcp_server import run_full_pipeline, check_status, get_shortlist

BAR = "=" * 72
HERE = Path(__file__).resolve().parent


def _seed_cache():
    """Stage the shipped cached runs where the MCP tools look (offline demo).

    The tools resolve runs under mcp_server.RUNS_ROOT; point that at a scratch dir
    and copy the reference example runs in, so the demo needs no network.
    """
    import shutil, tempfile
    root = Path(tempfile.mkdtemp(prefix="s2s_demo_"))
    mcp_server.RUNS_ROOT = root
    shutil.copytree(HERE / "oplah_run", root / "oplah_5amp")
    shutil.copytree(HERE / "myc_run", root / "myc")
    return root


def _banner(title):
    print(f"\n{BAR}\n  {title}\n{BAR}")


def _show_run(man):
    print(f"  overall_status : {man['overall_status'].upper()}   (reached {man['reached_module']})")
    for r in man["results"]:
        conf = f" conf={r['confidence']:.2f}" if r.get("confidence") is not None else ""
        print(f"    {r['module']:14s} {r['status']:15s}{conf}  {r['reason'][:66]}")


def demo_oplah():
    _banner("TARGET 1 — OPLAH (O14841) + 5-AMP  [the enhancer niche]")
    print("  Structure-free workflow: AlphaFold model -> liganded-homolog pocket ->")
    print("  validate the known modulator -> screen -> prioritize.\n")
    man = run_full_pipeline(
        target="O14841",
        modulator_smiles="Nc1ncnc2c1ncn2[C@@H]1O[C@H](COP(=O)([O-])[O-])[C@@H](O)[C@H]1O",
        modulator_name="5-AMP", modulator_mode="activator", run_id="oplah_5amp")
    _show_run(man)

    print("\n  agent calls get_shortlist('oplah_5amp', top_n=5):")
    g = get_shortlist("oplah_5amp", top_n=5)
    print(f"    available={g['available']}  status={g['status']}  "
          f"interpretation={g['interpretation']!r}")
    print(f"    {g['n_beat_anchor']} compounds beat the 5-AMP anchor (comparative-within-box)")
    print(f"    {'lig':7s}{'affinity':>10s}{'LE':>8s}   name")
    for r in g["shortlist"]:
        print(f"    {r['lig_id']:7s}{r['affinity_kcal_mol']:>10s}{r['ligand_efficiency']:>8s}"
              f"   {r.get('pref_name') or r.get('chembl_id','')}")
    print("\n  --> Delivered a ranked shortlist, HONESTLY labeled: the scores rank")
    print("      compounds within the box; the anchor pose is induced-fit limited")
    print("      (pose_trust 0.59), so this is a hypothesis generator, not a verdict.")


def demo_myc():
    _banner("TARGET 2 — c-Myc (P01106) + 10058-F4  [deliberate stress test]")
    print("  Intrinsically disordered 'undruggable' oncoprotein. We EXPECT this to fail —")
    print("  the point is that it fails HONESTLY and says why.\n")
    # cached: the live run through M4 was produced earlier; reuse it.
    man = check_status("myc")
    if not man.get("found"):
        # fall back to running (needs network for M1/M4); cached example is preferred
        man = run_full_pipeline(
            target="P01106", modulator_smiles=r"CC1=CC(=CC=C1)/C=C2\SC(=S)N(C2=O)CC=C",
            modulator_name="10058-F4", modulator_mode="inhibitor", run_id="myc")
        _show_run(man)
        reached = man["reached_module"]
    else:
        print(f"  overall_status : {man['overall_status'].upper()}   (reached {man['reached_module']})")
        for r in man["modules"]:
            conf = f" conf={r['confidence']:.2f}" if r.get("confidence") is not None else ""
            print(f"    {r['module']:14s} {r['status']:15s}{conf}  {r['reason'][:66]}")
        reached = man["reached_module"]

    print("\n  agent calls get_shortlist('myc'):")
    g = get_shortlist("myc")
    print(f"    available={g['available']}")
    print(f"    reason: {g['reason']}")
    print("\n  --> NO shortlist fabricated. The tool found a liganded homolog (8OTS) but")
    print("      refused to trust a 39.5 A superposition, and returned next_actions")
    print("      (blind docking / domain restriction) for the agent to try instead.")


def main():
    _seed_cache()
    print("\n" + "#" * 72)
    print("#  structure-to-screen — agent-callable pipeline for structure-free targets")
    print("#  with a known modulator.  Two targets, two honest outcomes.")
    print("#" * 72)
    demo_oplah()
    demo_myc()
    _banner("THE POINT")
    print("  Same pipeline, same status contract, two very different targets:")
    print("    * a shortlist you can trust to be honestly caveated, and")
    print("    * a refusal you can trust to be correct.")
    print("  Every module returns ok / low_confidence / unscreenable — an agent branches")
    print("  on the status, never on prose. That is what makes it callable.\n")


if __name__ == "__main__":
    sys.exit(main())
