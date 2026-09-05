# Close Step 4, then spend the holdout

*2026-09-05. Operator directive: the EACL demo track is abandoned — this is a
full conference paper, so the 22 September date no longer constrains anything.
Two pieces of measurement remain before the record is closed for writing:
finish the cross-model re-grade (Step 4), then spend the sealed holdout
(Step 7). Nothing else is to be run.*

## 1. Introduction

The publication table lists Step 4 as "re-grade the August comparisons
cross-model, 1–2 days". **That estimate is stale, and in our favour.** Most of
it was already done on 2026-08-31 by
[`EXP-2026-08-021`](../research/experiments/EXP-2026-08-021-grader-model-sensitivity/):
the 360 saved August answers were re-graded **five times** by the now-identified
`qwen38-27B-v2`, giving **zero arm-ordering reversals across 5 sessions × 12
cells** and zero contrast sign flips. C-012's own headline has since been
replaced outright by
[`EXP-2026-09-005`](../research/experiments/EXP-2026-09-005-post-repair-arm-comparison/)
at n=284 with a named grader and two counterbalanced passes.

So one thing is left of Step 4, and it is narrow:

> **The August answers behind C-021 and C-022 have never been graded by a model
> from a different family.** Everything they have survived is a change of
> *session*, not a change of *family*.

That is worth closing because C-021 (co-authorship bias, the paper's most
quotable methodological result) and C-022 (federation-versus-merge) are the two
claims a reviewer is most likely to attack on grader grounds, and because the
post-repair arms already carry a cross-family check that these do not. Closing
it makes one sentence true of the whole record rather than half of it.

Then the holdout. It is the last unspent measurement in the project and the
only one that can say the result generalises rather than merely replicates.

## 2. Gaps & Unanswered Questions

- **The second family is not the one we used last night.** `gemma4-31B-mtp` is
  **gone**: `:9091` is down, and `:9090`'s `default-model-2` and
  `default-model-3` both report `failed` and are pinned to `qwen38-27B-v2`
  anyway. Probed 2026-09-05. What *is* healthy is `:4000`'s `local` →
  **`gemma-4-26B-it`**, a genuinely different family from qwen.
  *Assumption*: **grade with `gemma-4-26B-it` and say so.** This is not a
  weakness to hide — it means the record ends up checked under **two**
  independent non-qwen families rather than one, and the property under test is
  *ordering survives a family change*, which does not require the same family
  twice. If the operator would rather have `gemma4-31B-mtp` back for exact
  parity with `EXP-2026-09-005`, that is a one-line change to the endpoint and
  a reason to wait; **it is not a reason to skip the pass.**
- **Sidecar contamination.** Twelve judgment suffixes already sit beside those
  answers (`.judgment.json`, `.qwen38`, `.qwen38r2`–`r5`, `.cross`, `.c015`,
  `.bld1`–`3`, `.bldrev`). A judging pass that globs the answer directory will
  re-consume them. *Assumption*: **exclude every `*.judgment*.json` explicitly**,
  and assert the input count is exactly 30 per arm before grading.
- **Order effect.** ≈0.01, measured (`EXP-2026-08-022`), and `merged` was graded
  before `federated` in every original pass — worth ≈0.005 *against* federation.
  *Assumption*: **two counterbalanced passes per arm**, as in `EXP-2026-09-005`.
- **What could this pass actually change?** Honestly: very little, and that is
  the point. *Prediction, recorded before running*: **zero ordering reversals on
  both banks; C-021's gap stays positive and above 0.02; C-022 stays
  indistinguishable from zero once ±0.06 question-sampling is applied.** A
  prediction that survives is a closed exposure. A prediction that fails is the
  most important thing we would have learned all month.
- **Is C-022 even worth re-grading?** Its reported figures are already marked
  superseded, and its conclusion is a *null*. *Assumption*: **yes, include it** —
  it costs nothing extra (the same 360 answers cover both claims) and a null
  that survives a family change is a much stronger null.
- **Holdout: two arms or three?** Three costs roughly five extra GPU-hours,
  because `llm_query` is the only slow arm. *Assumption*: **all three.** The
  holdout is spent exactly once; a two-arm holdout would leave the paper's
  headline three-way comparison unconfirmed on unseen questions, which is
  precisely the thing the holdout exists to confirm.
- **Which `llm_query` configuration?** The 512-token thinking cap is wired but
  **unverified against a live endpoint**, and the operator has called a halt to
  experiments. *Assumption*: **run the settled configuration** — budget 32,768,
  cutoff 4,096 s, no thinking cap — the one that produced 0.3781. The holdout
  must test the configuration the paper describes, not a newer untested one.
  The thinking cap stays on the shelf, unrun and recorded as unrun.
- **Does the holdout still have to be re-hashed?** It has been *answered* once
  (deterministic, 2026-09-02, model-free, published as `holdout 0.4683`) and
  **never judged**. Judging is the property being spent. *Assumption*: assert by
  hash that the 288 questions are byte-identical to their preflight value, and
  assert that **no `*.judgment*.json` exists for any holdout case id**, before a
  single answer is written.

## 3. Steps

### Part A — finish Step 4

#### Step A1: Scaffold and pre-register — 20 min
- **Locations**: `make new-experiment SLUG=cross-family-august-regrade`;
  `PROTOCOL.md` in the new folder.
- **Rationale**: house rule — the prediction in §2 goes on disk *before* a
  candidate judgment exists, or the pass measures our expectations. Record the
  served model from `scripts/model_identity.py`, never the alias (D-028).
- **Action**: validate, then commit: *Step 4 (1/4): pre-register the
  cross-family re-grade of the August answers.*

#### Step A2: Grade 360 answers under the second family — ~1.5–2.5 h
- **Locations**: `utils.evaluation.judge_answers --root
  docs/evaluation/experiments/bank2026081{9,20} --arm <arm>`, six arms per bank,
  suffixes `.g26` and `.g26p2` with grading position swapped;
  `EVAL_LLM_BASE_URL=http://localhost:4000/v1`, `EVAL_LLM_MODEL=local`,
  `--judge-max-tokens 32768` (the same budget as every other pass — a cheaper
  one would confound grader with budget, `EXP-2026-08-021`).
- **Rationale**: one variable changes. No pipeline runs, no answers are
  regenerated, the stores are not touched. 720 judgments.
- **Action**: validate, then commit: *Step 4 (2/4): 720 cross-family judgments
  over the frozen August answers.*

#### Step A3: Roll up, and adjudicate against the prediction — 30 min
- **Locations**: extend `scripts/grader_sensitivity.py` (it already computes
  ordering reversals and contrast sign flips); write `RESULTS.md`,
  `manifest.yaml`, `ISSUES.md`.
- **Rationale**: the reportable quantities are **arm-ordering reversals**,
  **contrast sign flips**, **C-021's catalogue-minus-blind gap**, and **C-022's
  federated-minus-merged margin** — each with the between-family offset stated
  beside the within-family spread, because those are different quantities and
  conflating them is how the last grader confusion started.
- **Action**: validate, then commit: *Step 4 (3/4): the August ordering
  survives / does not survive a change of grader family.*

#### Step A4: Update the ledgers — 30 min
- **Locations**: `docs/research/CLAIMS.md` (the model-provenance table, C-021,
  C-022), `DECISIONS.md`, `OPEN_QUESTIONS.md` (Q12 closes if the prediction
  holds); `make validate-research`.
- **Rationale**: the provenance table currently says these three claims are
  graded "by a model nobody can name". After A3 that sentence must either be
  struck or narrowed, and one of those is a materially different paper.
- **Action**: validate, then commit: *Step 4 (4/4): close the grader-provenance
  exposure on C-021 and C-022.*

**Exit condition for Step 4**: every judged claim in `CLAIMS.md` names its
grader model and has been checked under at least one other family. If a
reversal appears, **stop** — that is a finding, it goes in the paper, and the
holdout waits until we understand it.

### Part B — spend the holdout

#### Step B1: Seal check and pre-registration — 45 min
- **Locations**: reuse the assertions already written in
  `scripts/overnight_two_track.py:278–318`; write
  `docs/evaluation/composition/bank/bank-holdout.json` (288 questions, the
  complement of `bank-dev.json`); `make new-experiment SLUG=holdout-spend`.
- **Rationale**: the holdout is spent once and cannot be un-spent. Before any
  answer is written: hash the 288 questions against their preflight value,
  assert **zero** existing judgments on any holdout case id, and write down the
  three expected numbers and the decision rule **in advance**. *Prediction*:
  the ordering holds — generic > deterministic > llm_query — and every level
  sits **below** its dev counterpart, because the dev half is where six defects
  were found and fixed.
- **Action**: validate, then commit: *Holdout (1/4): sealed, hashed and
  pre-registered.*

#### Step B2: Three arms answer the 288 — ~5–6 h, one overnight
- **Locations**: `utils.evaluation.experiment_untruncated` into
  `docs/evaluation/experiments/holdout-spend-2026-09-XX/{deterministic,generic,llm_query}`.
  The two model-free arms finish in minutes; `llm_query` needs the healthy GPU
  at 16 concurrency, budget 32,768, `SPECIALIST_LLM_TIMEOUT_S=4096`.
- **Rationale**: same code, same stores, same configuration as the dev
  measurement — otherwise the holdout tests a different system than the one the
  paper describes. If a second GPU comes back, split by `d_tier` as in
  `scripts/split_llm_query_run.py` and halve the wall clock.
- **Action**: validate, then commit: *Holdout (2/4): 864 answers over the
  unseen 288.*

#### Step B3: Judge, both graders, counterbalanced — ~4–6 h
- **Locations**: two passes per arm per grader; qwen on `:4000`/`:9090`, the
  second family on `:4000`'s `local`. 3,456 judgments.
- **Rationale**: the holdout is the one number that will be quoted hardest, so
  it gets the strongest instrument the project has rather than the cheapest.
- **Action**: validate, then commit: *Holdout (3/4): judged under two families.*

#### Step B4: Report against the pre-registration — 1 h
- **Locations**: new experiment folder; `CLAIMS.md`; a paired bootstrap via
  `utils/evaluation/stats.py::bootstrap_ci` (2,000 resamples, seed 1729);
  model-free recall reported beside judged correctness and never merged with it.
- **Rationale**: the pre-registered prediction is compared to the outcome
  **in writing, including where it was wrong** — this project has twice
  predicted 47 and 23 and delivered 2 and 14, and saying so is what makes the
  rest of the record credible.
- **Action**: validate, then commit: *Holdout (4/4): the held-back 288, spent.*

**Exit condition for Step 7**: three arms, 288 unseen questions, two grader
families, intervals, and a written comparison against a prediction made before
the run. After this the measurement phase is closed and **nothing further is
run before the paper is drafted.**

## 4. What this plan deliberately does not do

- **No thinking-cap experiment.** Wired, unverified, and staying that way. It is
  recorded as an untested lever, not a result.
- **No fix to the two known scoring faults** (abstention boilerplate crediting
  refusals; the scorer recognising the source's id vocabulary rather than the
  graph's, worth 0.185 on the subset measured). Both would *raise* our numbers,
  both need pre-registration, and changing the scorer between the dev
  measurement and the holdout would destroy the comparison this plan exists to
  make. They stay on their task chips as declared limitations.
- **No Step 5.** The gold-query resource targets query correctness, and
  retrieval is no longer the binding constraint — it moved +0.0684 while the
  judged score moved +0.0012. Recommend dropping it from the paper plan.
- **No new banks, no new questions, no rebuilds.**

## 5. Risks

| risk | mitigation |
|---|---|
| `gemma-4-26B-it` grades too differently to be informative | The test is *ordering*, not level. A large offset with stable ordering is the expected outcome and is reportable as such. |
| The second family disagrees and an ordering flips | **That is a result, not a failure.** Part B stops; the flip is investigated and written up. |
| The holdout is found already contaminated | B1 aborts before any answer is written. Cheap to discover, catastrophic to discover late. |
| One GPU only, so `llm_query` takes the whole night | Accept it. B2 is resumable per-arm, and the two model-free arms complete regardless. |
| Sidecar re-consumption inflates a figure | Explicit exclusion plus an asserted input count of exactly 30 per arm, per the 2026-09-01 contamination finding. |
