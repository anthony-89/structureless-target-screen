#!/usr/bin/env python3
"""Nucleotide-focused arm for Task C: natural nucleotides/nucleosides + clinical
nucleoside/nucleotide drugs + base analogs. Canonical SMILES fetched from PubChem
by name (reliable), merged with the existing adenine/nucleotide ChEMBL set (the 73),
deduped, MW-filtered. Docks into AMP's pocket alongside the diverse 50k arm.
"""
import urllib.request, urllib.parse, json, time, csv, sys
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

BASE = Path("/Users/antonioesquivel/Desktop/claude_code_handoff")
OUT = BASE / "05b_pocket_detection/taskC/library/nucleotide_focused.csv"

NAMES = [
    # natural nucleosides
    "adenosine","guanosine","cytidine","uridine","inosine","xanthosine",
    "2'-deoxyadenosine","2'-deoxyguanosine","2'-deoxycytidine","thymidine","2'-deoxyuridine",
    # natural nucleotides (mono/di/tri)
    "adenosine monophosphate","adenosine 5'-diphosphate","adenosine 5'-triphosphate",
    "guanosine monophosphate","guanosine 5'-diphosphate","guanosine 5'-triphosphate",
    "cytidine 5'-monophosphate","cytidine 5'-diphosphate",
    "uridine 5'-monophosphate","uridine 5'-diphosphate",
    "inosine monophosphate","xanthosine 5'-monophosphate",
    "2'-deoxyadenosine 5'-monophosphate","2'-deoxyguanosine 5'-monophosphate",
    "thymidine 5'-monophosphate","2'-deoxycytidine 5'-monophosphate",
    # cyclic nucleotides
    "cyclic AMP","cyclic GMP",
    # bases / purine analogs
    "adenine","guanine","hypoxanthine","xanthine","2-aminopurine","6-mercaptopurine",
    "6-thioguanine","allopurinol","8-azaguanine","2-chloroadenosine","8-bromoadenosine",
    "N6-methyladenosine","1-methyladenosine","tubercidin","nebularine","sinefungin",
    # antiviral nucleoside/tide drugs
    "acyclovir","ganciclovir","penciclovir","valacyclovir","valganciclovir","vidarabine",
    "ribavirin","tenofovir","adefovir","cidofovir","entecavir","abacavir","didanosine",
    "zidovudine","stavudine","lamivudine","emtricitabine","telbivudine","sofosbuvir",
    "molnupiravir",
    # anticancer nucleoside drugs
    "cytarabine","gemcitabine","fludarabine","cladribine","clofarabine","nelarabine",
    "decitabine","azacitidine","mercaptopurine","thioguanine","capecitabine",
    "floxuridine","trifluridine","fluorouracil","pentostatin",
    # cofactor-ish small nucleotides / methyl donors
    "nicotinamide riboside","nicotinamide mononucleotide","S-adenosylmethionine",
    "S-adenosylhomocysteine","5-fluorouridine",
]

def pubchem_smiles(name):
    q = urllib.parse.quote(name)
    for prop in ("IsomericSMILES","CanonicalSMILES"):
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{q}/property/{prop}/TXT"
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"vHTS/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                s = r.read().decode().strip().splitlines()
                if s and s[0]:
                    return s[0].strip()
        except Exception:
            continue
    return None

rows = {}   # canonical_smiles -> (name, source)
# 1) curated names via PubChem
got = miss = 0
for nm in NAMES:
    smi = pubchem_smiles(nm)
    time.sleep(0.15)
    if not smi:
        miss += 1; print(f"  [miss] {nm}", flush=True); continue
    m = Chem.MolFromSmiles(smi)
    if m is None:
        miss += 1; continue
    can = Chem.MolToSmiles(m)
    rows.setdefault(can, (nm, "curated_pubchem"))
    got += 1
print(f"PubChem: {got} resolved, {miss} missed", flush=True)

# 2) fold in the existing adenine/nucleotide ChEMBL set (the 73) — legitimate here
n_from73 = 0
for r in csv.DictReader(open(BASE/"01_inputs/candidate_library.csv")):
    m = Chem.MolFromSmiles(r["can_smiles"])
    if m is None: continue
    can = Chem.MolToSmiles(m)
    if can not in rows:
        rows[can] = (r.get("pref_name") or r["chembl_id"], "chembl_73")
        n_from73 += 1
print(f"added {n_from73} unique from existing 73-set", flush=True)

# 3) MW filter (drop the very large cofactors/tri-phosphates if huge); keep 120-750
out = []
for can,(nm,src) in rows.items():
    m = Chem.MolFromSmiles(can)
    mw = Descriptors.MolWt(m)
    if 120 <= mw <= 750:
        out.append((nm, can, src, round(mw,1)))
out.sort(key=lambda x: x[3])

with open(OUT,"w",newline="") as f:
    w = csv.writer(f); w.writerow(["lig_id","pref_name","can_smiles","source","mw"])
    for i,(nm,can,src,mw) in enumerate(out):
        w.writerow([f"N{i:04d}", nm, can, src, mw])
print(f"\nNucleotide-focused library: {len(out)} molecules -> {OUT}")
from collections import Counter
for k,v in Counter(x[2] for x in out).most_common():
    print(f"  {v:>3}  {k}")
