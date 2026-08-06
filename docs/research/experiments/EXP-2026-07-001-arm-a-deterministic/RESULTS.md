# RESULTS — EXP-2026-07-001 Arm A — fully deterministic pipeline (planning, extraction, synthesis)

## 1. Headline

Correctness **0.9972** over 120 questions
(120 CORRECT / 0 PARTIAL / 0 INCORRECT),
with **0 hallucination(s)** across
0 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

This is the study's ceiling and its reproducible fallback: no model in planning, extraction, or synthesis, 120/120 CORRECT, zero hallucinations, and the whole catalogue in **1.6 seconds**.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.9972 | 1 |
| `completeness` | 1.0000 | 1 |
| `faithfulness` | 0.9993 | 1 |
| `groundedness` | 1.0000 | 1 |
| `answer_coverage` | 1.0000 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 1.6 s |
| Evidence records | 1061 |
| Related neighbours | 839 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm A is the evidence that the deterministic path is not a fallback but the ceiling. Its 1.6 s wall clock against Arm B's 1,020 s is a 637x ratio, and it is byte-reproducible, which makes it the correct CI regression gate and the correct thing to run on stage.

The caution that belongs beside it: 120/120 on a catalogue co-authored with the templates that answer it is exactly the shape a coverage artifact would take. This number does not become a paper claim until the blind holdout reports.

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

That the fully deterministic path won outright. The system is documented and framed as agentic; the arm with no model anywhere in it is the most accurate and roughly 600x the fastest.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Run this arm blind on 30 held-out questions authored by someone else. Until then 0.9972 cannot be distinguished from a coverage artifact.
* Re-run with recorded seeds so the figure carries a variance.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm deterministic --root docs/evaluation/experiments/untruncated-fixed --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-fixed
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-fixed/deterministic/answers/`](../../../evaluation/experiments/untruncated-fixed/deterministic/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).
