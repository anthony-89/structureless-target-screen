"""Command-line entry point.

    python -m structure_to_screen --target O14841 \
        --modulator "Nc1ncnc2c1ncn2[C@@H]1O[C@H](COP(=O)([O-])[O-])[C@@H](O)[C@H]1O" \
        --modulator-name 5-AMP --modulator-mode activator --workdir s2s_run/oplah
"""
from __future__ import annotations
import argparse
import sys
from .config import PipelineConfig
from .orchestrator import run_pipeline


def main(argv=None):
    p = argparse.ArgumentParser(prog="structure_to_screen",
        description="Structure-to-screen pipeline for structure-free targets with a known modulator.")
    p.add_argument("--target", required=True, help="UniProt accession, e.g. O14841")
    p.add_argument("--modulator", required=True, help="Modulator SMILES (the validation anchor)")
    p.add_argument("--modulator-name", default="modulator")
    p.add_argument("--modulator-mode", default="unknown",
                   choices=["activator", "inhibitor", "unknown"],
                   help="Pharmacology of the known modulator (activator = the enhancer niche)")
    p.add_argument("--workdir", default="s2s_run")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    cfg = PipelineConfig(target=args.target, modulator_smiles=args.modulator,
                         modulator_name=args.modulator_name, modulator_mode=args.modulator_mode,
                         workdir=args.workdir)
    man = run_pipeline(cfg, verbose=not args.quiet)
    # exit code encodes overall status for shell/agent callers
    return {"ok": 0, "low_confidence": 0, "unscreenable": 2}[man.overall_status.value]


if __name__ == "__main__":
    sys.exit(main())
