# Overnight 2026-09-04 — two tracks, two graders

Started None. Gemma deadline 08:30.

| arm | grader | cases | judgments | mean correctness |
|---|---|---:|---:|---:|
| deterministic | qwen | 284 | 568 | 0.4946 |
| deterministic | gemma | 284 | 568 | 0.4175 |
| generic | qwen | 284 | 568 | 0.6569 |
| generic | gemma | 284 | 568 | 0.6659 |
| llm_query | qwen | 284 | 519 | 0.3842 |
| llm_query | gemma | 0 | 0 | None |

## What did not run

- **A4-gemma-judge-llm-query** — not_run: past the 08:30 gemma deadline
- **F-rollup** — running: 

## The holdout

Not touched. Asserted at preflight by bank hash and by checking that no answered case id belongs to the holdout split. It stays sealed for a three-arm spend once the query-writing arm is settled.
