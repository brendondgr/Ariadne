# RESULTS — EXP-2026-11-018 Era 2 Step 8 follow-up 3: six typed-path faults, fixed and re-run

## 1. Headline

**The six fixes carry to the full banks: T-lazy now loses 21 dev questions, down from 59, and G2
passes for the first time (21 against a bar of 23; English loses 47).**
- E1 and E2 pass, and every arm passed H1 on its first attempt.
- **Confident mistakes are unchanged.** T-lazy makes 48 on the variants, against 52 before and
  English's 34. G4 fails on the variants, and on dev by one answer (1 against 0). G1 and G3 fail.

Under the pre-registered rule, the faults are fixed and the remaining gap is the near-sibling
trade on vague paraphrases. **English stays the default; the fixes carry into Step 9.**

## 2. Results table

From `data/metrics.json` (`scripts/era2_catalog_score.py`, `scripts/era2_scanfix_compare.py
--against EXP-2026-11-017`, `scripts/era2_anchor_exact.py`, `scripts/era2_modelless.py --merge`).
- **Runs:** one per arm (`n_runs: 1`), all on commit b14cf953 in one sitting.
- **Intervals:** paired 95% bootstrap, 2,000 resamples, seed 20261118. Variants are clustered by
  gold question.

**Pre-registered checks and gates**

| | Bar | T-lazy | E | Pass |
|---|---|---|---|---|
| E1 dev lost, against EXP-2026-11-017's 59 | ≤ 44 | 21 (−38 [−50, −26]) | — | **yes** |
| E2 variants confidently wrong | ≤ 52 | 48 (−4 [−14, +6]) | — | **yes** |
| H1 model-less answers, every arm | ≤ 12 | 4 (variants), 1 (dev) | 5, 1 | yes, all arms, first attempt |
| G1 T1 `records_exact` | ≥ 0.80 | 0.6083 | 0.5333 | no |
| G2 dev lost | ≤ ⌊E/2⌋ = 23 | 21 | 47 | **yes** |
| G3 T0 `records_exact` | ≥ 0.98 | 0.6000 | 0.6583 | no |
| G4 CW, variants T0–T5 | ≤ E | 48 | 34 | no |
| G4 CW, dev | ≤ E | 1 | 0 | no |

**Per tier, `records_exact`** (`tables/scoreboard.md`)

| Arm | T0 | T1 | T2 | T3 | T4 | T5 | T6 | CW T0–T5 | dev lost | dev CW |
|---|---|---|---|---|---|---|---|---|---|---|
| R | — | 0.3917 | 0.3667 | 0.1782 | 0.0000 | 0.0000 | 0.0667 | 51 | — | — |
| E | 0.6583 | 0.5333 | 0.5500 | 0.4653 | 0.1250 | 0.0865 | 0.0333 | 34 | 47 | 0 |
| T-lazy | 0.6000 | 0.6083 | 0.5750 | 0.5743 | 0.2500 | 0.2404 | 0.1000 | 48 | 21 | 1 |
| T-full | 0.6750 | 0.6917 | 0.5833 | 0.6238 | 0.2404 | 0.2308 | 0.0667 | 47 | 17 | 0 |
| T-lazy-G | 0.6333 | 0.6333 | 0.5750 | 0.6634 | 0.3077 | 0.2596 | 0.1000 | 26 | 34 | 2 |

**The secondary measure, pre-registered:** exact answers, out of the tier's n, with the gold
question's own ids removed from both sides (`scripts/era2_anchor_exact.py`).

| Arm | T0 /120 | T1 /120 | T2 /120 | T3 /101 | T4 /104 | T5 /104 |
|---|---|---|---|---|---|---|
| E | 79 | 66 | 67 | 50 | 16 | 15 |
| T-lazy | 85 | 80 | 73 | 68 | 31 | 30 |
| T-full | 92 | 84 | 71 | 72 | 25 | 28 |
| T-lazy-G | 83 | 77 | 71 | 71 | 37 | 31 |

The scoreboard also prints an older table, "with the anchor ids ignored". It removes the plan's
anchors rather than the case's, so its figures differ slightly. The pre-registered measure is the
one above.

**This run minus EXP-2026-11-017, same arm, same items** (`tables/compare.md`)

| Arm | T0 | T1 | CW T0–T5 | dev lost | dev CW |
|---|---|---|---|---|---|
| E | −0.0333 [−0.0750, +0.0083] | −0.0417 [−0.1083, +0.0333] | −5 [−16, +7] | +4 [−8, +16] | −1 [−3, 0] |
| T-lazy | +0.0083 [−0.0417, +0.0667] | −0.0083 [−0.0667, +0.0500] | −4 [−14, +6] | **−38 [−50, −26]** | +1 [0, +3] |
| T-full | **+0.0917 [+0.0250, +0.1583]** | **+0.0750 [+0.0250, +0.1333]** | +3 [−7, +14] | **−31 [−42, −21]** | 0 [0, 0] |
| T-lazy-G | +0.0333 [−0.0167, +0.0917] | +0.0417 [−0.0083, +0.0917] | −1 [−10, +8] | **−21 [−32, −10]** | 0 [0, 0] |

**Where the fixes acted, on the variants** (EXP-2026-11-017 → this run)

| Arm | same-graph merges | no-path describes | `taxonomy` refusals | same-graph refusals | plans still refused |
|---|---|---|---|---|---|
| T-lazy | 0 → 71 | 0 → 94 | 90 → 0 | 73 → 12 | 70 → 14 |
| T-full | 0 → 88 | 0 → 151 | 0 → 0 | 117 → 5 | 31 → 5 |
| T-lazy-G | 0 → 60 | 0 → 3 | 40 → 0 | 102 → 22 | 51 → 24 |

The scan guard blocked no legitimate scan in any arm. F1 (EXP-2026-11-016/017) is 0 for T-lazy on
both sets.

## 3. Figures

None.

## 4. Interpretation

- **Most of the dev gap was engine faults, not the hand-off.** T-lazy's dev losses fell from 59
  to 21, now well below English's 47, and T-full's from 48 to 17.
  - **The largest single cause was the validator** rejecting two-hop CAPEC walks before they ran.
  - **The others:** steps refused for a property name the prompt itself taught, and same-graph
    chains refused instead of merged.
  - **None of it was the model choosing wrongly.** The model's plans were right, and the
    engine or the checker refused or broke them.
- **The original-wording gap is mostly the scoring shape.** `records_exact` still puts T-lazy
  below English on T0, 0.6000 against 0.6583. On the case-defined secondary measure, T-lazy is
  exact on 85 of 120 against English's 79. It is ahead on every paraphrase tier: T3 68 against
  50, T5 30 against 15.
- **Confident mistakes did not move, and they are not a defect.** T-lazy's 48 against 52 is
  within noise.
  - The residual sits on vague T4/T5 paraphrases where the model picks a near sibling of the
    gold anchor.
  - The offline provenance check (PROTOCOL) found no signal that separates these picks from
    correct ones, so no guard or gate is proposed for them.
  - **Gemma** makes fewer confident mistakes than English (26 against 34) with more exact
    answers on every tier. It is the replication arm and is not gated.
- **The one dev mistake is a new, small pattern** (§ 6), with a deterministic guard available
  (§ 7).
- **No claim moves.** This is an engineering run.

## 5. Threats to validity

- **One run per arm.** E moved −5 on variants CW and +4 on dev lost against EXP-2026-11-017, and
  its prompt changed by one word (fault 4). That is the only noise estimate.
- **The smoke items are inside the measured banks.** E1 counts them by design.
- **Six changes measured together.** The coercion and refusal counts above show where each acted.
  The model-free replay (PROTOCOL) attributes the engine faults separately.
- **Readings, not defects.** Some newly accepted plans answer "what defenses apply" with CAPEC's
  own mitigations as well as ATT&CK's. The gold counts only ATT&CK. Those plans could not run
  before, because they were refused.

## 6. What surprised us

- **The validator, not the planner, was the largest dev cost.** Every one of those plans was
  correct and never ran.
- **The prompt taught the most common refusal.** The join key description wrote
  `taxonomy=ATTACK`, and the model copied it 90 times in one arm.
- **A written id loses to a name match when two entities share a name.**
  - **The case:** D2-detects-DET0891 writes DET0891, whose name it shares with DET0862. Both
    Qwen and Gemma resolved the name, anchored DET0862 and answered confidently wrong.
  - **On the variants:** Gemma does the same 10 times (none confidently wrong, none exact). Qwen
    does it 0 times.

## 7. Follow-ups

- **A written id outranks a name.** When the question writes an id that a graph holds, a step
  anchored by name on a different id of the same family should take the written id, logged as a
  coercion. Prove it on D2-detects-DET0891 and on Gemma's 10 variant cases before any full run.
- **The planned path keeps English;** that decision is unchanged.
- **Step 9 (the operator set, scoped to retrieval) is next.** The six fixes and the replay harness
  carry into it.

## 8. Reproduction

```bash
# on commit b14cf953, after the full suite and a store reload:
bash docs/research/experiments/EXP-2026-11-018-era2-typed-engine-fixes/data/run.sh
D=docs/research/experiments/EXP-2026-11-018-era2-typed-engine-fixes/data; R=docs/evaluation/experiments/typed-engine-fixes-2026-11-20
uv run python scripts/era2_catalog_score.py --data $D --runs $R
uv run python scripts/era2_scanfix_compare.py --against EXP-2026-11-017 \
    --old-runs docs/evaluation/experiments/bridge-guard-2026-11-19 --new-runs $R --data $D
uv run python scripts/era2_anchor_exact.py --runs $R --merge $D/metrics.json
for p in variants/E.json variants/T-lazy.json variants/T-full.json variants/T-lazy-G.json \
         dev/planned_llm_english dev/planned_llm_typed_lazy dev/planned_llm_typed_full dev-gemma/planned_llm_typed_lazy; do
  uv run python scripts/era2_modelless.py $R/$p --merge $D/metrics.json
done
```
