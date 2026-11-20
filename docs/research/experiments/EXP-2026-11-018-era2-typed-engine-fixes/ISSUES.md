# ISSUES — EXP-2026-11-018

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

## 2026-11-20 — Two "anchor ignored" measures exist; the pre-registered one is case-defined
**What:** `scripts/era2_catalog_score.py` already prints a table of `records_exact` "with the anchor ids ignored", which removes the plan's own anchors. The secondary measure pre-registered here (`scripts/era2_anchor_exact.py`) removes the ids written in the gold question, so it is defined by the case and treats every arm alike.
**Impact:** RESULTS quotes the pre-registered measure; the scorer's table is left as it is and differs by a few answers per tier.

## 2026-11-20 — The first dev smoke launch failed on argument splitting
**What:** dev ids containing spaces (`MAPS_TO[OWASP Attacks]`) split the unquoted `--only` argument; the harness exited with rc=2 before any call. Re-run with the argument quoted (smoke only; the measured run does not use `--only`).
**Impact:** none on the measured run.
