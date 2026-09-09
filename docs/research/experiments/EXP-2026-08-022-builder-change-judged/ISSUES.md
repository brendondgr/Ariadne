# ISSUES — EXP-2026-08-022

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

## 2026-09-09 — Dirty tree explained; no seeds apply; wall clock and metrics file back-filled
**Impact:** none on the numbers. `scripts/builder_change_judged.py` and this folder were uncommitted during the four grading sessions and entered at `338ad90` (20:19), after the last session (20:16); the answer-generating code was committed (`bfac8cc` for the new builder). `seeds: []` because both answer conditions are LLM-free and byte-reproducible (hashed in POINTERS) and the grading call takes no seed. `wall_clock_hours` corrected 0.0 → 2.5 from file mtimes; `data/metrics.json` created from the script's `--out` (RESULTS A-1).
**Cause:** the manifest was filled before the analysis script existed.
**Resolution:** recorded.

## 2026-09-09 — Answer-directory pointers re-pinned as tree hashes
**Impact:** the four answer-directory rows mismatched the validator's tree hash although the 30 answer files in each directory are unchanged (their original 30-file digests reproduce). Rows now carry tree hashes; the `bank2026*` trees will move again whenever another experiment grades those answers, so the judgment-set glob rows are the durable pins for this experiment (RESULTS A-1).
**Resolution:** re-hashed.
