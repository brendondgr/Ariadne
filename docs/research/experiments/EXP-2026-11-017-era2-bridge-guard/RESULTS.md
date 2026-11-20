# RESULTS — EXP-2026-11-017 Era 2 Step 8 follow-up 2: the bridge-route scan guard, re-run

## 1. Headline

**The fix closes the route it targeted, but F1 still fails, by 2 answers.**
- **The targeted route is closed.** F-REV-06 T5 now builds the two-step plan (describe the
  technique, then expand into CAPEC) and is no longer confidently wrong.
- **F1 on the variants: 2.** Two other T-lazy answers on variants are anchorless scans:
  - **F-PART-01 T5** lists every ATT&CK `DataComponent` beside a correctly anchored step on the
    **same** graph. This is a route the guard deliberately left open.
  - **A-MC-02 T5** is a vague question on which the model looked nothing up and scanned. This is
    out of scope by design.
- **F1 on dev: 0.** No dev plan of T-lazy contains a scan.

Under the pre-registered rule, no arm-level verdict is drawn. G1–G4 fail exactly as in
EXP-2026-11-016. Paired against EXP-2026-11-016, T-lazy is unchanged on every reported measure.
H1 passed for every scored arm, after one T-full re-run caused by the relay.

## 2. Results table

From `data/metrics.json` (`scripts/era2_catalog_score.py`, `scripts/era2_scanfix_compare.py`,
`scripts/era2_modelless.py --merge`). Each arm ran once (`n_runs: 1`). Every interval is a
paired 95% bootstrap: 2,000 resamples, seed 20261118, with variants clustered by gold question.

**Pre-registered checks and gates (T-lazy against E, same tree)**

| | Bar | T-lazy | E | Pass |
|---|---|---|---|---|
| F1 anchorless-scan CW, variants T0–T5 | 0 | 2 | — | **no** |
| F1 anchorless-scan CW, dev | 0 | 0 | — | yes |
| H1 model-less answers, every arm | ≤ 12 | 5 (variants), 0 (dev) | 9, 1 | yes, all arms (T-full: 5 and 0, after one re-run) |
| G1 T1 `records_exact` | ≥ 0.80 | 0.6167 | 0.5750 | no |
| G2 dev lost | ≤ ⌊E/2⌋ = 21 | 59 | 43 | no |
| G3 T0 `records_exact` | ≥ 0.98 | 0.5917 | 0.6917 | no |
| G4 CW, variants T0–T5 | ≤ E | 52 | 39 | no |
| G4 CW, dev | ≤ E | 0 | 1 | yes |

**Per tier, `records_exact`** (`tables/scoreboard.md`)

| Arm | T0 | T1 | T2 | T3 | T4 | T5 | T6 | CW T0–T5 | dev lost | dev CW |
|---|---|---|---|---|---|---|---|---|---|---|
| R | — | 0.3917 | 0.3667 | 0.1782 | 0.0000 | 0.0000 | 0.0667 | 51 | — | — |
| E | 0.6917 | 0.5750 | 0.5667 | 0.4059 | 0.1058 | 0.0385 | 0.0667 | 39 | 43 | 1 |
| T-lazy | 0.5917 | 0.6167 | 0.5583 | 0.5050 | 0.2404 | 0.2308 | 0.0667 | 52 | 59 | 0 |
| T-full | 0.5833 | 0.6167 | 0.5417 | 0.5347 | 0.2788 | 0.2019 | 0.1000 | 44 | 48 | 0 |
| T-lazy-G | 0.6000 | 0.5917 | 0.5417 | 0.6436 | 0.2885 | 0.2596 | 0.1000 | 27 | 55 | 2 |

T-lazy minus E on T4 is +0.1346, and on T5 +0.1923. The gain over English on the hardest
paraphrases holds.

**This run minus EXP-2026-11-016, same arm, same items** (`tables/compare.md`)

| Arm | T0 | CW T0–T5 | dev lost | dev CW |
|---|---|---|---|---|
| E (noise floor) | +0.0333 [−0.0083, +0.0833] | +3 [−10, +16] | −7 [−18, +4] | −3 [−7, 0] |
| T-lazy | −0.0167 [−0.0583, +0.0167] | +1 [−11, +12] | +7 [0, +15] | 0 [0, 0] |
| T-full | +0.0167 [−0.0417, +0.0750] | 0 [−11, +10] | +2 [−4, +8] | 0 [0, 0] |
| T-lazy-G | 0.0000 [−0.0417, +0.0417] | −11 [−20, −1] | −2 [−10, +6] | +1 [0, +3] |

**The scan checks** (every refusal whose text contains "a scan lists every")

| Arm | set | questions with a scan refused | fixed by repair | still refused | legitimate scans blocked |
|---|---|---|---|---|---|
| T-lazy | variants | 16 | 15 | 1 | 0 |
| T-lazy | dev | 5 | 4 | 1 | — |
| T-full | variants | 11 | 11 | 0 | 0 |
| T-full | dev | 4 | 4 | 0 | — |
| T-lazy-G | variants | 5 | 3 | 2 | 0 |
| T-lazy-G | dev | 2 | 2 | 0 | — |

## 3. Figures

None.

## 4. Interpretation

- **The mechanism works where it applies.**
  - **The targeted bridge case is closed.** T-lazy's F-REV-06 T5 went from 262 records to a
    two-step plan with 1 record, no longer confidently wrong.
  - **The checks fire and are repaired.** They refused scans in 16 T-lazy variant questions, and
    the repair turn fixed 15.
  - **No legitimate scan was blocked** in any arm.
  - **The planner no longer produces this kind of answer on dev.** Not one dev plan of T-lazy
    contains a scan.
- **F1 as written is not reachable by plan checks alone.**
  - **One of the two misses can be caught.** A same-graph scan beside an anchor: across every
    typed run on record (EXP-2026-11-015, -016, -017 and the smoke runs), only 2 plans had this
    shape, and neither was correct.
  - **The other cannot.** A model that looks nothing up and scans leaves nothing in the plan for a
    guard to read. Telling it apart from a real "list them all" question means judging the
    question's wording.
  - **What this means:** the remaining confident-wrong risk on vague paraphrases belongs to an
    abstention gate, not to more guards.
- **Nothing moved at arm level.**
  - **T-lazy against EXP-2026-11-016:** every paired interval contains 0. The guards remove rare
    answer shapes, not the bulk of the confident wrong answers.
  - **T-lazy against E:** the confident-wrong gap on variants is 52 against 39 (+13 [−3, +29]).
    It is concentrated on T4/T5 confident wrong anchors, as in EXP-2026-11-016.
- **Gemma's confident wrong answers fell by 11 [−20, −1].** It is the one arm that moved, and it
  now sits below E (27 against 39). It is not gated, and this is one run.
- **No claim moves.** This is an engineering run.

## 5. Threats to validity

- **One run per arm.** E's run-to-run change is the only noise estimate. Its dev lost moved −7
  and its dev CW −3 between two runs of unchanged code. T-lazy's dev lost +7 [0, +15] is within
  that range.
- **Two sittings** (ISSUES). Dev E and dev T-lazy are both from sitting 2, and E and T-lazy on
  the variants are both from sitting 1. Each gate therefore compares arms within one sitting, on
  the same commit.
- **The smoke items are among the measured items.** F1 is about the mechanism, not about
  accuracy.
- **F1 counts each answer whose final plan contains a scan and which is confidently wrong.**
  That counts A-MC-02 T5, whose scan is on the wrong graph entirely. The pre-registered measure
  is kept as written.

## 6. What surprised us

- **The bridge route had two siblings.** Each was found only by repeating the same items. In 10
  repeated drafts, every first draft linked ATT&CK to CAPEC with `from_step`, a form the planner
  always refuses. The prompt's rule on `from_step` likely invites a link the join key cannot
  carry from that side; this run cannot test that.
- **The relay, not the code, cost the most time.**
  - T-full's first attempt on the variants took 2 h 40 min and still ended model-less on 29
    answers.
  - The re-run then took 1 h on a healthy relay.
  - The tunnel's 20 s restart window killed four arm starts in one second.
- **Gemma's confident wrong answers fell the most.** It makes fewer than half as many catalog
  calls as Qwen (1.45 against 3.84 per question). This run cannot say which of the five changes
  did it.

## 7. Follow-ups

- **The same-graph extension of the scan check.** It is small and has an evidence base: 2 plans
  on record, neither correct. Prove it on F-PART-01 T5 and the legitimate scans before any full
  run.
- **The prompt's `from_step` rule.** Say that an ATT&CK id anchors a CAPEC step directly, not
  through `from_step`. This is a wording change: spot-check it first.
- **An abstention gate on typed answers** for vague paraphrases, where neither guards nor wording
  apply. This is the operator's call.
- **Add the relay wait to every run script,** and make `run.sh` the template for future runs.

## 8. Reproduction

```bash
# on commit 39b79c30, after the full suite and a store reload:
bash docs/research/experiments/EXP-2026-11-017-era2-bridge-guard/data/run.sh
# sitting 2 (the arms the 21:15 tunnel drop stopped): logs/resume.sh, recorded in ISSUES
uv run python scripts/era2_catalog_score.py --data docs/research/experiments/EXP-2026-11-017-era2-bridge-guard/data \
    --runs docs/evaluation/experiments/bridge-guard-2026-11-19
uv run python scripts/era2_scanfix_compare.py --against EXP-2026-11-016 \
    --old-runs docs/evaluation/experiments/scan-fix-2026-11-19 \
    --new-runs docs/evaluation/experiments/bridge-guard-2026-11-19 \
    --data docs/research/experiments/EXP-2026-11-017-era2-bridge-guard/data
for p in variants/E.json variants/T-lazy.json variants/T-full.json variants/T-lazy-G.json \
         dev/planned_llm_english dev/planned_llm_typed_lazy dev/planned_llm_typed_full dev-gemma/planned_llm_typed_lazy; do
  uv run python scripts/era2_modelless.py docs/evaluation/experiments/bridge-guard-2026-11-19/$p \
      --merge docs/research/experiments/EXP-2026-11-017-era2-bridge-guard/data/metrics.json
done
```
