# ISSUES — EXP-2026-08-009

## D1 — The pre-registered comparison was confounded, and the first pass proved it

**Severity: high. Found by running it. Recorded here rather than quietly fixed.**

`PROTOCOL.md` names `generic` as *"the like-for-like comparison"* and says the
number of stores is the only variable between it and `merged`. **That is false**,
and the first grading pass is what showed it.

`generic` is in the arm group that `untruncated_env` gives the LLM posture to:
it disables the hand-written templates **and** turns on the claim-grounded LLM
narrator and the facet-chasing loop. `merged` was built with the deterministic
posture. So reading one against the other varies two things at once — one store
against two, *and* a deterministic composer against a language model.

The evidence is visible in the answers themselves. Every `generic` answer's
`run_meta` reads `synthesis: llm (claim-grounded)`; `merged` and `deterministic`
read `synthesis: deterministic`. All three of the merged arm's fabrications in
the first pass were one defect of the **deterministic composer** — naming
software and group identifiers as "used techniques" — which the narrator arm
does not have because a language model writes its prose. Attributing that to
merging would have been wrong.

**What changed.** A new arm, `generic_composed`: schema-derived primitives,
deterministic composition, two stores. Against `merged` the only remaining
difference is the number of stores, and **neither side has a language model**,
so both are byte-reproducible and a difference between them cannot be run
variance. EXP-2026-08-001 measured this configuration's retrieval and called it
Arm H; it has never been judged.

`generic` is retained as a secondary — it is the recorded Arm H and the study's
strongest arm — but it is no longer the comparison C-015 rests on.

**Consequence for the record.** The first pass's figures are superseded by the
second, and both are kept. Nothing from the first pass is quoted as a C-015
result. The protocol's original text stands with a dated amendment rather than
an edit, because a protocol rewritten after its first result is not a protocol.

## D2 — Two cases needed a larger grading budget

`bank20260819/merged/H-REV-01` and `bank20260820/deterministic/H-CHN-01` both
returned an empty reply at 8192 tokens and again at the automatic 16384 retry,
leaving those two cells at n=29. Both graded on a manual third attempt at 32768.

Unlike the night-2 case recorded in `docs/evaluation/night2-2026-08-20/UNGRADED-CASE.md`,
one of these **is** an oversized answer: the deterministic H-CHN-01 answer is
177,220 characters. The merged H-REV-01 answer is 15,662, which is ordinary, so
size is not the whole story even here.

## D3 — The preflight's answer count was wrong in the first pass's state file

It globbed `*.json` in the answers directory, which also holds `.judgment*.json`
sidecars, so it recorded 90 where there are 30 answers. The grader itself was
never affected — `answer_files` excludes any name containing `.judgment`, a fix
made earlier this month — so no figure is wrong. Only the recorded preflight
number was. Fixed to count through the judge's own selector.

## D4 — Headline values withdrawn; the "8 passes" include the pass being corrected

**Date:** 2026-09-09 (record audit)

A-1 (2026-08-31) says the reported −0.0334 / +0.0000 "should not be quoted",
but until 2026-09-09 they were still the manifest's `metrics.values` and its
`primary`. They are now in `metrics.withdrawn` (withdrawn_on 2026-08-31) and the
A-1 order-corrected eight-pass values −0.0587 / −0.0520 (merged − federated)
are in `values`; `primary` points at the bank-19 one. RESULTS A-2.

Two caveats on the A-1 figures, established by recomputation from the
sidecars on 2026-09-09: the "forward, 6 passes" means (−0.0565 / −0.0491)
reproduce **only if the original `.c015` pass is one of the six** (five
`.qwen38*` passes + `.c015`), i.e. the eight-pass figure includes the very pass
"by a model that cannot be identified" that A-1 corrects for; and two of the
`qwen38` passes (`r3`, `r4`) have n = 29 on one side, so bank 20's forward mean
is −0.0490 paired / −0.0480 unpaired. Without `.c015` the seven-pass figures
are −0.0610 / −0.0571. None of this changes A-1's reading; it is recorded so
the eight-pass number is not mistaken for eight passes by a named model.

The quotable cross-grader readings of the same contrast are EXP-2026-08-021
(+0.0625 / +0.0567, five `qwen38-27B-v2` sessions, **generic − merged sign**)
and EXP-2026-09-006 (+0.0608 / +0.0581 qwen; +0.0500 / +0.0400 gemma,
saturated).

## D5 — Provenance gaps closed in place

**Date:** 2026-09-09

`code.commit` was the 7-character `79e11b0`; it is now the full
`79e11b0ed11e6566cd0ce8f931db3aaed73dbd45` (2026-08-21 11:55:01 −0400,
"Correct the C-015 control", verified with `git log`). `llm.model` was
`relay/skynet` with a truncated comment ("no model is in the loop for  or ");
the `.c015` grader's served model is not recorded in any sidecar
(`{"model": "skynet"}` only) and A-1 already calls it unidentified, so it is now
`relay/unknown@2026-08-21`. `nondeterminism_note` was template text and now
says what was actually done. `data/POINTERS.md` was the blank scaffold and is
filled.

Unrecorded dependency: EXP-2026-08-011 I-13 notes that the `describe` id-column
widening (2026-08-22) is a behavioural change to the merged store measured
here; every figure here predates it. EXP-2026-08-011 is added to `related`.
