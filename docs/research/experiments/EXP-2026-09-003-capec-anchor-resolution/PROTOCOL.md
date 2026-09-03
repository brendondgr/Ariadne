# PROTOCOL — EXP-2026-09-003

Written from `docs/plans/2026-09-03-capec-anchor-resolution.md`, which was
committed at `b41f63e` **before** any code changed and states the predicted
scope this experiment then falsified.

## Question

Does anchoring CAPEC queries on identity rather than on a guessed vertex label
recover the View and Category questions EXP-2026-09-002 recorded as failing?

## Independent variable

One change to `utils/specialists/gremlin/builder.py`, landed at `2432ce8`:

1. `_capec_candidate_ids` offers all three CAPEC id namespaces for a bare
   `CAPEC-<n>`, never `cwe:`.
2. The seeded `describe`, `capec_neighbors`, `capec_facets` and `capec_maps_to`
   anchors drop `hasLabel("AttackPattern")` and bind on the id alone.
3. The name-anchored `describe` widens its label scope to the three CAPEC kinds.

`_cwe_chain`, `_capec_reverse_maps` and `_capec_hierarchy_chain` are deliberately
untouched.

## Held constant

Same 37 questions, same bank file (hash pinned in `manifest.yaml`), same arm,
same deterministic composer, no model anywhere in the loop. The CAPEC store was
reloaded from the same committed export before both halves were compared — see
ISSUES I-3 for the one difference and why it does not touch these questions.

## Selection

Dev-half questions only, so the 288-question holdout stays sealed. Selected as:
containment shapes, or D1 property reads on a View/Category anchor, that scored
below 1.0 in EXP-2026-09-002. 37 questions.

## Prediction, recorded before the run

25 of the 37 move; 12 named cases do not. Scoring the prediction is the point.

## Measurement

`deterministic_scores.coverage.coverage` per question, before from the
EXP-2026-09-002 artifacts and after from this run's, plus a live probe of three
seeds against the store to establish that the anchor resolves at all.
