# RESULTS — EXP-2026-07-004 Arm D — authored plan with an LLM writer reading verified claims

## 1. Headline

Correctness **0.9917** over 120 questions
(119 CORRECT / 0 PARTIAL / 1 INCORRECT),
with **1 hallucination(s)** across
1 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

Authored plan with the LLM writing over *verified claims* rather than raw evidence. The change that made an LLM writer nearly free.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.9917 | 1 |
| `completeness` | 0.9958 | 1 |
| `faithfulness` | 0.9936 | 1 |
| `groundedness` | 0.9975 | 1 |
| `answer_coverage` | 1.0000 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 501.0 s |
| Evidence records | 1061 |
| Related neighbours | 839 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm D isolates the claims-narrator switch: the LLM writes prose over the verified claim set instead of re-reading raw evidence. Correctness 0.9917 with a single INCORRECT and one hallucination, against Arm C's 0.9690 with eight PARTIAL.

This is the change that made the accuracy-versus-readability trade disappear. Binding the narrator to verified claims removes its opportunity to re-interpret evidence, which is where Arm C's PARTIALs came from.

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

How much of the LLM writer's error was avoidable by changing what it reads rather than how it is prompted. Same model, same evidence upstream, eight PARTIALs to zero.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Determine whether the claims-narrator gain holds on a model other than Gemma 4 31B. One model, one day.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm gold_llm --root docs/evaluation/experiments/untruncated-claimnarr --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-claimnarr
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-claimnarr/gold_llm/answers/`](../../../evaluation/experiments/untruncated-claimnarr/gold_llm/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).
