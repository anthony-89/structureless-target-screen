"""M1 — Target intake: UniProt sequence + AlphaFold DB model.

If no AlphaFold DB model exists for the accession, the target is `unscreenable`
by this route (the honest failure the pipeline is designed to surface); a GPU
predictor (Boltz-2/Chai-1) would be the swap-in, recorded as a next action.
"""
from __future__ import annotations
import json
import requests
from ..config import PipelineConfig
from ..status import ModuleResult, ok, unscreenable

UNIPROT = "https://rest.uniprot.org/uniprotkb/{acc}.fasta"
AF_API = "https://alphafold.ebi.ac.uk/api/prediction/{acc}"


def run(cfg: PipelineConfig) -> ModuleResult:
    seq_path = cfg.path("m1", f"{cfg.target}.fasta")
    cif_path = cfg.path("m1", f"{cfg.target}_af.cif")
    pae_path = cfg.path("m1", f"{cfg.target}_pae.json")
    meta_path = cfg.path("m1", "intake.json")

    # resumable: if we already fetched, reuse
    if seq_path.exists() and cif_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        return ok("M1_intake", f"cached: {cfg.target} ({meta.get('seq_len','?')} aa)",
                  data=meta, artifacts=[str(seq_path), str(cif_path)])

    # --- sequence ---
    r = requests.get(UNIPROT.format(acc=cfg.target), timeout=30)
    if r.status_code != 200 or not r.text.startswith(">"):
        return unscreenable("M1_intake",
                            f"UniProt has no sequence for '{cfg.target}' (HTTP {r.status_code})",
                            data={"accession": cfg.target})
    fasta = r.text
    seq = "".join(fasta.split("\n")[1:])
    seq_path.write_text(fasta)

    # --- AlphaFold model ---
    ar = requests.get(AF_API.format(acc=cfg.target), timeout=30)
    if ar.status_code != 200 or not ar.json():
        return unscreenable("M1_intake",
            f"No AlphaFold DB model for {cfg.target}; predict de novo (Boltz-2/Chai-1) before continuing.",
            data={"accession": cfg.target, "seq_len": len(seq),
                  "next_action": "run_structure_predictor"},
            artifacts=[str(seq_path)])
    entry = ar.json()[0]
    cif_path.write_bytes(requests.get(entry["cifUrl"], timeout=60).content)
    pae_url = entry.get("paeDocUrl") or entry.get("paeImageUrl")
    if pae_url and pae_url.endswith(".json"):
        pae_path.write_bytes(requests.get(pae_url, timeout=60).content)

    meta = {"accession": cfg.target, "seq_len": len(seq),
            "af_entry": entry.get("entryId"), "af_version": entry.get("latestVersion"),
            "modulator": cfg.modulator_name, "modulator_mode": cfg.modulator_mode}
    meta_path.write_text(json.dumps(meta, indent=2))
    return ok("M1_intake", f"{cfg.target}: {len(seq)} aa, model {entry.get('entryId')}",
              data=meta, artifacts=[str(seq_path), str(cif_path), str(pae_path)])
