# ISSUES — EXP-2026-11-009

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

## 2026-11-15 — The first rerun recorded no stage timings; fixed and the three arms rerun
**Impact:** The first rerun at 3187ad51 saved no per-stage timings for `generic_planned`. The text-replace edit matched the gold-replay loop runner first, not `_run_real_pipeline`. Coverage figures were unaffected.
**Resolution:** `_run_real_pipeline` now records `run.timings`, and a test fails if it does not. All three arms were rerun back to back at the fixing commit, and the first rerun was discarded. Every rerun figure in RESULTS.md comes from the second rerun.
