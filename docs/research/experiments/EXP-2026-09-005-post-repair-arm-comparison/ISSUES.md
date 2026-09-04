# ISSUES — EXP-2026-09-005

## I-1 — One run per arm, no interval

`D-010` still in force. Each arm answered once; only the grading was repeated,
twice, order-counterbalanced. The 0.1623 gap is argued from magnitude — 32× the
grader's measured 0.0050 spread — not from a test. This is the same limitation
EXP-2026-09-002 recorded as its I-5 and it is not fixed here.

## I-2 — The two arms did not see identical graphs across the comparison

"Pre-repair" figures come from EXP-2026-09-002, produced against the ATT&CK build
that preceded the property-policy widening. The widening was applied to the
graph **both** arms read, so it is not a per-arm confound, but the deterministic
arm's +0.0684 is attributable to the retrieval repairs *and* the build change
together and cannot be split between them from this run.

## I-3 — The pre-repair recall figure quoted here is not the published one

Published dev recall was 0.4350; this uses **0.4492**, the same artifacts
re-scored under the property-gold rule. Comparing 0.5176 against 0.4350 would
credit the repair with the scoring rule's effect. Both numbers are in the record
and the smaller move is the one quoted.

## I-4 — Two scorer defects remain, and they depress both arms

EXP-2026-09-004 I-2 and I-3: an abstention can earn credit from the refusal
message's example ids, and a correct CAPEC answer scores zero because it names
`capec:category:152` where the gold expects `CAPEC-152`. The second was worth
0.185 on the subset it was measured over. Both were left unfixed deliberately —
they raise scores and need the pre-registration discipline the property-gold rule
carries. **Every figure here is a floor.**

## I-5 — `llm_query` is absent

Not re-run. Its budget defect is fixed but its cost is unmeasured; the probe was
sharing a relay with this judging run and was stopped rather than reported from
confounded timings. C-012's baseline is therefore still open.

## I-6 — The grader is the same model that served the arms' relay

`qwen38-27B-v2` graded answers produced by a system whose `llm_query` arm uses
the same served model. That arm is absent from this run, so nothing here is
self-graded — but the relation is recorded so a reader does not have to infer it.
