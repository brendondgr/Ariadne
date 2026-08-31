# PROTOCOL — EXP-2026-08-021 Grader-model sensitivity

**Written 2026-08-31, before any candidate judgment existed.** Step 1's
calibration had run; no cell of Step 2 had.

## 1. Question

The relay alias `skynet` has served three different models (`D-028`, `Q12`).
Every judged figure this project recorded from 19 August onward was graded
through that alias, and for `EXP-2026-08-007`, `-008` and `-009` — which carry
**C-012, C-021 and C-022** — the serving model is **not determinable**.

**Does a judged comparison survive a change of grader model?**

The level was never quotable; `D-002` and `C-009` already say the local grader is
for comparing arms, not for publication. What must survive is the **ordering**.
If it does not, no judged comparison in this record survives.

## 2. Why this is measurable now and was not before

The answers are on disk and do not move. Grading them again changes exactly one
variable. The existing 0.0050 "grader spread" (`EXP-2026-08-007`) was measured
**within one model over three passes** and bounds nothing about a model change —
a distinction that experiment's own threats section draws and that nothing has
tested until now.

## 3. Design

**Conditions.** Two grading passes over byte-identical saved answers.

| | pass |
|---|---|
| reference | the committed judgments backing each experiment's reported figures — base `.judgment.json` for `EXP-2026-08-008`'s arms, `.judgment.c015.json` for `EXP-2026-08-009`'s merged/federated pair |
| candidate | `.judgment.qwen38.json`, graded by **`relay/qwen38-27B-v2@2026-08-31`**, identified by probe (`scripts/model_identity.py`) rather than by alias |

**Cells.** Both fresh banks × six arms = 12 cells, 360 answers.
`deterministic`, `generic`, `generic_composed`, `gold_loop_llm`, `llm_query`,
`merged` over `bank20260819` and `bank20260820`.

**Held constant.** Rubric, prompt builder, `max_tokens`, workers, temperature 0,
and the answers themselves. Only the weights differ.

## 4. Pre-registered hypotheses

| | Prediction |
|---|---|
| **H1** | **Arm ordering is preserved in every bank.** The falsifier is any bank where the two graders rank the arms differently |
| **H2** | The between-model mean absolute delta exceeds the 0.0050 within-model spread by **at least an order of magnitude** |
| **H3** | **C-012's margin survives.** `deterministic` − `llm_query` stays positive and larger than the grader's own spread, on both banks |
| **H4** | Disagreement is **larger on the weak arm than on the strong ones**. A grader has little room to disagree about an answer everything scores near 1.0 |

## 5. Decision rule, written before the numbers

- **H1 holds** → the affected claims keep their direction and gain a
  "reproduced under a second, independently calibrated grader" note. The
  *levels* remain unquotable, exactly as before.
- **H1 fails on any cell** → that cell's claim drops to `partial` pending a
  cross-model Sonnet panel, and the failure is the headline.
- **H3 fails** → C-012 drops to `partial` immediately. It is the project's one
  unambiguously positive claim and it may not rest on one grader.

## 6. Gate already passed (Step 1)

Calibration of the candidate grader against the **committed Sonnet judgments**,
30 cases, `holdout-v1/deterministic`:

| | Ornith-era | **`qwen38-27B-v2`** | gate |
|---|---|---|---|
| Pearson r | 0.9275 | **0.9612** | ≥ 0.90 ✅ |
| mean delta | +0.031 | **+0.021** | ≤ 0.05 ✅ |
| verdict agreement | 0.70 | **0.7667** | — |

The candidate is **better** calibrated against the cross-model reference than the
instrument it replaces, on all three measures. That is what licenses Step 2; had
it failed, the correct action was to escalate to the Sonnet panel, not to grade.

The pre-existing `.judgment.local.json` files were copied to
`.judgment.local.pre-qwen38.json` first — `calibrate()` hardcodes `force=True`
and would have destroyed the artifacts behind the recorded 0.9275. The backup
suffix contains `.judgment`, so `answer_files()` excludes it and it cannot be
re-consumed as an answer.

## 7. Threats known in advance

- **Dropout biases a mean upward if the failures are the hard cases**, and this
  is not hypothetical: an existing `.cross` pass over `llm_query` failed on
  exactly the three lowest-scoring answers (0.20, 0.30, 0.35) and read **0.7407
  against the base pass's 0.5000** partly for that reason. `grader_sensitivity.py`
  therefore pairs on case id and reports dropout separately rather than absorbing
  it.
- **Two graders, not two instruments.** Both are local relay models on one
  server. Agreement between them is weaker evidence than agreement with the
  provider-hosted Sonnet panel, which is why Step 1's gate is against Sonnet.
- **n = 30 per cell.** Small, and the arms are bunched near the ceiling on five
  of six, which compresses the room for disagreement.
- **One run per pass.** Within-model variance for the candidate is not
  re-measured here; the 0.0050 figure is carried over from a different model and
  is used only as an order-of-magnitude reference in H2.
- **`qwen38-27B-v2`'s `max_model_len`, quantisation and concurrency ceiling are
  unconfirmed** (`Q11`, reopened). Workers were held at 12, below the last known
  ceiling of 16, rather than tuned.

## 8. Reproduction

```bash
uv run python scripts/model_identity.py skynet --date 2026-08-31 --json

uv run python -m utils.evaluation.judge_answers \
  --root docs/evaluation/experiments/holdout-v1 --arm deterministic --calibrate --workers 12

for root in bank20260819 bank20260820; do
  for arm in deterministic generic generic_composed gold_loop_llm llm_query merged; do
    uv run python -m utils.evaluation.judge_answers \
      --root docs/evaluation/experiments/$root --arm $arm --suffix .qwen38 --workers 12
  done
done

uv run python scripts/grader_sensitivity.py \
  --root docs/evaluation/experiments/bank20260819 \
  --arms deterministic generic gold_loop_llm llm_query --candidate-suffix .qwen38
```

---

# AMENDMENT A-1 (2026-08-31) — repeats, pre-registered before pass 2 exists

Pass 1 is complete on 10 of 12 cells and **nothing below has been run.** The
amendment is written now so the repeat hypotheses cannot be fitted to what the
repeats show.

## Why repeat, precisely

Not "to make sure the results are accurate" — repeats cannot do that. Re-grading
frozen answers measures the **precision of the instrument**, not the accuracy of
the arms, and not the stability of the pipeline (`D-010` stays open for the arms;
only Step 4 can close it). Accuracy against an external reference is what Step 1's
Sonnet calibration measured.

What repeats *do* settle is a claim pass 1 made and cannot defend:

> Pass 1 measured a candidate-minus-reference offset of **+0.023 to +0.057** on
> the four base-pass cells and **−0.007 to −0.038** on the `.c015` pair, and
> `ISSUES.md` I-4 reads that as a directional difference between grading passes.
> **With n = 1 that reading is indefensible.** If the within-model spread across
> repeats is of the same order, the offset is noise and I-4's reading must be
> withdrawn.

## Design

**Five sessions total** (pass 1 plus four repeats), each a *complete* pass over
all twelve cells, suffixes `.qwen38`, `.qwen38r2` … `.qwen38r5`.

**Sessions, not cells, are the unit of repetition**, following
`EXP-2026-08-009`'s protocol: every contrast is computed *within* a session so
session-level drift cancels out of it. Repeating cell-by-cell at different times
would fold drift into the contrast, which is the confound that protocol exists to
avoid.

Nothing else changes: same rubric, same prompt builder, same `max_tokens`, same
12 workers, temperature 0, same answers.

**Temperature 0 is not determinism.** Greedy decoding still reduces floating
point over whatever batch a request lands in, which is what concurrency perturbs
(`EXP-2026-08-019`, `utils/llm_sampling.py`). The other variance source is the
parse-failure path, which retries at double `max_tokens` and so grades a
different request. Both are expected to produce non-zero spread.

## Pre-registered hypotheses

| | Prediction |
|---|---|
| **H5** | Within-model spread on a cell mean is **small relative to the between-model offset** — sd ≤ 0.02, against offsets of 0.023–0.057. *Falsifier: sd of the same order as the offset, which withdraws I-4.* |
| **H6** | **Spread is larger on `llm_query` than on the near-ceiling arms**, for the same reason H4 gave: an arm bunched at 1.0 has no room to disagree with itself either |
| **H7** | **The paired contrasts are more stable than their components.** sd of (`deterministic` − `llm_query`) is smaller than the sum of the two arms' sds, because a session-level offset shifts both arms together and cancels |
| **H8** | **No repeat reverses an ordering.** Falsifier: any session in which `llm_query` ≥ `deterministic`, or in which merged/federated flip beyond the tie already recorded |

## Decision rule, written first

- **H5 holds** → I-4's directional reading stands, with an interval attached.
- **H5 fails** → **I-4 is withdrawn in the results**, the offset is reported as
  indistinguishable from noise, and the `RESULTS.md` sentence about the candidate
  being "more generous on base-pass cells and stricter on `.c015` cells" is cut.
- **H8 fails on any session** → the affected claim drops to `partial`
  immediately, whatever the means say.

## Cost, stated because it was underestimated once

Per-cell wall clock in pass 1 was **227–565 s** (mean ≈ 350 s), so a full pass is
**≈ 70 minutes** and four repeats are **≈ 4.7 hours**. This is an overnight job,
not a cheap one. It is judged worth it because n = 1 on a grader is the same
defect this experiment was created to expose in someone else's numbers.

## Reporting

`scripts/grader_sensitivity.py` compares two passes. Aggregation across five
passes — per-cell mean ± sd, per-session contrasts, and the H5 comparison against
the between-model offset — is `scripts/grader_repeats.py`, written before the
repeats finish and reported whatever it shows.
