# Protocol — EXP-2026-09-020

## The question

Should the shipped workbench swap its query-construction engine?

`EXP-2026-09-018` answered a neighbouring question — templates against
schema-derived primitives — and the primitives won by 0.3480 judged on a sealed
set. That comparison replayed a human-authored plan. `app.py` does not:
`api/services/query.py` calls `iter_pipeline`, so the planner executes. The
decision therefore rests on a cell no arm on record occupies.

## Design

A 2×2, both factors crossed, all four cells on one tree.

| | authored plan | real planner |
|---|---|---|
| templates | `deterministic` | `deterministic_planned` *(new)* |
| primitives | `generic_composed` | `generic_planned` |

`deterministic_planned` is `generic_planned` with `SPECIALIST_GENERIC_ONLY`
inverted and nothing else changed. Both drive `run_planned`, so both execute the
planner for real and both resolve `SynthesisConfig` by the same route — the
confound `EXP-2026-09-019` `I-8` caught between gold-replay and real-pipeline
arms cannot appear between them.

The flag is stated `false` rather than omitted. Omitting it would let a stray
`SPECIALIST_GENERIC_ONLY` in the environment turn the arm into `generic_planned`
and report a difference of exactly zero — a failure that looks like a result.

## Metric

Deterministic gold coverage (`deterministic_scores.coverage`), paired per
question. Chosen because every cell is model-free and byte-reproducible, so a
difference cannot be grading noise or run variance, and a 284-question 2×2 costs
seconds rather than the hours a judged pass costs. It measures **retrieval, not
judged correctness**, and the write-up says so wherever the figure appears.

Separability: `|difference| > 2·SE`.

## Pre-registered reading

- **Engine effect** = primitives − templates, computed at each plan source
  separately. The right-hand column is the one that speaks to `app.py`.
- **Plan effect** = real planner − authored plan, computed for each engine.
- **Interaction** = engine effect at the real planner − engine effect at the
  authored plan. A near-zero interaction would mean the published comparison
  transfers to production; a large one would mean it does not.

## Hypothesis, stated before the run

The engine advantage narrows under a real planner but stays positive and
separable, because the engine comparison holds plan source constant on both
sides.

## What would falsify a swap recommendation

Any of: the engine effect at the real planner not separable from zero; the
primitive cell returning more zero-record answers than the template cell; or the
effect changing sign across question tiers.

## Guards

- All four cells on one tree, run back to back — `EXP-2026-09-018` I-8 and the
  "one tree per comparison" rule.
- `ORCH_MAX_HOPS=5` explicitly, because the committed `.env` pins it to 1 and
  every arm on record used 5.
- Verified before spending the bank: the new arm emits only hand-written
  template identifiers and its `run_meta` carries an `observed_plan` with the
  planner's own limits rather than a replayed one.
