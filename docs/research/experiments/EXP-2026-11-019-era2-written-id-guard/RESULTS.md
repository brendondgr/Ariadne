# RESULTS — EXP-2026-11-019 Era 2 Step 8 follow-up 4: a written id outranks a name match

## 1. Headline

**The guard fired 12 times, every time on a target and never on a control. Every firing
anchored the written id, and none was confidently wrong.** Gemma's eight variant firings all
became exact (0 → 8). D2-detects-DET0891 is no longer confidently wrong, for Qwen or Gemma.
S1, S2 and H1 hold, so the guard is kept. Its full-bank effect is counted in Step 9's run.

## 2. Results table

From `data/metrics.json` and `tables/per_item.txt` (`data/score.py`, against EXP-2026-11-018's
outputs).
- **Runs:** one per arm (`n_runs: 1`) on 37 items. Unpaired with the earlier sitting.
- **Intervals:** none. At this n, the per-item table is the result.

**Checks**

| Check | Bar | Result | Pass |
|---|---|---|---|
| S1: guard firings on controls | 0 | 0 of 54 control answers (24 variant, 30 dev) | yes |
| S1: control losses the guard caused | 0 | 0 (one control fell, from the model's draft, § 4) | yes |
| S2: firings that anchor the written id | all | 12 of 12 | yes |
| S2: firings confidently wrong | 0 | 0 | yes |
| H1: model-less answers per subset | ≤ 1 | 0, 0, 0, 1, 0 | yes |
| Guard refusals ("fits several labels") | reported | 0 | — |

**Variants, 22 items per arm** (EXP-2026-11-018 → this run)

| Arm | Set | n | Guard fired | Exact | CW |
|---|---|---|---|---|---|
| T-lazy-G (Gemma) | targets | 10 | 8 | 0 → 8 | 0 → 0 |
| T-lazy-G (Gemma) | controls | 12 | 0 | 12 → 11 | 0 → 0 |
| T-lazy (Qwen) | targets | 10 | 0 | 9 → 8 | 0 → 0 |
| T-lazy (Qwen) | controls | 12 | 0 | 9 → 11 | 0 → 0 |

On Gemma's fired targets (C-CWE2-01 T0/T1, F-CTM-01 T0–T2, F-CTM-07 T0–T2), the answer now has
the same ids as Qwen's exact answer to the same item.

**Dev, 15 questions per arm** (EXP-2026-11-018 → this run)

| Arm | Guard fired | Targets lost | Controls lost | DET0891 CW |
|---|---|---|---|---|
| Qwen T-lazy | DET0891 | 0 → 1 | 1 → 1 | 1 → 0 |
| Qwen T-full | T1598.002 | 0 → 1 | 1 → 1 | 0 → 0 |
| Gemma T-lazy | DET0891, CAPEC-686 | 1 → 1 | 1 → 1 | 1 → 0 (ids equal the authored answer) |

## 3. Figures

None.

## 4. Interpretation

- **The guard does what it should, where it should.** It acted only when the model anchored by
  name and the lookup returned an entity other than the one the question wrote. Every swap
  made the anchor correct.
- **It is a Gemma fix more than a Qwen one, as predicted.** Gemma passes the id itself as a name
  ("CAPEC-600"), and the fuzzy name lookup returns a different pattern. Qwen rarely takes the
  name route when an id is written; it fired once per Qwen dev arm.
- **No answer got worse because of the guard.** Four answers got worse without it firing.
  Their logs show the model's own draft:
  - **Gemma F-CTT-02 T0 (control):** the second step asks for HAS_TACTIC on Technique, a
    relation that does not exist.
  - **Qwen F-CTT-03 T1 (target):** the plan walked to Category.
  - **Qwen T-lazy and T-full on dev CAPEC-3000 (target):**
    - T-lazy's step was refused for a View relation that does not exist.
    - T-full fell back to English.
  - **Run-to-run variation is the same size:** Qwen's controls gained two exact answers, with
    the guard idle.
- **No claim moves.** This is an engineering change, measured small.

## 5. Threats to validity

- **Small n, one sitting.** 22 variant and 15 dev items, one run per arm. The before side is
  EXP-2026-11-018, a different sitting, so only firings are credited to the guard.
- **Some targets were not re-tested.** The model did not take the name route this time on:
  - Gemma's T1001.003 and CAPEC-3000 dev targets;
  - its F-CTT-03 T1 and F-NEG-06 T6 variant targets;
  - most Qwen targets.

  The guard was not exercised on those. Their logs show no firing and no guard refusal.
- **The rule was designed from the same 16 cases it was proven on.** The controls guard against
  over-fitting in one direction (firing where it should not). Whether it catches every future
  name collision is not tested. Step 9's full run counts every firing.

## 6. What surprised us

- **Gemma's id-as-name failure has a second form the guard does not reach.** Sometimes the
  lookup finds no confident match for "CAPEC-49". The step is then refused before the guard
  runs, and only the repair turn fixes it (Gemma F-CTT-02 T0, F-NEG-06 T6). Here the repair
  turn did fix it, so the guard is not widened. It is recorded in ISSUES.

## 7. Follow-ups

- **Step 9 (the operator set, scoped to retrieval) is next.** Its full run carries this guard.
  Count the `written_id` coercions there.
- **If the no-confident-match form shows up in Step 9's refusal counts:** take a written id when
  the name text contains it, before the lookup is consulted.

## 8. Reproduction

```bash
# on the commit that adds this record (its utils/ diff is data/DIFFSTAT), after the full suite
# and a store reload:
bash docs/research/experiments/EXP-2026-11-019-era2-written-id-guard/data/run.sh   # writes to the session scratchpad; set S
uv run python docs/research/experiments/EXP-2026-11-019-era2-written-id-guard/data/score.py "$S" \
    docs/evaluation/experiments/harness-attribution-qwen-walkfix-2026-11-16/generic_composed/answers
```
