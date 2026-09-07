# RESULTS — EXP-2026-09-012 — grader repeatability, from passes already on disk

**Analysed 2026-09-07.** No new judgment was made. Every figure comes from
sidecars that already existed.

---

## Headline

**Re-grading the same frozen answers with the same grader family moves the
reported mean by a median of 0.0066 and up to 0.0242.** Across **22 cells and
117 grading passes**, that variance has never been reported by this project.

Every judged figure here carries a bootstrap interval **over questions**. None
carries one **over grading passes**. A reader assumes the second is negligible.
On the worst cell it is a quarter of the effect the paper's §6 reports.

| | SD across passes |
|---|---|
| minimum | 0.0021 |
| **median** | **0.0066** |
| mean | 0.0093 |
| maximum | **0.0242** |

## By arm — and the ordering is not incidental

| arm | cells | mean SD | max |
|---|---|---|---|
| `llm_query` | 2 | **0.0218** | 0.0234 |
| `merged` | 4 | 0.0151 | 0.0242 |
| `gold_loop_llm` | 2 | 0.0075 | 0.0090 |
| `deterministic` | 7 | 0.0073 | 0.0156 |
| `generic` | 3 | 0.0053 | 0.0084 |
| `generic_composed` | 4 | 0.0047 | 0.0072 |

**The arm with a model in the query path is the least repeatably gradeable**, at
roughly four times `generic_composed`. A plausible reading is that its answers
sit in a quality band where the grader is least decisive — consistent with
`EXP-2026-09-008`, where resolution collapsed on a homogeneous population — but
this experiment cannot establish that and does not claim it.

## Why it matters for what is already published

`C-012`'s holdout margin is **0.0822**. Grader repeatability on `llm_query`
cells is **~0.02**. A single grading pass therefore carries a fifth to a quarter
of that margin as unmodelled noise, on top of the question-sampling interval the
paper does report.

This does **not** overturn the result: `EXP-2026-09-007` graded every cell twice
by position and `EXP-2026-09-006` re-graded across families, so the published
figures are already averages rather than single passes. What it means is that
**the reported interval is narrower than the total uncertainty**, and the paper
should say so.

## What this cannot support

- **Not a correction.** Knowing a pass carries ±0.02 does not say which way any
  particular published pass erred.
- **Not one project-wide number.** The cells differ by population, arm and date;
  the variation between them is the finding.
- **Not generation variance.** These are re-gradings of **frozen answers**.
  `EXP-2026-09-010` and `-011` cover the generation side.
- **An upper bound, not an estimate.** Passes within a family differ in grading
  position, and that effect is measured at ~0.01 three separate times
  (`EXP-2026-08-022`, `-09-009`, `-09-011`). Each SD here **includes** it.

## Two method notes

**The audit read a quarantine bin.** Thirty sidecars under
`outerjoin-holdout/deterministic/_contaminated_run3/` are judgments of
judgments — the failure mode `ariadne-judge-pass-contamination` names. They were
**already found and quarantined by an earlier session**; the defect was that this
audit read them, not that they exist. Included, they inflated one cell to
**0.0774** against a 0.0066 median. Excluded by path and by double suffix.

**142 of 218 computed cells appear in no manifest.** Most are legitimately
intermediate — repeat passes, spot checks after a fix. The number is reported
rather than resolved, because deciding which intermediates deserve a metric is a
judgement this analysis is not entitled to make on its own.

## The recommendation

The paper should state that its intervals cover question sampling and not grader
re-run variance, and quote **0.0066 median / 0.0242 max** as the scale of what is
uncovered. That is cheaper and more honest than widening every interval on an
estimate this coarse.
