# PROTOCOL — EXP-2026-09-025 Execute the form, do not re-parse its rendering

> Written 2026-09-15, before any run of this experiment. Plan:
> [`docs/plans/2026-09-15-open-question-correctness.md`](../../../plans/2026-09-15-open-question-correctness.md),
> Step 6. Control is `EXP-2026-09-023`'s `anchor_first` arm on both banks.

## Question

The rewrite stage fills a form and then renders it to an English sentence
for the drafter's word-router to parse again. Does executing the bound form
directly as a plan — anchor id in the text, anchor label / relation / target
labels in `entities`, the declared join for a second source — remove the
answers the round trip breaks, and does it then make it safe to run the
stage on identifier-bearing questions (lifting the D-034 skip) with the
anchor fixed by D-035?

## Hypothesis

**H1 (round trip).** `form_execute` vs `anchor_first`, exposed bank: T3
`records_exact` rises by **≥ 0.05** (paired: fixed − broken ≥ 5) with
`wrong_entity` and `catalogue_dump` unchanged and T1/T2 byte-identical (the
identifier skip still holds, so no id-bearing question reaches the stage).
Sealed bank: the three T3 answers `EXP-2026-09-023` recorded as broken by the
deterministic rung's rendering ("Putter Panda", "Tonto Team", "Storm-0501")
are recovered; T3 `records_exact` ≥ the sealed control.

**H2 (identifier skip lifted).** `form_execute_ids` vs `form_execute`,
exposed bank: T1 and T2 `records_exact` **not below control − 0.02** (the
D-034 not-worse-than-baseline rule) and `records_recall` up by ≥ 0.05, with
`wrong_entity` unchanged — because the anchor is an exact-id bind the model
cannot touch and the relation it fills is executed, not rendered.

## Setup

One tree; arms differ by `ARIADNE_FORM_EXECUTE` and, for H2,
`ARIADNE_REWRITE_ONLY_WITHOUT_ID`. All other flags as `anchor_first`.
32 workers, 600 s budgets, the same references.

## Data

Exposed bank (579) and sealed bank (160).

## Metrics

As `EXP-2026-09-023`; paired fixed/broken per tier. **Primary:** T3
`records_exact`, exposed bank, `form_execute` arm.

## Baselines

`scored_anchor_first.json` on both banks (EXP-2026-09-023).

## Procedure

```bash
T="--llm-timeout-s 600 --pipeline-timeout-s 600 --workers 32 --reference reference.json"
for arm in form_execute form_execute_ids; do
  uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-holdout-2026-09 --rewrite $arm $T --name scored_$arm.json
  uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-2026-09-15 --rewrite $arm $T --name scored_$arm.json
done
uv run python docs/research/experiments/EXP-2026-09-025-direct-form-execution/data/report.py
```

## What would falsify this

- **H1**: T3 exact not up by 0.05, or any rise in `wrong_entity` or
  `catalogue_dump` — then the round trip was not the loss and the deterministic
  rung's *form* is wrong (a card-vocabulary relation the question did not
  ask for), which is a Step 8 problem.
- **H2**: T1 or T2 `records_exact` below control − 0.02 — then the identifier
  skip stays and only questions without an identifier execute their form.

## Amendment before the run (2026-09-15, after a three-question smoke test, before any bank was scored)

The smoke test showed "What malware and tools does the Putter Panda threat
group use?" executing as a *describe*: the intent classifier calls an
identifier-bearing question a lookup, `_mode_for` projects that to describe,
and a describe form needs no relation, so it bound without one and the model
rung never ran. Direct execution cannot fix a form whose mode is wrong. So
`deterministic_fill` now sets `mode = enumerate` when the router matched a
target label other than the anchor's in the question's own words and the
phrasing is not definitional (`sources[mode] = "relation-in-question"`); the
relation itself may stay unbound ("use" does not stem to `USES`) and is then
the model rung's to fill, with the anchor held by D-035. This is part of
the `form_execute` arms as run; the bank results below include it. It is a
change to the *form*, made from a smoke test, and is disclosed here rather
than folded in silently.
