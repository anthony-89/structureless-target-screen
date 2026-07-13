# MCP Tools — structure-to-screen

The server (`structure_to_screen/mcp_server.py`, `FastMCP`) exposes exactly three
tools. Start it with:

```bash
python -m structure_to_screen.mcp_server      # stdio transport
```

or register in an MCP client config:

```json
{ "mcpServers": {
    "structure-to-screen": {
      "command": "python", "args": ["-m", "structure_to_screen.mcp_server"] } } }
```

Every tool returns JSON with a machine-readable status field. **An agent never
parses prose** — it branches on `overall_status` / `status` / `available`.

---

## 1. `run_full_pipeline`
Run the pipeline for a target + known modulator.

| arg | type | default | notes |
|-----|------|---------|-------|
| `target` | string | — | UniProt accession, e.g. `O14841` |
| `modulator_smiles` | string | — | SMILES of the known modulator (validation anchor) |
| `modulator_name` | string | `"modulator"` | human label |
| `modulator_mode` | string | `"unknown"` | `activator` \| `inhibitor` \| `unknown` (activator = the enhancer niche) |
| `run_id` | string? | `<target>_<name>` | run identifier / working dir |

**Returns** the run manifest: `overall_status` (`ok`\|`low_confidence`\|`unscreenable`),
`reached_module`, and the per-module `results[]` cascade. A structure-free or
no-homolog target returns `overall_status="unscreenable"` **with a reason — it does
not raise.**

## 2. `check_status`
Return a run's current status **without recomputing** (poll to decide trust/retry/escalate).

| arg | type | default |
|-----|------|---------|
| `run_id` | string | — |

**Returns** `{found, overall_status, reached_module, modules:[{module,status,confidence,reason}]}`,
or `{found: false, reason}` if the run doesn't exist.

## 3. `get_shortlist`
Return the prioritized shortlist for a completed run.

| arg | type | default |
|-----|------|---------|
| `run_id` | string | — |
| `top_n` | int | 15 |

**Returns** `{available: true, status, interpretation, n_beat_anchor, note, shortlist:[...]}`
if the run reached M8. If it stopped earlier (e.g. `unscreenable` at site definition),
returns `{available: false, reason}` **tied to where it stopped** — never an empty list
with no explanation.

---

## The status contract

| status | meaning | agent action |
|--------|---------|--------------|
| `ok` | trustworthy result | use it |
| `low_confidence` | result produced, a quantified check is marginal | use WITH the attached caveat (e.g. `interpretation: "comparative-within-box"`) |
| `unscreenable` | cannot produce a usable result | read `reason` / `next_actions`; retry with a different method, escalate, or tell the user |

### Worked example — the graceful-degradation state (M4, no liganded homolog)
```json
{ "pocket_source": "none_found",
  "confidence": "unscreenable",
  "fallback_attempted": "rcsb_sequence_search",
  "next_actions": ["blind_docking_diffdock_l", "cavity_detection_p2rank",
                   "manual_site_from_literature"] }
```

See `docs/agent_call_transcript.json` for a captured session exercising all three
status types (a `low_confidence` run with a flagged shortlist, an `unscreenable`
run, and an unknown run).
