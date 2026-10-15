# Judging harnesses

Workflow scripts that grade saved answers with independent model judges, one
agent per question. They are run through a multi-agent workflow runner, not
through `uv run`, and each file's header comment gives its arguments.

| Script | Grades |
|---|---|
| `judge_workflow.mjs` | The golden-catalogue answers in `docs/evaluation/answers/` |
| `judge_untruncated.mjs` | The un-truncated retrieval arms |
| `judge_holdout.mjs` | The blind holdout runs (derived from `judge_untruncated.mjs`) |
| `author_holdout.mjs` | Not a grader: writes the blind holdout questions, one fresh agent per anchor |

Until 2026-10-15 these lived in a top-level `scratchpad/` folder. Completed
experiment protocols under `docs/research/experiments/` and the dated audits
still cite them at that old path; the files are unchanged apart from one
comment in `judge_holdout.mjs` that names its source.
