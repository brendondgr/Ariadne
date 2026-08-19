# PROTOCOL — EXP-2026-08-007 Judged arm comparison, generation 2

> **On the timing of this document.** The results were written after the run,
> but the protocol was not reconstructed: it was fixed in advance *as executable
> code*. `scripts/overnight_sweep.py` — the phase list, their order, the
> grader's rubric and token budget, and the roll-up statistics — was committed
> at `9da80fa` before a single phase executed, and the run is exactly that
> script with `--workers 12`. That is why `code.commit` is a real sha rather
> than `unknown`. What genuinely was *not* fixed in advance is a hypothesis
> about how the arms would order; that half is exploratory and is recorded as
> such in the manifest rather than invented here.

## Question

Three experiments (EXP-2026-08-004, -005, -006) moved blind retrieval from
0.7688 to 1.0000 and every one of them closed by admitting that nothing had
been judged. Retrieval saturating means the evidence arrived; it says nothing
about whether the answer was written. So:

1. Does the repair improve **answers**, not just coverage?
2. Do the generic (Arm H) and gold-loop-LLM (Arm F) arms differ from the
   default cascade on anything that matters?
3. Can this grader be trusted at all?

Each has an answer that could come out either way, and question 1 could
plausibly have come out at zero — a pipeline can retrieve perfectly and compose
badly.

## Hypothesis

From EXP-2026-08-006 RESULTS §5, written before this ran: retrieval is
saturated on both banks and can no longer detect anything, so a judged re-run
is the only instrument left. No prediction was recorded about the *direction*
or *size* of any arm difference. Exploratory on that axis.

## Setup

Three arms, all at commit `9da80fa`, all reading answers produced by the same
pipeline code:

| Arm | `--arm` | What differs |
|---|---|---|
| Cascade | `deterministic` | templates, deterministic composition, no narrator |
| Arm H | `generic` | templates disabled; schema-derived primitives only |
| Arm F | `gold_loop_llm` | authored plan injected into the real agent, LLM narrator |

Held constant: the graphs (ATT&CK 19.0 in Neo4j, CAPEC 3.9 in Gremlin), the
question banks, the grader, its rubric, its temperature (0.0) and its token
budget. Arm F was **re-run** on this tree (generation 2) rather than compared
across code states, which is what EXP-2026-08-006 recorded as an open item.

The cascade and Arm H answers were already on disk from the prior experiments;
this run graded them. Arm F's answers were generated during this run.

## Data

- **Blind holdout v1** — 30 questions, `utils/specialists/tests/golden/holdout_questions.json`.
  Card: [`../../datasets/cards/blind-holdout-30.md`](../../datasets/cards/blind-holdout-30.md).
  **Selection bias to state plainly:** this bank found the direction defect and
  the join defect, and both were then fixed. It is no longer blind with respect
  to this system — it is a practice test. Figures from it are diagnostics.
- **Golden catalogue** — 120 questions, co-authored commit-for-commit with the
  templates that answer them. Card:
  [`../../datasets/cards/golden-catalogue-120.md`](../../datasets/cards/golden-catalogue-120.md).
  Structurally flattering, and used here only for arm-to-arm comparison at
  larger n and to measure the size of that flattery.

## Metrics

**`correctness`** — the grader's 0–1 scalar per answer, averaged over the bank.
Not the verdict rate; the two are reported side by side because they disagree
(a bank can be 0.98 mean with 119/120 CORRECT, or 0.84 mean with 22/30). 95%
intervals are percentile bootstrap, 2000 resamples, seed 1729
(`utils/evaluation/stats.py:bootstrap_ci`).

**`repair_paired_delta`** — mean of per-question `after − before` over the 30
questions present in both the pre-fix and post-fix answer sets, where both sides
were graded by *this* grader on *this* night. This is the only figure in the
experiment that isolates a code change from the grader.

**`judge_pass_spread`** — max minus min mean correctness across three grading
passes over one fixed set of answers. The cascade is fully deterministic, so
every point of this spread is grader variance and none of it is pipeline
variance. This is the noise floor every other delta is read against.

**`judge_calibration_pearson_r`** — correlation between this grader and the
committed Sonnet 5 judgments from EXP-2026-08-002 over the 30 answers that
carry both. Success is not "high correctness"; success is *rank agreement*,
because every comparison here is a difference rather than a level.

**`abstention_proof_rate`** — of the answers that declined to assert, the
fraction whose abstention carried the executed query. Directly the property
C-017 claims.

**`answer_gap` classes** — `utils/evaluation/answer_gap.py` attributes each
question's shortfall to the largest of several deficits. Note it is a
magnitude-argmax, not an ordered ladder, and shares are fractions of the whole
run's deficit so they do not sum to 1.

## Baselines

- **EXP-2026-08-002** — the pre-fix blind figures, and the source of the
  committed Sonnet judgments used for calibration.
- **EXP-2026-08-003** — Arm H's blind retrieval, never judged until now.
- **EXP-2026-08-006** — the immediately preceding tree state.

The comparison is fair on the axis it claims: all three arms are graded by one
grader, on one night, over identical questions, at one commit. It is *not* fair
as a cost comparison — Arm F calls an LLM per question and the cascade does
not — and no cost figure is drawn from this run.

## Procedure

```bash
uv run main.py --dataset capec --graph gremlin     # the Gremlin store does not survive a restart
uv run main.py --dataset capec --graph verify
nohup uv run python scripts/overnight_sweep.py --workers 12 > logs/overnight.log 2>&1 &
```

Phase order is value-first rather than dependency-first, so an interrupted run
still answers the most important questions: calibrate, judge the cascade blind,
judge Arm H blind, two repeat passes, answer-gap both, both arms on the
catalogue, then Arm F generation 2 on both banks.

## What would falsify this

- **Question 1** dies if the paired repair delta's interval includes zero — the
  fix would then be unproven on correctness however good the retrieval figure
  looks.
- **Question 2** dies if an arm delta is smaller than the grader's own pass
  spread, which would mean the arms were not measured apart at all.
- **Question 3** dies if calibration shows weak rank agreement with the Sonnet
  judgments. Below roughly r = 0.8 the arm comparisons would have to be thrown
  away and re-run against the cross-model panel, because a grader that reorders
  answers cannot support a claim about a difference.
