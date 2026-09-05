# PROTOCOL — EXP-2026-09-006 Do the August comparisons survive a change of grader *family*?

> Written 2026-09-05 10:55 EDT, **before any candidate judgment existed**.
> The operator restarts `gemma4-31B-mtp` on `:9090`/`default-model-2` this
> morning and it disappears at **16:00 EDT**, so the pass order below is a
> priority order: an early cutoff must still close the two claims that matter.

## Question

C-021 (co-authorship bias) and C-022 (federation versus merging) rest on
judgments made in the 19–21 August window, when the model behind the relay alias
is **not determinable** (`Q12`, `D-028`). `EXP-2026-08-021` repaired part of this
by re-grading the two blind banks five times under the now-identified
`qwen38-27B-v2`. Two gaps remain, and this experiment closes both:

1. **Everything so far is one family.** Those answers have survived a change of
   grading *session*, never a change of *model family*.
2. **C-021's contrast was never re-graded at all.** Its catalogue-versus-blind
   figure comes from `composerfix-dev` (120 answers) and `composerfix-holdout`
   (30 answers), and each of those 150 answers carries **exactly one** judgment
   sidecar, written by the unidentified model. `EXP-2026-08-021` did not touch
   them.

So: **does the ordering, and does C-021's gap, survive when the grader family
changes and both graders are named?**

## Hypothesis

**H1** — Zero arm-ordering reversals on `bank20260819` and `bank20260820` under
`gemma4-31B-mtp`, matching the zero found across five qwen sessions.

**H2** — C-021's catalogue-minus-blind gap stays **positive and above 0.02**
under both named graders. The recorded value is **0.0483**; a family change is
expected to move the level, not the sign.

**H3** — C-022's federated-minus-merged margin remains **indistinguishable from
zero** once the ±0.06 question-sampling component at n=30 is applied. The
order-corrected qwen value is −0.0587 / −0.0520. A null that survives a family
change is a stronger null.

**H4** — The between-family offset is **larger than the within-family spread by
at least an order of magnitude** (within-family sd was 0.0036–0.0249), and
**larger than the ≈0.01 grading-position effect**. Levels are not quotable; this
experiment does not try to make them quotable.

**H5** — Disagreement is concentrated on the weak arm (`llm_query`), because a
grader has little room to disagree about an answer everything scores near 1.0.
This replicates `EXP-2026-08-021`'s H4 under a second family.

## Setup

**Nothing is re-run.** No pipeline executes, no query is built, no graph store is
read. The answers on disk are byte-identical to the ones the August figures were
computed over, so a difference between passes is attributable to the grader and
to nothing else. This is the whole reason the experiment is cheap and the whole
reason it is interpretable.

Two endpoints, deliberately on separate GPUs so neither pass starves the other:

| role | endpoint | alias | served model | workers |
|---|---|---|---|---|
| second family | `http://localhost:9090/v1` | `default-model-2` | `gemma4-31B-mtp` | 24 |
| same family, named | `http://localhost:9090/v1` | `default-model` | `qwen38-27B-v2` | 16 |

The served model is read from the response envelope by
`scripts/model_identity.py` and recorded in the manifest as
`relay/<served-model>@2026-09-05`. **The alias is never taken as evidence** — it
has served three different models (`D-028`).

`--max-tokens 32768` on **both** graders. `EXP-2026-08-021` found 7–8% of the
largest answers fail to parse at smaller budgets, and the failures land on the
thorough answers, so a cheaper second pass would confound grader with budget.

Every cell is graded **twice with its position swapped** (`--position 1` / `2`).
The grading-position effect is ≈0.01 (`EXP-2026-08-022`), and in the original
C-022 passes `merged` was graded before `federated` every time — worth ≈0.005
against federation. Counterbalancing removes it rather than arguing about it.

## Data

510 saved answers, none regenerated:

| set | arms | n | prior grading |
|---|---|---:|---|
| `composerfix-dev` | `deterministic` | 120 | **1 pass, unidentified model** |
| `composerfix-holdout` | `deterministic` | 30 | **1 pass, unidentified model** |
| `bank20260819` | all 6 | 180 | 1 unidentified + 5 qwen sessions |
| `bank20260820` | all 6 | 180 | 1 unidentified + 5 qwen sessions |

The 150 `composerfix` answers get a **qwen pass as well as a gemma pass**, because
comparing an unidentified model against gemma would change two things at once.
Both graders named, one variable.

**Selection bias**: none introduced here — the sets are exactly the ones the
claims were computed over, taken whole. The sets themselves carry the biases
already recorded against them (`bank20260819`/`20260820` are 30-question blind
banks; ±0.06 question-sampling at n=30 dominates every margin below 0.06).

**Sidecar hazard.** Twelve judgment suffixes already sit beside the August
answers (`.judgment.json`, `.qwen38`, `.qwen38r2`–`r5`, `.cross`, `.c015`,
`.bld1`–`3`, `.bldrev`). The 2026-09-01 contamination finding was exactly this:
sidecars beside inputs get re-consumed. New suffixes are `.g31`/`.g31p2`
(gemma) and `.q38b`/`.q38bp2` (qwen on composerfix), and the input count is
**asserted to equal the answer count** before each cell is graded.

## Metrics

- **`arm_order_reversals`** — over each bank, rank the arms by mean correctness
  under grader A and under grader B; count pairs whose relative order differs.
  Population: 6 arms × 2 banks. **Success = 0.** This is the claim-bearing
  metric; everything else is context.
- **`contrast_sign_flips`** — for each named contrast (C-012
  `deterministic − llm_query`; C-022 `generic_composed − merged`; C-021
  `catalogue − blind`), does the sign differ between graders? **Success = 0.**
- **`c021_gap`** — mean correctness on `composerfix-dev` (120) minus mean on
  `composerfix-holdout` (30), per grader. Unpaired by construction: they are
  different questions, which is the point of the claim.
- **`c022_margin_bank19` / `_bank20`** — `generic_composed − merged`, paired on
  case id.
- **`between_family_offset`** — mean absolute per-case difference, paired,
  reported beside `EXP-2026-08-021`'s within-family sd. **These are different
  quantities and are never added or compared as if interchangeable.**
- **`grading_failures`** — count, and *which* cases. A pass that drops its
  hardest answers reads high; an earlier `.cross` pass failed on exactly the
  three lowest-scoring `llm_query` answers and read 0.24 higher for it. Dropped
  cases are excluded from paired statistics **and reported**.

## Baselines

The five `qwen38-27B-v2` sessions from `EXP-2026-08-021` (suffixes `.qwen38`,
`.qwen38r2`–`r5`) for the two banks; a fresh named qwen pass for `composerfix`.
The unidentified August pass is retained as a historical reference and is
**never used as a baseline**, because an unnamed grader cannot anchor a
comparison — that is the defect this experiment exists to remove.

## Procedure

Priority order. An early cutoff must still close C-021 and C-022.

```bash
# 0. Identify what is actually being served. Never trust the alias.
uv run python scripts/model_identity.py --date 2026-09-05 --json

# 1. C-021 — never re-graded by anything named. Highest exposure.
#    gemma on :9090/default-model-2, qwen on :9090/default-model, concurrently.
uv run python scripts/cross_family_regrade.py --phase c021

# 2. C-022 — generic_composed vs merged, both banks.
uv run python scripts/cross_family_regrade.py --phase c022

# 3. C-012's August support — deterministic vs llm_query, both banks.
uv run python scripts/cross_family_regrade.py --phase c012

# 4. The remainder — generic, gold_loop_llm. Closes C-001/C-014/C-017 exposure.
uv run python scripts/cross_family_regrade.py --phase rest

# 5. Roll up, paired on case id, dropout reported.
uv run python scripts/grader_sensitivity.py --root ... \
    --reference-suffix .qwen38 --candidate-suffix .g31 --arms ...
```

## What would falsify this

**H1 fails** if any arm-ordering reversal appears on either bank. That would mean
no judged comparison in this record survives a change of grader family, and it
would be the most consequential finding of the month. **It is also the stop
condition**: the sealed 288-question holdout does not get spent until a reversal
is understood.

**H2 fails** if C-021's gap goes negative, or falls below 0.02, under either
named grader — i.e. the blind bank scores at or above the catalogue. C-021 would
then be unsupported at the level it is currently quoted, and the paper's
methodological headline would have to be withdrawn or restated as a null.

**H3 fails** if C-022's margin exceeds 0.06 in magnitude *and* holds its sign
under both families. That would make federation-versus-merging a measurable
difference rather than a null, which is a **better** result than the one on
record and would need the claim rewritten upward rather than defended.

**H4 fails** if the between-family offset is comparable to the within-family
spread. That would be surprising and would mean grader choice matters less than
this project has assumed — in which case `EXP-2026-08-021`'s central caution is
too strong and should be relaxed in writing.

A pass that cannot be completed inside the 16:00 window is recorded `not_run`
with its phase named. **A partially graded cell is not a result** and is not
rolled up.
