#!/usr/bin/env python3
"""Describe WHERE AMP binds on OPLAH by its actual contact residues.
Uses AMP's best pose (mode 1) from the pocket-1 focused dock (best affinity overall)
and reports every receptor residue with an atom within CUTOFF of the ligand.
No reference to any assumed/homolog site is used to define the answer.
"""
import math
from pathlib import Path

BASE = Path("/Users/antonioesquivel/Desktop/claude_code_handoff")
REC = BASE / "01_inputs/oplah_receptor.pdbqt"
POSE = BASE / "05b_pocket_detection/taskB/pockets/amp_pocket01_out.pdbqt"
CUTOFF = 4.0

three2one = {
    'ALA':'A','ARG':'R','ASN':'N','ASP':'D','CYS':'C','GLN':'Q','GLU':'E','GLY':'G',
    'HIS':'H','ILE':'I','LEU':'L','LYS':'K','MET':'M','PHE':'F','PRO':'P','SER':'S',
    'THR':'T','TRP':'W','TYR':'Y','VAL':'V'}

# ligand atoms = first MODEL of pose
lig = []
started = False
for l in open(POSE):
    if l.startswith("MODEL"):
        if started: break
        started = True; continue
    if started and l.startswith(("ATOM", "HETATM")):
        lig.append((float(l[30:38]), float(l[38:46]), float(l[46:54])))

# receptor atoms with residue id
rec = []
for l in open(REC):
    if l.startswith(("ATOM", "HETATM")):
        resn = l[17:20].strip(); ch = l[21:22].strip(); resi = l[22:26].strip()
        rec.append((float(l[30:38]), float(l[38:46]), float(l[46:54]), resn, ch, resi))

contacts = {}   # (resn,resi) -> min distance
for (rx, ry, rz, resn, ch, resi) in rec:
    for (lx, ly, lz) in lig:
        d = math.sqrt((rx-lx)**2 + (ry-ly)**2 + (rz-lz)**2)
        if d <= CUTOFF:
            key = (resn, int(resi))
            if key not in contacts or d < contacts[key]:
                contacts[key] = d
            break

ordered = sorted(contacts.items(), key=lambda kv: kv[0][1])
print(f"AMP binding site on OPLAH — residues within {CUTOFF} A of AMP's best pose")
print(f"({len(ordered)} contact residues)\n")
labels = []
for (resn, resi), d in ordered:
    one = three2one.get(resn, 'X')
    labels.append(f"{one}{resi}")
    print(f"  {one}{resi:<5} ({resn})   min dist {d:.2f} A")

print("\nContact set:", " ".join(labels))

# --- footnote only: overlap with the old assumed footprint (NOT the question) ---
assumed = {13,15,16,17,18,20,34}
hit = sorted({resi for (resn,resi),_ in ordered} & assumed)
print(f"\n[footnote] of the old assumed footprint {sorted(assumed)}, AMP's unbiased pose contacts: {hit}")
