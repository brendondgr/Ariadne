# PROTOCOL — EXP-2026-11-016 Era 2 Step 8 follow-up: the anchorless-scan fix, re-run

Written 2026-11-19, before any measured call. The operator asked for it the same day: "fix the
anchorless scan and then rerun the typed arms."

## What was looked at before writing

- **EXP-2026-11-015 RESULTS and its diagnosis.**
  - All four gates failed for T-lazy against E.
  - 11 of T-lazy's 12 dev confidently-wrong answers, and 16 of its 61 on variants T0–T5, were
    `scan` steps with no anchor.
  - Half of them followed the repair turn, whose refusal suggested a scan. The other half
    were first emissions after `resolve_entity` found nothing for an id the question writes.
- **The code.** `check_step` already accepts a step anchored on an id that is missing from
  the graph (T9999 has the form of a Technique id, so the step is valid and returns nothing).
  It also accepts an ATT&CK id on a CAPEC step through the join key. The model never wrote
  either, because:
  - the reply to `resolve_entity("T9999")` said "no entity matches; try other words";
  - the reply to `resolve_entity("T1195", graph="capec")` said the same;
  - the prompt gave no instruction for a named entity that is not found.
- **A smoke run of the fix** on the six T0 failures and the twelve dev failures (§ Smoke).
  These are tuning items. They are reported separately and are not a result.

## The fix (Ariadne, committed with this protocol)

All four changes are in `utils/planner/typed.py`, and all are on the typed path only.

1. **Prompt wording.**
   - The `scan` kind now says it is "only when the question asks for all of them".
   - A new rule says: "When the question writes an entity id, anchor on that id even if
     resolve_entity cannot find it. The engine then answers that the entity is not in the
     graph… Never put a scan in place of an anchor you could not find."
2. **The no-anchor refusal no longer suggests a scan.** Its `fix` now says to give the id the
   question writes, even if it was not found.
3. **`resolve_entity` on an id-shaped text answers plainly:**
   - **Not in any graph:** `status: not_found`, with "anchor the step on {"id": "T9999"}
     anyway… Do not replace it with a scan".
   - **An id of the other graph:** `found` there, with a note that it can anchor this
     graph's step through the join key.
4. **A hard guard.** A `scan` step is refused when either of these holds:
   - the question writes a token with the form of an entity id of a live graph
     (`PlanContext.written_ids`);
   - an id-shaped lookup found nothing during this draft.

   The refusal's fix names the anchor. Neither gold scan question (A-SCN-01, C-SCN-01) writes
   such a token. The planner reads the question; the specialists still do not.

Tests: 6 new cases in `utils/planner/tests/test_typed_planner.py`. The English path and the
rules path are untouched: no file outside the typed planner changes.

## Question

Does the fix remove the anchorless-scan answers? With them gone, where does the typed hand-off
stand against the English one on the same tree, measured on EXP-2026-11-015's gates?

## Data, arms, settings

Identical to EXP-2026-11-015 (its PROTOCOL and amendments 1–2), except that the commit is the
one this protocol is committed with.
- **Data:** 120 gold questions (T0), 579 variants (T1–T6) and the 284-question dev bank.
- **Arms:** E, T-lazy, T-full and T-lazy-G (Gemma). R is re-captured twice. The authored dev
  baseline is the same committed `generic_composed` answers.
- **Settings:** 16,384 tokens, no thinking budget and a 900 s deadline for every planner arm.
  Qwen runs at `reasoning_effort=medium`. Identity is checked by token id before and after
  every arm.
- **Order:** every arm runs back to back on one commit.
- **Concurrency:** 16 per model, with Qwen and Gemma in parallel.
- **Outputs:** `docs/evaluation/experiments/scan-fix-2026-11-19/`.

E's code path is unchanged, so **E against EXP-2026-11-015's E measures run-to-run change**
with one run each. It is reported.

## Pre-registered check and gates

| | Bar | Measured as | Falsified if |
|---|---|---|---|
| **F1** the fix | 0 | T-lazy confidently-wrong answers that are anchorless scans, variants T0–T5 and dev, each | either count above 0 |
| **G1** synonym tier | ≥ 0.80 | T-lazy T1 `records_exact` | below |
| **G2** empty retrievals | ≤ ⌊E / 2⌋ | T-lazy dev lost, against this run's E | above |
| **G3** original wording | ≥ 0.98 | T-lazy T0 `records_exact` | below |
| **G4** confidently wrong | not above E | T-lazy against E, variants T0–T5 and dev, each | either above |

G1–G4 keep EXP-2026-11-015's bars unchanged, so the verdicts compare directly. G3's bar is
known to be out of reach for any model planner (EXP-2026-11-015 ISSUES), and it is kept for
continuity.

**Reported, not gated:**
- **T-lazy (this run) minus T-lazy (EXP-2026-11-015),** per tier and for each
  confidently-wrong count. These are paired over the same items with 2,000 bootstrap
  resamples, seed 20261118 (clustered by gold question on variants).
- **E (this run) minus E (EXP-2026-11-015),** computed the same way. This is the noise floor.
- **T-lazy against E with the anchor ids ignored** (EXP-2026-11-015's diagnosis), on T0.
- **Scan refusals:**
  - how many plans the guard refused;
  - how many of those were then fixed by the repair turn;
  - how many legitimate scans it blocked. A legitimate scan is one on a question whose
    reference capture is a scan template.
- **The same figures for T-full and T-lazy-G.**

## Predictions (from EXP-2026-11-015's post-hoc counts; written before the run)

- **F1 passes:** 0 and 0.
- **Dev confidently wrong:** T-lazy about 1, near E's. The G4 dev part passes.
- **Variants confidently wrong:** T-lazy about 45, still above E's 33. The G4 variants part
  fails. The residual is T4/T5 questions that E abstains on and the typed plan answers wrongly.
- **T0:** T-lazy about 0.55 (about 0.65 with anchor ids ignored). G3 fails.
- **T4 and T5:** the gain over E holds, within ±0.03 of EXP-2026-11-015's.
- **G1 and G2:** no change in verdict.

## Decision rules

- **F1 fails:** the guard or the wording missed a route. Diagnose it before anything else; no
  arm-level conclusion is drawn.
- **F1 passes, and G4 passes on both parts:** the typed hand-off is no less safe than English.
  - **Next:** propose a combined planner (typed plan, falling back to abstention where the
    typed path refuses) as the planned-path candidate. It needs its own gates.
  - **The planned path still keeps English until such a protocol passes.** G3's bar cannot be
    met as written.
- **F1 passes, and G4 still fails on variants:** the remaining risk is the trade, not the
  defect. English stays the default on the planned path. The typed catalog continues into
  Step 9's agent loop, where the scan guard and the not-found wording carry over.
  - **Next is the operator's call:** an abstention gate on typed answers, or move on.
- **In every case,** the fix stays in the tree, because it affects only the typed path, which
  is off by default.

## Procedure

```bash
uv run python -m pytest -q                                   # full suite on the commit
bash docs/research/experiments/EXP-2026-11-016-era2-scan-fix/data/run.sh  # the chain; writes logs/ (gitignored)
uv run python scripts/era2_catalog_score.py --data docs/research/experiments/EXP-2026-11-016-era2-scan-fix/data \
    --runs docs/evaluation/experiments/scan-fix-2026-11-19
uv run python scripts/era2_scanfix_compare.py                # this run against EXP-2026-11-015, paired
```

The chain is EXP-2026-11-015's `logs/phase2.sh`, with the output root changed: verify the
stores, then capture R twice and compare the two captures byte for byte, then run the Qwen arms
and the Gemma arms in parallel.

## Threats, stated in advance

- **The smoke items are the failures being fixed.** They are reported, not counted as
  evidence. The measured run uses the same banks as EXP-2026-11-015, so these items are in it
  too. That is unavoidable when re-running the same banks, and it is the reason F1 is about
  the mechanism, not about accuracy.
- **The guard reads the question.** A question that names an id and also asks for a whole
  label would have that scan refused. The scan-refusal counts report it.
- **One run per arm.** E's run-to-run change is the only noise estimate.
- **Wording was changed and measured together with the guard.** The run cannot separate the
  two. The scan-refusal counts show how often the guard, not the wording, did the work.

## Smoke (before the measured run; tuning items, not results)

T-lazy (Qwen) ran on 2026-11-19 with the fix in the working tree, before the commit. Output is in
the session scratchpad and is not kept.

**The six T0 failures of EXP-2026-11-015, run as one-off items,** plus two controls:

| Case | Before (EXP-2026-11-015) | After |
|---|---|---|
| A-NEG-01 (T9999) | 222 techniques | `describe T9999`, 0 records, exact |
| A-EXC-01, A-EXC-02 (retired) | 222 techniques each | `describe`, 0 records, exact |
| C-NEG-01 (CAPEC-99999) | 558 patterns | `describe`, 0 records, exact |
| F-PART-01 (T1021) | 261 taxonomy entries | `expand T1021` through the bridge, exact |
| F-PART-02 (T1566) | 261 taxonomy entries | exact, after one repair turn (not a scan refusal) |
| A-MIT-07 T5 (control) | exact | exact |
| A-GRP-01 T1 (control) | 18 records (lists the anchor) | unchanged |

**The 12 dev confidently-wrong questions of EXP-2026-11-015:**
- **10 of the 11 anchorless-scan cases** now return records that overlap the authored plan's.
- **1 returns nothing** (D6 HAS_ALTERNATE_TERM T1557), which now counts as lost.
- **The non-scan case** (D2 detects DET0891) is still confidently wrong.
- **No answer is an anchorless scan.**

**The guard refused no scan in the smoke run.** The wording and the `not_found` reply did the
work. The guard stays in as the hard stop, and the measured run counts how often it fires.
