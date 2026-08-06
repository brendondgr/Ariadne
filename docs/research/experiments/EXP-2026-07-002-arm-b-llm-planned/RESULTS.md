# RESULTS — EXP-2026-07-002 Arm B — LLM planning with deterministic extraction and an LLM writer

## 1. Headline

Correctness **0.8505** over 120 questions
(92 CORRECT / 14 PARTIAL / 14 INCORRECT),
with **12 hallucination(s)** across
8 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

The LLM-planned arm, and the study's central regression. Identical extraction and synthesis to Arm C — only the planner changes — for **-0.1185** correctness.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.8505 | 1 |
| `completeness` | 0.8692 | 1 |
| `faithfulness` | 0.9683 | 1 |
| `groundedness` | 0.9750 | 1 |
| `answer_coverage` | 0.8074 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 1019.7 s |
| Evidence records | 2814 |
| Related neighbours | 621 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm B minus Arm C is the study's cleanest contrast — same extraction, same synthesis, only the planner differs — and it is **-0.1185** correctness. Failure localisation shows *where*: only 2 of Arm B's 36 failures were faithfulness, and 26 of 36 were planning or retrieval. LLM answers here do not fail by making things up; they fail by asking the wrong question.

Arm B also retrieves 2,814 records to Arm F's 1,080 and surfaces 20% less of the gold. Precision in planning beat volume in retrieval throughout.

## 5. Threats to validity

Shared across every arm of this study:

* **All 120 questions are anchored.** Every one names an entity or an id.
  Nothing here measures open-ended analyst questions, which is exactly where a
  template router is weakest.
* **The catalogue was co-authored with the system.** Each question ships an
  `expected_template`, and the questions were written commit-for-commit with the
  templates that answer them. There is **no holdout**. This is the single
  largest threat to the headline number and it is unresolved.
* **The gold set is small and fixed.** 120 questions, categories of 1–10
  members, so one case moves a category mean substantially.
* **No baseline exists.** Not one alternative system was implemented, so no arm
  here has ever been contrasted with a counterfactual.
* **The judge is a model.** Cross-model and evidence-grounded, but still an LLM,
  and its verdicts are not perfectly stable across runs. It occasionally
  penalised correct answers over citation metadata.
* **One run, one model, one day.** `n_runs: 1`, seeds unrecorded, and everything
  ran against one served model (`skynet` = Gemma 4 31B) whose quantisation and
  context window are unrecorded. Nothing generalises to other models without
  re-running.

## 6. What surprised us

That the failures were not hallucinations. The intuition going in was that an LLM-planned arm fails by inventing facts; failure localisation showed 26 of 36 failures were planning or retrieval and only 2 were faithfulness.

The single largest cause was mechanical rather than cognitive: the planner emitted the plan-level join correctly but left each sub-question's own `join_key` null, and the router keys on the sub-question's field. Two representations of the same fact disagreed, and 19 of 36 failures followed.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Route on the sub-question's declared `entities` rather than surface phrasing, so single-source questions stop downgrading to `describe`.
* Raise or parallelise the stage deadline — 6 of 120 LLM-arm questions finish `partial` on the timeout.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm llm --root docs/evaluation/experiments/untruncated-fixed --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-fixed
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-fixed/llm/answers/`](../../../evaluation/experiments/untruncated-fixed/llm/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).
