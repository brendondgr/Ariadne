# PROTOCOL — EXP-2026-11-018 Era 2 Step 8 follow-up 3: six typed-path faults, fixed and re-run

Written 2026-11-20, before any measured call. After EXP-2026-11-017 the operator asked for "as many
tests as needed in order to improve results or ensure things are running as they are meant to".
The standing rule holds: small changes, proven on the items that failed before, then the large
run. The proof is § Smoke. This protocol is the large run.

## What was looked at before writing

- **Every T0 question English answers exactly and T-lazy does not, in EXP-2026-11-017** (21).
  - **9 of the 21 are the answer's own anchor, not a retrieval miss.** A typed `expand` returns
    its anchor (C0027 next to its 10 techniques). The reference template for that question lists
    the techniques alone. `records_exact` then fails a correct answer. English routes to the same
    templates as the reference and never meets this.
  - The other 12 led to the faults below.
- **Every dev question T-lazy loses and English does not** (46). About 30 were rejected by the
  Gremlin validator before they ran (fault 2).
- **The refusal counts of all T-lazy plans, on variants and on dev.**
  - `'taxonomy' is not a property of TaxonomyEntry`: 90 times on variants, 15 on dev (fault 4).
  - "an expand step needs a path": 70 (fault 5).
  - "from_step is on the same graph": 42 on variants, 41 on dev (fault 5).
- **A model-free replay of all 2,034 recorded typed variant answers.** A stub drafter returns
  each saved plan into the full pipeline. On the unchanged commit it reproduces every recorded
  answer's entity ids, 2,034 of 2,034, so it measures engine changes exactly. The engine fixes
  alone (faults 1–3, 6) moved T-full +12 exact, and T-lazy and T-lazy-G by 0 (net).
- **Anchor provenance of every confidently wrong T4/T5 answer.** Each `resolve_entity` call was
  re-run offline and classed: exact name, ranked, candidate list, or model memory. No class
  separates wrong anchors from right ones; each runs about 1:1. The wrong anchors are near
  siblings (Valid Accounts for its sub-technique, T1059.001 for .003). **An abstention gate on
  these signals would cost about as many exact answers as the mistakes it removes, so it is not
  built.**

## The fixes (Ariadne, committed with this protocol)

1. **CWE seeds are not foreign** (`utils/specialists/gremlin/builder.py`). The CAPEC store keys a
   weakness `cwe:287`. The foreign-seed check tried only the raw seed and the attack-pattern
   form. It read every `CWE-<n>` as the other graph's key, so the typed step fell through to
   `describe`, and the gate rejected that. All 14 CWE-anchored T-lazy plans returned nothing.
2. **Each `union` branch is checked from where the union starts** (`gremlin/validator.py`).
   - **The defect:** the direction check carried the label from the end of one branch into the
     next. So the prefix branch of every two-hop typed walk was rejected, for example
     `in("EXPLOITS_WEAKNESS") from 'Mitigation'`.
   - **Scope:** the deterministic and generic arms are byte-identical to the previous commit on
     both banks and on dev (284 of 284), so the change reaches typed walks only.
3. **Typed steps link by the `from_step` they state** (`utils/specialists/federation.py`, both
   sequencing loops).
   - **The defect:** `dependency_map` keyed producers and consumers by source. A plan that bridged
     CAPEC into two ATT&CK steps linked only the last one. The other ran with no anchor and fell
     through to a label-wide template: 222 techniques for F-CTT-01, and 18 to 23 answers per run
     of T-full.
   - **What changes:** the planner now writes `from_step` into the step.
   - **The guard:** a typed step with no anchor and no producer returns an honest empty instead
     of running.
4. **The join key description names the real property** (`utils/planner/join_keys.py`).
   `TaxonomyEntry(taxonomy=ATTACK)` becomes `TaxonomyEntry(taxonomy_name=ATTACK)`. The
   description is in both planners' prompts, and the model copied the spelling. A new test checks
   every `Label(property=...)` a description names against the cards.
5. **Two refusals become the fix they recommended** (`utils/planner/typed.py`, logged as
   coercions).
   - **"from_step is on the same graph" merges instead.** It said "add this step's hops to the
     path of step X". The step is now merged into that path, when the joined path ends at the
     named label, carries no filter or repeated hop on the way, and fits the card's depth.
     Otherwise it is refused as before.
   - **"an expand step needs a path" becomes a describe.** It said "or use kind describe", and
     the step is now a `describe`.
6. **A redundant bridged describe is dropped from the plan** (`typed.to_plan`).
   - **When:** a `describe` that starts from the same step, label and graph as an `expand`, and
     that no later step starts from.
   - **Why:** seeding these (fault 3) made the pipeline's facet chase add tactics and
     sub-techniques nobody asked for. In replay that made 7 exact T0 answers inexact; dropping
     the describe restored them.

**Tests:** 14 new cases across the planner, sequencing, validator, builder and join key tests.
1,528 planner, specialist, orchestration and agent tests pass on the working tree. The full suite
runs on the commit before the store reload.

**Harness addition (no answer changes):** `scripts/era2_anchor_exact.py`, the secondary measure
below.

## Question

How much of the typed hand-off's measured gap to English came from these faults? Where does it
stand against English, on the same tree, on EXP-2026-11-015's gates?

## Data, arms, settings

Identical to EXP-2026-11-017 except for the commit (the one this protocol is committed with) and
the output root, `docs/evaluation/experiments/typed-engine-fixes-2026-11-20/`.

- **Data:** the 120 gold questions (T0), the 579 variants (T1–T6) and the 284-question dev bank.
- **Arms:**
  - R, captured twice and compared byte for byte;
  - E, T-lazy, T-full and T-lazy-G (Gemma), each on the variants and on dev.
- **Settings:**
  - 16,384 tokens, no thinking budget, and a 900 s deadline for every planner arm;
  - Qwen at `reasoning_effort=medium`;
  - identity checked by token id before and after every arm.
- **Run order:** every arm runs back to back on one commit, at 16 per model, with Qwen and Gemma
  in parallel. `run.sh` now waits for the relay before every arm attempt (EXP-2026-11-017
  ISSUES).

**E is not untouched this time:** fault 4's one-word change reaches the English prompt too. E
against EXP-2026-11-017's E is therefore reported, not treated as a pure noise floor.

## Pre-registered checks and gates

| | Bar | Measured as | Falsified if |
|---|---|---|---|
| **E1** the fixes, dev | ≥ 15 fewer | T-lazy dev lost against EXP-2026-11-017's 59 | T-lazy dev lost above 44 |
| **E2** the fixes, safety | not above 52 | T-lazy confidently wrong on variants T0–T5 (EXP-2026-11-017: 52) | above 52 |
| **H1** the harness | ≤ 12 | model-less answers per planner arm, variants and dev | above 12 after one automatic re-run |
| **G1** synonym tier | ≥ 0.80 | T-lazy T1 `records_exact` | below |
| **G2** empty retrievals | ≤ ⌊E / 2⌋ | T-lazy dev lost, against this run's E | above |
| **G3** original wording | ≥ 0.98 | T-lazy T0 `records_exact` | below |
| **G4** confidently wrong | not above E | T-lazy against E, on variants T0–T5 and on dev, each | either above |

G1–G4 are EXP-2026-11-015's bars, unchanged.

**Reported, not gated:**
- **The secondary measure, per tier and arm.** `records_exact` with every id written in the gold
  question removed from both the answer and the reference. It is defined by the case, not the
  plan, and differs from `records_exact` only on answers that differ by anchor ids.
- **This run minus EXP-2026-11-017, per arm, paired over the same items.** 2,000 bootstrap
  resamples, seed 20261118, variants clustered by gold question.
- **The coercion and refusal counts:** merges, no-path describes, dropped describes, refusals by
  kind, and plans still refused after repair.
- **F1 (EXP-2026-11-016/017),** anchorless-scan confidently-wrong answers, for continuity.

## Predictions (written before the run, from the smoke runs and the replay)

- **E1 passes:** T-lazy dev lost 20 to 30 (the 59 previously lost fell to 18 in the smoke). G2 is
  borderline: its bar is about 21.
- **E2 passes:** T-lazy variants confidently wrong 44 to 52. G4 variants still fails, against E's
  about 39. The residual is near-sibling anchors on T4/T5.
- **T0 `records_exact`:** T-lazy 0.60 to 0.66. G3 fails. On the secondary measure T-lazy is
  within ±4 of E on T0, and above E on T1–T5.
- **T1:** about 0.62 to 0.68. G1 fails.
- **T-full gains the most** from fault 3; its variants exact rises by 10 or more.
- **H1 passes** for every arm.

## Decision rules

- **H1 fails for an arm after its re-run:** that arm is reported, not scored.
- **E1 fails:** the smoke result did not carry to the full bank. Diagnose on the failing items
  before any further full run.
- **E2 fails:** a fix added confident mistakes. Find which, from the coercion log, before
  anything else.
- **E1 and E2 pass, G2 and G4 both pass:** the typed hand-off is no less safe than English and
  no worse on dev. Propose a combined planner with its own gates.
- **E1 and E2 pass, G4 variants still fails:** the faults are fixed and the remaining gap is the
  near-sibling trade on vague paraphrases.
  - English stays the default on the planned path.
  - The fixes carry into Step 9's agent loop.
  - **Next is the operator's call:** Step 9.
- **In every case, the fixes stay in the tree.**
  - Faults 1–3 are engine fixes on the typed path.
  - Fault 4 is a description fix.
  - Faults 5–6 are typed-planner only, which is off by default.

## Procedure

```bash
uv run python -m pytest -q          # full suite on the commit, BEFORE the store reload (it can rewrite manifests)
uv run main.py --dataset attack --graph neo4j && uv run main.py --dataset capec --graph gremlin
bash docs/research/experiments/EXP-2026-11-018-era2-typed-engine-fixes/data/run.sh   # writes logs/ (gitignored)
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

## Threats, stated in advance

- **The smoke items are among the measured items.** They are the failures being fixed. E1 counts
  them by design, since it asks whether the fixes carry to the full bank.
- **Six changes are measured together.** The coercion and refusal counts show where each one
  acts. The replay separates the engine faults from the planner ones.
- **E's prompt changed by one word (fault 4).** E against EXP-2026-11-017's E mixes that change
  with run-to-run noise.
- **One run per arm.** Between two runs of unchanged code, E's dev lost moved by 7 and its dev CW
  by 3 (EXP-2026-11-017).
- **Some new inexact answers are readings, not defects.** For example, "what defenses apply" is
  now answered with CAPEC's own mitigations as well as ATT&CK's, while the gold counts ATT&CK
  only. These plans were refused before, so they could not happen.

## Smoke (before the measured run; tuning items, not results)

T-lazy (Qwen) on the working tree, at 16 workers. The output is in the session scratchpad and is
not kept.
- **Model-less answers:** 1 per subset (H1 healthy).
- **Identity checks:** both passed.

**Replay (no model):** all 2,034 typed variant answers of EXP-2026-11-017, on the old and new
engine, tree against tree.

| Arm | Exact, old engine → new | Gained | Lost | CW |
|---|---|---|---|---|
| T-lazy | 310 → 310 | 2 | 2 (F-FAN-02/03 T0; multi-producer plans the replay must guess the links of) | 53 → 53 |
| T-full | 310 → 322 | 16 | 4 | 44 → 45 (F-CTT-06 T5: a 224-row dump became a 3-row wrong answer) |
| T-lazy-G | 330 → 330 | 1 | 1 | 27 → 27 |

**Variants, 189 items.**
- **Targets (149):** every item whose EXP-2026-11-017 T-lazy plan met a same-graph, `taxonomy`
  or no-path refusal, plus the F-CWE, F-CTT and T0-missed bridge items.
- **Controls (40):** previously exact items, including every gold scan question and the replay's
  regressed F-CTM/F-FAN T0 items.

| Set | Exact | CW | Empty | Still refused after repair |
|---|---|---|---|---|
| Targets, EXP-2026-11-017 → smoke | 36 → 58 | 7 → 4 | 47 → 22 | 126 → 5 |
| Controls | 40 → 39 | 0 → 0 | 4 → 4 | 1 → 0 |

In the smoke, the new rules fired often:
- **51 same-graph merges and 66 no-path describes,** and the `taxonomy` refusal never appeared.
- **Legitimate scans:** 6 of 6 still exact.
- **3 targets and 1 control fell from exact.**
  - F-NEG-02 T3 (a target) and F-NEG-01 T1 (the control) add CAPEC mitigations for "defenses".
  - F-CTT-05 T1 is a different one-step plan.
  - F-FAN-02 T1 is a describe that starts from a `common` step.
- **1 new confident mistake:** C-ABS-03 T5, which had an empty answer before.

**Dev, 85 questions.** These are all 59 that T-lazy lost in EXP-2026-11-017 (46 that only T-lazy
lost and 13 that both arms lost), plus 26 controls.

| Set | Lost, EXP-2026-11-017 → smoke | Confidently wrong |
|---|---|---|
| Previously lost (59) | 59 → 18 | 0 → 0 |
| Controls (26) | 0 → 0 | 0 → 0 |
