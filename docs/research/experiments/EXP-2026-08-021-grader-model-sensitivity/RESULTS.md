# RESULTS — EXP-2026-08-021 Grader-model sensitivity

**Status: complete.** Five complete grading sessions over one frozen answer set —
1,794 judgments over 360 answers in 12 cells — plus a calibration against the
committed Sonnet judgments. **No arm ordering moved anywhere, in any session.**

## 1. Headline

**A judged comparison in this record survives a change of grader model.** Across
5 sessions × 12 cells, **zero ordering reversals** and **zero sign flips** on
either contrast.

| | bank 19 | bank 20 |
|---|---|---|
| `deterministic − llm_query` (**C-012**) | **+0.4260 ± 0.0164** | **+0.5303 ± 0.0303** |
| `generic_composed − merged` (**C-022**) | **+0.0625 ± 0.0147** | **+0.0567 ± 0.0097** |

C-012's margin is 14–26× the grader's own spread. It is not an artifact of the
unidentified instrument that produced it.

**And the gate that licensed this run:** the candidate grader is *better*
calibrated against the cross-model Sonnet reference than the instrument it
replaces — Pearson **r 0.9275 → 0.9612**, mean delta **+0.031 → +0.021**, verdict
agreement **0.70 → 0.767**, on the same 30 answers.

## 2. Per-cell spread, five sessions

| bank | arm | p1 | r2 | r3 | r4 | r5 | mean | **sd** | n |
|---|---|---|---|---|---|---|---|---|---|
| 19 | deterministic | 0.9833 | 0.9750 | 0.9700 | 0.9750 | 0.9633 | 0.9733 | 0.0074 | 30 |
| 19 | llm_query | 0.5317 | 0.5483 | 0.5417 | 0.5650 | 0.5500 | 0.5473 | 0.0122 | 30 |
| 19 | generic | 0.9667 | 0.9717 | 0.9750 | 0.9767 | 0.9700 | 0.9720 | 0.0040 | 30 |
| 19 | gold_loop_llm | 0.9883 | 0.9867 | 0.9617 | 0.9817 | 0.9850 | 0.9807 | 0.0109 | 30 |
| 19 | merged | 0.8931 | 0.8672 | 0.8903 | 0.8897 | 0.9000 | 0.8881 | 0.0124 | 29 |
| 19 | generic_composed | 0.9476 | 0.9552 | 0.9448 | 0.9431 | 0.9621 | 0.9506 | 0.0079 | 29 |
| 20 | deterministic | 0.9655 | 0.9793 | 0.9862 | 0.9828 | 0.9845 | 0.9797 | 0.0083 | 29 |
| 20 | llm_query | 0.4750 | 0.4517 | 0.4350 | 0.4150 | 0.4700 | 0.4493 | **0.0249** | 30 |
| 20 | generic | 0.9850 | 0.9800 | 0.9883 | 0.9817 | 0.9800 | 0.9830 | 0.0036 | 30 |
| 20 | gold_loop_llm | 0.9776 | 0.9759 | 0.9672 | 0.9621 | 0.9690 | 0.9704 | 0.0064 | 29 |
| 20 | merged | 0.8983 | 0.8717 | 0.8833 | 0.8833 | 0.8850 | 0.8843 | 0.0095 | 30 |
| 20 | generic_composed | 0.9414 | 0.9379 | 0.9414 | 0.9483 | 0.9362 | 0.9410 | 0.0046 | 29 |

Grader spread runs **0.0036 – 0.0249**. For scale, the previously recorded figure
was **0.0050**, measured within *one* model over three passes on *one* arm; the
range here is the same order and the old figure sits near its bottom.

## 3. The hypotheses, adjudicated

### H5 — split, and **I-4 stands rather than being withdrawn**

The pre-registered falsifier was that the within-model spread would swallow the
between-model offsets, in which case `ISSUES.md` I-4's directional reading was to
be cut. **It does not.** Taking 2 × sd as the bar, **8 of 12 offsets survive**:

| reference pass | cells surviving | offsets |
|---|---|---|
| base `.judgment.json` | **6 of 8** | **all positive**: +0.037, +0.032, +0.023, +0.057, +0.010, +0.013 |
| `.judgment.c015.json` | **2 of 4** | **all negative**: −0.027, −0.038 |

Every surviving base-cell offset is positive and every surviving `.c015` offset
is negative, so **the directional difference between the two reference passes is
real**. The four cells that fail are the four *smallest* offsets (0.003, 0.011,
0.007, 0.005) — which is what a real effect plus noise looks like, not what noise
alone looks like.

**H5's literal prediction (sd ≤ 0.02) fails on one cell**: `llm_query` bank 20 at
0.0249. Recorded as a miss rather than rounded away; the substantive conclusion
is unaffected.

**What this does *not* license.** The offsets are real and remain *unexplained*.
The reference grader is unidentified (`Q12`), so a measured difference between
two passes cannot be attributed to anything. **That is the cost `D-028` exists to
stop accruing, now quantified rather than argued.**

### H6 — refuted as stated; the corrected predictor is headroom, not weakness

Predicted: spread largest on the weak arm. **It is not.** On bank 19 `merged`
(0.0124) edges out `llm_query` (0.0122), and `merged` is not the weak arm.

The predictor that actually fits is **distance from the ceiling**:

| arm band | mean score | sd |
|---|---|---|
| near-ceiling (`generic`, `generic_composed`, `gold_loop_llm`, `deterministic`) | 0.94 – 0.98 | **0.0036 – 0.0109** |
| mid (`merged`) | 0.88 | 0.0095 – 0.0124 |
| low (`llm_query`) | 0.45 – 0.55 | **0.0122 – 0.0249** |

An arm bunched at 1.0 has nowhere to vary, so it cannot disagree with itself
either. This restates H4 from the pass-1 analysis on a second axis and is the
better-specified claim.

### H7 — held, 4 of 4, and it is the design working

Contrast sd is below the sum of its component sds in **every** case:

| contrast | contrast sd | sum of component sds |
|---|---|---|
| 19 `deterministic − llm_query` | 0.0164 | 0.0196 |
| 19 `generic_composed − merged` | 0.0147 | 0.0203 |
| 20 `deterministic − llm_query` | 0.0303 | 0.0332 |
| 20 `generic_composed − merged` | 0.0097 | 0.0141 |

A session-level offset shifts both arms together and cancels out of the
difference. **This is why the within-session design was chosen and it is the
justification for `EXP-2026-08-009`'s rule** that all cells of a comparison be
graded in one session — now supported by measurement rather than by argument.

### H8 — held completely

Sign stable on all four contrasts in all five sessions. **Zero ordering
reversals.** This is the load-bearing result: the record's judged comparisons do
not depend on which grader ran them.

### Drift — tested, and refuted

A spread across passes assumes the passes are exchangeable. **At k = 5, 0 of 12
cells are monotone** against ~0.1 expected by chance.

The check earned its place. At n = 4, `llm_query` on bank 20 read
0.4750 → 0.4517 → 0.4350 → 0.4150 — a strictly monotone −0.060 slide, the largest
movement in the table, and in the direction that would have **flattered C-012** by
widening its margin. **r5 broke it at 0.4700.** It was scatter.

## 4. The failures, and the finding they produced

**6 failures in 1,794 gradings — and every one is in the top 5% by answer size.**

| pass | cell | case | KB | symptom |
|---|---|---|---|---|
| r2 | 20/gold_loop_llm | H-CHN-01 | 178 | truncated mid-object |
| r3 | 19/merged | H-CHN-03 | 79 | `JSONDecodeError: Extra data` |
| r3 | 19/generic_composed | H-CHN-03 | 85 | judgment missing 5 fields |
| r3 | 20/generic_composed | H-CHN-01 | 177 | empty reply |
| r4 | 20/deterministic | H-CHN-01 | 173 | empty reply |
| r4 | 20/generic_composed | H-CHN-01 | 177 | empty reply |

Median answer is **10.3 KB**; p90 is **25.3 KB**; every failure is **≥ 79 KB**.
The at-risk population is 17 of 360 answers (4.7%) spanning four case ids and
**two question types**. Inside it the failure rate is ≈ 7% per attempt; outside
it, **0 of ~1,700**.

**So judged evaluation in this record fails systematically on its longest
answers, and answer length is a property of the question type.** A judged mean is
computed over a case set that intermittently excludes the hardest questions, and
nothing in a reported figure shows it, because a case that errors is not in the
denominator. Full diagnosis in [`ISSUES.md`](ISSUES.md) I-6 – I-8.

**None of this was visible at n = 1.** Pass 1 graded 360 of 360. The loss rate
exists as an observable *only because the passes were repeated* — a return on
repetition entirely separate from the variance estimate they were run for.

## 5. Threats to validity

* **This measures grader precision, not accuracy, and not the pipeline.** The
  answers are frozen. `D-010` stays open for the arms; only re-running the
  pipeline closes it. Accuracy against an outside reference is §1's calibration.
* **⚠️ The sds here are NOT confidence intervals on the arm comparisons.** They
  are grader variance at fixed questions. **Question-sampling variance is a
  separate and much larger component** — `EXP-2026-08-009` reports bootstrap
  intervals of roughly ±0.06 over questions at n = 30. So C-022's
  +0.0625 ± 0.0147 means *the grader is confident*, **not** that federated beats
  merged: the difference remains well inside the question-sampling interval.
  Reading a grader sd as an effect interval would be the central error available
  here.
* **Two local models are not two instruments.** Both are relay models on one
  server. Agreement between them is weaker evidence than agreement with the
  provider-hosted Sonnet panel, which is why the gate was against Sonnet.
* **The reference passes have n = 1** and an unidentified model. Every offset in
  §3 is a five-sample mean against a single sample.
* **n = 30 questions per cell**, and five of six arms bunch near the ceiling,
  which compresses the room for any grader to disagree.
* **`max_model_len`, quantisation and concurrency for `qwen38-27B-v2` are still
  unconfirmed** (`Q11`, reopened). Workers were held at 12, below the last known
  ceiling, rather than tuned.

## 6. What this changes

| Claim | Effect |
|---|---|
| **C-012** | Strengthened. The margin survives a grader change at 14–26× the grader's spread. Add: *"reproduced under a second, independently calibrated grader."* Levels remain unquotable |
| **C-021, C-022** | Directions hold; **levels still not quotable**, and C-022's gains nothing about the architecture because grader precision is not question-sampling precision |
| **C-009** | Second, independent line of support. A grader swap moves absolute levels by up to 0.057 while leaving every ordering intact — self-judged *levels* are the unreliable part, exactly as the claim says |
| **C-001, C-014, C-017, C-023** | Unaffected in direction; they inherit the same "levels not quotable" caveat |

## 7. Follow-ups

1. **Fix the extraction path** — `json.JSONDecoder().raw_decode` from the first
   `{` recovers the two parser modes. The empty-reply mode needs the larger
   budget `EXP-2026-08-009` established. **Both are needed; neither suffices.**
2. **Report `n` and the error count beside every judged mean.** The denominator
   has never been constant and has always been reported as though it were.
3. **Re-grade the July arms?** No. Those answers were produced by weights that no
   longer exist; re-grading them measures this grader against that model's
   answers, which is a different question from the one anyone is asking.
4. **Step 4 of the migration plan still has two variables** (model and builder,
   after `9f02dc6`). See the plan's §"Step 4 has acquired a second variable".

## 8. Reproduction

```bash
uv run python scripts/model_identity.py skynet --date 2026-08-31 --json

uv run python -m utils.evaluation.judge_answers \
  --root docs/evaluation/experiments/holdout-v1 --arm deterministic --calibrate --workers 12

for r in "" r2 r3 r4 r5; do
  for root in bank20260819 bank20260820; do
    for arm in deterministic llm_query merged generic_composed generic gold_loop_llm; do
      uv run python -m utils.evaluation.judge_answers \
        --root "docs/evaluation/experiments/$root" --arm "$arm" \
        --suffix ".qwen38$r" --workers 12
    done
  done
done

uv run python scripts/grader_repeats.py \
  --root docs/evaluation/experiments/bank20260819 \
  --arms deterministic llm_query generic gold_loop_llm merged generic_composed \
  --suffixes .qwen38 .qwen38r2 .qwen38r3 .qwen38r4 .qwen38r5 \
  --contrast deterministic:llm_query --contrast generic_composed:merged
```
