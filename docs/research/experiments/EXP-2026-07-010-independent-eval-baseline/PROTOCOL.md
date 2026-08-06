# PROTOCOL — EXP-2026-07-010 Independent cross-model grading (pre-fix baseline)

> **Back-filled 2026-08-06.** Reconstructed from the recorded method.
> **This experiment is `superseded`.** It is kept because a deleted baseline is
> a comparison nobody can check.

## Question

When the pipeline's answers are graded by a model *other* than the one that
wrote them, does answer quality look the same as the self-judged evaluation
(`EXP-2026-07-009`) reports?

## Hypothesis

That the self-judged scores overstate quality, because the grading model is the
model under test. Unlike every other experiment in this record, this one did
have a prior expectation, and it is recorded rather than retrofitted as
"exploratory".

## Setup

120 saved end-to-end answers, each graded by a **separate Sonnet 5 agent**
against the question's gold assertions and its full retrieved evidence. The
pipeline under test ran on `skynet`; the judge is Sonnet 5. No pipeline code
changes — this grades already-saved answers.

## Data

The same 120-question golden catalogue and the answers saved by
`--e2e-generate`, under the **truncated** (pre-un-truncation) profile.

## Metrics

Correctness (primary), completeness, faithfulness, groundedness — each the mean
of 120 independent judge scores — plus CORRECT/PARTIAL/INCORRECT verdict counts
and the number of answers carrying a flagged hallucination.

## Baselines

The self-judged scores from `EXP-2026-07-009`, for the faithfulness and
groundedness comparison only.

## Procedure

```bash
uv run main.py --e2e-generate    # writes the 120 answers
# then: one Sonnet 5 agent per answer, external to this repository
```

## What would falsify this

If the independent scores had matched the self-judged ones, the self-preference
concern would have been unfounded and the seven-arm study would not have needed
an external judge panel.
