# PROTOCOL — EXP-2026-11-001 Answer-invariance gate: run every plausible interpretation, answer only when they agree

Written 2026-11-13, before any code for this experiment ran. Kill test T2.

## Question

When a question can be read more than one way, can a system run every interpretation the
source card allows, execute each exactly, answer only when all non-empty interpretations
return the same records, and ask otherwise? Can it do this without asking on questions that
were never ambiguous, and without discarding the reading the question actually meant?

## Hypothesis

H1: with interpretations pruned by an off-the-shelf decision model (T2-filtered), the gate asks
on at most 40% of unambiguous questions and prunes the gold interpretation on fewer than 30%
of questions. It also makes fewer confident wrong answers than answering with the single
top-ranked interpretation (the guess baseline).

Without any model (T2-raw), we expect the ask-rate to be far above 40%. T2-raw is reported
as the floor, not tested.

## Setup

An **interpretation** is `(dataset, anchor node, facet)`. The facet is either `describe` (the
anchor node itself) or `(relation, direction, target label)`, taken from the schema registry's
plausible facets for the anchor's label (`SourceCardView.label_facets`).

1. **Anchors.** Identifiers cited in the text are pinned. Otherwise the top `K=5` candidates
   per dataset come from the BM25 name index (`utils/specialists/schema/namesearch.search_in`),
   over ATT&CK and CAPEC.
2. **Facets.**
   - **T2-raw:** facets lexically supported by the question (a relation or target-label token
     appears in it), plus `describe`. If no facet is supported, every facet plus `describe`.
   - **T2-filtered:** the decider on `:7500` (`pplx-decider-flash-v1.2-fp8`, `choice`
     questions, temperature 1.0) scores the anchors, with a "none of these" option, and then
     the facets for each surviving anchor label. Anchors and facets with p < 0.05 are dropped.
   - At most 40 interpretations per question; every time the cap applies is recorded.
3. **Execution.** Each interpretation is compiled by the existing deterministic compilers
   (`CypherQueryBuilder.expand`, `GremlinQueryBuilder.expand`) with a page size large enough
   to return every member: exact results, no truncation. A `describe` interpretation's record
   set is `{anchor id}`.
4. **Policy.**
   - Drop interpretations with empty record sets.
   - Group the rest by identical record-id sets.
   - One group means **answer**; two or more mean **ask**; none means **abstain**.
5. **Guess baselines.**
   - **guess-filtered:** the decider's top anchor × top facet.
   - **guess-raw:** BM25 top-1 × the first lexically supported facet.

   Each executes that one interpretation and answers if it is non-empty.

Held constant: the code at tag `killtests-start` for every shipped module; the ATT&CK 19.0 and
CAPEC 3.9 stores, with counts in `logs/killtests-2026-11/preconditions.json`.

## Data

- **Development:** `docs/evaluation/variants-2026-08-29`, single-source variants only
  (attack + capec, 384 of 579; federated excluded), tiers T1–T6.
- **Confirmation:** `docs/evaluation/variants-holdout-2026-09`, 160 variants, tiers T3–T6.
  This bank has already been opened (D-037/D-038), so it confirms rather than seals.
- **Gold:** `slot_gold.json` (anchors, relation, target labels) per case. The direction is the
  one for which the registry has `(anchor label, relation, direction, target)`. The gold record
  set is the execution of the gold interpretation, unioned over gold target labels.
- Every T1–T5 variant is unambiguous by construction: it was written from one gold question.
  T6 variants name an invented entity and have no correct answer.

## Metrics

All are over the confirmation bank, with the development bank reported alongside. Bootstrap
95% CIs use 2,000 resamples.

- **ask_rate:** the share of T1–T5 variants on which the gate asks.
- **gold_pruned_rate:** the share of T1–T5 variants for which no surviving interpretation
  equals the gold interpretation, i.e. same anchor, relation, direction and target label, or
  `describe` with the same anchor.
- **answer_exact:** the share of T1–T5 variants answered whose record set equals the gold
  record set.
- **confident_wrong:** the count of T1–T5 variants answered with a record set ≠ gold, plus T6
  variants answered at all.
- **t6_answered:** the share of T6 variants answered (should be 0).
- Per-tier breakdowns of all of the above.

## Baselines

The guess baselines above run on the same candidates, the same decider scores and the same
executor. The only difference is the policy, so the comparison isolates the gate.

## Procedure

```bash
KILLTESTS_SMOKE=1 uv run python scripts/killtests_run.py --only t2   # smoke
uv run python scripts/killtests_run.py --only t2                     # full (part of the chain)
uv run python -m utils.killtests.analysis t2
```

## What would falsify this

**Kill rule**, evaluated mechanically by `utils/killtests/analysis.py` on the confirmation bank
for T2-filtered: `ask_rate > 0.40` **or** `gold_pruned_rate >= 0.30`.

If either holds, the gate is not a viable mechanism as specified. A narrower claim may survive
on a subset of tiers, reported as exploratory.
