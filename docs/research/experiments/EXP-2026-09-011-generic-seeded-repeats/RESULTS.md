# RESULTS — EXP-2026-09-011 — how much does the primary result move across seeds?

**Run 2026-09-06/07.** Three seeded generations, six grading passes, 1,704
judgments. Hypotheses pre-registered before any run; none edited.

---

## Headline

**The wording moves. The score does not.**

`EXP-2026-09-010` established that `generic` — the arm carrying this project's
primary result — words **143 of 276** answers differently on a rerun at the same
seed, in the field the grader reads. The obvious worry was that the paper's
headline sat on a number that wanders.

It does not. Across three seeds the judged score has a **balanced across-seed SD
of 0.0039**, and the gap it supports is **0.1623** — **forty-one times** the
spread.

| Seed | block q1 | pos | block q2 | pos | balanced |
|---|---|---|---|---|---|
| 1729 | 0.6646 | 0 | 0.6394 | 2 | **0.6520** |
| 20260906 | 0.6451 | 1 | 0.6444 | 1 | **0.6448** |
| 424242 | 0.6468 | 2 | 0.6394 | 0 | **0.6431** |

**Balanced SD 0.0039**, range 0.0089. Reference figure for this arm on this bank
is **0.6569** (`EXP-2026-09-005`); all three seeds sit within 0.014 of it.

## Hypotheses

| | Prediction | Outcome |
|---|---|---|
| **H1** | `generic > deterministic` in all runs | ✅ **holds** — lowest seed 0.6431 against 0.4946 |
| **H2** | across-seed SD < 0.03 | ✅ **holds** — 0.0039, an order of magnitude under |
| **H3** | the gap exceeds 3×SD | ✅ **holds** — 3×SD = 0.0116 against a 0.1623 gap |

H3 as pre-registered names the **holdout** gap (0.1684) while the spread is
measured on the **dev** half. That mismatch is in the protocol as written. Both
comparisons are reported and both hold; the same-population one (0.1623) is the
meaningful test and is quoted above.

---

## What this settles

**The `EXP-2026-09-010` finding is real but bounded, and now the bound is
measured.** Both statements are true and neither cancels the other:

- `generic` is **not** deterministic. It words the majority of its answers
  differently between runs.
- The judged score is **stable to 0.004**.

The reconciliation is the architecture doing its job. Retrieval, coverage,
claims and evidence are byte-identical across runs (`EXP-2026-09-010`); the
verifier admits claims against those fixed records; so the narrator's freedom is
freedom over *phrasing*, not over *content*. A grader scoring what was asserted
sees the same assertions in different words.

**That is a stronger result than determinism would have been.** A system whose
prose is fixed proves nothing about whether its scores are robust to prose. This
one varies the prose across 52% of answers and moves 0.004, which is evidence
about the *measurement*, not just the system.

## What it does not settle

- **Three seeds is a spread, not a distribution.** `n_runs: 3`.
- The spread is measured on the **dev half**. The holdout was answered once and
  is spent; nothing here says its figures would be equally stable, only that the
  same arm on the same bank is.
- **Same grader throughout.** Both blocks are `qwen38-27B-v2`
  (`default-model-2/-3/-4`). This is position-balanced *repeatability*, not
  cross-grader agreement. The second family was unavailable — its GPU was
  reserved — and `EXP-2026-09-009` showed that family can produce an opposite
  ordering on a population like this, so **cross-grader stability is not claimed
  and should not be inferred.**
- It does not localise *which* wording changes are inert. That every one of them
  is inert is an inference from the aggregate, not a per-answer finding.

---

## Incidental: the grading-order effect, replicated a third time

The two blocks are the same grader over the same answers, differing only in when
they ran:

| block | graded | mean |
|---|---|---|
| q1 | first | **0.6522** |
| q2 | second | **0.6411** |

**−0.0111 for being graded second.** `EXP-2026-08-022` measured −0.0088 on
byte-identical answers; `EXP-2026-09-009`'s qwen half showed a ~0.01 spread of
the same shape. Three independent measurements, all near 0.01, all in the same
direction.

This is why the design counterbalances rather than grading in a fixed order.
Un-counterbalanced, the block effect alone (0.0111) would be **nearly three times
the entire across-seed signal** (0.0039) and would have been reported as seed
variance. The counterbalancing did not merely tidy the estimate — it prevented a
wrong conclusion.

## Consequences for the paper

1. **§5's figures may be quoted as point estimates.** The arm's spread is 0.0039;
   the effect is 0.1623.
2. **Limitation 5 narrows.** `generic` is no longer "a single draw of a
   stochastic process whose spread we have not measured". The spread is measured
   and it is small. The wording instability stays in the paper as a finding.
3. **§11 gains a number it was carrying as a bound.** It can now state both that
   52% of answers are re-worded and that the score moves 0.004.
4. **The grading-order caveat gets a third citation**, which makes it a property
   of the instrument rather than an anecdote about one experiment.
