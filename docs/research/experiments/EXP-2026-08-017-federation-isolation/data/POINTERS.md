# POINTERS — EXP-2026-08-017

The figures are a count over canonical build artifacts. Those trees are
gitignored, so the count is committed here in `data/metrics.json` and the inputs
are pinned by hash below.

| Artifact | Path (repo-relative) | Bytes | SHA-256 |
|---|---|---:|---|
| Merged canonical nodes | `data-merged/graphs/merged/canonical/nodes.jsonl` | 8081978 | sha256:3f6f7be014a73fc406e3d3a76a341567ce17c3479390ba2195e3c208007f790d |
| Federated ATT&CK canonical nodes | `data/graphs/attack/canonical/nodes.jsonl` | 6276406 | sha256:1aaf504615ddd60a6119f1eaccee0f57531331462e16d818a75f1264a8940a38 |
| Federated CAPEC canonical nodes | `data/graphs/capec/canonical/nodes.jsonl` | 1778465 | sha256:53725a891e7e42893a680569a9674f743003174afe12d494b310c90593cda863 |

A hash mismatch means the catalogues were rebuilt, which is exactly the event
this experiment is about — re-count rather than assuming the figures still hold.

## Reproducing

```bash
uv run python -m utils.kg_builder.merge --check
```

Then count nodes whose `properties.attack_id` is set among CAPEC-origin ids
(`capec:*`, `cwe:*`) in each condition. Deterministic; no database, no model.
