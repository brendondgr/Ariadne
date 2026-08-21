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
