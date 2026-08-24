# PROTOCOL — EXP-2026-08-015

**Written before the run.**

## 1. The question

Q2 has been open since July: *what is the variance on any of these numbers?*
Every arm manifest carries `n_runs: 1` and a null `statistical_test`, and the
templates-vs-generic gap — the quantity C-023 turns on — is a difference of two
point estimates with no interval.

## 2. Why re-running the arms would measure nothing

Both arms are LLM-free end to end. Ten runs of either produces ten byte-identical
numbers, because the deterministic path is byte-reproducible — that is the
property C-004 and the README already claim. **Pipeline variance on this path is
zero by construction**, and the honest move is to state it, not to estimate it.

The variance that actually exists is in **which thirty anchors you happened to
draw.** Every blind figure in the study rests on one draw. So this resamples the
bank, not the run.

## 3. Design

Ten anchor-disjoint banks per population, both arms over each, retrieval only.

* **Draws** are seeded (`9001`–`9010`, `9101`–`9110`) and mutually exclusive:
  the catalogue draws go through `make_bank`'s anchor registry, the identity
  draws chain `--exclude-bank` over every prior bank plus the three the
  schema-transfer fixes were developed against.
* **Arms** are `deterministic` (the template cascade) and `generic` (the
  schema-derived primitives, every hand-written template disabled), run by
  `utils.evaluation.experiment_untruncated`, the same runner behind every
  recorded arm figure.
* **Metric** is `gold_in_evidence` from `utils/evaluation/retrieval_coverage.py`:
  the mean per-question fraction of gold that reached the evidence. A set
  membership test against the committed artifact — no judge, no model.
* **Statistic** is a paired percentile bootstrap over the ten per-bank
  differences, 2000 resamples, seed 1729 (matching EXP-2026-08-007's precedent).

## 4. Two populations, reported side by side and never pooled

| population | why it is in |
|---|---|
| `catalogue` (ATT&CK + CAPEC) | where the templates-vs-generic comparison is the paper claim and every recorded arm figure lives |
| `identity` (ReliaQuest customer schema) | where the arm gap is an order of magnitude larger (+0.59) and has never carried an interval — the most exposed number in the record |

They measure different things over different schemas with different gold, and a
pooled number would mean nothing.

## 5. Retrieval only — pre-registered scope

Judged correctness on twenty bank-runs is a separate purchase the operator has
deferred (`docs/plans/2026-08-23-record-hardening-decisions.md` Q1/Q2). Nothing
here forecloses it: `experiment_untruncated` writes exactly the artifacts a judge
pass consumes, so the judged half is a later command over these same runs, not a
re-run.

**What this cannot tell us:** whether the gap in *correctness* has the same
interval as the gap in retrieval. Retrieval is the necessary condition, not the
sufficient one.

## 6. Hypotheses

**H1.** The catalogue gap is small with an interval that includes zero —
consistent with EXP-2026-08-007's finding that the two arms are indistinguishable
where the templates were written to serve.

**H2.** The identity gap is large with an interval well clear of zero, and its
sd is larger than the catalogue's, because a foreign schema exposes more
per-anchor variation in what the templates happen to cover.

**H3.** Within-arm sd is non-trivial in both populations — i.e. a single 30-anchor
draw is a noisy instrument, which would retroactively qualify every blind figure
in the record.

## 7. Threats declared in advance

* **Machine-authored phrasing.** These banks are authored by `skynet`, not a
  human, so they are as *blind* as holdout-v1 (the Author never sees the
  templates) but explore a narrower band of phrasing. This is a regression and
  comparison instrument, not a source of a headline figure. Recorded in Q16.
* **Anchor pool depth.** Ten catalogue banks consume 300 anchors on top of the 90
  already drawn. Confirmed feasible by ten dry runs before authoring (271
  distinct anchors across ten independent draws).
* **The registry keys on the output path.** `make_bank --out <dir>/<name>.json`
  keys the registry on the *parent directory*, so a flat layout silently
  collapses every bank onto one key and exclusion degrades to "the previous bank
  only". This experiment hit it: the first five banks shared 8 anchors across 3
  pairs. Caught by a pairwise-overlap check, fixed in `make_bank.py`, and the
  affected banks were discarded and redrawn. **Disjointness is asserted by
  measurement in RESULTS, never assumed from the printed exclusion count.**
