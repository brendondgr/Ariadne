# ISSUES — EXP-2026-09-025

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

## 2026-09-15 — run from the working tree, committed without change
**Impact:** `dirty: true`. **Cause:** the arms ran before the record commit. **Resolution:** commit
`8b269edc` holds the code that ran; nothing under `utils/` or `scripts/` changed between the runs
and that commit except the addition of the `generic` harness arm and a new test file, neither of
which the running arms read.
**Paper implication:** none.

## 2026-09-15 — the mode amendment is not separated from direct execution
**Impact:** the T3 gain attributed to "direct execution" includes the effect of binding a form as an
enumerate when it names a target label (PROTOCOL.md amendment).
**Cause:** both landed in the same arm; a separate arm was not run.
**Resolution:** disclosed; the combined arm is what ships or does not.
**Paper implication:** describe the two together as "execute the form the question denotes".
