# ISSUES — EXP-2026-08-019

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

## 2026-09-09 — "Wall clock per repeat 398 s / 321 s" is in no artifact
**Impact:** the two elapsed-time figures in RESULTS §"Throughput" and the derived "19 % wall clock" cannot be reproduced from the record; the sweep writes only summed per-question latency (`wall_s_total`). The per-request latency (53.0 → 85.5 s, +61 %) and fallback (14.0 → 28.3) rows, which carry the finding, do reproduce. Also corrected: `n_runs` 1 → 3 (Q34) and `per_question_latency_s_w16.std` 6.5 → 6.6 (RESULTS A-1).
**Cause:** elapsed time was read off the console and not written down.
**Resolution:** not recoverable. Future sweeps should record start/end timestamps per run.
**Paper implication:** do not quote 398 s / 321 s or the 19 %; quote the latency and fallback rows.
