# Evaluation — Index

Ariadne carries several evaluation reports written at different times against
different configurations. This file says which is which, so no number gets
quoted out of the run that produced it.

## Current

| Report | What it measures | How to regenerate |
|---|---|---|
| [`2026-07-26/README.md`](2026-07-26/README.md) | **The standing record.** Seven full runs over the 120-question catalogue, each answer graded by an independent Sonnet 5 agent. Deterministic planning + deterministic synthesis (Arm A) scores 0.9972 / 120 CORRECT / zero hallucinations; LLM planning is the largest single regression. Also lists the eight defects found and fixed, and the limitations. | `utils/evaluation/experiment_untruncated.py` per arm, then the judge workflow — see §6 of that file |
| [`2026-07-26/portability.md`](2026-07-26/portability.md) | What survives a dataset that isn't MITRE: which layers are schema-agnostic and which of the 24 query templates are MITRE-specific. | Audit, not a run |
| [`component-evaluation.md`](component-evaluation.md) / `.json` | Planner (source selection, sub-question quality, schema adherence) and specialists (query validity, execution accuracy vs snapshot gold, safety adherence, latency). Deterministic; no LLM judge. | `uv run main.py --component-eval` |
| [`e2e-evaluation.md`](e2e-evaluation.md) / `.json` | The four `goals.md` end-to-end metrics — cross-source answer accuracy, CAPEC→ATT&CK mapping recall, provenance correctness, analyst inspectability — plus the opt-in LLM judge. | `uv run main.py --e2e-eval [--judge]` |
| [`answers/`](answers/) | The 120 saved end-to-end answers and their judgments backing `e2e-evaluation.md`. | `uv run main.py --e2e-generate` |
| [`experiments/`](experiments/README.md) | Per-question answer + evidence + verdict artifacts for each arm of the 2026-07-26 study. | See that index |

## Superseded

| Report | Status |
|---|---|
| [`archive/independent-eval.md`](archive/independent-eval.md) | The first independent cross-model grading pass — 0.8946 correctness, 91/27/2, 11 answers with hallucinations. This is the **"Committed baseline" row** of the 2026-07-26 table: the "before" the eight defect fixes were applied to. Its numbers are historically correct and currently obsolete. |
| [`archive/independent-eval-analysis.md`](archive/independent-eval-analysis.md) | The failure analysis that produced the four fixes merged in `df700ee`. All four shipped. |

## Not committed

`docs/evaluation/golden/` is git-ignored run output from the decoupled
run → judge → report harness (`uv run main.py --golden-eval`). It grades a
different configuration from everything above — the **agentic** path, where the
LLM plans from raw question text and a local LLM grades correctness — so its
lower pass rate is measuring the LLM-planned arm, not the deterministic one, and
is consistent with the 2026-07-26 finding rather than in tension with it.
Regenerate it rather than citing a stale copy.

## Reading rule

When quoting a figure, name the arm and the run. The single most common error in
this repository's history was mixing two judge runs: a −0.196 planning delta
computed before the defect fixes was quoted beside a post-fix arm table that
gives −0.1185. Both were faithfully recorded; neither was labelled with its run.
