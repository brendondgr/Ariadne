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

---

## AMENDMENTS

### A-1 (2026-09-04) — "the holdout is untouched" was too strong

PROTOCOL.md says *"288 questions, untouched"* and RESULTS.md leans on the same
word. That is not accurate and the correction matters, because the holdout's
value is exactly the thing being claimed about it.

**What is true:** no holdout question has ever been **judged** — 0 judgments
across every run in the repository — and neither the `generic` nor the
`llm_query` arm has ever answered one.

**What is also true, and was not said here:** the **deterministic** arm answered
all 288 on 2026-09-02, and its model-free recall was **reported** — the published
`holdout 0.4683` against `dev 0.4350` in EXP-2026-09-002 is that look. It was
deliberate and its purpose is on the record: the two halves landing within 3.3
points is the evidence that the bank was not tuned against the system.

**So the holdout has had one model-free look by one arm, pre-repair.** What
remains genuinely unspent is a *judged* holdout and any holdout answer from the
other two arms. Every assertion in this experiment that the seal held is correct
under that definition and overstated under the plain reading of "untouched".

The check that produced this correction is now in
`scripts/overnight_two_track.py::preflight`, which asserts the precise property
rather than the loose one and refuses to start if a holdout question has been
judged.

## I-7 — 2026-09-09: seeds and lockfile

`seeds: []` is accurate: both arms take no model and no random draw; the grader
ran at temperature 0 with no seed parameter exposed by the relay, and its
position effect is handled by counterbalancing rather than seeding.
`environment.lockfile` pointed at `env/requirements.lock`, which was never
written; set to `null` in A-2. The dependency set is `uv.lock` at `a1e20f6`.

## I-8 — 2026-09-09: the pre-repair recall baseline lived outside this experiment

**Impact:** `deterministic_recall_move_vs_prerepair` (0.0684) subtracts a
0.4492 that no file pointed by this experiment held; the `recall_before` column
in `post-repair-deterministic.json` is a copy of `recall`, not the pre-repair
value.
**Cause:** the re-scoring of `expansion-2026-09-01` under the property-gold
rule was run for EXP-2026-09-007's model-free half and written to that
experiment's `data/recall-summary.json`, two days after this one was filed.
**Resolution:** that file and the pre-repair answer directory are pointed here
(A-2 §2) and the baseline is a manifest metric,
`deterministic_recall_prerepair_dev`.
**Paper implication:** none; the +0.0684 is unchanged. Quote it with both
endpoints.
