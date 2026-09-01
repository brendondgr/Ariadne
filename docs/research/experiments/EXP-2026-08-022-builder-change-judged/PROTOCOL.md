# PROTOCOL — EXP-2026-08-022 Is the shipped builder change an improvement, judged?

**Written 2026-08-31 before any judgment of the new-builder answers existed.**

## 1. Question

`9f02dc6` flipped `ARIADNE_LEXICON` and `ARIADNE_EXACTNAME` to default **on** and
moved name resolution to the top of `build()`. Its regression evidence covers the
**120-question catalogue** (6 better, 0 worse) and the variant bank (+18/−8). It
does **not** cover the two fresh banks — and those are the banks carrying
**C-012, C-021 and C-022**.

Re-running the deterministic arm at `HEAD` over both fresh banks
(EXP-2026-08-021 follow-up, recorded in the migration plan) found:

| of 60 answers, clock keys excluded | |
|---|---|
| byte-identical | **29** |
| **answer text changed, retrieval identical** | **30** |
| retrieval changed | **1** (an improvement: `records 0→1`) |

So on these banks the change is **almost entirely a rendering change**, and
rendering is exactly what a judge scores. **Is it better?**

## 2. Design

Two conditions, identical questions, identical gold, **no language model in
either answer path** — both are the deterministic arm, so both are
byte-reproducible.

| condition | answers |
|---|---|
| **old builder** | `docs/evaluation/experiments/bank20260819\|20/deterministic` — committed, produced pre-`9f02dc6` |
| **new builder** | `docs/evaluation/experiments/builderiso-b19\|20-newbuilder/deterministic` — produced at `HEAD` 2026-08-31 |

**Grading: three paired sessions.** Each session grades *both* conditions on
*both* banks back to back, suffixes `.bld1`, `.bld2`, `.bld3`. Pairing within a
session is `EXP-2026-08-009`'s rule — *"all cells graded in one session so the
grader cancels out of every comparison"* — and `EXP-2026-08-021` H7 measured that
it works: every contrast sd came in below the sum of its component sds.

Grader: `relay/qwen38-27B-v2@2026-08-31`, calibrated at r = 0.9612 against the
committed Sonnet judgments (`EXP-2026-08-021` §1). 12 workers, `max_tokens` 8192
with the standard escalation.

## 3. The control that makes this measurable

**The 29 byte-identical answers are a null control.** Identical bytes must score
identically up to grader noise, so their measured old-vs-new difference **is** the
noise floor — measured in the same sessions, on the same instrument, on this
exact comparison. It is a better floor than importing `EXP-2026-08-021`'s
0.0036–0.0249, which came from different cells.

**Every claim below is the changed-set difference against that floor.** A
difference in the changed set that does not exceed the difference in the
unchanged set is not evidence of anything.

## 4. Pre-registered hypotheses

| | Prediction |
|---|---|
| **H1** | **Null control holds:** mean \|old − new\| on the 29 byte-identical answers is ≤ 0.02, and their mean signed difference is ≈ 0. *Falsifier: a non-zero signed difference on identical inputs, which would mean the sessions are not comparable and would void the rest.* |
| **H2** | **The new builder is not worse.** Signed mean difference (new − old) over all 60 ≥ 0. |
| **H3** | **Any real movement is confined to the 31 changed answers**, and their signed difference exceeds the null control's. |
| **H4** | **Paired counts favour the new builder**: among the 31 changed answers, more improve than regress. |

## 5. Decision rule, written first

- **H1 fails** → stop. Report the session comparison as void and re-run; nothing
  else in this experiment is interpretable.
- **H2 holds and H3 holds** → `9f02dc6` is confirmed as an improvement on the
  banks its own regression check missed, and the gap in that check is closed.
- **H2 fails (new worse)** → this is a **regression on the banks carrying C-012,
  C-021 and C-022**, and it must be raised as such regardless of the catalogue
  and variant-bank results, which measured different question sets.
- **H2 and H3 both inside the null floor** → the honest answer is *"the change is
  invisible to a judge on these banks"*, which is a legitimate and useful null:
  it would mean the 30 prose changes are cosmetic, and that judged figures
  recorded pre-`9f02dc6` may be quoted after it.

## 6. What this does not measure

* **Not the model change.** Both conditions run the same grader and neither
  answer path contains a model. This isolates the builder only. Model isolation
  is Step 4/A of the migration plan and needs the `758813f` worktree.
* **Not the catalogue or the variant bank.** Those are already covered by
  `9f02dc6`'s own evidence and are not re-run here.
* **Not question-sampling variance.** n = 30 per bank; the bootstrap interval
  over questions is roughly ±0.06 (`EXP-2026-08-009`), far wider than any grader
  effect. **A grader sd is not an interval on the builder change.**
* **Retrieval is unchanged on 59 of 60 answers**, so this cannot and does not
  speak to retrieval quality.

## 7. Reproduction

```bash
# new-builder answers (deterministic arm, no model, ~1.5 s per bank)
for b in 19 20; do
  uv run python -m utils.evaluation.experiment_untruncated --arm deterministic \
    --bank docs/evaluation/banks/bank-2026-08-$b/bank.json \
    --root docs/evaluation/experiments/builderiso-b$b-newbuilder --workers 4
done

# three paired sessions, both conditions in each
for s in bld1 bld2 bld3; do
  for b in 19 20; do
    uv run python -m utils.evaluation.judge_answers \
      --root docs/evaluation/experiments/bank202608$b --arm deterministic --suffix ".$s" --workers 12
    uv run python -m utils.evaluation.judge_answers \
      --root docs/evaluation/experiments/builderiso-b$b-newbuilder --arm deterministic --suffix ".$s" --workers 12
  done
done
```
