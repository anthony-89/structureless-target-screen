"""Live-path docking helpers (M5 validation, M7 screen) — AutoDock Vina.

Cold-start path: build ligand PDBQTs with Meeko, dock into the M4-defined box with
AutoDock Vina (parallelised, per-ligand timeout), and — for the reference modulator —
compare the top pose geometry against the transplanted homolog ligand to produce the
`pose_overlap` / `contact_jaccard` metrics M5 classifies on. Cache-first callers reuse
existing outputs; these functions run only when no cache exists.

Requires external binaries on PATH: `vina`, `mk_prepare_ligand.py` (Meeko). Import of
RDKit is lazy so the package imports cleanly without the dock extra installed.
"""
from __future__ import annotations
import glob
import os
import subprocess
from multiprocessing import Pool


# ---------------------------------------------------------------- ligand prep
def _smiles_to_pdbqt(smiles, out_pdbqt, seed=42):
    """Standardise -> 3D embed -> MMFF -> Meeko PDBQT. Returns path or None."""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit.Chem.MolStandardize import rdMolStandardize
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    m = rdMolStandardize.Cleanup(rdMolStandardize.LargestFragmentChooser().choose(m))
    m = Chem.AddHs(m)
    if AllChem.EmbedMolecule(m, randomSeed=seed, maxAttempts=200) != 0:
        return None
    try:
        AllChem.MMFFOptimizeMolecule(m, maxIters=500)
    except Exception:
        pass
    sdf = out_pdbqt.replace(".pdbqt", ".sdf")
    w = Chem.SDWriter(sdf); w.write(m); w.close()
    subprocess.run(["mk_prepare_ligand.py", "-i", sdf, "-o", out_pdbqt],
                   capture_output=True, timeout=120)
    try:
        os.remove(sdf)
    except OSError:
        pass
    return out_pdbqt if os.path.exists(out_pdbqt) and os.path.getsize(out_pdbqt) > 0 else None


# ---------------------------------------------------------------- vina call
def _vina(receptor_pdbqt, ligand_pdbqt, center, size, out_pose,
          exhaustiveness=12, num_modes=5, seed=42, timeout=240):
    """Dock one ligand. Returns (best_affinity_or_None, poses_written)."""
    cx, cy, cz = center
    try:
        r = subprocess.run(
            ["vina", "--receptor", receptor_pdbqt, "--ligand", ligand_pdbqt,
             "--center_x", str(cx), "--center_y", str(cy), "--center_z", str(cz),
             "--size_x", str(size), "--size_y", str(size), "--size_z", str(size),
             "--exhaustiveness", str(exhaustiveness), "--num_modes", str(num_modes),
             "--seed", str(seed), "--cpu", "1", "--out", out_pose],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, False
    except Exception:
        return None, False
    for ln in r.stdout.splitlines():
        s = ln.split()
        if len(s) >= 2 and s[0] == "1":
            try:
                return float(s[1]), os.path.exists(out_pose)
            except ValueError:
                pass
    return None, os.path.exists(out_pose)


def _box(cfg, site):
    center = site.get("box_center", [-25.6, -7.46, 18.85])
    size = site.get("box_size", [cfg.box_size] * 3)
    return center, (size[0] if isinstance(size, (list, tuple)) else size)


# ---------------------------------------------------------------- M5 reference
def dock_reference(cfg, receptor_pdbqt, site):
    """Dock the known modulator; compare top pose to the transplanted reference ligand.

    Returns a metrics dict with the keys M5 classifies on: top_affinity_kcal_mol,
    pose_overlap_frac_within_3A, max_contact_jaccard.
    """
    import numpy as np
    center, size = _box(cfg, site)
    lig_dir = cfg.path("m5", "ligand"); lig_dir.mkdir(parents=True, exist_ok=True)
    lig_pdbqt = str(lig_dir / "modulator.pdbqt")
    if not os.path.exists(lig_pdbqt):
        if _smiles_to_pdbqt(cfg.modulator_smiles, lig_pdbqt, seed=cfg.seed) is None:
            return {"top_affinity_kcal_mol": None,
                    "reason": "reference modulator failed ligand preparation"}
    pose = str(cfg.path("m5", "modulator_poses.pdbqt"))
    aff, _ = _vina(receptor_pdbqt, lig_pdbqt, center, size, pose,
                   cfg.exhaustiveness, max(cfg.num_modes, 12), cfg.seed, timeout=600)
    v = {"top_affinity_kcal_mol": aff, "box_center": list(center), "box_size": size}
    if aff is None:
        return v
    # geometry vs the transplanted reference ligand, if M4 saved it
    ref_atoms = _read_ligand_atoms(cfg.path("m4", "reference_ligand.pdb"))
    pose_atoms = _read_pose_atoms(pose)
    if ref_atoms is not None and pose_atoms is not None and len(ref_atoms) and len(pose_atoms):
        d = np.linalg.norm(pose_atoms[:, None, :] - ref_atoms[None, :, :], axis=2)
        nearest = d.min(axis=1)
        v["pose_overlap_frac_within_3A"] = round(float((nearest < 3.0).mean()), 3)
        v["min_pose_centroid_offset_A"] = round(
            float(np.linalg.norm(pose_atoms.mean(0) - ref_atoms.mean(0))), 2)
    else:
        v["pose_overlap_frac_within_3A"] = 0.0
        v["pose_overlap_note"] = "no transplanted reference-ligand geometry available"
    # contact-residue jaccard vs the site residues M4 listed
    v["max_contact_jaccard"] = _contact_jaccard(pose_atoms, receptor_pdbqt, site)
    return v


def _read_ligand_atoms(path):
    import numpy as np
    if not os.path.exists(str(path)):
        return None
    xs = []
    for ln in open(str(path)):
        if ln.startswith(("ATOM", "HETATM")):
            xs.append([float(ln[30:38]), float(ln[38:46]), float(ln[46:54])])
    return np.array(xs) if xs else None


def _read_pose_atoms(pose_pdbqt):
    """First MODEL (top pose) heavy-atom coords from a Vina output."""
    import numpy as np
    if not os.path.exists(pose_pdbqt):
        return None
    xs = []
    for ln in open(pose_pdbqt):
        if ln.startswith("ENDMDL"):
            break
        if ln.startswith(("ATOM", "HETATM")):
            xs.append([float(ln[30:38]), float(ln[38:46]), float(ln[46:54])])
    return np.array(xs) if xs else None


def _contact_jaccard(pose_atoms, receptor_pdbqt, site):
    """Jaccard of pose contact residues vs the M4 site residues (<4.5 A)."""
    import numpy as np
    ref_res = site.get("site_residues") or []
    if pose_atoms is None or not len(pose_atoms) or not ref_res:
        return 0.0

    def _resi(r):
        # accept int, "13", "D13" (code+number), or dict with resnum/resi/resSeq
        if isinstance(r, dict):
            for k in ("resnum", "resi", "resSeq", "residue_number", "seqid"):
                if r.get(k) is not None:
                    r = r[k]; break
            else:
                r = None
        s = "".join(ch for ch in str(r) if ch.isdigit())
        return int(s) if s else None

    ref_set = {n for n in (_resi(r) for r in ref_res) if n is not None}
    if not ref_set:
        return 0.0
    contacts = set()
    for ln in open(receptor_pdbqt):
        if ln.startswith(("ATOM", "HETATM")):
            try:
                resi = int(ln[22:26]); xyz = np.array(
                    [float(ln[30:38]), float(ln[38:46]), float(ln[46:54])])
            except ValueError:
                continue
            if (np.linalg.norm(pose_atoms - xyz, axis=1) < 4.5).any():
                contacts.add(resi)
    inter = len(contacts & ref_set); union = len(contacts | ref_set)
    return round(inter / union, 3) if union else 0.0


# ---------------------------------------------------------------- M7 screen
def _dock_one(args):
    """Dock one ligand, persisting its score atomically to a per-ligand .sc file.

    Atomic incremental persistence (os.replace) + skip-if-exists makes the screen
    crash-resilient and resumable: a killed parent or a hung worker loses at most the
    ligands in flight, and re-running picks up where it stopped. This is the failure
    mode a large CPU screen actually hits, so the persistence lives here, not in a
    single end-of-run CSV write.
    """
    idx, lig_pdbqt, receptor, center, size, exh, nmodes, seed, pose_dir, score_dir = args
    scf = os.path.join(score_dir, f"{idx}.sc")
    if os.path.exists(scf):
        try:
            return idx, (lambda s: float(s) if s not in ("", "NaN") else None)(
                open(scf).read().strip())
        except ValueError:
            pass
    pose = os.path.join(pose_dir, f"{idx}.pdbqt")
    aff, _ = _vina(receptor, lig_pdbqt, center, size, pose, exh, nmodes, seed, timeout=240)
    tmp = scf + ".tmp"
    with open(tmp, "w") as fh:
        fh.write("NaN" if aff is None else str(aff))
    os.replace(tmp, scf)
    return idx, aff


def screen_library(cfg, receptor_pdbqt, site, library_csv, out_scores):
    """Dock every ligand in the library into the box. Writes out_scores CSV.

    Ligand PDBQTs are read from m6/ligands_pdbqt/ if present (built by M6), else built
    on the fly from the library CSV's `smiles` column. Per-ligand scores are written
    atomically to m7/scores/<lig_id>.sc as they complete, so the run is resumable after
    a crash; the consolidated CSV is assembled from those .sc files. Returns (n_ok, n_fail).
    """
    import csv
    import glob
    center, size = _box(cfg, site)
    lig_dir = cfg.path("m6", "ligands_pdbqt"); lig_dir.mkdir(parents=True, exist_ok=True)
    pose_dir = cfg.path("m7", "poses"); pose_dir.mkdir(parents=True, exist_ok=True)
    score_dir = cfg.path("m7", "scores"); score_dir.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(library_csv)))
    tasks, ids = [], []
    for r in rows:
        idx = r.get("lig_id") or r.get("idx") or r.get("chembl_id")
        ids.append(idx)
        lig_pdbqt = str(lig_dir / f"{idx}.pdbqt")
        if not os.path.exists(lig_pdbqt):
            smi = r.get("smiles") or r.get("canonical_smiles")
            if not smi or _smiles_to_pdbqt(smi, lig_pdbqt, seed=cfg.seed) is None:
                continue
        # resumable: skip ligands already scored
        if os.path.exists(str(score_dir / f"{idx}.sc")):
            continue
        tasks.append((idx, lig_pdbqt, receptor_pdbqt, center, size,
                      cfg.exhaustiveness, cfg.num_modes, cfg.seed,
                      str(pose_dir), str(score_dir)))
    n_workers = max(1, (os.cpu_count() or 2) - 1)
    if tasks:
        with Pool(n_workers) as pool:
            for _ in pool.imap_unordered(_dock_one, tasks, chunksize=1):
                pass
    # consolidate from the atomic per-ligand .sc files (source of truth)
    scores = {}
    for f in glob.glob(str(score_dir / "*.sc")):
        idx = os.path.basename(f)[:-3]
        s = open(f).read().strip()
        scores[idx] = None if s in ("", "NaN") else float(s)
    n_ok = sum(1 for idx in ids if scores.get(idx) is not None)
    n_fail = len(ids) - n_ok
    with open(out_scores, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["lig_id", "affinity_kcal_mol"])
        for idx in ids:
            a = scores.get(idx)
            w.writerow([idx, "" if a is None else a])
    return n_ok, n_fail
