# ISSUES — EXP-2026-08-021

## I-1 — `calibrate()` would have destroyed the artifacts behind the recorded r = 0.9275

**Impact:** none, because it was caught first. Recorded because the next person
to run a calibration will hit it.

**Cause:** `judge_answers.calibrate()` hardcodes `suffix=".local"` **and**
`force=True`, so it overwrites any existing `.judgment.local.json`. Those files
were the Ornith-era calibration behind `EXP-2026-08-007`'s r = 0.9275 — the only
evidence about how far that instrument could be trusted.

**Resolution:** copied to `.judgment.local.pre-qwen38.json` before running. The
backup suffix contains `.judgment`, so `answer_files()` excludes it and it cannot
be re-consumed as an answer — the contamination mode that module's own docstring
warns about.

**Paper implication:** none. **Repo implication:** `calibrate()` should refuse to
overwrite without an explicit flag, or should suffix by date. Not fixed here.

## I-2 — An existing `.cross` pass is not cross-model, and its `llm_query` mean is inflated by dropout

**Impact:** nothing in this experiment uses it. It is recorded because it is
quotable-looking and wrong in two ways at once.

Found while locating the reference pass. On `bank20260819/llm_query` the
`.judgment.cross.json` pass reads **0.7407 (n=27)** against the base pass's
**0.5000 (n=30)**.

1. **It is not cross-model.** Every judgment in it records `"model": "skynet"` —
   the local relay, same as the base pass. The suffix name suggests otherwise.
2. **Its three missing cases are three of the arm's worst answers.** `H-CHN-02`,
   `H-CHN-03` and `H-CTM-04` failed with `ValueError: no JSON object in reply: ''`
   and score **0.30, 0.20, 0.35** in the base pass. Imputing them back gives
   ≈ 0.695, so roughly a fifth of the 0.24 gap is dropout, not disagreement.

**Paper implication:** a grading pass that fails on its hardest cases reports a
flattering mean, and the failure mode is silent. This is the same shape as
`EXP-2026-08-019`'s fallback contamination (r = +0.62 between failure rate and
measured quality) on a different mechanism. **`grader_sensitivity.py` therefore
pairs on case id and reports dropout separately rather than absorbing it.**

## I-3 — My own comparison script reported an ordering flip that was a tie

**Impact:** a wrong intermediate reading, corrected before it reached a
conclusion. Recorded because it is exactly the class of defect this experiment
exists to catch.

On `bank20260820` the reference pass scores `merged` and `generic_composed` at
**exactly 0.9367**. Sorting by mean and comparing the two sorted lists reported
`arm_order_preserved: False` — but there was no ordering to preserve, and the
"flip" was the sort's tie-break.

**Resolution:** the script now detects ties in the reference, excludes tied arms
from the ordering test, and prints the tie explicitly. Both banks pass H1 once
ties are handled.

**Paper implication:** an ordering test is only meaningful over pairs the
reference actually ranked. Stated in the results rather than silently handled.

## I-4 — The reference grader is unidentified, so the offset between passes cannot be attributed

**Impact:** bounds what this experiment can conclude, and it is the reason it
exists.

The candidate grader is `qwen38-27B-v2`, probed and recorded. The reference
passes were run 2026-08-19..21, inside the window where the alias's serving model
is **not determinable** (`Q12`). So the measured offsets are real and their
*cause* is not recoverable.

They also do not run in one direction:

| reference pass | cells | offset (candidate − reference) |
|---|---|---|
| base `.judgment.json` | the four `EXP-2026-08-008` arms | **+0.023 to +0.057** (candidate more generous) |
| `.judgment.c015.json` | the `EXP-2026-08-009` pair | **−0.007 to −0.038** (candidate stricter) |

Both reference passes fall in the same undetermined window but were run in
different sessions, so the disagreement between them cannot be separated from the
disagreement with the candidate.

**Paper implication:** report the offsets as measured and **do not explain them**.
The honest sentence is that a grader offset of ±0.05 exists between passes and
its source is unrecoverable — which is the cost `D-028` was written to stop
accruing, observed rather than argued.

## I-5 — The candidate pass supports a six-arm comparison the reference cannot

Not a defect; a property worth recording before someone builds the wrong table.

All twelve candidate cells were graded in **one session with one instrument**. The
reference figures are split across two sessions — base for four arms, `.c015` for
the merged/federated pair — and `EXP-2026-08-009`'s protocol explicitly graded its
eight cells together *"so the grader cancels out of every comparison"*, warning
against comparing arms graded in different sessions.

**So a six-arm ordering table may be built on the candidate side and must not be
built on the reference side.** Every reference-versus-candidate comparison in
`RESULTS.md` is therefore within-arm and paired, never across arms.
