# PROTOCOL — EXP-2026-11-019 Era 2 Step 8 follow-up 4: a written id outranks a name match

Written 2026-11-20, after the full test suite passed and while the smoke was running, before any
of its outputs were read. EXP-2026-11-018 (RESULTS § 6–7) found one new, small pattern: the
question writes an id, the plan anchors by name, and the name lookup returns a different entity.
The operator asked for the guard. The standing rule holds: prove it on the items that failed,
with controls. **There is no full-bank run here.** The guard is committed before Step 9, and its
full-bank effect is measured in Step 9's run, where every firing is logged as a coercion and can
be counted.

## What was looked at before writing

Every typed answer of EXP-2026-11-018 was searched: 2,097 variant rows (T-lazy, T-full, T-lazy-G)
and 852 dev answers (Qwen T-lazy, Qwen T-full, Gemma T-lazy).
- **The case:** a `resolve_entity` coercion turned a name anchor into an id. The question writes
  an id of the same graph, and the lookup did not return it.
  - **16 answers, every one with the wrong anchor:**
    - 10 Gemma variants (C-CWE2-01 T0/T1, F-CTM-01 T0/T1/T2, F-CTM-07 T0/T1/T2, F-CTT-03 T1,
      F-NEG-06 T6);
    - 1 Qwen T-lazy dev (D2-detects-DET0891);
    - 1 Qwen T-full dev (T1598.002);
    - 4 Gemma dev (DET0891, T1001.003, CAPEC-686, CAPEC-3000).
  - **Qwen T-lazy on variants:** none.
- **There are three shapes, not one:**
  - **A shared name:** DET0891 and DET0862 are both "Detection of DNS Server", and T1598.002
    and T1566.001 are both "Spearphishing Attachment".
  - **The id given as the name:** Gemma passes "CAPEC-600" as a name, and the fuzzy lookup
    returns CAPEC-16.
  - **A name the question pairs with an id the graph lacks:** "CAPEC-9999 (Quantum Keystroke
    Inference)" resolved to CAPEC-306. This is a negative item, so the right answer is not
    found.
- **The wrong match is not always the same label.** CAPEC-3000 is a View and CAPEC-4 is an
  AttackPattern; T1001.003 is a SubTechnique and T1572 is a Technique. A same-label rule would
  miss 3 of the 16.
- **The rule below, simulated offline over every recorded name lookup, fires on exactly these
  16 and on nothing else.**
- **The model writing a wrong id directly** (not through a name) never occurs in these runs. It
  is out of scope.

## The change (Ariadne, committed with this protocol)

`PlanContext.written_for_name` and its call after a name lookup, in `utils/planner/typed.py`.
- **When it acts:** a step anchored by name resolves to ids that include none of the question's
  written ids of that graph.
- **What it does:** it takes a written id when exactly one is tied to the name, by any of:
  - the graph stores that name for it;
  - the name text contains it;
  - the question pairs the two, as "id (name)" or "name (id)".
- **The label:** the step takes the written id's label when that differs (logged as
  `id_scheme`). If the id fits several labels, the step is refused.
- **Logging:** each swap is a coercion with `filled_by: written_id`.
- **What is untouched:** id anchors, `from_step` anchors and scans. A name tied to no written
  id keeps the lookup's answer.

**Tests:** 6 new, in `utils/planner/tests/test_typed_planner.py`, class `TestWrittenIdOutranksName`:
- shared name;
- id as the name;
- a label change;
- a missing id kept;
- an unrelated written id ignored;
- a lookup that already found the written id left alone.

The full suite passes: 2,994 passed, 359 skipped.

## Smoke (the measurement here)

Run on the working tree (base commit 4f0aac6f plus this change), at temperature 0. Output is in
the session scratchpad; the per-item table goes in RESULTS.
- **Variants, 22 items, arms T-lazy (Qwen) and T-lazy-G (Gemma):**
  - **10 targets:** Gemma's 10 above.
  - **12 controls:** previously exact in both arms. Six had a name lookup that found the
    written id, so the guard checks them but must not act. Six are paraphrases that write an id.
- **Dev, 15 items, arms Qwen T-lazy, Qwen T-full and Gemma T-lazy:**
  - **5 targets:** the dev items above.
  - **10 controls:** dev items whose name lookup found the written id.

**Checks:**
- **S1 (controls):** the guard fires on no control. No control falls from exact, or from a
  non-empty answer to empty, unless its log shows the change was the model's draft rather than
  the guard.
- **S2 (targets):** every target where the guard fires anchors the written id and is not
  confidently wrong.
- **H1:** model-less answers are 0 or 1 per subset.

The model may not take the name route again on a given target. A target where the guard does not
fire is reported, not counted against it.

**Predictions:**
- The guard fires on most Gemma targets and on few Qwen ones.
- Targets where it fires become exact or near exact. F-NEG-06 T6 becomes an honest empty, not
  confidently wrong.
- Controls are unchanged.

**Decision rule:**
- **S1 and S2 hold:** the guard is kept and committed. Its full-bank effect is counted in Step
  9's run.
- **S1 fails:** the rule is narrowed to the shared-name and id-as-name shapes and re-proven.
- **S2 fails:** the swap is reverted and the case is recorded as open.

## Threats

- **Small n:** 22 + 15 items, one run per arm.
- **Unpaired with the past run:** the targets' previous behaviour comes from EXP-2026-11-018, a
  different sitting. A target that is now exact because the model chose a different route is not
  credited to the guard. Only firings are.
- **The offline simulation reads recorded coercions.** It cannot see name lookups that a
  different draft would make.
