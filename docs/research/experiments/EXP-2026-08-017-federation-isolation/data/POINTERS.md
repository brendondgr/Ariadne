# POINTERS — EXP-2026-08-017

The figures are a count over canonical build artifacts. Those trees are
gitignored, so the count is committed here in `data/metrics.json` and the inputs
are pinned by hash below.

| Artifact | Path (repo-relative) | Bytes | SHA-256 |
|---|---|---:|---|
| Merged canonical nodes | `data-merged/graphs/merged/canonical/nodes.jsonl` | 8081978 | sha256:3f6f7be014a73fc406e3d3a76a341567ce17c3479390ba2195e3c208007f790d |
| Federated ATT&CK canonical nodes (as rebuilt 2026-09-07; re-hashed 2026-09-09, see A-1) | `data/graphs/attack/canonical/nodes.jsonl` | 6945959 | sha256:371147e271d4294a87a7eb58098cf1f4aaf0c026bc77054c2a5bf710208931e7 |
| Federated CAPEC canonical nodes (rebuilt 2026-09-11 by `EXP-2026-09-018` Step 4b; see below) | `data/graphs/capec/canonical/nodes.jsonl` | 2438431 | sha256:2deb6d930a32d21e1a67af55429c720b88b3238dac46b83ceefda82ef69a13ab |

A hash mismatch means the catalogues were rebuilt, which is exactly the event
this experiment is about — re-count rather than assuming the figures still hold.

**That event has happened once.** The two federated files were rebuilt on
2026-09-07 17:31 (ATT&CK 6,276,406 → 6,945,959 bytes; CAPEC 1,778,465 →
2,413,194 bytes, 4,769 → 6,374 nodes). The rows above pin the rebuilt files;
the original hashes (`sha256:1aaf5046…`, `sha256:53725a89…`) are preserved in
RESULTS A-1 and ISSUES. The federated count was re-run on the rebuilt files on
2026-09-09 and is still 0 rewritten nodes; the merged file is unchanged and
still reproduces 1,083 / 189.

**And once more, on 2026-09-11.** `EXP-2026-09-018` Step 4b repaired the CAPEC
parser to read `Typical_Severity` and `Likelihood_Of_Attack`, which the source
publishes and the load had discarded (`Q54`), so the CAPEC canonical node file
was rebuilt: 2,413,194 → 2,438,431 bytes, the same 6,374 nodes with two more
properties on 488 and 344 of them. **The count was re-run and is unchanged: 0
rewritten nodes, and `merge --check` still reports 1,083 public ids promoted.**
The ATT&CK node file is byte-identical, because that repair is CAPEC-only.

## Reproducing

```bash
uv run python -m utils.kg_builder.merge --check
```

Then count nodes whose `properties.attack_id` is set among CAPEC-origin ids
(`capec:*`, `cwe:*`) in each condition. Deterministic; no database, no model.
