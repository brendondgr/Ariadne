# POINTERS — EXP-2026-09-011

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Filled 2026-09-09 (RESULTS.md A-2); hashes are of the paths as they stand on
that date. The tree has not been written to since 2026-09-07 12:59.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Six seeded `generic` runs, graded twice | `docs/evaluation/experiments/seeded-repeats-generic-2026-09-06` | 44035878 | `sha256:388a77a687124cd23fc52eca112d20c0aab13ef5343db07aceca917ab0ffb062` | Tree. `seed-{1729,20260906,424242,31337,8675309,271828}/generic/answers/`: 284 answers each plus `*.judgment.q1.json` and `*.judgment.q2.json` (284 each, 3,408 sidecars, zero failures) and a run `manifest.json` per seed. Every block mean, balanced mean, SD and range is computed from these. `seed-1729` also holds 283 stale `*.judgment.q1.error.txt` files from a first grading attempt that hit HTTP 502 and was retried (ISSUES.md); no number reads them. |
| Question bank | `docs/evaluation/composition/bank/bank-dev.json` | 573495 | `sha256:a4ca6702029cae7784574b0307b9f76d4718a039f3254f2c0ff708a2fa1a4119` | The 284-question dev half; hash asserted in pre-flight (`data/run-state.json`). |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
