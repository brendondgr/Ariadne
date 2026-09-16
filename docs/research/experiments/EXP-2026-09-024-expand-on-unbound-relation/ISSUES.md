# ISSUES — EXP-2026-09-024

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

## 2026-09-15 — the pre-registered exact guard could not pass by construction
**Impact:** H1 is recorded as falsified on `records_exact`; the recall result stands.
**Cause:** the fallback returns a superset of the anchor's record; where the gold *is* that
record (26 of 240 T1/T2 questions), a superset is not exact. The guard "records_exact within
± 0.02" assumed the fallback would not fire there, and nothing in the mechanism could know.
**Resolution:** reported as written; not moved. The plan's recall-primary rule is the one
Step 10 applies.
**Paper implication:** widened answers need a judged score; exact-match cannot grade them.

## 2026-09-15 — `abstained` counts an abstaining expansion hop against a whole answer
**Impact:** T1 `abstained` 0.1917 → 0.2667 under the treatment while several of those rows reach recall 1.0.
**Cause:** the harness sets `abstained` when the answer carries any abstention statement; a
joined expansion sub-question that finds nothing adds one.
**Resolution:** noted; the harness definition is not changed inside an experiment.
**Paper implication:** report abstention per hop for multi-hop arms.

## 2026-09-15 — run from the working tree, committed without change
**Impact:** `dirty: true`. **Cause:** the arm ran before the record commit. **Resolution:** commit
`3a32d2b0` holds the code that ran; nothing under `utils/` or `scripts/` changed between.
**Paper implication:** none.
