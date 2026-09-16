# ISSUES — EXP-2026-09-023

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

## 2026-09-15 — Step 0 numbers were first computed outside the record
**Impact:** none on the values; `data/shipped_vs_prototype.py` and
`data/exact_name_probe.py` re-derive them from hash-pinned inputs and the two
agree to four decimals with the scratchpad run that the 2026-09-15 review of
`EXP-2026-09-022` reported in chat.
**Cause:** the review was a reading of another experiment, not an experiment,
and its probes were run in a scratchpad before this folder existed.
**Resolution:** entered here as Step 0, labelled as motivation rather than
result. The reranker half of that review (bge-small over the shipped top 25)
is **not** entered here; it belongs to plan Step 9's experiment.
**Paper implication:** none.

## 2026-09-15 — H1's threshold was seen on the exposed bank
**Impact:** the 1 % document-frequency cut in H1 is a value read off the exposed
bank during the review, so the exposed-bank H1 figures are confirmation of a
fit, not a test. The sealed bank is the test.
**Cause:** the review measured four candidate thresholds (0.5 %, 1 %, 2 %, 5 %)
to see whether *any* rule separated gold from incidental binds.
**Resolution:** the value is fixed in `PROTOCOL.md` before the sealed bank is
opened; if it must move to pass there, H1 is recorded as failed.
**Paper implication:** the rule's generality claim rests on the sealed bank and
on the non-cyber fixture tests, not on the exposed-bank numbers.
