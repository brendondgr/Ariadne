# ISSUES — EXP-2026-08-003

## 2026-08-10 — The Gremlin fixture was empty when the session began

**Impact:** None to the recorded numbers — it was caught before the run that
counts. A first attempt was started against an empty CAPEC graph (0 vertices),
killed, and its output directory deleted. Every CAPEC and federated question
would have retrieved nothing, and the arm would have looked catastrophically
worse than the templates.

**Cause:** The Docker volume does not survive between sessions. This is a
recurring trap: the same thing cost 73 failing specialist tests at the start of
`EXP-2026-08-001`.

**Resolution:** `uv run main.py --dataset capec --graph gremlin` before the run;
verified 4769 vertices and a clean 407-test specialist suite before restarting.
Recorded because a reader reproducing this must load the fixture first, and
because an empty-graph run fails *quietly* — every query returns zero rows and
nothing errors.

## 2026-08-10 — Arm H is not judged on this bank

**Impact:** No correctness figure exists for Arm H here. The headline is
retrieval.

**Paper implication:** `gold_in_evidence` 0.8952 may **not** be printed beside
Arm A's 0.689 or Arm F's 0.708. The ≤0.838 upper bound in `RESULTS.md` §3 is
arithmetic under an explicitly optimistic assumption and is not a measurement.

## 2026-08-10 — The metric cannot see the failure mode Arm H is most exposed to

**Impact:** `gold_in_evidence` is pure recall. Arm H's two deliberately
over-returning primitives (`EXP-2026-08-001` `ISSUES.md`) are invisible to it and
would cost precision under a judge.

**Note:** the two categories where that over-return applies, `H-ABS` and
`H-PRE`, already score 0.100 judged on both template arms with retrieval at
1.000 — so the category is weak for every arm, and this experiment cannot
separate Arm H's contribution to that weakness from the pre-existing one.

## 2026-08-10 — n = 30

**Impact:** `EXP-2026-08-002` reports 95% CIs of roughly ±0.13 on judged
correctness at this size. Four improved questions sit inside that band.

**Why it is still worth reporting:** the improvement is measured on retrieval,
where the per-question quantity is a set-membership test with no judge variance,
and it is *concentrated* — 2 categories moved, 14 did not. A diffuse gain of the
same magnitude would deserve much less confidence.

## 2026-08-10 — The residual defect is shared with the templates, not introduced

**Impact:** All five remaining missing ids come from `_generic_bridge` being an
inner join. `capec_maps_to` and `cwe_chain` have the same shape, which is why
Arm A and Arm F lose the same ids.

**Note:** three of the four affected questions are `expect_no_correlation` cases
that the judge already scored 1.00 or 0.50 on Arm F. The retrieval metric is
stricter than the judge here, and correctly so: an ungrounded abstention and a
grounded one are not the same answer.
