# PROTOCOL — EXP-2026-07-004 Arm D — authored plan with an LLM writer reading verified claims

> **Back-filled 2026-08-06.** This protocol was written *after* the run, from
> the study's recorded method. It is a reconstruction, not a pre-registration,
> and it is marked as such because the difference matters: nothing here
> constrained the run that produced the numbers. Future arms must have a real
> protocol written first.

## Question

With the other two stages held fixed, what does this configuration —
plan: **authored gold replay**, extract: **deterministic templates**, synthesize: **LLM over verified claims** — score on the
120-question golden catalogue against the live ATT&CK and CAPEC graphs?

## Hypothesis

Exploratory. The study is a factorial comparison; no per-arm prediction was
registered, and inventing one now would be dishonest.

## Setup

One of seven arms (plus the Arm G control) over three independent variables:

* **Plan** — the catalogue's authored plan (correct seeding, zero variance) versus
  an LLM planner working from raw question text.
* **Extract** — deterministic template router, optionally with the facet-chasing
  retrieval loop.
* **Synthesize** — deterministic composer, LLM narrator over raw evidence, or LLM
  narrator over verified claims.

Every arm runs under the **un-truncation profile**, which lifts each retrieval,
synthesis-evidence, and judge-artifact bound. Its env keys default to the
committed values, so a normal run is unaffected. This arm's overlay is
`untruncated_env(arm="gold_llm")` in
`utils/evaluation/experiment_untruncated.py`.

## Data

The 120-question golden catalogue, all questions, fixed order. Every question is
anchored — it names an entity or an id — and each ships an `expected_template`
field. See [`../../datasets/cards/golden-catalogue-120.md`](../../datasets/cards/golden-catalogue-120.md)
for provenance and the coverage limitation this implies.

## Metrics

Each answer is graded by **one independent Sonnet 5 agent** against the
question's gold assertions *and* its full retrieved evidence. Cross-model on
purpose: the pipeline's own model must not grade its own output.

| Metric | What it computes |
|---|---|
| `correctness` | Mean over 120 of the judge's correctness score; the primary metric. |
| `completeness` | Whether the answer covers every gold assertion. |
| `faithfulness` | Whether each stated claim follows from the retrieved evidence. |
| `groundedness` | Whether each claim carries a citation to a retrieved record. |
| `answer_coverage` | Deterministic, not judged: the fraction of gold surfaced by retrieval. |

Reported alongside, from the same artifacts: CORRECT/PARTIAL/INCORRECT verdict
counts, hallucination count and the number of answers carrying one, evidence
volume, and wall clock.

Failure localisation uses `utils/evaluation/failure_terminus.py`, which
classifies each graded case by the last stage at which the gold answer was still
recoverable — computed from the artifacts, not from judge prose.

## Baselines

**None.** No alternative system was implemented or run, so this arm is compared
only against the other arms of the same system. That is a real limitation of the
whole study and is recorded in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md),
not glossed here.

## Procedure

```bash
# 0. Fixtures must be live and non-empty
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin

# 1. Run this arm
uv run python -m utils.evaluation.experiment_untruncated \
  --arm gold_llm --root docs/evaluation/experiments/untruncated-claimnarr --workers 4

# 2. Judge — 120 independent Sonnet agents, one per question
#    scratchpad/judge_untruncated.mjs via the Workflow tool

# 3. Localise failures, then roll up
uv run python -m utils.evaluation.failure_terminus --root docs/evaluation/experiments/untruncated-claimnarr --arms gold_llm
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-claimnarr
```

## What would falsify this

For the study as a whole: if the deterministic arms failed to beat the
LLM-planned arms, or if disabling the templates (Arm G) cost less than swapping
in LLM planning (Arm B), the claim that accuracy lives in the templates would
not survive. Both contrasts came out the other way.
