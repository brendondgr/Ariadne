# PROTOCOL — EXP-2026-11-022 Era 2 Step 9 Phases G–H: does showing the operators to the planner help, without harm?

Written 2026-11-20, after the exposure code and the probe set were built and before any model ran
with the operators visible. The step plan's Phases G and H are this protocol's stages.

## Question

When the typed planner is shown the operator algebra:
- does it answer questions that need the new operators (the probe set)?
- does it keep answering today's questions as well as before (the existing banks)?

Separately: does each of the two switch groups earn its place?

## What exists before the runs

- **Switches** (`utils/specialists/algebra/switches.py`), read at call time, both off by default:
  - `ARIADNE_ALGEBRA_CORE`: operators 1–7;
  - `ARIADNE_ALGEBRA_EXTENDED`: reach, shortest, time conditions; it needs CORE.
- **Off means unchanged:**
  - the planner messages and tool specs hash equal to ea7a7e59, for both cards and both modes
    (`utils/planner/tests/test_algebra_exposure.py`);
  - 1,121 recorded steps compile byte-identically;
  - an answer capture with the switches off is compared with Phase F's (RESULTS § 2).
- **With CORE on:**
  - today's step kinds are also checked by the algebra validator, which refuses the 2
    card-invalid drafts;
  - a typed filter on a property the store does not hold matches nothing (amendment 4).

  Both are part of the "core" treatment.
- **Probe set** (`docs/evaluation/algebra-2026-11/probe/`):
  - **Size:** 232 questions, split by hash into tune (117) and measure (115).
  - **Coverage:** every operator on both graphs; verify about 30 per graph; 15 AttackQA verify
    items; 7 Step 6 out-of-coverage items now answerable.
  - **Gold:** computed by the algebra on the live stores.
  - **Wording:** by Sonnet 5.5; every identifier and number was checked to survive.
  - **Groups:** 190 items "core", 42 "extended" (O7b time, O8 paths).
  - **Six edge-filter items** need relationship properties the cards do not declare. They are
    reported apart.
- **Controls** (`docs/evaluation/algebra-2026-11/exposure/controls.json`): 30 variant and 30 dev
  questions answered exactly by every typed arm in EXP-2026-11-018. Seed 20261120.

## Configurations and arms

- **Configurations:**
  - **off:** no switch;
  - **core:** `CORE=1`;
  - **core+ext:** `CORE=1 EXTENDED=1`.
- **Arms:**
  - T-lazy (Qwen 3.8 27B, `default-model-2`);
  - T-full (Qwen);
  - T-lazy-G (Gemma 4 31B, `default-model`).
- Temperature 0. Model identity checked by token id before and after each sitting.

## Stages

**Stage 1 (Phase G): Qwen T-lazy only.** Each configuration runs on the probe tune half plus the
60 controls.
- **Drop extended** if core+ext gains no exact answer over core on the extended tune items. The
  code stays; the switch stays off; the full run loses one configuration.
- **If core loses a control** and its plan used a new operator or the new checks: fix the prompt
  text or the description, and re-run Stage 1, at most three rounds. Then stop and report.
- **If off loses a control:** the log decides whether it is the model (noise) or the code
  (stop).

**Stage 2 (Phase G): Qwen T-full and Gemma T-lazy-G.** The configurations that survived, same
items, same checks.

**Stage 3 (Phase H): the full measurement, one configuration per sitting,** each checked before
the next starts:
1. **off-A;**
2. **core**, with a **stop rule:** stop and return to Phase G if, on any typed arm, confidently
   wrong answers rise by more than 5, or exact answers fall by more than 10, against off-A;
3. **core+ext**, if it survived;
4. **off-B.**

Each sitting covers:
- the variant set (699) for T-lazy, T-full and T-lazy-G;
- dev 284 for Qwen T-lazy, Qwen T-full and Gemma T-lazy;
- the probe measure half for all three typed arms.

E and R run once, in off-A, since they do not use the catalog.

**Order of work before Stage 3:** the full suite, then a reload of both stores, then the runs.

## Metrics

- **Probe:** per operator and per switch group (`scripts/algebra_probe_score.py`):
  - **exact:** node ids equal gold, or the value equal, floats within relative 1e-9;
  - **confidently wrong:** non-empty, not exact, not abstained;
  - **abstained/empty**;
  - **unparsed:** a value claim without `algebra_results`, never exact.
- **Existing banks:** per arm, as in EXP-2026-11-018:
  - variants: `records_exact`, confidently wrong;
  - dev: lost and confidently wrong against the authored answers (`scripts/era2_catalog_score.py`).
- **Counted, not gated:**
  - `written_id` coercions (the EXP-2026-11-019 guard);
  - "no confident match" refusals;
  - algebra steps per answer;
  - refusals by the new validator.
- **H1:** model-less answers per subset, as before.

## Gates (Phase H; fixed here)

| Check | Bar |
|---|---|
| Existing banks, exact, per arm and switch-on configuration | ≥ the lower off run minus the off-A/off-B spread |
| Existing banks, confidently wrong, per arm | ≤ the higher of off-A and off-B |
| Probe (measure half), per switch group | switch-on exact > off exact; per-operator table reported |
| `extended` stays on | its probe items gain over core, and the existing banks hold |
| H1 | ≤ 1 model-less answer per subset in every arm |

## Predictions

- **Probe, off:** near zero exact on operator questions, except verify and some typescans, which
  today's expand and describe can sometimes answer.
- **Probe, core (Qwen):** ≥ 0.5 exact on the core items. Verify, filter and typescan are best;
  groupby, rank and two-step medians are worst.
- **Extended:** gains on O8; time items are few (ATT&CK only). Shortest paths on ATT&CK may time
  out (5 s query limit; the probe gold used depth 3).
- **Existing banks:** within noise of off, except where the dropped-filter fix and the new
  validator turn a confidently wrong answer into an empty or a refusal.
- **Gemma** is lower than Qwen on the probe, as in every earlier typed comparison.

## What would falsify this

- **No help:** core does not beat off on the probe measure half. Exposure does not help, and the
  operators stay off for Step 11 until the planner prompt is reworked.
- **Harm:** core fails the existing-bank gates. The new prompt text costs today's questions, and
  the step stops (stop rule).

## Amendment 1 (2026-11-22, before any re-run): fix round 4 and the Stage 3 re-run

Written after the stop rule fired on the core sitting (ISSUES, 2026-11-22). The operator chose to
fix and re-run. This is a deviation: Stage 1 allowed three fix rounds, and this is a fourth.

**The fix (CORE only):**
1. **Teaching text.** The operator section of the system prompt now says that the text ops
   (`contains_text`, `starts_with`, `ends_with`) match the stored characters exactly, case
   included, and are not for finding an entity the question only describes. For that, the model
   names the entity if it knows it, or calls `resolve_entity`, and anchors on the id found.
2. **An empty text scan is refused once.** When a `typescan` or whole-label `filter` has a text
   condition, the planner counts it on the live store while checking the step
   (`runtime.scan_total`). If it matches nothing, the step is refused with that same advice. The
   same step sent again passes, so a question whose right answer is empty still gets it. If no
   count can be had, the step passes unchanged.

Switches off: the prompt, the tool specs and the check path are unchanged (the hash test passes).

**Prove small first** (stage runner, configurations core and core+ext; Qwen T-lazy, Qwen T-full,
Gemma T-lazy-G). The items are:
- every variant item that any typed arm lost under core in Phase H;
- the 60 controls;
- the probe tune half.

It goes ahead to Stage 3 if:
- Gemma's operator-attributed variant losses fall well below 17;
- no control is lost to an operator step on an arm that lost none in round 4;
- probe tune exact per arm stays within 5 of round 4.

**Stage 3 re-run:**
- **off-A is kept, not re-run:** with the switches off, the code paths and prompt bytes are
  unchanged.
- **core, core+ext and off-B** run on the fixed tree, in that order, with the same stop rule
  against off-A.
- **off-B, now on the new tree,** is also the check that off did not move. If off-B differs from
  off-A by more than the stop-rule margins on any arm, that is reported as drift, and the gates
  use both off runs as written.
