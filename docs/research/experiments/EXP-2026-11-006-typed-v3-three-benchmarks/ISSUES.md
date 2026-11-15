# ISSUES — EXP-2026-11-006

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

## 2026-11-14 — Part B: 5 typed3 requests disagree across backends by float rounding
**Impact:** typed3's backend agreement on part B is 0.987 (Gemma) and 0.990 (Qwen), not 1.000.
H1 still holds there (differences 0.013 and 0.010). Parts A and C agree on 1.000.
**Cause:**
- All five are `per` requests summing fincen's `Filing.amount`, a float, over many filings.
- Neo4j and TinkerGraph add the floats in different orders, so the last digit differs, e.g.
  1713352259.1799994 against 1713352259.1799998.
- The normaliser compares floats at full precision. The two compiled queries mean the same
  thing, and the Cypher side matched the gold.

**Resolution:** not changed after the run; the scorer is pre-registered. A tolerance on float
comparison would make these five agree.
**Paper implication:** say that backend disagreement here is summation order, not compiler logic.

## 2026-11-14 — The typed2 arm runs on the v3 validator and compilers
**Impact:** Gemma's part-A typed2 score is 0.950 here against 0.920 in EXP-2026-11-005.
- **Four of the six changed answers are identical replies.** EXP-2026-11-005's v2 validator
  rejected them ("optional[0]: an edge must be an object"); v3 accepts an edge reference in
  `optional`.
- **The other two changed because the reply itself changed.** That is provider nondeterminism
  at temperature 0: 55 of Gemma's 200 part-A typed2 replies differ in text from EXP-2026-11-005.
**Cause:** by design. v3 is a superset, and the typed2 arm here means v2's prompt text run on
the v3 engine. The protocol states this.
**Resolution:** none needed. typed3 minus typed2 therefore measures the v3 prompt text, not the
v3 engine.
**Paper implication:** call the arm "v2 prompt", not "v2 format".

## 2026-11-14 — Gemma hits the token cap on a third of part-C typed3 replies
**Impact:** 161 of Gemma's 450 part-C typed3 replies (36%) ended at the 8,192-token cap before
any JSON was written; typed2 101, free Gremlin 86, free Cypher 7.
- 99 of Gemma's 210 part-C typed3 misses where free Cypher was right are such cut-offs.
- Qwen at `medium` never capped on typed arms. It was killed as well, so the verdict does not
  rest on the cap.

**Cause:** Gemma's long reasoning before the answer; its server has no reasoning setting.
**Resolution:** none; the protocol stated the cap as a known limit, the same for every arm.
**Paper implication:** report Gemma's typed figures with the cut-off share beside them.

## 2026-11-14 — Shared runner reused from EXP-2026-11-005
**Impact:** none on either experiment.
- `utils/killtests/t2c/run.py` gains a `KILLTESTS_EXPERIMENT=exp006` mode: parts A/B/C, the EXP-006
  arms, and v3 cards. The default mode is EXP-2026-11-005's, unchanged in behaviour; that run is
  at tag `killtests-exp005-run`.
- `t2c/load.py` writes v3 cards to `cards-v3/`, so EXP-2026-11-005's cards stay as run.
**Paper implication:** none.

## 2026-11-14 — Verification stores recreated
**Impact:** none. The verification containers (`killtests-verify-*`, ports 5480/6480) were
removed after EXP-2026-11-005 and recreated from the same images for v3's verification. The
fixture and terrorist_attack were reloaded, and node counts matched (1,629).
