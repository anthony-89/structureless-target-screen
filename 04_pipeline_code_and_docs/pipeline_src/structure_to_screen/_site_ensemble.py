"""Ensemble site selection for M4 — the modulator picks which proposed site is real.

The original M4 defines one site by liganded-homolog transplant. This backend adds
two *independent* site proposers and lets the known modulator adjudicate between them:

  proposers (pluggable, each returns [] on any failure — never raises):
    * homolog   — liganded-homolog transplant (the existing method; owned by m4_site
                  so its RCSB seams stay monkeypatchable)
    * fpocket   — ligand-free geometric cavity detection, ranked by DRUGGABILITY
                  (fpocket's default `Score` buries real sites; see docs/FAILURE_MODES)
    * diffdock  — blind dock of the modulator; top-confidence pose localises the site

  selection: dock the known modulator into a uniform probe box centred on each
  candidate and score how well it engages —
     composite = 0.45*contact_jaccard + 0.35*affinity + 0.20*cross-method consensus
  The best-engaged candidate wins; the rest are returned as runner-ups with a
  viable/rejected flag rather than discarded. If the modulator engages no candidate,
  the site is `unscreenable` — an honest failure grounded in the modulator's own
  binding, not merely in homolog availability.

Design notes
  * Selection uses a UNIFORM probe box (cfg.box_size) on every candidate so affinity
    and Jaccard are compared on equal footing; fpocket/DiffDock contribute a *location*,
    not a box size.
  * Heavy deps (RDKit/Meeko/Vina, the fpocket binary, a DiffDock install) are only
    touched on the cold-start path and only for the proposers actually enabled.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Callable

import numpy as np

# affinity (kcal/mol) normalisation window: -4 -> 0.0 (barely bound), -12 -> 1.0 (strong)
_AFF_WEAK, _AFF_STRONG = -4.0, -12.0
CONTACT_CUTOFF_A = 4.5
# a candidate counts as "engaged" only if this fraction of the modulator's docked
# contacts fall inside the proposer's predicted residues (size-robust vs Jaccard).
_COVERAGE_FLOOR = 0.30


@dataclass
class SiteProposal:
    """One candidate binding site from a single proposer."""
    source: str                                   # "homolog_transplant" | "fpocket" | "diffdock"
    box_center: list[float]
    site_residues: list = field(default_factory=list)   # residue numbers (int) or "D13" codes
    method_conf: float = 0.0                      # proposer-internal confidence in [0,1]
    meta: dict = field(default_factory=dict)      # proposer-specific detail (rmsd, druggability, ...)
    # filled in during selection:
    box_size: list[float] | None = None
    modulator_affinity_kcal_mol: float | None = None
    modulator_coverage: float | None = None       # frac of modulator contacts inside proposer set (size-robust)
    modulator_contact_jaccard: float | None = None  # symmetric overlap (reported; size-biased for big pockets)
    consensus_n: int = 0                          # other proposers agreeing on this location
    composite: float | None = None

    @property
    def engaged(self) -> bool:
        return (self.modulator_affinity_kcal_mol is not None
                and (self.modulator_coverage or 0.0) >= _COVERAGE_FLOOR)

    def summary(self) -> dict:
        d = asdict(self)
        d["engaged"] = self.engaged
        d["confidence_flag"] = "viable" if self.engaged else "rejected"
        return d


# --------------------------------------------------------------------------- fpocket
def fpocket_propose(cfg, receptor_pdb) -> list[SiteProposal]:
    """Run fpocket and return the top-K pockets ranked by DRUGGABILITY score.

    fpocket needs a .pdb (not .pdbqt); we use the sibling receptor.pdb if present,
    else strip the pdbqt down to a minimal PDB. Returns [] if the binary is missing
    or writes nothing (the historical silent-failure mode).
    """
    pdb = _ensure_pdb(cfg, receptor_pdb)
    if pdb is None:
        return []
    binary = getattr(cfg, "fpocket_bin", "fpocket")
    workdir = cfg.path("m4", "fpocket")
    workdir.mkdir(parents=True, exist_ok=True)
    stem = os.path.splitext(os.path.basename(pdb))[0]
    local_pdb = str(workdir / f"{stem}.pdb")
    if os.path.abspath(local_pdb) != os.path.abspath(pdb):
        try:
            with open(pdb) as src, open(local_pdb, "w") as dst:
                dst.write(src.read())
        except OSError:
            return []
    out_dir = os.path.join(os.path.dirname(local_pdb), f"{stem}_out")
    info = os.path.join(out_dir, f"{stem}_info.txt")
    if not os.path.exists(info):
        try:
            subprocess.run([binary, "-f", local_pdb],
                           capture_output=True, text=True, timeout=900)
        except (OSError, subprocess.SubprocessError):
            return []
    if not os.path.exists(info):
        return []
    return _fpocket_top_pockets(out_dir, stem, top_k=getattr(cfg, "fpocket_top_k", 3))


def _fpocket_top_pockets(out_dir, stem, top_k) -> list[SiteProposal]:
    info = os.path.join(out_dir, f"{stem}_info.txt")
    pockets, cur = {}, None
    for line in open(info):
        m = re.match(r"Pocket (\d+)", line)
        if m:
            cur = int(m.group(1)); pockets[cur] = {}
            continue
        m = re.match(r"\t(.+?) :\s*\t?(-?[\d.]+)", line)
        if m and cur:
            pockets[cur][m.group(1).strip()] = float(m.group(2))
    props = []
    drug_vals = [p.get("Druggability Score", 0.0) for p in pockets.values()] or [1.0]
    dmax = max(drug_vals) or 1.0
    ranked = sorted(pockets, key=lambda i: -pockets[i].get("Druggability Score", 0.0))
    for pid in ranked[:top_k]:
        vert = os.path.join(out_dir, "pockets", f"pocket{pid}_vert.pqr")
        atm = os.path.join(out_dir, "pockets", f"pocket{pid}_atm.pdb")
        center = _centroid(vert)
        if center is None:
            continue
        drug = pockets[pid].get("Druggability Score", 0.0)
        props.append(SiteProposal(
            source="fpocket",
            box_center=[round(float(x), 2) for x in center],
            site_residues=sorted(_residues(atm)),
            method_conf=round(float(drug), 3),          # already ~[0,1]
            meta={"pocket_rank_by_druggability": ranked.index(pid) + 1,
                  "druggability": round(drug, 3),
                  "fpocket_score": round(pockets[pid].get("Score", 0.0), 3),
                  "volume_A3": round(pockets[pid].get("Volume", 0.0), 1),
                  "n_pockets_total": len(pockets)}))
    return props


# --------------------------------------------------------------------------- diffdock
def diffdock_propose(cfg, receptor_pdb) -> list[SiteProposal]:
    """Localise the site from a blind DiffDock dock of the modulator.

    Pose source, in order:
      1. an explicit `cfg.diffdock_poses_dir` (a completed run), else
      2. the canonical per-run cache `m4/diffdock/<complex>/`, else
      3. if `cfg.diffdock_run` and `cfg.diffdock_repo` are set, launch DiffDock into the
         cache (a ~1 h CPU job) and use the result.
    Returns [] if no poses are available and a live run is not enabled/possible — the
    proposer never blocks a run it was not told to, and never raises.
    """
    poses = _find_diffdock_poses(cfg, receptor_pdb)
    if not poses:
        return []
    top = poses[0]
    xyz = _sdf_heavy(top)
    if xyz is None or not len(xyz):
        return []
    center = xyz.mean(axis=0)
    prot, meta = _pdb_heavy(_ensure_pdb(cfg, receptor_pdb) or receptor_pdb)
    residues = sorted(_contact_residues(xyz, prot, meta)) if prot is not None else []
    conf = _confidence(top)
    # DiffDock confidence is a logit-like score; squash to [0,1] for method_conf.
    method_conf = 1.0 / (1.0 + np.exp(-conf)) if conf is not None else 0.0
    return [SiteProposal(
        source="diffdock",
        box_center=[round(float(x), 2) for x in center],
        site_residues=residues,
        method_conf=round(float(method_conf), 3),
        meta={"top_pose": os.path.basename(top),
              "diffdock_confidence": conf,
              "n_poses": len(poses)})]


def _diffdock_complex_name(cfg):
    return f"{cfg.target}_{cfg.modulator_name}_blind".replace(" ", "_").replace("/", "_")


def _find_diffdock_poses(cfg, receptor_pdb):
    """Return ranked pose paths from an explicit dir, the per-run cache, or a fresh run."""
    def _sorted(d):
        # accept poses directly in d or nested one level (DiffDock writes out/<complex>/)
        hits = (glob.glob(os.path.join(d, "rank*_confidence*.sdf"))
                or glob.glob(os.path.join(d, "*", "rank*_confidence*.sdf")))
        return sorted(hits, key=_rank)

    explicit = getattr(cfg, "diffdock_poses_dir", None)
    if explicit and os.path.isdir(explicit):
        got = _sorted(explicit)
        if got:
            return got

    cache = str(cfg.path("m4", "diffdock", _diffdock_complex_name(cfg)))
    got = _sorted(cache)
    if got:                                   # resumable: a prior run already produced poses
        return got

    if getattr(cfg, "diffdock_run", False) and getattr(cfg, "diffdock_repo", None):
        if _run_diffdock(cfg, receptor_pdb, cache):
            return _sorted(cache)
    return []


def _run_diffdock(cfg, receptor_pdb, out_dir):
    """Launch a blind DiffDock dock of the modulator into out_dir. Returns True on poses.

    Self-contained and defensive: builds batch.csv + a samples-patched blind.yaml inside
    out_dir, wires certifi's CA bundle (DiffDock downloads weights + ESM over HTTPS), and
    shells out to the repo's inference module. Any failure returns False so M4 degrades to
    the other proposers rather than raising.
    """
    repo = cfg.diffdock_repo
    inference = os.path.join(repo, "inference.py")
    default_yaml = os.path.join(repo, "default_inference_args.yaml")
    if not (os.path.isfile(inference) and os.path.isfile(default_yaml)):
        return False
    pdb = _ensure_pdb(cfg, receptor_pdb)
    if pdb is None:
        return False
    os.makedirs(out_dir, exist_ok=True)
    name = _diffdock_complex_name(cfg)
    staged_pdb = os.path.join(out_dir, "receptor.pdb")
    try:
        with open(pdb) as s, open(staged_pdb, "w") as d:
            d.write(s.read())
        import csv
        batch = os.path.join(out_dir, "batch.csv")
        with open(batch, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["complex_name", "protein_path", "ligand_description", "protein_sequence"])
            w.writerow([name, staged_pdb, cfg.modulator_smiles, ""])
        yaml_txt = open(default_yaml).read()
        yaml_txt = re.sub(r"samples_per_complex:\s*\d+",
                          f"samples_per_complex: {int(getattr(cfg, 'diffdock_samples', 40))}", yaml_txt)
        blind_yaml = os.path.join(out_dir, "blind.yaml")
        open(blind_yaml, "w").write(yaml_txt)
    except OSError:
        return False

    env = dict(os.environ)
    try:
        import certifi
        env.setdefault("SSL_CERT_FILE", certifi.where())
        env.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except Exception:
        pass
    env.setdefault("OMP_NUM_THREADS", str(os.cpu_count() or 4))
    py = getattr(cfg, "diffdock_python", None) or __import__("sys").executable
    # DiffDock writes its SO(3)/torus caches into CWD, so run from the repo.
    try:
        subprocess.run([py, "-W", "ignore", "-m", "inference",
                        "--config", blind_yaml, "--protein_ligand_csv", batch,
                        "--out_dir", out_dir],
                       cwd=repo, env=env, capture_output=True, text=True, timeout=14400)
    except (OSError, subprocess.SubprocessError):
        return False
    # DiffDock nests poses under out_dir/<complex_name>/; flatten a level if needed.
    nested = os.path.join(out_dir, name)
    if os.path.isdir(nested) and not glob.glob(os.path.join(out_dir, "rank*_confidence*.sdf")):
        for f in glob.glob(os.path.join(nested, "rank*_confidence*.sdf")):
            try:
                os.replace(f, os.path.join(out_dir, os.path.basename(f)))
            except OSError:
                pass
    return bool(glob.glob(os.path.join(out_dir, "rank*_confidence*.sdf")))


# --------------------------------------------------------------------------- selection
def select_site(cfg, receptor_pdb, proposers: list[Callable]) -> dict:
    """Run every proposer, dock the modulator into each candidate, and rank.

    Returns a dict:
      {proposals:[SiteProposal...], winner:SiteProposal|None,
       proposers_run:[...], proposers_failed:[...]}
    """
    proposals: list[SiteProposal] = []
    run, failed = [], []
    for prop in proposers:
        name = getattr(prop, "proposer_name", getattr(prop, "__name__", "proposer"))
        try:
            got = prop(cfg, receptor_pdb) or []
        except Exception as e:                      # defensive: a proposer must never crash M4
            failed.append({"proposer": name, "error": f"{type(e).__name__}: {e}"})
            continue
        (run if got else failed).append(
            {"proposer": name, "n_candidates": len(got)} if got else {"proposer": name, "n_candidates": 0})
        proposals.extend(got)

    if not proposals:
        return {"proposals": [], "winner": None, "proposers_run": run, "proposers_failed": failed}

    # cross-method consensus: candidates whose centers cluster together
    radius = getattr(cfg, "consensus_radius_A", 8.0)
    centers = np.array([p.box_center for p in proposals])
    for i, p in enumerate(proposals):
        d = np.linalg.norm(centers - centers[i], axis=1)
        # count *other* proposers (distinct sources) agreeing on this location
        near_sources = {proposals[j].source for j in range(len(proposals))
                        if j != i and d[j] <= radius}
        p.consensus_n = len(near_sources)

    # dock the modulator once, reuse the pdbqt for every candidate
    lig_pdbqt = _prepare_modulator(cfg)
    box = float(getattr(cfg, "box_size", 22.0))
    for p in proposals:
        p.box_size = [box, box, box]
        if lig_pdbqt is None:
            continue
        aff, cov, jacc = _dock_modulator(cfg, receptor_pdb, lig_pdbqt, p.box_center, box, p.site_residues, p.source)
        p.modulator_affinity_kcal_mol = aff
        p.modulator_coverage = cov
        p.modulator_contact_jaccard = jacc

    n_methods = len({p.source for p in proposals})
    for p in proposals:
        p.composite = _composite(p, n_methods)

    engaged = [p for p in proposals if p.engaged]
    winner = max(engaged, key=lambda p: p.composite) if engaged else None
    proposals.sort(key=lambda p: (p.composite if p.composite is not None else -1), reverse=True)
    return {"proposals": proposals, "winner": winner,
            "proposers_run": run, "proposers_failed": failed}


def _composite(p: SiteProposal, n_methods: int) -> float:
    cov = p.modulator_coverage or 0.0
    aff = p.modulator_affinity_kcal_mol
    aff_norm = 0.0 if aff is None else float(np.clip((aff - _AFF_WEAK) / (_AFF_STRONG - _AFF_WEAK), 0.0, 1.0))
    cons_norm = (p.consensus_n / (n_methods - 1)) if n_methods > 1 else 0.0
    return round(0.40 * cov + 0.40 * aff_norm + 0.20 * cons_norm, 3)


# --------------------------------------------------------------------------- modulator docking
def _prepare_modulator(cfg):
    """Build the modulator PDBQT once (reuses M5's ligand prep if already present)."""
    lig = str(cfg.path("m4", "select", "modulator.pdbqt"))
    if os.path.exists(lig) and os.path.getsize(lig) > 0:
        return lig
    m5_lig = cfg.path("m5", "ligand", "modulator.pdbqt")
    if m5_lig.exists() and m5_lig.stat().st_size > 0:
        return str(m5_lig)
    try:
        from ._dock import _smiles_to_pdbqt
    except Exception:
        return None
    return _smiles_to_pdbqt(cfg.modulator_smiles, lig, seed=getattr(cfg, "seed", 42))


def _dock_modulator(cfg, receptor_pdb, lig_pdbqt, center, size, site_residues, source):
    """Dock the modulator into one probe box; return (affinity, coverage, jaccard).

    coverage = |modulator_contacts ∩ proposer_residues| / |modulator_contacts|
      — size-robust: a large but correct pocket that contains the ligand scores high,
        unlike Jaccard which a big residue list deflates.
    jaccard  = |∩| / |∪|  — reported for context.
    """
    try:
        from ._dock import _vina, _read_pose_atoms
    except Exception:
        return None, 0.0, 0.0
    receptor_pdbqt = _receptor_pdbqt(receptor_pdb)
    pose = str(cfg.path("m4", "select", f"modulator_in_{source}.pdbqt"))
    aff, _ = _vina(receptor_pdbqt, lig_pdbqt, center, size, pose,
                   exhaustiveness=getattr(cfg, "exhaustiveness", 12),
                   num_modes=max(getattr(cfg, "num_modes", 5), 5),
                   seed=getattr(cfg, "seed", 42), timeout=600)
    if aff is None:
        return None, 0.0, 0.0
    pose_atoms = _read_pose_atoms(pose)
    if pose_atoms is None or not len(pose_atoms):
        return aff, 0.0, 0.0
    contacts = _pose_contact_residues(pose_atoms, receptor_pdbqt)
    proposer = {n for n in (_resi(r) for r in site_residues) if n is not None}
    if not contacts or not proposer:
        return aff, 0.0, 0.0
    inter = len(contacts & proposer)
    coverage = inter / len(contacts)
    jaccard = inter / len(contacts | proposer)
    return aff, round(coverage, 3), round(jaccard, 3)


def _pose_contact_residues(pose_atoms, receptor_pdbqt, cutoff=CONTACT_CUTOFF_A):
    """Residue numbers of the receptor within `cutoff` of any modulator pose atom."""
    contacts = set()
    for ln in open(receptor_pdbqt):
        if ln.startswith(("ATOM", "HETATM")):
            try:
                resi = int(ln[22:26])
                xyz = np.array([float(ln[30:38]), float(ln[38:46]), float(ln[46:54])])
            except ValueError:
                continue
            if (np.linalg.norm(pose_atoms - xyz, axis=1) < cutoff).any():
                contacts.add(resi)
    return contacts


def _resi(r):
    """Coerce a residue token (int, '13', 'D13', or dict) to an int residue number."""
    if isinstance(r, dict):
        for k in ("resnum", "resi", "resSeq", "residue_number", "seqid"):
            if r.get(k) is not None:
                r = r[k]; break
        else:
            return None
    s = "".join(ch for ch in str(r) if ch.isdigit())
    return int(s) if s else None


# --------------------------------------------------------------------------- IO helpers
def _ensure_pdb(cfg, receptor):
    """Return a path to a .pdb receptor (sibling receptor.pdb, or stripped from pdbqt)."""
    if receptor is None:
        return None
    if str(receptor).endswith(".pdb") and os.path.exists(receptor):
        return receptor
    sib = os.path.splitext(str(receptor))[0] + ".pdb"
    if os.path.exists(sib):
        return sib
    if not os.path.exists(receptor):
        return None
    out = str(cfg.path("m4", "receptor_from_pdbqt.pdb"))
    try:
        with open(receptor) as src, open(out, "w") as dst:
            for ln in src:
                if ln.startswith(("ATOM", "HETATM")):
                    dst.write(ln[:66].rstrip() + "\n")
                elif ln.startswith(("TER", "END")):
                    dst.write(ln)
    except OSError:
        return None
    return out


def _receptor_pdbqt(receptor):
    if str(receptor).endswith(".pdbqt"):
        return receptor
    sib = os.path.splitext(str(receptor))[0] + ".pdbqt"
    return sib if os.path.exists(sib) else receptor


def _centroid(pqr):
    pts = _xyz_from(pqr)
    return pts.mean(axis=0) if pts is not None and len(pts) else None


def _xyz_from(path):
    if not path or not os.path.exists(path):
        return None
    xs = [[float(l[30:38]), float(l[38:46]), float(l[46:54])]
          for l in open(path) if l.startswith(("ATOM", "HETATM"))]
    return np.array(xs) if xs else None


def _residues(atm_pdb):
    if not atm_pdb or not os.path.exists(atm_pdb):
        return set()
    out = set()
    for l in open(atm_pdb):
        if l.startswith(("ATOM", "HETATM")):
            try:
                out.add(int(l[22:26]))
            except ValueError:
                pass
    return out


def _pdb_heavy(pdb):
    if not pdb or not os.path.exists(pdb):
        return None, None
    xs, meta = [], []
    for l in open(pdb):
        if l.startswith("ATOM") and l[76:78].strip() != "H":
            xs.append([float(l[30:38]), float(l[38:46]), float(l[46:54])])
            try:
                meta.append(int(l[22:26]))
            except ValueError:
                meta.append(-1)
    return (np.array(xs), meta) if xs else (None, None)


def _contact_residues(lig_xyz, prot_xyz, prot_meta, cutoff=CONTACT_CUTOFF_A):
    d = np.linalg.norm(prot_xyz[:, None, :] - lig_xyz[None, :, :], axis=-1).min(axis=1)
    return {prot_meta[i] for i in range(len(d)) if d[i] <= cutoff and prot_meta[i] > 0}


def _sdf_heavy(path):
    try:
        lines = open(path).read().splitlines()
        n = int(lines[3][0:3])
        xs = []
        for l in lines[4:4 + n]:
            if l[31:34].strip() != "H":
                xs.append([float(l[0:10]), float(l[10:20]), float(l[20:30])])
        return np.array(xs) if xs else None
    except (OSError, ValueError, IndexError):
        return None


def _rank(path):
    m = re.search(r"rank(\d+)", os.path.basename(path))
    return int(m.group(1)) if m else 10**6


def _confidence(path):
    m = re.search(r"confidence(-?\d+(?:\.\d+)?)", os.path.basename(path))
    return float(m.group(1)) if m else None
