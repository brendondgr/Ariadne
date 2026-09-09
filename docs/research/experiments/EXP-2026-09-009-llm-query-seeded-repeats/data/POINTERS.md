# POINTERS — EXP-2026-09-009

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Filled 2026-09-09 (RESULTS.md A-1); hashes are of the paths as they stand on
that date.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Three seeded `llm_query` runs, graded | `docs/evaluation/experiments/seeded-repeats-2026-09-06` | 6447825 | `sha256:7d3ff28d0a93ef473af3d3197a3c2a1c427e38a134d56d940aa2ae025b0252e4` | Tree. `seed-{1729,20260906,424242}/llm_query/answers/`: 284 answers each, plus `*.judgment.q.json` (qwen38-27B-v2; 284 / 284 / 283 — seed 424242 has one `*.judgment.q.error.txt`, the disclosed grading failure) and `*.judgment.g31.json` (gemma4-31B-mtp; 284 each), and a run `manifest.json` per seed. Every per-seed mean, family SD and the balanced SD are computed from these. Nothing here was written after 2026-09-06 22:22. |
| Question bank | `docs/evaluation/composition/bank/bank-dev.json` | 573495 | `sha256:a4ca6702029cae7784574b0307b9f76d4718a039f3254f2c0ff708a2fa1a4119` | The 284-question dev half; its hash is asserted in pre-flight (`data/run-state.json`). |
| Reference arm, `deterministic` | `docs/evaluation/experiments/post-repair-2026-09-03/deterministic/answers` | 24872613 | `sha256:e3db4bb1c730efd64183249f8ac4d849d1777a1c026b5573e45208ea4f46440f` | Tree. The recorded `deterministic` run on the same bank. The qwen reference 0.4924 is the mean of `*.judgment.json` (position 0); the gemma reference 0.4169 ± 0.0033 is over the ten `*.judgment.gemma*.json` passes. The directory carries more sidecars than this experiment reads (`.pass2`, `.gemma_r3`…`.gemma_r10`, written by later grading passes); the answer files are unchanged since 2026-09-03. See A-2. |
| Reference arm, `generic` | `docs/evaluation/experiments/post-repair-2026-09-03/generic/answers` | 9286482 | `sha256:3863fe3a81521bd5e3bbfc4d5f45ba6de6f6e2e9572e15e0cb54ad279cb6efd5` | Tree. Same as above for `generic`: 0.6600 from `*.judgment.json`, 0.6698 ± 0.0084 over nine `*.judgment.gemma*.json` passes. |
| Holdout cross-check | `docs/evaluation/experiments/holdout-spend-2026-09-05/llm_query` | 5304134 | `sha256:52adf468d385a8fb0ba4d27f3b1dbf168baaa4602549426f965e3b70d61e2fd5` | Tree. Read once, for §"What the mechanism does not explain" (holdout abstention rate, gemma mean on abstentions, 13 distinct values). EXP-2026-09-007's artifact; pointed here because a figure in this RESULTS was computed from it. |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
