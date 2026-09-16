# PROTOCOL — EXP-2026-09-029 A judged pass over the shipped arm's sealed-bank answers

> Written 2026-09-16 while the run was already in progress: the judge was
> started from `scripts/judge_variants.py` before this folder existed, and no
> judgment had been read when this file was written. Plan
> [`docs/plans/2026-09-15-open-question-correctness.md`](../../../plans/2026-09-15-open-question-correctness.md), Step 10.

## Question

The variant harness grades by record identity. Two mechanisms this plan
measured — widening an answer, disclosing a resolution — cannot be graded
fairly that way, and the operator's real question is whether the analyst
gets a correct answer. What does the recorded judge say about the answers
the **shipped** configuration (`form_execute` = D-037's four flags over
D-034/D-035) gives on the sealed bank, tier by tier?

## Hypothesis

Exploratory — no prior quantitative hypothesis. This is the first judged
reading of any arm on this bank; it is the denominator the next round's
judged comparisons will need.

## Setup

`scripts/judge_variants.py --bank sealed --arm form_execute --tiers T3,T4,T5,T6
--workers 8`: each scored row becomes an answer file (question, the gold
question's own ids as `must_include_ids`, the composer's claims and
abstentions), graded by `utils/evaluation/judge_answers.py` with its default
configuration — the local model on `:9090`, the same rubric and budget ladder
that graded every recorded arm. Not the cross-model judge of
`EXP-2026-08-007`: that grader is an external API the operator has not been
asked to spend.

## Data

`docs/evaluation/variants-holdout-2026-09/scored_form_execute.json`, 160 rows.

## Metrics

Per tier: mean `faithfulness`, `groundedness`, `completeness`; share
`abstained`; counts of `fabricated_mapping` and of answers with any listed
hallucination. **Primary:** T3 `completeness`.

## Baselines

None judged on this bank. The harness's record-identity columns for the same
arm are beside it in `EXP-2026-09-025`.

## Procedure

```bash
uv run python scripts/judge_variants.py --bank sealed --arm form_execute --tiers T3,T4,T5,T6 --workers 8
```

## What would falsify this

Nothing to falsify; a judged mean is recorded. Two readings would matter: a
T6 answer the judge calls faithful *and* non-abstaining (an invented anchor
answered), and any `fabricated_mapping` — both would name a defect the
harness cannot see.
