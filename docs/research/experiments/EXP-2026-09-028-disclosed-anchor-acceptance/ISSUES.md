# ISSUES — EXP-2026-09-028

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

## 2026-09-16 — run from the working tree, committed without change
**Impact:** `dirty: true`. **Cause:** the arm ran before the record commit. **Resolution:** commit
`311eb446` holds the code that ran. **Paper implication:** none.

## 2026-09-16 — the reranker ran through the evaluation venv, not in-process
**Impact:** ~3 s of subprocess start per reranked question; no effect on the answers.
**Cause:** `fastembed` is not a project dependency and installing it is a download the operator
has not approved. **Resolution:** the adapter's venv bridge, recorded in the manifest.
**Paper implication:** name the reranker backend and model exactly.
