# ISSUES — EXP-2026-08-018

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

## 2026-09-09 — Elapsed wall clock was never recorded; the 6.5 h in the manifest was summed latency
**Impact:** `compute.wall_clock_hours` is now `null`. The old 6.5 was Σ `wall_s_total` over the three LLM repeats / 3600; `wall_s_total` is the sum of per-question `elapsed_s`, not elapsed time at 16 workers. The 67× cost ratio (§T5) compares two summed latencies and stands. Also corrected: `n_runs` 1 → 3 (Q34).
**Cause:** the sweep records per-request latency only; the field was filled from it.
**Resolution:** not recoverable for this run. Future sweeps should record start/end timestamps.
**Paper implication:** quote the 67× as a latency ratio; do not quote 6.5 h as run time.
