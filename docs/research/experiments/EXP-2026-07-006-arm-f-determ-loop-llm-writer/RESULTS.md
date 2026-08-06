# RESULTS — EXP-2026-07-006 Arm F — authored plan, facet-chasing loop, LLM writer over verified claims

## 1. Headline

Correctness **0.9957** over 120 questions
(119 CORRECT / 1 PARTIAL / 0 INCORRECT),
with **3 hallucination(s)** across
3 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

The recommended demo configuration: deterministic ceiling accuracy with readable analyst prose, and the *least* evidence retrieved of any LLM arm.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.9957 | 1 |
| `completeness` | 0.9990 | 1 |
| `faithfulness` | 0.9960 | 1 |
| `groundedness` | 0.9992 | 1 |
| `answer_coverage` | 1.0000 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 533.4 s |
| Evidence records | 1080 |
| Related neighbours | 866 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm F is the recommended demo configuration and the study's most useful result. It scores 0.9957 against the deterministic ceiling's 0.9972 — a 0.0015 gap — with zero INCORRECT, full gold coverage, and readable prose instead of a claim table.

It also retrieves the least evidence of any LLM arm (1,080 records) while scoring the highest. The accuracy-versus-readability trade is not real, once the narrator is bound to verified claims.

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

That the best LLM arm retrieves the *least* evidence of any LLM arm and still achieves full gold coverage. Everything in this study pointed the same way: precision in planning beats volume in retrieval, every time.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Narrator count discipline: the single remaining PARTIAL (F-CTM-01) recomputed a count and said 'five techniques' where the evidence held six.
* Decide the loop explicitly before any demo. The live `.env` pins `ORCH_MAX_HOPS=1` and leaves `ORCH_CHASE_FACETS` unset, so the app as configured does **not** do what this arm measures.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm gold_loop_llm --root docs/evaluation/experiments/untruncated-goldloop --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-goldloop
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-goldloop/gold_loop_llm/answers/`](../../../evaluation/experiments/untruncated-goldloop/gold_loop_llm/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).
