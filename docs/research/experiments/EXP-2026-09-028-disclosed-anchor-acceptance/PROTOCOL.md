# PROTOCOL — EXP-2026-09-028 A described entity is resolved from a reranked list, and the answer says so

> Written 2026-09-15, before any run of this experiment. Plan:
> [`docs/plans/2026-09-15-open-question-correctness.md`](../../../plans/2026-09-15-open-question-correctness.md),
> Step 9. Control is `EXP-2026-09-025`'s `form_execute` arm on both banks.

## Question

At T4 (paraphrased name) and T5 (description only) the shipped tree answers
nothing: the gold entity is in the name index's top five for 0.62 / 0.83 of
questions, D-034 let the model choose it and paid `wrong_entity` ≈ 0.30, and
D-035 refuses the model's choice. Does choosing from a **reranked** list, with
the model's own "none of these" available, and **disclosing** the resolution
on the answer's first line, recover T4/T5 answers at a wrong-entity rate the
analyst can live with — visible and correctable rather than silent?

## Hypothesis

**H1.** `disclosed` vs `form_execute`: on the sealed bank (the calibration
bank for this step, opened once) T4 and T5 `records_exact` ≥ **0.30** with
`wrong_entity` ≤ **0.15**, T6 (invented anchors) accepting nothing wrong
(`wrong_entity` ≤ 0.10); T3 unchanged (the reranker stands down on an exact
name). The exposed bank is reported beside it with the same lines.

**Falsifier:** `wrong_entity` above 0.15 at T4 or T5, or T6 above 0.10 — the
rung then ships as a clarification ("did you mean X or Y?"), not as an
answer; that variant is plan Step 10's to build, not this experiment's.

## Setup

Reranker: `BAAI/bge-small-en-v1.5` through FastEmbed (`ARIADNE_RERANK=1`,
pool 25 → top 5), in-process when importable, else through the evaluation
venv's interpreter over a pipe (the weights are cached there). The large model
the August probe preferred needs a download the operator has not approved and
is not used. Acceptance: the existing closed-choice rung with its `ambiguous`
flag; a model-chosen anchor stands only under `ARIADNE_ANCHOR_DISCLOSED=1`
and is written into the answer's first claim and headline. 32 workers, 600 s
budgets, both banks.

## Data

Exposed bank (579), sealed bank (160).

## Metrics

As `EXP-2026-09-023`; plus the count of answers carrying a disclosure and, of
those, how many are exact / wrong. **Primary:** T4 `records_exact`, sealed,
`disclosed` arm.

## Procedure

```bash
T="--llm-timeout-s 600 --pipeline-timeout-s 600 --workers 32 --reference reference.json"
uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-holdout-2026-09 --rewrite disclosed $T --name scored_disclosed.json
uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-2026-09-15 --rewrite disclosed $T --name scored_disclosed.json
uv run python docs/research/experiments/EXP-2026-09-028-disclosed-anchor-acceptance/data/report.py
```

## What would falsify this

- `wrong_entity` > 0.15 at T4 or T5, or T6 `wrong_entity` > 0.10, on the sealed bank.
- T3 moving by more than ± 0.02 — the reranker did not stand down on exact names.
