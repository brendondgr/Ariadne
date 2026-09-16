# PROTOCOL — EXP-2026-09-023 Anchor hygiene and Q59: exact names that are lookups, and looking them up first

> Written 2026-09-15, before any run of this experiment. Plan:
> [`docs/plans/2026-09-15-open-question-correctness.md`](../../../plans/2026-09-15-open-question-correctness.md),
> Steps 2–4. The bank it confirms on was sealed in Step 1
> (`docs/evaluation/variants-holdout-2026-09/SEAL.md`) before this file was written.

## Question

Two deterministic changes to how a question's **anchor entity** is bound, both
reading only the graph's own records and the source cards:

1. **Hygiene.** When a complete entity name occurs in the question, is it
   evidence that the analyst named that entity — or is it an ordinary word that
   happens to be a node's name? Can a rule computed from the corpus alone
   (nothing catalogue-specific) tell the two apart without losing the genuine
   binds at T3?
2. **Q59.** When the name *is* a lookup, does binding it **before** choosing
   the dataset — instead of after, as `deterministic_fill` does today — recover
   the T3 questions that currently reach no anchor because the router could not
   pick a source from the question's other words?

## Hypothesis

**Step 0 (recorded, not hypothesised).** The review of `EXP-2026-09-022` on
2026-09-15 measured, in a scratchpad, that the shipped name index
(`utils/specialists/schema/namesearch.search_in`) beats that experiment's pooled
discovery arm at every candidate budget of five or more on T4/T5, on identical
gold groups; and that the shipped exact-name matcher, run across both sources,
binds a single wrong name on 28 T4 and 26 T5 questions, of which 27 are one
node named "Credentials". Those numbers are re-derived here by
`data/shipped_vs_prototype.py` so they exist in the record. They motivate H1
and H2; they are not results of this experiment.

**H1 (distinctiveness).** A single-token exact name whose token appears in more
than **1 %** of the corpus's own documents is an ordinary word, not a lookup.
Applied to `exact_name_matches`, the rule keeps every T3 gold bind on the
exposed bank (60/60 measured during the review, so this is confirmation on the
exposed bank and the real test is the sealed one) and removes at least 60 % of
the single wrong binds at T4/T5 and at least 7 of the 9 at T6. **On the sealed
bank**: T3 gold-bind loss ≤ 2 % of T3 questions; single wrong binds at T4/T5
reduced by ≥ 60 %; T6 binds ≤ 2 of 40. *The 1 % value was read off the exposed
bank during the review and is fixed here; it is not moved to pass.*

**H2 (anchor before routing, with a tie-break).** Looking an exact name up
across every live source before dataset selection, with the router's own
selection as the tie-break when the same name exists in more than one source,
takes T3 `skipped_unresolved_anchor` on the exposed bank from 37 to ≤ 15 and T3
`records_exact` from 0.3267 to ≥ 0.45, leaves T1/T2 unchanged, holds T6
`wrong_entity` ≤ 0.0667 and T4/T5 `wrong_entity` at or below the D-035 values
(0.1442 / 0.1346) because H1 runs first. **On the sealed bank**: T3
`records_exact` at least 0.10 above the sealed baseline; T6 `wrong_entity` ≤
0.05.

## Setup

One tree per comparison (`ariadne-one-tree-per-comparison`). Every arm runs
through `scripts/variant_harness.py compare` with the shipped rewrite
configuration (`--rewrite model_noid_anchored`, i.e. D-034 + D-035) so the only
difference between arms is the flag under test:

| Arm | `ARIADNE_EXACT_NAME_DISTINCT` | `ARIADNE_ANCHOR_BEFORE_ROUTING` | tests |
|---|---|---|---|
| `baseline` | 0 | 0 | the shipped tree |
| `distinct` | 1 | 0 | H1 |
| `anchor_first` | 1 | 1 | H2 (on top of H1) |

Held constant: the reference captures, both banks, `ORCH_MAX_HOPS=5`, 32
workers, the graph snapshots (verified against their pinned manifests by the
harness preflight). The rewrite model rung is the one model call in the chain;
it is unchanged across arms and its served identity is asserted from the
response envelope.

## Data

- **Exposed bank** — `docs/evaluation/variants-2026-08-29/variants.json`, 579
  variants (T1 120, T2 120, T3 101, T4 104, T5 104, T6 30), reference
  `docs/evaluation/variants-2026-09-15/reference.json`. Every rule in this
  plan's ancestry has read it; it is the development set.
- **Sealed bank** — `docs/evaluation/variants-holdout-2026-09/` (Step 1): 40
  entity-held-out gold questions, 160 variants (T3/T4/T5/T6 × 40), reference
  captured twice and byte-identical. Opened once per hypothesis, for
  confirmation only.
- `EXP-2026-09-022`'s hash-pinned `predictions.jsonl` for Step 0.

## Metrics

Per tier, from `scripts/variant_harness.py`:

- `records_exact` — the variant's extracted entity-id set equals its gold
  question's captured set. **Primary** at T3 on the exposed bank.
- `records_recall` — fraction of the gold set the variant extracted.
- `wrong_entity` — the variant extracted records and none is in the gold set.
- `abstained`, `catalogue_dump` — as defined in `EXP-2026-09-021`.
- rewrite rung counts, in particular `skipped_unresolved_anchor` at T3.

For H1 directly, from `data/exact_name_probe.py` (no pipeline run):

- **gold bind** — `exact_name_matches` across all sources returns exactly one
  entity and it is the question's gold anchor.
- **wrong single bind** — returns exactly one entity and it is not gold.
- **T6 bind** — returns exactly one entity on an invented-anchor question.

## Baselines

The shipped tree at the commit in `manifest.yaml`, `--rewrite
model_noid_anchored`, both flags off. Fair because every arm differs from it by
one flag, on one tree, over the same reference.

## Procedure

```bash
# Step 0 — enter the review probes into the record (no pipeline run)
uv run python docs/research/experiments/EXP-2026-09-023-anchor-hygiene-and-q59/data/shipped_vs_prototype.py
uv run python docs/research/experiments/EXP-2026-09-023-anchor-hygiene-and-q59/data/exact_name_probe.py --arm baseline

# H1 — after the distinctiveness rule lands behind ARIADNE_EXACT_NAME_DISTINCT
uv run python docs/research/experiments/EXP-2026-09-023-anchor-hygiene-and-q59/data/exact_name_probe.py --arm distinct
ARIADNE_EXACT_NAME_DISTINCT=1 uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-2026-09-15 --reference reference.json --rewrite model_noid_anchored --workers 32 --name scored_distinct.json
ARIADNE_EXACT_NAME_DISTINCT=1 uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-holdout-2026-09 --reference reference.json --rewrite model_noid_anchored --workers 32 --name scored_distinct.json

# H2 — after anchor-first routing lands behind ARIADNE_ANCHOR_BEFORE_ROUTING
ARIADNE_EXACT_NAME_DISTINCT=1 ARIADNE_ANCHOR_BEFORE_ROUTING=1 uv run python scripts/variant_harness.py compare ... --name scored_anchor_first.json   # both banks

# the sealed-bank baseline, once, so the sealed deltas have a denominator
uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-holdout-2026-09 --reference reference.json --rewrite model_noid_anchored --workers 32 --name scored_baseline.json
```

## What would falsify this

- **H1** is falsified by any T3 gold-bind loss above 2 % on the sealed bank, or
  by the 1 % threshold having to move for the sealed bank to pass. In the second
  case the rule is tuning, and the experiment records it as failed rather than
  adjusting it.
- **H2** is falsified by T3 `wrong_entity` above 0.07 on the exposed bank, by
  any rise in T6 acceptance, or by a sealed-bank T3 gain under 0.10. A T3 gain
  bought with T4/T5 `wrong_entity` above the D-035 values is also a failure,
  because it means H1 did not do its job first.
- Any arm that changes T1/T2 `records_exact` by more than ± 0.02 has touched a
  path it was not supposed to touch and is not shipped regardless of T3.
