# ISSUES — EXP-2026-08-004

## 2026-08-10 — The hand-written templates keep the defect, deliberately

**Impact:** `capec_maps_to` and `cwe_chain` are inner joins with the same shape
and lose the same identifiers. Arms A–G therefore still cannot ground a
"no mapping exists" answer, and `EXP-2026-08-003` shows them losing exactly the
ids this experiment recovers.

**Cause:** Fixing them changes default-cascade behaviour, which breaks
`test_generic_only_isolation.py` — the byte-identical check against
`freeze/holdout-v1` — and makes every arm figure in the 2026-07-26 study
non-comparable with every other.

**Resolution:** Not fixed. This is an operator decision about whether the study's
arm figures are re-run, not a call the implementation should make unilaterally.
Recorded as a follow-up in `RESULTS.md` §7.

## 2026-08-10 — Nothing in this experiment is judged

**Impact:** All figures are retrieval. `1.0000` on either set may not be printed
beside a correctness number.

**Note:** the `answer_gap` block in `data/metrics.json` reuses
`EXP-2026-08-002`'s committed **Arm F** judgments. It characterises Arm F's
answers, not Arm H's. Arm H has never been judged on either bank.

## 2026-08-10 — The primary metric is now saturated on both sets

**Impact:** `gold_in_evidence` reads 1.0000 on the development catalogue *and*
the blind holdout. It has no headroom left and cannot detect a regression that
trades precision for recall — which is the failure mode this arm is most exposed
to, since two of its primitives deliberately over-return.

**Resolution:** Not resolvable with this instrument. Recorded because a reader
should not take a second 1.0000 as twice the evidence; it is the same metric
telling us it has stopped being informative. Further work on this arm needs a
judged measurement.

## 2026-08-10 — The answer-gap classifier ranks by magnitude, which is a choice

**Impact:** `answer_gap.classify` picks the class with the largest observable
deficit rather than following a fixed severity ladder. A different, defensible
ordering would put `unfaithful` first unconditionally and report 2 unfaithful
cases instead of 3 under-enumeration ones.

**Cause:** A fixed ladder scatters one defect across classes. `H-PRE-01` states
1 of 4 gold ids and carries a 0.1 faithfulness deduction; precedence would file
a 0.75 failure under a 0.1 symptom.

**Resolution:** Magnitude ranking, documented in the module and asserted in
`utils/evaluation/tests/test_answer_gap.py` in both directions — a large
faithfulness deficit still wins. Recorded because the taxonomy is an analytical
choice and the counts depend on it.

## 2026-08-10 — Development-set saturation hid this defect entirely

**Impact:** The 120-question catalogue moved not at all: 1.0000 before and
after, 0 improved. The same defect was present — record count rose 950 to 966 —
but no gold assertion in that catalogue ever required an anchor with an empty
mapping.

**Note:** the blind author wrote four such questions in thirty. This is the
co-authoring threat visible in miniature, and an argument for treating a
saturated development metric as evidence of exhausted measurement rather than of
a solved problem.

## 2026-08-10 — Single run, one model, seeds unrecorded

Same limitation as every arm of the study. `n = 30` on the blind set.
