# ISSUES — EXP-2026-11-011

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

## 2026-11-16 — Built and tuned before pre-registration (disclosed)
**Impact:** None on the recorded figures, which come from a run at ef2e80c0.
**Cause:** The code and tests were written first. A dry run of the hub benchmark then showed Neo4j's 10⁶ fetch at 8.3 s, and the fetch was changed twice before the protocol was written: no server-side sort and a 10,000-record fetch size (6.5 s), then one collected list (1.5 s).
**Resolution:** Disclosed in PROTOCOL.md. G4 was amended before any run, because the dev answers use the "X has N" enumeration form, not "N result(s)".
