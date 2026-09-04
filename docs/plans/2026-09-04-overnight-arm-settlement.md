# Overnight — settle the query-writing arm, and re-grade with a second model

*Written 2026-09-04 for an unattended run of roughly seven hours. It deliberately
does **not** spend the 288-question holdout; the reasoning is in §2.*

---

## 1. Introduction

Two of the nine items on the publication path are blocked on measurements that
need an idle relay and several unattended hours, which is exactly what tonight
is. The first is the query-writing arm: its 0.3712 is a token-budget artifact,
the budget defect is fixed but its cost was never measured, and C-012's support
therefore still rests on a single 30-question run from August. The second is
grader provenance: three of the paper's four legs were marked by a local model
in a window when nobody can say which model was behind the alias.

Neither needs new code. Both are re-runs of existing harnesses against the
repaired system, and both change exactly one variable. The run is ordered by
value rather than by dependency, so an interruption leaves the most important
questions answered, and each phase writes its state so a crash costs one phase
rather than the night.

---

## 2. Gaps & Unanswered Questions

- **Why not spend the holdout tonight?** It is the obvious candidate and it is
  the wrong call. The holdout answers *C-023* — does the generic-over-template
  gap generalise — and it can be spent exactly once. Spending it tonight buys a
  two-arm number, and `llm_query` is the arm that is not yet settled. Settle it
  first and one later night buys a **three-arm** holdout; spend it now and that
  number can never exist. *Decision: the holdout is not touched, and the run
  asserts as much by hash.*
- **What budget should the fair re-run use?** Unknown, which is why Phase B
  measures it before Phase C consumes it. *Assumption*: the smallest budget at
  which a real query comes back, not the largest that fits — a re-run at 32768
  that nobody can afford to repeat is not a baseline either.
- **Is a second local model a real cross-model check?** Partly. The audit asks
  for a provider-hosted Sonnet panel and `.env` carries no provider key, so that
  cannot run unattended here. The relay does serve `gemma-4-26B-it`, a different
  family from `qwen38-27B-v2`. *Assumption*: a different-family local grader is
  worth having and is **not** a substitute for the Sonnet panel; the artifact
  must say which it is.
- **How much of the paper's grading does this cover?** Tonight re-grades the
  *post-repair* answers, which are the ones that will be quoted. The August
  answers behind C-012, C-021 and C-022 are a separate export and are out of
  scope here. *Human intervention is needed* on whether the August figures are
  re-graded at all or simply superseded.
- **What if Phase C overruns?** *Assumption*: cap it. A partial arm is not a
  measurement, so an overrun is recorded as "not run" and Phase E still gets its
  hours, rather than the night ending with two half-answers.

---

## 3. Hierarchical Step-by-Step Instructions

**Order is by value, not dependency.** Phase B is cheap and unblocks a decision;
Phase E is certain-value and independent; Phase C is the expensive one and is
capped so it cannot eat the others.

#### Step 1: Preflight — establish what is being measured before measuring it

- **Locations**: `scripts/model_identity.py`, `utils/research_record/hashing`,
  `docs/evaluation/composition/bank/bank.json`; new state file
  `docs/evaluation/composition/bank/overnight-2026-09-04-state.json`.
- **Rationale**: the alias `skynet` has served three models, so a judged figure
  without a probe is dated evidence about an unknown instrument. Probe both
  aliases, hash the bank, assert both stores are reachable and hold their
  expected counts (attack 4,369/27,669; capec 6,374/8,582), and assert the
  holdout is untouched. Refuse to start if any check fails, because every later
  number inherits them.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Arm Settlement (1/6) Complete:
  preflight recorded both grader identities, both store counts and the holdout
  seal.*

#### Step 2: Phase B — what an honest query-writing arm costs

- **Locations**: `scripts/builder_budget_probe.py`, output
  `docs/evaluation/composition/bank/budget-cost.json`.
- **Rationale**: the decision to re-run or cut this arm has never had cost
  evidence, and the one attempt was abandoned because it shared a relay with a
  judging run. Four real failing cases at 8192 / 16384 / 32768 with a 900 s
  ceiling, recording wall-clock, completion tokens and relay timeout rate.
  Nothing else may touch the relay while this runs. The output selects Phase C's
  budget: **the smallest at which a real query returns**, and if none does
  inside the ceiling, Phase C does not run and that is the finding.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Arm Settlement (2/6) Complete: the
  per-budget cost of the query-writing arm is measured on an idle relay.*

#### Step 3: Phase E — re-grade the post-repair answers with a second model family

- **Locations**: `utils.evaluation.judge_answers` with `EVAL_LLM_MODEL=local`
  (`gemma-4-26B-it`), over
  `docs/evaluation/experiments/post-repair-2026-09-03/{deterministic,generic}`;
  suffix `.gemma` so the existing judgments are untouched.
- **Rationale**: run **before** the expensive phase because its value is certain
  and its cost is known — 568 answers at the measured 9.1 s/answer is about 1.5
  hours. It changes exactly one variable against figures already in the record,
  using the same prompt byte for byte. If the arm ordering survives a change of
  grader *family*, the 0.1623 gap stops being a property of one model. If it
  does not, that is the more important finding and it arrives before the paper
  is written rather than after review.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Arm Settlement (3/6) Complete: the
  post-repair arms re-graded by a second model family.*

#### Step 4: Phase C — the fair re-run of the query-writing arm

- **Locations**: `utils.evaluation.experiment_untruncated --arm llm_query
  --bank docs/evaluation/composition/bank/bank-dev.json --llm-max-tokens <from
  Phase B> --workers 8`, into
  `docs/evaluation/experiments/llm-query-fair-2026-09-04`.
- **Rationale**: C-012's support is one 30-question run, and the only larger
  measurement is confounded by the budget defect fixed in `a1e20f6`. This is the
  re-measurement the claim has been waiting for, on 284 questions, with the plan
  held constant so query generation is the only variable. **Hard cap of 3 hours**
  — a partially answered arm is not a measurement, and an overrun is recorded as
  not-run so Phase F still has time.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Arm Settlement (4/6) Complete: the
  query-writing arm re-run at a budget that lets it answer.*

#### Step 5: Phase D — judge the re-run arm against the other two

- **Locations**: `judge_answers` at positions 1 and 2 over the Phase C answers,
  grader `skynet`, `max_tokens=32768`, 16 workers.
- **Rationale**: two counterbalanced passes so the ~0.01 order effect is
  subtractable, and the same grader as the post-repair arms so the three-way
  comparison is like-for-like. Skipped outright if Phase C did not complete;
  half an arm graded is worse than none, because it looks like a number.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Arm Settlement (5/6) Complete: the
  re-run arm judged under the same protocol as the other two.*

#### Step 6: Phase F — roll up, record, and say what did not run

- **Locations**: `make new-experiment`, `scripts/score_bank.py`, a rendered
  morning summary; `docs/research/CLAIMS.md` C-012.
- **Rationale**: every number cites an `EXP-` id or it does not exist. The
  record must state which phases ran, which were capped, and that the holdout is
  still sealed — the previous overnight run's own plan made "what did not run" a
  mandatory section for exactly this reason. C-012 is amended only if Phase C
  and D both completed.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Overnight Arm Settlement (6/6) Complete:
  results recorded, with the phases that did not run named.*

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Orchestrator | Six phases, value-ordered, resumable from a state file, hard per-phase caps. | `scripts/overnight_arm_settlement.py` |
| Orchestrator tests | Dry-run lists phases in order; a phase marked done is skipped on restart; a capped phase records `not_run` rather than a partial figure. | `scripts/tests/test_overnight_arm_settlement.py` |
| Preflight record | Both grader identities, both store counts, bank hash, holdout seal. | `docs/evaluation/composition/bank/overnight-2026-09-04-state.json` |
| Budget cost table | Wall-clock, completion tokens, timeout rate at three budgets. | `docs/evaluation/composition/bank/budget-cost.json` |
| Second-family judgments | 568 `.gemma` judgments beside the existing ones, untouched. | `docs/evaluation/experiments/post-repair-2026-09-03/*/answers/` |
| Fair re-run answers | 284 `llm_query` answers at an adequate budget. | `docs/evaluation/experiments/llm-query-fair-2026-09-04/` |
| Three-arm rollup | Judged correctness per arm with denominators and per-pass means. | `docs/evaluation/composition/bank/three-arm-judged.json` |
| Experiment record | Manifest, results, issues, hashed pointers; names every phase that did not run. | `docs/research/experiments/` |
| Morning summary | Jargon-free, rendered from artifacts on disk, with a mandatory "what did not run" section. | `docs/reports/2026-09-04-overnight-report.md` |
