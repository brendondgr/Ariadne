# ISSUES — EXP-2026-09-009

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

## 2026-09-09 — `code.dirty: true` cannot be verified after the fact
**Impact:** provenance only.
**Cause:** `code.commit` is `26bd352` (2026-09-06 17:28, the paper draft).
`scripts/seeded_repeats.py` was committed at `c8ad1a7` (17:57) before the
first run finished (18:23), and `scripts/seeded_repeats_judge.py` at `9f66921`
(19:05) before the first grading pass (~19:34–20:34). Whether any other file
was modified while the runs were in flight is not recoverable.
**Resolution:** `dirty: true` kept as recorded; the code that produced the
numbers is `c8ad1a7` (generation) and `9f66921` (grading), not `26bd352`.
**Paper implication:** none.

## 2026-09-09 — one qwen judgment on seed 424242 failed
**Impact:** seed 424242's qwen mean (0.4009) is over n=283; the pooled qwen
population is 851 judgments, not 852. Zero failures on the other five passes.
**Cause:** the judge returned without `verdict`, `correctness`, `faithfulness`,
`groundedness`, `completeness`, `rationale`
(`D3-subtechnique-of-T1589-3f64fc::formal`, `*.judgment.q.error.txt`).
**Resolution:** disclosed in RESULTS Limits at write-up time; recorded in the
manifest as `grading_failures`.
**Paper implication:** none beyond n=283 for that cell.

## 2026-09-09 — the abstention predicate behind §"The mechanism, partly identified" was not recorded
**Impact:** 98.2 % / 0.7014 / 0.4023 and the holdout cross-check
71.2 % / 0.4098 reproduce only approximately (RESULTS A-4 item 4).
**Cause:** the split was computed in-session and the field it keyed on was
not written down; no script in `scripts/` produces it.
**Resolution:** not resolved. The nearest definition
(`evidence_volume.records == 0`) lands within one case on the seeded runs and
within ~1 pt on the holdout; 13 distinct values on the holdout is exact.
**Paper implication:** quote the abstention split as approximate, or recompute
it from a stated predicate before quoting it.

## 2026-09-09 — the qwen and gemma reference figures were constructed differently
See RESULTS A-2: single position-0 pass means for qwen (0.6600 / 0.4924, not
EXP-2026-09-005's two-position 0.6569 / 0.4946), multi-pass means for gemma.
Both contrasts keep their sign; `0.1034` is recorded beside `0.1012`.

## 2026-09-09 — the manifest was a scaffold until the record repair
See RESULTS.md A-1 for every field filled on 2026-09-09 (old → new). One
metric value changed in place: `qwen_distinct_values_this_population` 15 → 17
(A-4).
