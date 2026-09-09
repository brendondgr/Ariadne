# ISSUES — EXP-2026-08-008

## 1. Seven of the LLM-query arm's failures are ours, not the model's

**Date:** 2026-08-19

The evidence reader dispatches on the column shapes the templates emit. A
free-form query returning `group_id`+`group_name` and nothing else matches no
branch and normalises to nothing, however correct the query and the rows.

**Impact:** the raw 0.5000 conflates query defects with reader limitations.

**Resolution:** reported apart (19 answered, 7 reader, 3 gate, 1 execution), and
the headline conclusion is stated against the reader-adjusted 0.5739 as well.
The conclusion does not depend on the ambiguous cases. Fixing the reader is
`Q18`; it was deliberately not attempted here, because doing so mid-experiment
would have made the arm unmeasurable in this run.

## 2. Two of the three gate rejections were empty replies

**Date:** 2026-08-19

`H-CHN-01` and `H-CHN-03` produced "pre-run gate rejected all drafts: empty
query" — the model returned nothing, the token-truncation mode already recorded
twice in this repository (judge runner, bank author).

**Impact:** part of the gate-rejection bucket is also our budget, not the
model's inability to write a legal query. Follow-up 2 re-runs with a larger one.

## 3. The fresh bank is machine-authored

**Date:** 2026-08-19

Blindness is preserved — the author sees one entity and nothing about the
system — but phrasing is less varied than a human's, and the bank may be easier.

**Impact:** the fresh-bank figures may be slightly optimistic.

**Mitigation:** the corrected co-authorship figure in RESULTS §2 rests on the
*paired* catalogue-vs-blind comparison over the original human-authored
questions, which this does not touch, and it shows the same collapse.

## 4. One catalogue answer did not grade

**Date:** 2026-08-19

n = 119 of 120. The oversized-enumeration truncation recorded in
EXP-2026-08-007 ISSUES §3; recoverable at a larger budget, not recovered here
because it cannot move a 120-question mean materially.

## 5. A regression that is not one

**Date:** 2026-08-19

`H-EXE-01` fell 1.0 → 0.7 across the composer fix. The answer strictly *gained*
content — claims went from three to four with none removed, and the grader
confirms all three gold identifiers are still present. It docked the answer for
naming execution-step ids rather than their content, a criticism that applies
equally to the pre-fix answer that scored 1.0. Recorded as grader instability at
the case level, consistent with the 0.70 verdict agreement in EXP-2026-08-007,
not as a functional regression.

The grader's underlying point is nonetheless correct and is follow-up 3.

## 6. Seeds unrecorded; one run per arm

**Date:** 2026-08-19

Consistent with D-010. No arm-level variance estimate exists; the grader-level
spread from EXP-2026-08-007 is not a substitute and is not presented as one.

## 7. Pointer scheme replaced; raw directories have gained later sidecars

**Date:** 2026-09-09 (record audit)

The six judgment-set rows in `data/POINTERS.md` carried set digests the
validator cannot check, and every one of the six directories has since gained
grader sidecars written by later experiments (2026-08-20 `.cross`; 2026-08-21
`.c015`, EXP-2026-08-009; 2026-08-31 `.qwen38*`, EXP-2026-08-021, and `.bld*`,
EXP-2026-08-022; 2026-09-05 `.g31*` / `.q38b*`). The answer files and the
`.judgment.json` sidecars this experiment's figures come from are unchanged
(all recorded figures were recomputed from them on 2026-09-09 and reproduce
exactly; the old set digests still verify). The rows are now tree hashes as of
2026-09-09 and name what was added. Any later addition will show as a hash
mismatch and must be recorded here.

## 8. The grader's and the query writer's model is not determinable from the record

**Date:** 2026-09-09

The manifest carried `llm.model: "relay/skynet (grader and query writer);
relay/local for bank authoring"` — two relay aliases, no model. Every
`.judgment.json` sidecar of this run records only `{"model": "skynet"}`, and
`docs/evaluation/README.md` §"The model behind `skynet`" classifies
2026-08-19..21 as a window whose served model is undetermined. The `llm_query`
arm's answers likewise record no model name. `llm.model` is now
`relay/unknown@2026-08-19` (RESULTS A-1); the roles (grader, query writer,
bank author via the `local` alias) are recorded there. The same answers
re-graded by a named model are in EXP-2026-08-021 (`qwen38-27B-v2`, five
passes) and EXP-2026-09-006.
