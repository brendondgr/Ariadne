# ISSUES — EXP-2026-08-006

## 2026-08-18 — The primary metric is saturated on both banks for both arms

**Impact:** `gold_in_evidence` reads 1.0000 for the default cascade and for the
generic branch, on the development catalogue and on the blind holdout. It cannot
detect a precision loss, which is the failure mode an outer join is most exposed
to, since it returns strictly more.

**Resolution:** not resolvable with this instrument. Further work on either arm
needs a judged measurement.

## 2026-08-18 — The outer join deleted an abstention before it was noticed

**Impact:** for one commit, "which ATT&CK techniques does CAPEC-116 map to?"
answered with the pattern's abstraction and status and no statement about
mappings. No fabrication, and the unsupported-claim rate stayed 0.0 — the answer
simply stopped answering.

**Cause:** `_empty_ok_results` keyed the honest-empty test on record count, a
definition the outer join invalidated.

**Resolution:** fixed in the same commit — a declared join with no join values
is an honest empty. Recorded rather than folded in silently, because it is the
clearest evidence on file that a rising retrieval metric can hide a fall in
answer honesty.

## 2026-08-18 — Arm F was not re-run

**Impact:** only the deterministic arm is measured. The generation-2 arm table
is incomplete, and Arm F's blind figure is still the generation-1 one.

**Cause:** the local LLM server was restarting during this run.

**Resolution:** follow-up 1. Not a defect in the result, but no arm comparison
may be drawn from this experiment alone.

## 2026-08-18 — Arm-figure comparability is now generational

**Impact:** every figure produced before `freeze/arm-baseline-2` and every
figure after it are comparable only with the generation labelled. The
2026-07-26 arm table is generation 1.

**Resolution:** the isolation test enforces both generations — eight templates
must still match `freeze/holdout-v1`, all ten must match generation 2 — so a
further silent divergence cannot ride along under cover of this one.

## 2026-08-18 — A draft of the gold change corrupted an unrelated case

**Impact:** `A-NEG-01` (nonexistent technique T9999) was briefly flipped from
`expect_empty` to `expect_no_join`, which also rewrote its `ex_gold.expected`
from `[]` to `["T9999"]` — asserting that a nonexistent technique should appear
in the evidence.

**Resolution:** reverted before commit, caught by diffing the recompiled bank
rather than by review. Recorded because it is the exact failure mode that makes
editing gold dangerous, and it happened on the first attempt.
