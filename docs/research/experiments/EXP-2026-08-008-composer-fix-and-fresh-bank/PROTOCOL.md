# PROTOCOL — EXP-2026-08-008 Composer fixes, and the first fresh bank

> The protocol was fixed in advance as executable code: `scripts/measure_arms.py`
> defines the phases, their order, the grader and its budget, and was committed
> before any phase ran. Results were written afterwards, as always.

## Question

Four things were built on 2026-08-19 and none had a number attached. Three
questions, each able to come out either way:

1. **Did the two answer-writing fixes improve answers?** The system was
   retrieving the right facts and not stating them — answering "what is this and
   how does it work?" with version numbers while the description sat unread in
   the cited record, and never mentioning a small related set at all.
2. **How do the four arms compare on questions none of them has seen?**
3. **When a language model writes the query itself, what actually fails?**

## Hypothesis

For (1), stated before the run: the three questions judged 0.5 on the blind set
for answering with the wrong field will move, and the aggregate will move less
because only a handful of questions are affected. For (2) and (3), exploratory.

## Setup

Four arms at one commit, one grader, one night:

| arm | what differs |
|---|---|
| `deterministic` | templates, deterministic composition |
| `generic` | templates disabled; schema-derived primitives |
| `gold_loop_llm` | authored plan, LLM narrator |
| `llm_query` | **new** — a model writes the query string |

`llm_query` holds the plan constant against `deterministic`, so a difference
between them is attributable to query generation and nothing else.

## Data

- **Blind holdout v1** (30) — used only for the paired before/after, where its
  burned status does not matter: both sides are the same questions and the only
  variable is the code.
- **Fresh bank** (30), `docs/evaluation/banks/bank-2026-08-19/` — generated this
  morning, drawn to exclude every anchor v1 used, authored by a model that saw
  one entity and nothing about the system. Card in that directory.
- **Golden catalogue** (120) — re-run with the fixes to test, on identical
  questions, whether the co-authorship gap recorded in EXP-2026-08-007 survives
  the composer fixes.

## Metrics

**`correctness`** — the grader's 0–1 scalar, averaged. Intervals are percentile
bootstrap, 2000 resamples, seed 1729.

**Paired delta** — mean per-question `after − before` over the questions present
in both runs. The grader's own run-to-run spread is 0.0050, the same order as a
small fix, so an unpaired comparison of means could not separate a code change
from grader drift. Pairing removes the grader.

**Failure split for `llm_query`** — each question assigned to: answered; safety
gate refused every draft; the database refused the query; or the evidence reader
could not parse output it did return. Only the middle two are the model's fault.

## Baselines

EXP-2026-08-007, which judged the same arms on the same banks before these
fixes, with the same grader.

## Procedure

```bash
uv run python scripts/measure_arms.py --workers 12
```

## What would falsify this

The fixes are unproven if the paired interval includes zero. The fresh-bank
comparison is uninformative if every arm lands inside the grader's 0.0050
spread. The `llm_query` arm tells us nothing about C-012 if most of its failures
turn out to be the evidence reader rather than the queries.
