# POINTERS — EXP-2026-11-005

Run outputs live under `logs/killtests-2026-11/exp005/` and `logs/killtests-2026-11/t2c/` (gitignored); the small summaries are copied into this folder (`metrics.json`, `killrule.json`, `taxonomy.json`, `sensitivity.json`, `expressibility-sample.json`). Code tag `killtests-exp005-run` (aa31340c); later changes in ISSUES.md.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `run_header.json` | `logs/killtests-2026-11/exp005/run_header.json` | 2,382 | `sha256:1fe2a93e3954f908950107cc59e1979170c4a059a014819f23e6ae90c9ac5256` | model identities by token id at start and at each resume; reasoning setting; concurrency |
| `gold.json` | `logs/killtests-2026-11/t2c/gold.json` | 1,580,698 | `sha256:05bd14b5eb0a82336d72301625b9987e434d12755db1c95dc32f34390b19491f` | the 390 selected Text2Cypher questions, gold Cypher, normalised gold rows, exclusion counts |
| `A-generate.json` | `logs/killtests-2026-11/exp005/A-generate.json` | 697,002 | `sha256:9ca4e8b9e6424c6c09bf38a8703718dbbafdf8d2b399daa96d841ceec9bdf10e` | part A replies |
| `A-execute.json` | `logs/killtests-2026-11/exp005/A-execute.json` | 1,361,339 | `sha256:b0c9a6c6b40a6d0169849480221aad346c68128789c95223d41086600af40b73` | part A requests, validation, compiled queries, correctness per backend |
| `A-score.json` | `logs/killtests-2026-11/exp005/A-score.json` | 12,199 | `sha256:8c96da72774b4dd37b68971b7ecc76e276deff132a976c8f262c51d8f16b6656` | part A scores and paired CIs (in data/metrics.json) |
| `B-generate.json` | `logs/killtests-2026-11/exp005/B-generate.json` | 2,910,702 | `sha256:fe879b73cf9f73ea1997814bb8204bb237ee1bcd91505b1cdce671f4d30b07c6` | part B replies, final pass (zero errors); Qwen entries carry `reasoning_effort` |
| `B-repair.json` | `logs/killtests-2026-11/exp005/B-repair.json` | 185,360 | `sha256:02f88390a1941f8423087485d38ca7898346f83ab706823d3989a127f1269c54` | part B repair turns |
| `B-execute.json` | `logs/killtests-2026-11/exp005/B-execute.json` | 3,017,800 | `sha256:5f6e25fe31f2367d1e063746aede197a341d5f42b9d6c88c4633a4c79c7abcb6` | part B execution and correctness |
| `B-score.json` | `logs/killtests-2026-11/exp005/B-score.json` | 13,487 | `sha256:c61fa542c6c98e390e25d362ab1103adee3078d83e69192d6117ab4d328b6c0d` | part B scores, by graph and source, paired CIs (in data/metrics.json) |
| `B-sensitivity-per-key.json` | `logs/killtests-2026-11/exp005/B-sensitivity-per-key.json` | 580,537 | `sha256:fc6618fd8246edc6e9895c5f056928dc9fcc8cceb0c4a2085ab01618ad3008a5` | per-question strict / set / set_proj results (summary in data/sensitivity.json) |
| `B-generate.qwen-xhigh-archive.jsonl` | `logs/killtests-2026-11/exp005/cache/B-generate.qwen-xhigh-archive.jsonl` | 293,190 | `sha256:604335c9048bb2b77583ba7e9e8f3c32d22c5870cf38c1793861f4909ef84fb5` | the 493 Qwen part-B generations made at `xhigh` before the setting changed; not scored |

Logs of each attempt: `logs/killtests-2026-11/exp005-run.log` (first pass), `exp005-resume-c64.log`, `exp005-resume-c16-try1.log`, `exp005-resume-c16-xhigh.log`, `exp005-resume.log` (final).

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
