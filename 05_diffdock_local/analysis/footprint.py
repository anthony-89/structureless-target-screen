"""Contact-footprint measurement shared by the AMP reference pose, DiffDock poses and fpocket pockets.

Footprint = set of receptor residues within CUTOFF of any ligand heavy atom.
Distances are min heavy-atom -> heavy-atom, matching how the reference AMP
footprint from the manual Vina run was defined.
"""
import numpy as np

CUTOFF = 4.5

# Reference footprint from the manual Vina work (Task B).
AMP_FOOTPRINT = {13, 15, 16, 17, 18, 20, 34}
ADENINE_MOTIF = {18}                     # F18 aromatic stack
PHOSPHATE_MOTIF = {13, 15, 16, 17, 20, 34}

BOX_AMP_ANCHORED = np.array([-16.2, -1.65, 15.2])
BOX_ORIGINAL_TRIPHOS = np.array([-25.6, -7.46, 18.85])


def parse_pdb_heavy(path, chain=None):
    """Return (coords Nx3, meta list of (resnum, resname, atomname))."""
    coords, meta = [], []
    with open(path) as fh:
        for line in fh:
            if not line.startswith(("ATOM", "HETATM")):
                continue
            elem = line[76:78].strip()
            atomname = line[12:16].strip()
            if elem == "H" or (not elem and atomname.startswith("H")):
                continue
            if chain and line[21] != chain:
                continue
            coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
            meta.append((int(line[22:26]), line[17:20].strip(), atomname))
    return np.asarray(coords), meta


def parse_pdbqt_ligand(path, model=1):
    """Heavy-atom coords from one MODEL of an AutoDock pdbqt pose.

    Vina writes every ranked pose into one file; model 1 is the top pose.
    AD types HD/H/HS are hydrogens; A/NA/OA/N/C/P are heavy.
    """
    coords, current = [], 0
    with open(path) as fh:
        for line in fh:
            if line.startswith("MODEL"):
                current = int(line.split()[1])
                continue
            if current and current != model:
                continue
            if not line.startswith(("ATOM", "HETATM")):
                continue
            if line[77:79].strip() in ("H", "HD", "HS"):
                continue
            coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
    return np.asarray(coords)


def parse_sdf_heavy(path):
    """Heavy-atom coords from an SDF (first molecule), without requiring rdkit."""
    with open(path) as fh:
        lines = fh.read().splitlines()
    counts = lines[3]
    natoms = int(counts[0:3])
    coords = []
    for line in lines[4:4 + natoms]:
        x, y, z = float(line[0:10]), float(line[10:20]), float(line[20:30])
        sym = line[31:34].strip()
        if sym == "H":
            continue
        coords.append((x, y, z))
    return np.asarray(coords)


def residue_min_distances(lig_xyz, prot_xyz, prot_meta):
    """resnum -> (min_dist, resname). Min over all heavy-atom pairs."""
    d = np.linalg.norm(prot_xyz[:, None, :] - lig_xyz[None, :, :], axis=-1).min(axis=1)
    out = {}
    for dist, (resnum, resname, _) in zip(d, prot_meta):
        if resnum not in out or dist < out[resnum][0]:
            out[resnum] = (float(dist), resname)
    return out


def footprint(lig_xyz, prot_xyz, prot_meta, cutoff=CUTOFF):
    mins = residue_min_distances(lig_xyz, prot_xyz, prot_meta)
    return {r for r, (d, _) in mins.items() if d <= cutoff}, mins


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else 0.0
