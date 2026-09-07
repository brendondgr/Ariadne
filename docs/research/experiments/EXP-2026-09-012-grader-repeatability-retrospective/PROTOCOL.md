# PROTOCOL — EXP-2026-09-012 — grader repeatability, from passes already on disk

**Written 2026-09-07.** Retrospective. **No new data is generated and no new
judgment is made.** This is an analysis of judgment sidecars that already exist.

> **Pre-registration does not apply in the usual way and pretending otherwise
> would be dishonest.** The data existed before the question was asked. What can
> be pre-committed, and is, below: the aggregation, the exclusions, and the
> statistic — all fixed before any number was computed for this write-up.

---

## The question

Every judged figure this project reports carries a bootstrap interval **over
questions**. None carries an interval **over grading passes**. The distinction
matters because they answer different questions:

- *bootstrap over questions*: what if we had sampled different questions?
- *variance over passes*: what if we had graded the same answers again?

The second has never been reported, and the second is the one a reader assumes is
negligible.

It is measurable without spending anything. Over its lifetime the project has
re-graded the same frozen answers many times — for grader-family comparisons,
for position counterbalancing, for spot checks after a fix. **Those repeat passes
are an unexploited replication study**, sitting in
`docs/evaluation/experiments/**/answers/*.judgment*.json`.

## Method

`scripts/recompute_audit.py` recomputes the mean correctness of every
(evaluation root, arm, judgment suffix) cell on disk. Cells are then grouped by
**(root, arm, grader family)** and the across-pass standard deviation is taken.

**Fixed before computing:**

- **Family assignment by suffix**: `g31`/`gem` → gemma; `cross` → cross-model;
  `qw`/`q`/`pass2`/unsuffixed → qwen. A suffix matching none is reported under
  its own name rather than forced into a family.
- **Minimum 3 passes** for a cell to be reported. Two points give a range, not a
  spread.
- **Minimum 20 judgments** per pass, so partial or aborted passes cannot
  contribute a mean.
- **Population standard deviation**, not sample: these are the passes that exist,
  not a sample from a larger set of passes.
- **No pooling across roots or arms.** A repeatability figure is a property of a
  grader on a population, and averaging across populations would hide exactly the
  variation being measured.

## What this can and cannot support

**Can:** a statement of the form "re-grading the same answers with the same
grader family moves the reported mean by about X on this population."

**Cannot:**
- Anything causal about *why* a grader varies.
- A single project-wide repeatability number. The cells differ in population,
  arm and date, and the whole point is that they differ.
- A correction to any published figure. Knowing that a pass carries ±X does not
  say which direction a particular published pass erred.
- Anything about *generation* variance. These are repeat gradings of **frozen
  answers**; the answers did not change. `EXP-2026-09-010` and `-011` cover
  generation.

**A confound stated up front:** passes within a family were not run under
identical conditions. Some differ in grading position, which
`EXP-2026-08-022`, `-09-009` and `-09-011` each measure at about 0.01. So a
reported SD **includes** position effect and is an upper bound on pure
re-run variance, not an estimate of it.
