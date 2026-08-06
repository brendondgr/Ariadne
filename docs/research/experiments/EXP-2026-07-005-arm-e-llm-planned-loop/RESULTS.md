# RESULTS — EXP-2026-07-005 Arm E — LLM planning with the facet-chasing retrieval loop enabled

## 1. Headline

Correctness **0.8560** over 120 questions
(97 CORRECT / 7 PARTIAL / 16 INCORRECT),
with **15 hallucination(s)** across
9 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

LLM planning with the facet-chasing loop actually chasing something. The loop compensates for weak planning; it does not replace it.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.8560 | 1 |
| `completeness` | 0.8877 | 1 |
| `faithfulness` | 0.9575 | 1 |
| `groundedness` | 0.9729 | 1 |
| `answer_coverage` | 0.8819 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 1043.1 s |
| Evidence records | 3449 |
| Related neighbours | 2000 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm E measures the retrieval loop on top of a *weak* plan. Against Arm B it is roughly neutral — 0.8505 to 0.8560 — buying completeness and costing faithfulness, while retrieving 3,449 records, the most of any arm.

Read against Arm F (same loop, authored plan, 0.9957) the conclusion is sharp: the loop's value is a function of plan quality. It compensates for weak planning at considerable cost; it does not substitute for good planning.

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

That more retrieval made things worse. Arm E pulls 3,449 evidence records — 3.2x Arm F — and scores 0.14 lower. Volume is not the lever.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Quantify the loop's cost/benefit separately from plan quality by running it against a mid-quality plan, not just the best and worst.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm llm_loop --root docs/evaluation/experiments/untruncated-loop2 --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-loop2
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-loop2/llm_loop/answers/`](../../../evaluation/experiments/untruncated-loop2/llm_loop/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).
