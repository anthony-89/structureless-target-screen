#!/usr/bin/env python3
"""Clean + rank the local 5k diverse dock. Run when dock_5k/results.csv is complete
(or partial — it works on whatever is done). Merges selection metadata (arm, Tanimoto),
counts how many beat AMP, and highlights the diversity-arm (novel) winners = the #4 story."""
import csv
from pathlib import Path

BASE = Path("/Users/antonioesquivel/Desktop/claude_code_handoff/05b_pocket_detection/taskC")
RES = BASE / "dock_5k/results.csv"
SEL = BASE / "selected_5k.csv"
AMP_F = BASE / "dock_5k/AMP_control_score.txt"
AMP = float(open(AMP_F).read().strip()) if AMP_F.exists() else -8.78

meta = {r["lig_id"]: r for r in csv.DictReader(open(SEL))}

best = {}
for r in csv.DictReader(open(RES)):
    lid = r["lig_id"]; a = r["best_affinity_kcal_mol"]
    if not a or a == "None": continue
    a = float(a)
    if lid not in best or a < best[lid]: best[lid] = a

clean = {k: v for k, v in best.items() if -15 <= v <= 0}
ranked = sorted(clean.items(), key=lambda kv: kv[1])
beat = [(k, v) for k, v in ranked if v < AMP]
beat_div = [(k, v) for k, v in beat if meta.get(k, {}).get("arm") == "diversity"]
beat_enr = [(k, v) for k, v in beat if meta.get(k, {}).get("arm") == "enrichment"]

out = BASE / "dock_5k/shortlist_5k.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["rank", "lig_id", "zinc_id", "affinity", "delta_vs_AMP", "arm", "tanimoto_to_amp", "can_smiles"])
    for i, (lid, a) in enumerate(ranked, 1):
        m = meta.get(lid, {})
        w.writerow([i, lid, m.get("zinc_id", ""), a, round(a - AMP, 2),
                    m.get("arm", ""), m.get("tanimoto_to_amp", ""), m.get("can_smiles", "")])

print(f"docked (usable): {len(clean)} of {len(best)}   AMP control: {AMP:.2f} kcal/mol")
print(f"beat AMP: {len(beat)}  (enrichment {len(beat_enr)} | diversity {len(beat_div)})")
print(f"\nTop 15 overall:")
for i, (lid, a) in enumerate(ranked[:15], 1):
    m = meta.get(lid, {})
    print(f'  {i:>2}. {m.get("zinc_id",lid):>12} {a:>7.2f}  {m.get("arm",""):<11} sim={m.get("tanimoto_to_amp","")}')
print(f"\nTop 8 from the DIVERSITY arm (novel, low AMP-similarity — the #4 story):")
for i, (lid, a) in enumerate(beat_div[:8], 1):
    m = meta.get(lid, {})
    print(f'  {i:>2}. {m.get("zinc_id",lid):>12} {a:>7.2f}  sim={m.get("tanimoto_to_amp","")}  {m.get("can_smiles","")[:48]}')
print(f"\n-> {out}")
