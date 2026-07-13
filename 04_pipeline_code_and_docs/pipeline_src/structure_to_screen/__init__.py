"""
structure_to_screen — agent-callable structure-to-screen pipeline.

From a protein target with NO experimental 3D structure and ONE known small-
molecule modulator, orchestrate public tools (UniProt, AlphaFold DB, RCSB PDB,
ChEMBL, AutoDock Vina) into a prioritized virtual-screen shortlist — with a
machine-readable ok / low_confidence / unscreenable status on every module so
an agent can reason about whether to trust each stage.
"""
from .config import PipelineConfig
from .status import Status, ModuleResult, RunManifest, ok, low_confidence, unscreenable
from .orchestrator import run_pipeline

__version__ = "0.1.0"
__all__ = ["PipelineConfig", "Status", "ModuleResult", "RunManifest",
           "ok", "low_confidence", "unscreenable", "run_pipeline"]
