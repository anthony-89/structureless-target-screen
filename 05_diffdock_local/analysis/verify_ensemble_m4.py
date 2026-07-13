"""End-to-end verification of the ensemble M4 on the real OPLAH case.

Stages a pipeline workdir with the OPLAH receptor, points the proposers at the local
fpocket binary and the Task-A DiffDock poses, runs m4_site.run() cold, and checks that
the modulator selects the AMP site.
"""
import json
import shutil
import sys
from pathlib import Path

HANDOFF = Path("/Users/antonioesquivel/Desktop/claude_code_handoff")
sys.path.insert(0, str(HANDOFF / "04_pipeline_code_and_docs/pipeline_src"))

from structure_to_screen.config import PipelineConfig
from structure_to_screen.modules import m4_site

AMP_SMILES = "Nc1ncnc2c1ncn2C1OC(COP(=O)(O)O)C(O)C1O"
AMP_BOX = [-16.2, -1.65, 15.2]

wd = Path("/tmp/s2s_ensemble_verify/oplah")
if wd.exists():
    shutil.rmtree(wd)
(wd / "m1").mkdir(parents=True)
(wd / "m3").mkdir(parents=True)
shutil.copy(HANDOFF / "01_inputs/oplah_receptor.pdb", wd / "m3/receptor.pdb")
shutil.copy(HANDOFF / "01_inputs/oplah_receptor.pdbqt", wd / "m3/receptor.pdbqt")
shutil.copy(HANDOFF / "01_inputs/oplah_sequence.fasta", wd / "m1/O14841.fasta")

cfg = PipelineConfig(
    target="O14841", modulator_smiles=AMP_SMILES, modulator_name="5-AMP",
    modulator_mode="activator", workdir=str(wd),
    site_proposers=("homolog", "fpocket", "diffdock"),
    fpocket_bin=str(HANDOFF / "05_diffdock_local/bin/fpocket"),
    fpocket_top_k=2,
    diffdock_poses_dir=str(HANDOFF / "05_diffdock_local/DiffDock/out/oplah_amp_blind"),
    exhaustiveness=8, num_modes=9, box_size=20.0,
)

print("Running ensemble M4 cold on OPLAH (docking the modulator into each candidate)...\n")
res = m4_site.run(cfg, str(wd / "m3/receptor.pdbqt"))

print("=" * 70)
print("ModuleResult:", res)
print("=" * 70)
site = res.data
print(f"\nwinner pocket_source : {site.get('pocket_source')}")
print(f"box_center           : {site.get('box_center')}")
sel = site.get("selection", {})
import numpy as np
if site.get("box_center"):
    d = float(np.linalg.norm(np.array(site["box_center"]) - np.array(AMP_BOX)))
    print(f"  distance to hand-found AMP box {AMP_BOX}: {d:.2f} A")
print(f"modulator affinity   : {sel.get('modulator_affinity_kcal_mol')} kcal/mol")
print(f"modulator Jaccard    : {sel.get('modulator_contact_jaccard')}")
print(f"methods agreeing     : {sel.get('consensus_n_methods_agreeing')}")
print(f"composite score      : {sel.get('composite_score')}")

print("\n--- proposers run / failed ---")
for r in site.get("proposers_run", []):
    print(f"  ran   : {r}")
for r in site.get("proposers_failed", []):
    print(f"  failed: {r}")

print("\n--- runner-up sites (flagged, not discarded) ---")
for ru in site.get("runner_up_sites", []):
    print(f"  {ru['source']:>18}  center={ru['box_center']}  "
          f"aff={ru.get('modulator_affinity_kcal_mol')}  "
          f"jacc={ru.get('modulator_contact_jaccard')}  "
          f"consensus={ru.get('consensus_n')}  composite={ru.get('composite')}  "
          f"[{ru['confidence_flag']}]")

print(f"\nbinding_site.json written to: {wd/'m4/binding_site.json'}")
