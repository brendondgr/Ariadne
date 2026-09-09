# ISSUES — EXP-2026-08-016

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

## 2026-09-09 — A-1's post-Q21 routing result has no artifact; the pointed sweep is pre-fix
**Impact:** the manifest's leak figures (568 → 5 records, 3 → 1 probes) are backed by `docs/evaluation/isolation-2026-08-23/metrics.json` (2026-08-24 14:02, pre-fix). A-1's post-fix readings — `attack_group` → `attack`, 1 record; totals unchanged; 0 of 300 catalogue answers changed — were never written to a file and cannot be verified from the record (RESULTS A-2).
**Cause:** the Q21 commit `6ee9f6e` changed `utils/planner/drafter.py` and prose only; the sweep was not re-emitted to a new `--out`.
**Resolution:** not resolved. `uv run python scripts/isolation_probes.py --out <a new directory>` at any commit ≥ `6ee9f6e`, with all three sources live, reproduces the post-fix table; the pre-fix artifact must not be overwritten.
**Paper implication:** quote the 568 → 5 leak reduction (artifact-backed); state the `attack_group` repair as reported in the amendment, not as measured in the pointed file.

## 2026-09-09 — Record repair: date inversion and phase-1 metrics back-filled
**Impact:** none on the numbers. `date_completed` corrected 2026-08-23 → 2026-08-24 (commit f362d3c); `manifest_metrics` added to `data/metrics.json` for the seven manifest values, three of which (`gate_probes`, `gate_block_rate_after_fix`, `gate_bypasses_found`) were never in any file because `score_safety()` computes them live.
**Resolution:** corrected in place (RESULTS A-2).
