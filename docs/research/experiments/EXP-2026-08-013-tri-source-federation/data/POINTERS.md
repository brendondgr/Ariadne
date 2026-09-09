# POINTERS — EXP-2026-08-013

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Table filled 2026-09-09 (it was the blank scaffold until then; RESULTS A-1).
Hashes as of 2026-09-09. Every figure in RESULTS and `data/metrics.json`
except `golden_owning_source_not_routed` (14 → 2, needs the golden-bank router
run) and the bridge demo (7 → 1 records, a single live query) was recomputed
from these files on 2026-09-09 and reproduces exactly.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Composition manifest (config) | `data-tri/tri_manifest.json` | 2187 | sha256:b06881859b847f9a984cf00f26110b55502ce2377d2737ac022f570f32f22d01 | The three-source composition `scripts/tri_compose.py` builds; also `config.hash` in the manifest |
| Phase 1, three sources, pre-routing-fix | `docs/evaluation/identity-bank3-tri-2026-08-22` | 3836923 | sha256:5d23e4dba4417c013c20e65ab2ed40771efcc7241200aef6820d6a3ae6ac0982 | `bank.json` + `sweep_state.json` (2026-08-22 13:58): 0.6239 / 0.1254, unanswerable 0.1667 / 0.0833, ids 180.36 / 391.47, max 2234 / 2608, 80 of 117 routed beyond identity (0.6838). The invalid first run (RESULTS "Two defects…") wrote to this path before it and does not survive |
| Phase 1a, one source, post-routing-fix | `docs/evaluation/identity-bank3-routing-1src-2026-08-22` | 2094386 | sha256:c4aae3061822988dc27ed8807a999d4331d944685e6cddab1a8fb87ce8cb075a | `sweep_state.json` 14:43: 0.7094 / 0.2194, ids 8.24 / 1.95, max 54 / 2 — the one-source baseline, unmoved by the rule |
| Phase 1a, three sources, post-routing-fix | `docs/evaluation/identity-bank3-routing-tri-2026-08-22` | 2094380 | sha256:d5a35d59891bf5ea001e33d586cc2a4f9dbb67b4985b66a6973f1cc027d518c3 | `sweep_state.json` 14:43: 0.7094 / 0.2194, 0 of 117 questions differing, 0 routed beyond identity |
| Phase 2 no-regression, one source, bridge declared | `docs/evaluation/identity-bank3-bridge-1src-2026-08-22` | 2094387 | sha256:cd930e2e0b2c7fdd1abc8af65066f2e612fe4174322ff68765135a8602a7164a | `sweep_state.json` 16:13: 0.7094 / 0.2194 |
| Phase 2 no-regression, three sources, bridge declared | `docs/evaluation/identity-bank3-bridge-tri-2026-08-22` | 2094387 | sha256:a2c2c4a1658ed354538ad2d2335b44d3a0704fd0754f7f5b9df6b2ade917c02e | `sweep_state.json` 16:20: 0.7094 / 0.2194, 0 differing |
| Tri-source bank run directory | `docs/evaluation/tri-bank-2026-08-22` | 6458454 | sha256:a4b0e9ba1f3dc15f7367e893db13a18f7bcf4f98bea23059ba3a4406b232a278 | Authoring batches (`batch_*.json`, `authored_*.json`, `author_views.json`, incl. the `_redraw` after the negative-anchor gold fix), `gold.json`, `bank.json`, `tri_sweep_state.json` |
| Tri-source bank | `docs/evaluation/tri-bank-2026-08-22/bank.json` | 75006 | sha256:7d9ceb57ebabc77938f3ca72895fbb8031c849ab0fbfc2001daa672428cdc3ee | 64 blind questions; 0 of 64 leak a gold identifier |
| Tri-source gold | `docs/evaluation/tri-bank-2026-08-22/gold.json` | 61758 | sha256:f21b52fe221f48e8c4dec7eb9e44c6c3f64866f38a380a82062eb57012a7cfc7 | Gold from the generator blueprint and the declared correspondence, after the negative-anchor fix |
| Tri-source sweep state | `docs/evaluation/tri-bank-2026-08-22/tri_sweep_state.json` | 6283225 | sha256:250710ef411a8b33c6b366ddf437904e46dae694227ff45db240e21c8c111175 | 16:42: generic 0.7724 (technique 0.8333, 24/24 reached ATT&CK; mitigation 0.3398; refusal 1.0; control 1.0, 0/12 reached ATT&CK); deterministic 0.3176 / 0.0 / 0.2081 / 0.4167 / 1.0; 7 false technique claims on refusal negatives |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
