# RESULTS — EXP-2026-07-007 Arm G — generic primitives only, every hand-written template disabled

## 1. Headline

Correctness **0.6388** over 120 questions
(64 CORRECT / 14 PARTIAL / 42 INCORRECT),
with **7 hallucination(s)** across
7 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

The generic-primitives control. Disabling the hand-written templates costs **-0.3568** correctness — three times what LLM planning costs.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.6388 | 1 |
| `completeness` | 0.6802 | 1 |
| `faithfulness` | 0.9658 | 1 |
| `groundedness` | 0.9788 | 1 |
| `answer_coverage` | 0.8979 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 914.8 s |
| Evidence records | 252 |
| Related neighbours | 1749 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm G is the load-bearing result for the paper's positioning. Disabling every hand-written intent template and leaving only schema-driven primitives costs **-0.3568** correctness (G - F), three times the -0.1185 that LLM planning costs. The templates, not the planner, are where this system's accuracy lives.

**What Arm G is not:** it is not free-form LLM query generation. No LLM writes Cypher or Gremlin in any arm of this study. That experiment has never been run, and the literature contains no controlled head-to-head of a template library against free-form generation — which is precisely the gap this repository is positioned to fill. See `../../OPEN_QUESTIONS.md`.

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

The magnitude. Losing the templates costs three times what swapping in an LLM planner costs, which inverts the framing the repository had been carrying — the interesting engineering was assumed to be in the planner.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Build the free-form text-to-Cypher/Gremlin baseline. Arm G is a generic-primitives control, not the LLM-writes-queries comparison the paper's positioning actually needs.
* Build the merged-single-graph baseline to test the federation claim against a counterfactual.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm generic --root docs/evaluation/experiments/untruncated-generic --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-generic
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-generic/generic/answers/`](../../../evaluation/experiments/untruncated-generic/generic/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).
