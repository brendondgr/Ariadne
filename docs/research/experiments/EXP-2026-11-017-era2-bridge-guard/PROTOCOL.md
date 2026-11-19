# PROTOCOL — EXP-2026-11-017 Era 2 Step 8 follow-up 2: the bridge-route scan guard, re-run

Written 2026-11-19, before any measured call. EXP-2026-11-016 removed the targeted anchorless
scans, but its F1 check missed by one answer. The operator chose to fix that route and prove the
fix on the items that had failed before running the full set again. They added: "only after we
could confirm things are running on the stuff that failed prior, then we go into the large scale
runs." The proof is § Smoke. This protocol is the large-scale run.

## What was looked at before writing

- **EXP-2026-11-016 RESULTS.** F1 failed by one answer, T-lazy on F-REV-06 T5.
  - The plan described ATT&CK T1114.001, then scanned every CAPEC `TaxonomyEntry`: 262 records
    against a gold of 2.
  - Its first draft linked the CAPEC step with `from_step`, and that link was refused: "from_step
    'q2' is on the same graph", with no word on how to cross graphs. The repair turn then wrote
    the scan.
  - The question writes no id, so EXP-2026-11-016's guard (an id written in the question, or an
    id lookup that failed) could not fire.
- **The final plans of all four planner arms in EXP-2026-11-016, replayed through the new guard
  offline.** It would have refused 4 variant plans and no dev plan. All 4 were wrong already.
- **The spot-check runs in § Smoke.** They found two further routes into the same scan, and the
  fix covers both.

## The fix (Ariadne, committed with this protocol)

All five changes are in `utils/planner/typed.py`, on the typed path only. The prompt is unchanged.

1. **The same-graph `from_step` refusal names the bridged anchor.** When another step of the plan
   found an entity on a joined graph, the fix says how to reach this graph from it:
   `"anchor": {"id": "T1114.002"}, "anchor_label": "TaxonomyEntry"`. The engine bridges that
   through the join key.
2. **The cross-graph `from_step` refusal names the same anchor.** Its detail is "no declared join
   key carries values from attack to capec".
   - In 10 repeated spot-check runs, every first draft linked ATT&CK to CAPEC with `from_step`,
     and every one was refused.
   - With the old generic fix text, the repair dropped the CAPEC step in some runs.
3. **A plan-level scan check, run after every step is checked, so step order does not matter.** A
   `scan` step is refused when either of these holds:
   - another step of the plan anchors an entity on a graph joined to the scan's;
   - `resolve_entity` found an entity during this draft that no step anchors (change 4).

   The fix names the anchor, as in change 1.
4. **The planner records every entity that `resolve_entity` found during the draft**
   (`PlanContext.found_lookups`). That record is what lets change 3 refuse a scan that replaces a
   found entity, on the same graph or a joined one.
5. **A scan beside a step that tried to anchor on an id or a name, and was refused, is refused
   too.** Its fix is to fix that step. Any step that starts from a refused step is refused with it.

**What is not covered, by design:** a vague question on which the model looks nothing up and
scans, for example "what methods let an attacker steal passwords…" (A-TAC-02 T5). Catching that
would mean judging from the question's wording whether it asks for every member, and that would
block legitimate scans.

**Tests:** 9 new cases in `utils/planner/tests/test_typed_planner.py`; the planner suite passes.
The English path and the rules path are untouched.

**Harness changes (no answer changes):**
- `scripts/era2_modelless.py` counts the model-less answers of an arm (check H1).
- `scripts/era2_scanfix_compare.py` takes `--against`, the experiment it is paired with. On
  EXP-2026-11-016 its output is still byte-identical.

## Question

Does F1 now hold, with no T-lazy confidently-wrong answer being an anchorless scan? Where does the
typed hand-off then stand against the English one on the same tree, measured on
EXP-2026-11-015's gates?

## Data, arms, settings

Identical to EXP-2026-11-016, except for the commit (the one this protocol is committed with)
and the output root, `docs/evaluation/experiments/bridge-guard-2026-11-19/`.

- **Data:** the 120 gold questions (T0), the 579 variants (T1–T6) and the 284-question dev bank.
- **Arms:**
  - R, captured twice and compared byte for byte;
  - E, T-lazy, T-full and T-lazy-G (Gemma), each on the variants and on dev.
- **Settings:**
  - 16,384 tokens, no thinking budget, and a 900 s deadline for every planner arm;
  - Qwen at `reasoning_effort=medium`;
  - identity checked by token id before and after every arm.
- **Run order and concurrency:** every arm runs back to back on one commit, at 16 per model, with
  Qwen and Gemma in parallel.

E's code path is unchanged, so **E against EXP-2026-11-016's E is the run-to-run noise floor.**

## Pre-registered checks and gates

| | Bar | Measured as | Falsified if |
|---|---|---|---|
| **F1** the fix | 0 | T-lazy confidently-wrong answers that are anchorless scans, on variants T0–T5 and on dev, each | either count above 0 |
| **H1** the harness | ≤ 12 | model-less answers per planner arm (`scripts/era2_modelless.py`), variants and dev | above 12 after one automatic re-run of that arm |
| **G1** synonym tier | ≥ 0.80 | T-lazy T1 `records_exact` | below |
| **G2** empty retrievals | ≤ ⌊E / 2⌋ | T-lazy dev lost, against this run's E | above |
| **G3** original wording | ≥ 0.98 | T-lazy T0 `records_exact` | below |
| **G4** confidently wrong | not above E | T-lazy against E, on variants T0–T5 and on dev, each | either above |

The G1–G4 bars are EXP-2026-11-015's, kept unchanged so that the verdicts compare directly. G3's
bar is known to be out of reach for any model planner; it is kept for continuity.

**H1** turns the harness defect from EXP-2026-11-016 into a gate.
- **The defect:** a relay drop mid-arm makes the rest of the arm model-less, while the identity
  check still passes.
- **Healthy arms** had 1–12 model-less answers in EXP-2026-11-016; a drop gave 152.
- **What `run.sh` does:** re-runs a failing arm once and keeps the dropped output in `logs/`.
- **If an arm still fails after its re-run,** that arm is reported, not scored.

**Reported, not gated:**
- **This run minus EXP-2026-11-016, per arm:**
  - `records_exact` per tier;
  - the confidently-wrong count over T0–T5;
  - dev lost and dev confidently wrong.

  These are paired over the same items with 2,000 bootstrap resamples, seed 20261118, and
  variants are clustered by gold question.
- **Scan refusals:** questions with a scan refused, how many the repair turn then fixed, and how
  many legitimate scans were blocked. The refusal text of every scan check contains "a scan lists
  every", so the existing counter covers all of them.
- **The same figures for T-full and T-lazy-G.** T-full's remaining anchorless scans are expected
  on vague questions; they are counted and are not part of F1.

## Predictions (written before the run, from EXP-2026-11-016 and the smoke runs)

- **F1 passes:** 0 and 0.
- **H1 passes for every arm,** after at most one re-run.
- **Variants confidently wrong:** T-lazy about 47, against E at about 36. The G4 variants part
  fails. The residual is confident wrong anchors on T4/T5, not scans.
- **Dev confidently wrong:** T-lazy 0 to 2, against E's about 4. The G4 dev part passes.
- **T0:** T-lazy about 0.62 (EXP-2026-11-016: 0.608). G3 fails.
- **G1 and G2:** no change in verdict; both fail.
- **T-full** keeps 1 to 3 anchorless-scan answers, on vague questions.

## Decision rules

- **H1 fails for an arm after its re-run:** that arm is reported, not scored. No gate that needs
  it is decided.
- **F1 fails:** a further route exists. Diagnose it with a spot-check on the failing items
  before any further full run (the operator's standing rule, 2026-11-19). No arm-level
  conclusion is drawn.
- **F1 passes, and G4 passes on both parts:** the typed hand-off is no less safe than English.
  - **Next:** propose a combined planner with its own gates.
  - **The planned path keeps English until then.**
- **F1 passes, and G4 still fails on variants:** the remaining risk is the trade, not a defect.
  - English stays the default on the planned path.
  - The typed catalog continues into Step 9's agent loop, and these guards carry over.
  - **Next is the operator's call:** an abstention gate on typed answers, or Step 9.
- **In every case,** the fix stays in the tree. It affects only the typed path, which is off by
  default.

## Procedure

```bash
uv run python -m pytest -q          # full suite on the commit, BEFORE the store reload (it can rewrite manifests)
uv run main.py --dataset attack --graph neo4j && uv run main.py --dataset capec --graph gremlin
bash docs/research/experiments/EXP-2026-11-017-era2-bridge-guard/data/run.sh   # writes logs/ (gitignored)
uv run python scripts/era2_catalog_score.py --data docs/research/experiments/EXP-2026-11-017-era2-bridge-guard/data \
    --runs docs/evaluation/experiments/bridge-guard-2026-11-19
uv run python scripts/era2_scanfix_compare.py --against EXP-2026-11-016 \
    --old-runs docs/evaluation/experiments/scan-fix-2026-11-19 \
    --new-runs docs/evaluation/experiments/bridge-guard-2026-11-19 \
    --data docs/research/experiments/EXP-2026-11-017-era2-bridge-guard/data
```

## Threats, stated in advance

- **The smoke items are among the measured items.** They are the failures being fixed, so they
  are reported, not counted as evidence. F1 is about the mechanism, not about accuracy.
- **The guards key on what the plan found, not on the question's wording.** A question that both
  names an entity and asks for every member of a label on a joined graph would have its scan
  refused. No such question is in the gold set, and the scan-refusal counts report it.
- **One run per arm,** so E's run-to-run change is the only noise estimate. The smoke runs showed
  F-REV items moving between exact and not exact from run to run with no guard involved.
- **Five changes are measured together.** The refusal counts show where each guard fired.

## Smoke (before the measured run; tuning items, not results)

Every smoke run used T-lazy and T-full (Qwen) on the working tree, at 6–8 workers per arm. The
output is in the session scratchpad and is not kept. Every identity check passed.

**The set: 87 variant items.** Together they cover:
- every tier of F-REV-04/05/06 (the bridge family);
- every tier of A-SCN-01 and C-SCN-01 (the only gold scan questions);
- every item where a typed plan in EXP-2026-11-015 or EXP-2026-11-016 contained a scan, or where
  EXP-2026-11-016's guard fired.

Each cell below compares against EXP-2026-11-016 on the same items.

| Smoke run | Code | Arm | Anchorless-scan CW | Exact | CW | Legitimate scans exact |
|---|---|---|---|---|---|---|
| 1. 87 items | changes 1, 3 | T-lazy | 1 → 0 | 32 → 34 | 7 → 4 | 6 / 6 |
| | | T-full | 2 → 2 | 35 → 37 | 9 → 8 | 6 / 6 |
| 2. F-REV-05/06 T5, ×5 | changes 1, 3 | T-lazy | 0 of 10 | 7 of 10 | 0 of 10 | — |
| 3. 87 items | changes 1–4 | T-lazy | 1 → 0 | 32 → 38 | 7 → 4 | 6 / 6 |
| | | T-full | 2 → 2 | 35 → 36 | 9 → 5 | 6 / 6 |
| 4. three bridge items, ×3 | changes 1–4 | T-lazy | 0 of 9 | 7 of 9 | 0 of 9 | — |
| | | T-full | 0 of 9 | 5 of 9 | 3 of 9 (all F-REV-06 T5) | — |
| 5. three bridge items and six legitimate scans, ×3 | changes 1–5 | T-lazy | 0 of 9 | 7 of 9 | 0 of 9 | 18 / 18 |
| | | T-full | 0 of 9 | 6 of 9 | 1 of 9 (2 records, not a scan) | 18 / 18 |

**What each step found:**
- **Run 1:**
  - F-REV-06 T5 went from 262 records to 1.
  - T-lazy F-REV-05 T1 lost its CAPEC step after the cross-graph `from_step` refusal; no guard
    was involved. That led to change 2.
- **Run 2:** every first draft linked ATT&CK to CAPEC with `from_step`. With the old fix text,
  the repair worked 8 times in 10.
- **Run 3:** T-full F-REV-06 T5 anchored the technique by name, the anchor was refused as
  ambiguous, and the CAPEC scan was all that was left. That led to change 5.
  - T-full's other anchorless scan, A-TAC-02 T5, is a vague question, out of scope.
- **Run 4:** T-full F-REV-06 T5 was confidently wrong in 3 of 3 runs.
  - One was a wrong anchor.
  - Two were model-less, after an empty model reply on the repair turn. That is not a relay drop,
    and H1 counts it.
- **Run 5:**
  - **The guard never fired on a legitimate scan:** 36 of 36 runs exact.
  - **The scan checks fired on bridge items in 2 of 18 runs.**
  - **No guard fired on a legitimate scan in any smoke run.**
  - **No legitimate scan question called `resolve_entity`** in any recorded typed run of
    EXP-2026-11-015, EXP-2026-11-016 or the smoke (48 answers). No exact answer, in any of those
    runs, came from a scan plan that called `resolve_entity`.
