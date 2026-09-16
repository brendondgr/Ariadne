# PROTOCOL — EXP-2026-09-024 Expand the anchor's neighbourhood when the relation is unbound

> Written 2026-09-15, before any run of this experiment. Plan:
> [`docs/plans/2026-09-15-open-question-correctness.md`](../../../plans/2026-09-15-open-question-correctness.md),
> Step 5. Baseline is `EXP-2026-09-023`'s `anchor_first` arm on both banks.

## Question

When the anchor binds and the question's words match no relation the card
carries — "How do I defend against T1047?", "What methods does G0016 rely
on?" — the shipped tree answers with the anchor's one record (a describe) and
scores a 1-record answer against a 5- or 17-record gold. Does expanding the
anchor's **smallest non-zero facets** instead, on the first re-plan only,
bounded, raise T1/T2 recall without turning answers into catalogue dumps?

## Hypothesis

**H1.** With `ORCH_EXPAND_UNBOUND=1` on top of the `anchor_first`
configuration, on the exposed bank: T1 and T2 `records_recall` rise from
0.5060 / 0.4838 to **≥ 0.75**; T1/T2 `records_exact` stay within **± 0.02**
(the expansion is a superset, not a different answer); `catalogue_dump` on
every tier stays **≤ baseline + 0.02**; `wrong_entity` unchanged (the anchor
is not touched). On the sealed bank, whose variants are T3–T6 only, T3 recall
rises and no tier's dump rate rises by more than 0.02.

The mechanism is deterministic and reads only the registry's facet block
(counts per `(relation, direction, label)` of the anchor), so nothing in it
names a catalogue.

## Setup

One tree. `anchor_first` (control) vs `expand_unbound` (treatment): identical
except `ORCH_EXPAND_UNBOUND=1` (and `ORCH_CHASE_FACETS=true`, which the
control also inherits from `.env`). Fallback parameters fixed a priori:
`ORCH_MAX_FACET_EXPANSIONS=4` facets per re-plan, first re-plan only, facets
of at most `ORCH_EXPAND_UNBOUND_MAX_MEMBERS=50` members, smallest first,
never on a definitional request. 32 workers, 600 s budgets, the same
references as `EXP-2026-09-023`.

## Data

Exposed bank (579) and sealed bank (160), as in `EXP-2026-09-023`.

## Metrics

As `EXP-2026-09-023`: `records_exact`, `records_recall`, recall excluding
dumps, `abstained`, `wrong_entity`, `catalogue_dump` per tier; paired
fixed/broken and recall deltas per variant. **Primary:** T1 `records_recall`
on the exposed bank.

## Baselines

`scored_anchor_first.json` on both banks (EXP-2026-09-023).

## Procedure

```bash
T="--llm-timeout-s 600 --pipeline-timeout-s 600 --workers 32 --reference reference.json"
uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-2026-09-15 --rewrite expand_unbound $T --name scored_expand_unbound.json
uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-holdout-2026-09 --rewrite expand_unbound $T --name scored_expand_unbound.json
uv run python docs/research/experiments/EXP-2026-09-024-expand-on-unbound-relation/data/report.py
```

## What would falsify this

- Any tier's `catalogue_dump` above baseline + 0.02 — the bound is wrong, and
  the step stops rather than tunes it.
- T1 or T2 `records_exact` falling by more than 0.02 — the expansion changed
  answers it should only have widened.
- T1/T2 recall below 0.75 with dumps flat means the 50-member cap excludes
  the facets that carry the gold; that is recorded as a partial result with
  the excluded facet sizes, not re-run with a larger cap.
