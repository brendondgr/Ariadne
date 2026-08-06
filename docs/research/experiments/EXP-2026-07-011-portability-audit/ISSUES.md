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
