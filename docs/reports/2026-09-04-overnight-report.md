# Overnight 2026-09-04 — two tracks, two graders

Started None. Gemma deadline 08:30.

| arm | grader | cases | judgments | mean correctness |
|---|---|---:|---:|---:|
| deterministic | qwen | 284 | 568 | 0.4946 |
| deterministic | gemma | 284 | 568 | 0.4175 |
| generic | qwen | 284 | 568 | 0.6569 |
| generic | gemma | 284 | 568 | 0.6659 |
| llm_query | qwen | 0 | 0 | None |
| llm_query | gemma | 0 | 0 | None |

## What did not run

- **A2-llm-query-rerun** — failed: TimeoutExpired: Command '['uv', 'run', 'python', '-m', 'utils.evaluation.experiment_untruncated', '--arm', 'llm_query', '--bank', '/home/bdgr/Agents/Ariadne/docs/evaluation/composition/bank/bank-dev.json', '--root', '/home/bdgr/Agents/Ariadne/docs/evaluation/experiments/llm-query-fair-2026-09-04', '--llm-max-tokens', '16384', '--workers', '8']' timed out after 9000.0 seconds
- **A3-judge-llm-query** — not_run: prerequisite A2-llm-query-rerun did not complete
- **A4-gemma-judge-llm-query** — not_run: prerequisite A2-llm-query-rerun did not complete
- **F-rollup** — running: 

## The holdout

Not touched. Asserted at preflight by bank hash and by checking that no answered case id belongs to the holdout split. It stays sealed for a three-arm spend once the query-writing arm is settled.
