# POINTERS — EXP-2026-11-004

Run outputs live under `logs/killtests-2026-11/typed/` and `logs/killtests-2026-11/typed-verify/` (gitignored); the small summaries are copied into this folder. Run of 2026-11-14 00:34–00:42 from tag `killtests-typed-run` (f3074fdd).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `run_header.json` | `logs/killtests-2026-11/typed/run_header.json` | 493 | `sha256:b7f23f2519d39caabc30d5d57773c341299a2e706ea0788815cc534f8c03ebad` | model identities (token ids), concurrency, budget |
| `generate.json` | `logs/killtests-2026-11/typed/generate.json` | 691,670 | `sha256:656162c435ca4cfc345bace5bf4fe570ae5149182e765d3c19168b1f5cb973c8` | every reply, served model recorded |
| `execute.json` | `logs/killtests-2026-11/typed/execute.json` | 854,324 | `sha256:ec8b0faf71e00101ae777a70518824263475623dc2ef9adf3ff946b761b0e93b` | parsed request, validation, both compiled queries, correctness per backend |
| `score.json` | `logs/killtests-2026-11/typed/score.json` | 7,820 | `sha256:629efe70c4b42e3c647c9a67aa5a04ab410d7191b744f13eb2597c36447d99f0` | scores and paired CIs vs free arms (copied to data/metrics.json) |
| `ceiling.json` | `logs/killtests-2026-11/typed/ceiling.json` | 29,886 | `sha256:dc171c5e17e6e5b0e7874ffe28e38836fd2d27a83c90a1a14302b94ce15da2b9` | gold converted to typed requests, per question (summary copied to data/ceiling.json) |
| `gold.json` | `logs/killtests-2026-11/typed-verify/gold.json` | 1,125,894 | `sha256:ec54ca2a54486fcff2d6c49800913f1562a7db60e24560fb3e644e527dc6f544` | pre-run verification on terrorist_attack training questions (summary in data/verify.json) |
| `diff.json` | `logs/killtests-2026-11/typed-verify/diff.json` | 2,606,201 | `sha256:0e548ca6430746daa80306022ac1c8e8df3c5c906928095e68c8e6a19cb389da` | pre-run Cypher/Gremlin differential on the synthetic graph (summary in data/verify.json) |

The free-arm comparison reads `logs/killtests-2026-11/t1-models/{gemma4-31b__via_default-model,qwen38-27b__via_default-model-2}/t1/execute.json` (EXP-2026-11-003).

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
