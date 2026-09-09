# ISSUES — EXP-2026-08-014

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

<!-- Entry template — newest first:

## YYYY-MM-DD — <one-line summary>
**Impact:** what this changes about the reported numbers (e.g. "seed 3 excluded; n=4 not 5 for this cell").
**Cause:** the mechanism, if known.
**Resolution:** what was done. "Not resolved" is a valid answer.
**Paper implication:** what must be stated in the paper because of this.

-->

## 2026-09-09 — Record repair: date inversion and an unreproducible test count
**Impact:** none on the numbers. `date_completed` was 2026-08-23 (before `date_started`); corrected to 2026-08-24 from artifact mtimes and commit `95b8c003` (RESULTS A-1). The "13 assertions" count quoted for `test_verifier_gates.py` does not match the file (9 tests, 29 asserts) and has no recoverable source.
**Cause:** the output-directory slug was copied into the date field; the assertion count was typed, not counted.
**Resolution:** date corrected in place; the count is flagged in A-1 and left in the prose (append-only).
**Paper implication:** none.
