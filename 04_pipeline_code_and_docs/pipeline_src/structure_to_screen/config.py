"""Run configuration for the structure-to-screen pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PipelineConfig:
    # --- required inputs ---
    target: str                 # UniProt accession, e.g. "O14841"
    modulator_smiles: str       # SMILES of the known modulator (the validation anchor)
    modulator_name: str = "modulator"

    # --- modulator pharmacology (the enhancer/activator angle) ---
    # 'activator' | 'inhibitor' | 'unknown' — recorded, surfaced in the report,
    # and reserved for the post-hackathon activator-aware scoring mode.
    modulator_mode: str = "unknown"

    # --- workspace ---
    workdir: Path = field(default_factory=lambda: Path("s2s_run"))

    # --- module thresholds (drive the ok / low_confidence / unscreenable calls) ---
    min_mean_plddt: float = 70.0          # M2: below -> low_confidence structure
    homolog_identity_cutoff: float = 0.25 # M4: RCSB search identity floor
    homolog_evalue_cutoff: float = 1.0    # M4: RCSB search e-value ceiling
    site_rmsd_ok: float = 2.5             # M4: superposition RMSD (A) for 'ok'
    site_rmsd_low: float = 4.0            # M4: above this -> unscreenable

    # --- M4 ensemble site selection (modulator adjudicates between proposers) ---
    # Which site proposers to run, in order. A proposer whose tool is unavailable
    # contributes nothing (listed under proposers_failed) rather than failing the run.
    site_proposers: tuple[str, ...] = ("homolog", "fpocket", "diffdock")
    fpocket_bin: str = "fpocket"          # fpocket binary on PATH
    fpocket_top_k: int = 3                # keep the top-K pockets by DRUGGABILITY
    # DiffDock proposer. By default M4 only *reads* a completed blind dock (a ~1 h CPU job
    # is a poor fit for an inline module). Point diffdock_poses_dir at rankN_confidence*.sdf,
    # OR set diffdock_run=True + diffdock_repo to let M4 launch DiffDock itself, cache the
    # poses under m4/diffdock/<complex>/, and reuse them on resume.
    diffdock_poses_dir: str | None = None # explicit dir of a completed blind dock
    diffdock_run: bool = False            # opt in to launching DiffDock from M4
    diffdock_repo: str | None = None      # path to a DiffDock checkout (has inference.py)
    diffdock_python: str | None = None    # python for that env (default: current interpreter)
    diffdock_samples: int = 40            # samples_per_complex for the blind dock
    consensus_radius_A: float = 8.0       # two proposers "agree" if centers within this
    site_select_coverage_ok: float = 0.6  # winner engages 'well' if this frac of modulator contacts are in-pocket
    site_select_affinity_ok: float = -6.0 # ...and at least this modulator affinity (kcal/mol)
    # M5: reference-pose recovery. Fraction of anchor atoms within tol of the
    # transplanted reference; below low -> low_confidence pose (not a hard fail).
    pose_overlap_ok: float = 0.30
    pose_contact_jaccard_low: float = 0.20

    # --- docking box / screen params ---
    box_size: float = 22.0
    exhaustiveness: int = 12
    num_modes: int = 5
    seed: int = 42

    # --- library ---
    library_similarity: tuple[int, ...] = (70, 80)
    library_max: int = 80

    def __post_init__(self):
        self.workdir = Path(self.workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)

    def path(self, *parts) -> Path:
        p = self.workdir.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
