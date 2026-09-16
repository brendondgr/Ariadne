# ISSUES — EXP-2026-09-026

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
**Impact:** `dirty: true`. **Cause:** each arm ran before its record commit. **Resolution:** commits
`48acff3d` (dispatch by seed origin) and `37a8c755` (A-1) hold the code the `generic` and
`generic_form` arms ran on respectively; nothing else under `utils/` changed between. The
`generic_form` arm ran while the Step 8 router consumer had been added behind its own flag
(off in every arm here).
**Paper implication:** none.

## 2026-09-15 — A-1 is a second look at the same banks
**Impact:** the `generic_form` figures are not a blind test of the two A-1 fixes.
**Cause:** both fixes came from tracing cases the first arm had already scored.
**Resolution:** disclosed in PROTOCOL.md; the verdict (parity falsified) does not depend on it.
**Paper implication:** none beyond the disclosure.
