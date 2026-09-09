# ISSUES — EXP-2026-07-011

## 2026-08-06 — Recorded as an experiment despite being an audit

**Impact:** `metrics.primary` is null and no metric here was measured against
gold. A reader scanning `INDEX.md` will see this row with an em-dash where every
other row has a score.

**Cause:** Deliberate. The portability claim needs a traceable ID like any other
claim, but assigning it a primary metric would misrepresent a code reading as a
measurement.

**Resolution:** Not a defect. Documented so the empty metric column is read as
honesty rather than an omission.

## 2026-08-04 — The template count was corrected after this audit

**Impact:** The audit was written against "17 Cypher and 11 Gremlin templates",
which reads as 28 distinct templates.

**Cause:** Those are per-builder counts. `describe`, `describe_by_name`, and
`expand` are declared in **both** builders.

**Resolution:** The true figure is **25 distinct template identifiers, of which
19 are exercised by the 120-question bank**. This folder records 25/19.
Additionally: 15 of 17 Cypher and 9 of 11 Gremlin templates are reachable from
`build()`, one each only from `expand()`, and one each (`node_lookup`,
`capec_lookup`) is **unreachable**.

**Paper implication:** Quote 25, not 28. Two templates are dead code and should
not be counted as capability.

## 2026-09-09 — The headline counts went stale without an amendment, and the pointer with them

**Impact:** For five weeks (2026-08-09 → 2026-09-09) this record asserted
25 distinct / 19 exercised while the script it cites as the derivation printed
first 25/19 on a tree that had already grown, then (after `b72eb23`,
2026-08-31) 29/20. The pointer hash for `derive_templates.py` failed from
2026-08-31.

**Cause:** The count is a property of the live builders, and the record had no
mechanism to notice the builders changing. `EXP-2026-08-001` added four
templates on 2026-08-09 and did not touch this folder.

**Resolution:** 25/19 withdrawn, 29/20 recorded from the script's output
(RESULTS A-1); the script and its five inputs are now hashed so the next
drift fails the validator instead of going unnoticed. The
`mitre_specific_templates` figure (19) is kept as the audit's classification;
the same rule applied today gives 18 literal (20 with the f-string pair), which
is recorded in `data/metrics.json` but not promoted, because the script does
not print it.

**Also unrecoverable:** the exact tree the audit prose was written against on
2026-07-26 — the 17 + 11 per-builder counts in `portability.md` predate the
2026-08-04 reconciliation and were never mechanically derived.

**Paper implication:** Quote 29 distinct / 19 builder templates exercised and
say "as of `e7ee893`"; re-run the script before quoting anything.
