"""Live-path implementation of the liganded-homolog transplant (M4).

Ported from the OPLAH/5-AMP reference run. Two entry points:
  search_liganded_homologs(cfg, receptor_pdb) -> list of hits (or [])
  transplant_and_box(cfg, receptor_pdb, hits) -> (best, rmsd, center, residues)

Kept dependency-light and defensive: any failure to find a *liganded* homolog
returns [] so M4 emits the `unscreenable` graceful-degradation state rather than
raising.
"""
from __future__ import annotations
import json
import requests
import numpy as np

RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_ENTRY = "https://data.rcsb.org/rest/v1/core/entry/{pdb}"

# ligand chemotypes worth transplanting, keyed by common modulator families.
# Non-polymer, non-ion, non-buffer components only.
_IGNORE_LIG = {"HOH", "GOL", "EDO", "SO4", "PO4", "CL", "NA", "K", "MG", "ZN",
               "CA", "MN", "ACT", "DMS", "PEG", "IOD", "BR", "FMT", "TRS"}


def _target_sequence(cfg):
    fasta = cfg.path("m1", f"{cfg.target}.fasta")
    if fasta.exists():
        return "".join(fasta.read_text().split("\n")[1:])
    return None


def search_liganded_homologs(cfg, receptor_pdb, want_ligand_like=None):
    """RCSB sequence search -> homologs that carry a non-trivial ligand."""
    seq = _target_sequence(cfg)
    if not seq:
        return []
    query = {
        "query": {"type": "terminal", "service": "sequence",
                  "parameters": {"evalue_cutoff": cfg.homolog_evalue_cutoff,
                                 "identity_cutoff": cfg.homolog_identity_cutoff,
                                 "sequence_type": "protein", "value": seq}},
        "return_type": "polymer_entity",
        "request_options": {"results_verbosity": "verbose",
                            "paginate": {"start": 0, "rows": 25}}}
    try:
        r = requests.post(RCSB_SEARCH, json=query, timeout=60)
        r.raise_for_status()
        rows = r.json().get("result_set", [])
    except Exception:
        return []

    hits = []
    seen = set()
    for row in rows:
        pdb = row["identifier"].split("_")[0]
        if pdb in seen:
            continue
        seen.add(pdb)
        ident = 0.0
        for m in row.get("services", [{}])[0].get("nodes", [{}])[0].get("match_context", [{}]):
            ident = max(ident, m.get("sequence_identity", 0.0))
        ligs = _entry_ligands(pdb)
        if not ligs:
            continue
        hits.append({"pdb_id": pdb, "identity": round(ident, 3), "ligand": ligs[0],
                     "all_ligands": ligs})
        if len(hits) >= 8:
            break
    # best identity first
    return sorted(hits, key=lambda h: -h["identity"])


def _entry_ligands(pdb):
    try:
        j = requests.get(RCSB_ENTRY.format(pdb=pdb), timeout=30).json()
        comps = j.get("rcsb_entry_info", {}).get("nonpolymer_bound_components", []) or []
        return [c for c in comps if c not in _IGNORE_LIG]
    except Exception:
        return []


def transplant_and_box(cfg, receptor_pdb, hits):
    """Superpose the best liganded homolog and transplant its ligand centroid.

    Returns (best_hit, rmsd, box_center[list3], site_residues[list]).
    Uses Biopython for structure IO + a simple iterative CA superposition.
    """
    from Bio.PDB import PDBParser, Superimposer
    from Bio import pairwise2

    parser = PDBParser(QUIET=True)
    model_struct = parser.get_structure("target", receptor_pdb)
    model_chain = next(model_struct.get_chains())

    for h in hits:
        fn = _fetch_pdb(cfg, h["pdb_id"])
        if fn is None:
            continue
        try:
            hs = parser.get_structure(h["pdb_id"], fn)
        except Exception:
            continue
        best = _superpose_and_extract(cfg, model_chain, hs, h, pairwise2, Superimposer)
        if best is not None:
            return best
    # nothing usable
    raise RuntimeError("no homolog could be superposed")


RCSB_FILE = "https://files.rcsb.org/download/{pdb}.pdb"


def _fetch_pdb(cfg, pdb_id):
    """Download a PDB coordinate file from the RCSB file server (allowlisted)."""
    dst = cfg.path("m4", "homologs", f"{pdb_id}.pdb")
    if dst.exists() and dst.stat().st_size > 0:
        return str(dst)
    try:
        r = requests.get(RCSB_FILE.format(pdb=pdb_id), timeout=60)
        if r.status_code == 200 and r.text.startswith(("HEADER", "ATOM", "CRYST")):
            dst.write_bytes(r.content)
            return str(dst)
    except Exception:
        pass
    return None


def _three_to_one(res):
    from Bio.PDB.Polypeptide import protein_letters_3to1
    return protein_letters_3to1.get(res.resname, "X")


def _superpose_and_extract(cfg, model_chain, homolog_struct, hit, pairwise2, Superimposer):
    """Sequence-align model vs homolog chain, iteratively superpose CA pairs,
    transplant the ligand centroid, and collect site residues within 4.5 A.

    Returns (hit, rmsd, center[list3], residues[list]) or None if no usable
    ligand/superposition (caller then tries the next homolog).
    """
    import numpy as np
    # pick homolog chain carrying the ligand
    lig = hit["ligand"]
    hchain = None
    lig_atoms = []
    for ch in homolog_struct.get_chains():
        atoms = [a for res in ch for a in res if res.resname == lig]
        if atoms:
            hchain, lig_atoms = ch, atoms
            break
    if hchain is None or not lig_atoms:
        return None

    def seq_of(chain):
        return "".join(_three_to_one(r) for r in chain if r.id[0] == " ")
    ms, hs = seq_of(model_chain), seq_of(hchain)
    if len(ms) < 30 or len(hs) < 30:
        return None
    aln = pairwise2.align.globalms(ms, hs, 2, -1, -5, -0.5, one_alignment_only=True)[0]

    m_res = [r for r in model_chain if r.id[0] == " "]
    h_res = [r for r in hchain if r.id[0] == " "]
    mi = hi = 0
    pairs = []
    for a, b in zip(aln.seqA, aln.seqB):
        if a != "-" and b != "-":
            if "CA" in m_res[mi] and "CA" in h_res[hi]:
                pairs.append((m_res[mi]["CA"], h_res[hi]["CA"]))
        if a != "-": mi += 1
        if b != "-": hi += 1
    if len(pairs) < 20:
        return None

    # iterative superposition dropping outliers > 4 A
    sup = Superimposer()
    keep = pairs
    for _ in range(6):
        sup.set_atoms([p[0] for p in keep], [p[1] for p in keep])
        sup.apply([a for r in hchain for a in r])  # move homolog onto model frame
        d = [np.linalg.norm(p[0].coord - p[1].coord) for p in keep]
        rmsd = float(np.sqrt(np.mean(np.square(d))))
        new = [p for p, di in zip(keep, d) if di < 4.0]
        if len(new) == len(keep) or len(new) < 20:
            break
        keep = new

    center = np.mean([a.coord for a in lig_atoms], axis=0)
    residues = []
    for r in m_res:
        if any(np.linalg.norm(at.coord - la.coord) < 4.5
               for at in r for la in lig_atoms):
            residues.append(f"{_three_to_one(r)}{r.id[1]}")

    # Persist the transplanted reference-ligand atoms (now in the model frame) so M5
    # can compute pose overlap / centroid offset against the crystallographic position.
    try:
        ref_pdb = cfg.path("m4", "reference_ligand.pdb")
        ref_pdb.parent.mkdir(parents=True, exist_ok=True)
        with open(str(ref_pdb), "w") as fh:
            for i, a in enumerate(lig_atoms, 1):
                x, y, z = a.coord
                el = (getattr(a, "element", "") or a.get_id()[0]).rjust(2)[:2]
                fh.write(f"HETATM{i:5d} {a.get_id()[:4]:<4} {lig:>3} L 900    "
                         f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {el}\n")
    except Exception:
        pass  # geometry file is best-effort; M5 degrades to jaccard-only if absent
    return hit, rmsd, [round(float(x), 2) for x in center], residues
