"""Live-path prioritization (M8) — consensus rank + scaffold diversity.

Pure post-processing of the docking scores CSV; no external calls. This one is
fully implemented so any completed screen (cached or live) can be prioritized.
"""
from __future__ import annotations
import csv


def prioritize(cfg, scores_csv, library_csv, out_shortlist, anchor_kcal=None):
    # Merge scores with library props on lig_id
    lib = {}
    with open(library_csv) as fh:
        for row in csv.DictReader(fh):
            lib[row.get("lig_id") or row.get("ligand_id")] = row
    rows = []
    with open(scores_csv) as fh:
        for row in csv.DictReader(fh):
            lid = row.get("lig_id") or row.get("ligand_id")
            aff = _f(row.get("affinity_kcal_mol") or row.get("affinity"))
            if aff is None:
                continue
            props = lib.get(lid, {})
            heavy = _f(props.get("n_heavy") or props.get("heavy_atoms")) or None
            le = round(-aff / heavy, 3) if heavy else None
            rows.append({"lig_id": lid, "affinity_kcal_mol": aff,
                         "ligand_efficiency": le,
                         "pref_name": props.get("pref_name", ""),
                         "chembl_id": props.get("chembl_id", ""),
                         "mw": props.get("mw", ""),
                         "murcko": props.get("murcko_scaffold", "")})
    if not rows:
        return 0, 0, []
    rows.sort(key=lambda r: r["affinity_kcal_mol"])
    n_beat = sum(1 for r in rows if anchor_kcal is not None and r["affinity_kcal_mol"] < anchor_kcal)
    # scaffold-diverse shortlist: best per Murcko scaffold, up to 15
    seen, shortlist = set(), []
    for r in rows:
        sc = r["murcko"] or r["lig_id"]
        if sc in seen:
            continue
        seen.add(sc); shortlist.append(r)
        if len(shortlist) >= 15:
            break
    with open(out_shortlist, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(shortlist[0].keys()))
        w.writeheader(); w.writerows(shortlist)
    return len(shortlist), n_beat, shortlist[:5]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
