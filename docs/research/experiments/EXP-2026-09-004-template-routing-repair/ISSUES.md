# ISSUES — EXP-2026-09-004

## I-1 — The prediction was wrong in the same direction, again

EXP-2026-09-003 predicted 47 movers and got 2. This one predicted 23 and got 14.
Both times the **"will not move"** half was exactly right — 12 of 12, then 9 of 9
— and both times the "will move" half was over-optimistic.

The asymmetry has a cause worth naming: predicting a failure will *persist*
requires only that the mechanism blocking it is unchanged, while predicting one
will *clear* requires that no other mechanism is behind it. Each fix in this
sequence has exposed another defect that the previous one was hiding.

**Refuse to conclude:** that any scope claim in this family is reliable before
its re-run.

## I-2 — Abstaining earns coverage credit from the refusal message

The composer's abstention text names concrete examples — *"e.g. T1566, M1017, or
CAPEC-98"* — and `_surfaced_ids` reads ids out of the narrative with a regex. Any
question whose gold contains one of those three is credited for **refusing to
answer it**.

Four answers in the EXP-2026-09-002 artifacts scored this way: 0.0196, 0.0213,
0.0345 and **0.1667**. Small in aggregate, and it silently inverts the sign of a
comparison on the affected question — the one in this run looked like a
regression and was the removal of a false positive.

Not fixed here: out of scope, and the fix belongs with the scorer changes that
carry a pre-registered rule.

## I-3 — The scorer recognises the source's id vocabulary, not the graph's

The answer names `capec:category:152`; the gold expects `CAPEC-152`.
`_ANSWER_ID_RE` matches `CAPEC-\d+` and nothing else, so a correct, fully
enumerated CAPEC answer can score 0.0000.

Measured on this set: **mean recall 0.4059 as scored, 0.5913 counting the URN
form** — the defect is worth 0.185 here.

This is the third defect of its family found in three days: the bank asks in the
source's vocabulary and the system answers in the build's, and every mismatch
reads as a system failure. The other two were the property-gold matcher and the
`HAS_MEMBER` / `MEMBER_OF` naming inversion.

**Refuse to conclude** that 0.4059 measures the routing fix. Not fixed here for
the same reason as I-2.

## I-4 — n = 32, one run, no interval

A targeted re-run, not a bank re-measurement. `D-010` still in force.

## I-5 — Before and after did not see identical ATT&CK graphs

"Before" comes from the EXP-2026-09-002 artifacts, produced against the graph
build preceding the 2026-09-03 property-policy widening. 29 of the 32 questions
are CAPEC-anchored and CAPEC's build did not change; the 3 ATT&CK property reads
**did** see a widened record, so their 0.0000 → 0.2250 and 0.0000 → 1.0000 are
attributable to the routing fix *and* the build change together, not to routing
alone.

## I-6 — Two pre-existing suite failures, neither caused here

Unchanged from EXP-2026-09-003 I-5: the dangling `POINTERS.md` path in
EXP-2026-09-001, and the `ORCH_MAX_HOPS` pin.
