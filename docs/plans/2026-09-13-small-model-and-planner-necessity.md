# Does the Generic tier need a big model, and does it need a planner?

**Date:** 2026-09-13 · **Endpoint under test:** `http://localhost:4000/v1`, alias
`local`, intended to serve **MiniCPM5-2B Q8** on llama.cpp · **Reference
endpoint:** `http://localhost:9090/v1` / `default-model` (`qwen38-27B-v2`) ·
**Git:** commit at every step, never push.

---

## 1. Introduction

Two questions have been sitting underneath every figure this programme has
produced, and neither is answered by any run on record. The first: the Generic
tier scores 0.9255 with a 27-billion-parameter model and 0.9205 without one, so
the model is worth 0.005 — can a 2B model hold that, and could the whole thing
run on a laptop? The second is sharper and cheaper to answer: **every headline
arm replays an authored plan.** `generic` and `generic_composed` are both driven
by `run_gold_loop_llm` / `run_deterministic`, which hand the pipeline a
decomposition rather than asking it to produce one. So 0.92 is the ceiling for
retrieval and composition *given a correct plan*, and nobody has measured what
happens when the planner actually runs.

The plan answers the second question first, because it is model-free, costs
seconds, and changes how the first question should be read. Then it works up the
model seams one at a time — narration before query drafting — because the
evidence says those two seams behave very differently, and a 2B model will fail
at one long before the other. Concurrency is established before any of it, since
llama.cpp on a workstation is the constraint that decides whether the rest is
even runnable.

Every step starts with a slice measured in single-digit questions and only then
widens. Nothing here judges anything on the holdout or the sealed fresh set.

---

## 2. Gaps & Unanswered Questions

- **The model is not loaded yet.** `local` on `:4000` currently answers
  `gemma-4-26B-it`, not MiniCPM5-2B. *Human intervention is needed*: the
  operator swaps the model when ready. Every step below begins by asserting the
  served model id, because this repository has been bitten three times by an
  alias that silently changed underneath it (`scripts/model_identity.py` exists
  for precisely this, and `D-028` / `Q12` record the incidents). A step that
  cannot confirm `minicpm` in the served id stops rather than producing a figure
  attributed to the wrong weights.
- **Safe concurrency is unknown.** llama.cpp serves a fixed number of slots and
  queues beyond them; over-subscribing costs latency and, on a shared desktop,
  responsiveness. *Assumption*: start at one and climb only while the knee has
  not been passed — Step 1 measures it rather than guessing, and the resulting
  number is what every later step uses.
- **Whether a 2B model emits usable JSON for the specialist seam.** The seam
  asks for a structured query draft. *Assumption*: it will be unreliable, and
  Step 4 is designed to measure the rejection rate rather than assume either
  way. The comparable figure to beat is the 27B model's, which is already poor:
  `llm_query` scored 0.4039 on the holdout against `generic`'s 0.2507 higher.
- **Context length and reasoning budget.** MiniCPM is not a reasoning model, so
  the ≥2048-token floor that `skynet` needs may not apply, and its context is
  likely far below 84,000. *Assumption*: probe both in Step 1 and pin them into
  the run env, rather than inheriting budgets tuned for a 27B reasoning model.
- **The operator directive.** The standing instruction has been `:9090` /
  `default-model` only. This plan uses `:4000` / `local` **because the operator
  asked for it on 2026-09-13**; `:9090` remains the reference arm so every
  comparison has a known-good side.
- **What "the planner is needed" would even mean.** *Assumption*: it is a
  measured difference, not a judgement — `generic_planned` minus
  `generic_composed` on the same 284 questions, paired per question, with the
  plan as the only variable. A difference inside the grader's own spread means
  the authored plan is not carrying the result.

---

## 3. Hierarchical Step-by-Step Instructions

### Step 1 — What the box can take, and what is actually in it

- **Locations:** new `scripts/local_endpoint_probe.py`; `scripts/model_identity.py`
  (reused, `resolve()` against `:4000`); `utils/config.py` for the per-stage
  variable names it writes out (`SPECIALIST_LLM_BASE_URL`,
  `SYNTHESIS_LLM_BASE_URL`, `*_LLM_MODEL`, `*_LLM_MAX_TOKENS`,
  `*_LLM_TIMEOUT_S`); output `docs/research/experiments/EXP-2026-09-019-small-model-generic/data/endpoint.json`.
- **What it does:** three things, in order, and it refuses to continue past any
  of them. (a) Resolve `local` and assert `minicpm` appears in the served id —
  the alias currently answers `gemma-4-26B-it`, so this is a real gate and not a
  formality. (b) Find the context ceiling by bisecting `max_tokens` on a trivial
  prompt until the server refuses, and record the error body verbatim; the
  judge's 400s on `:9090` were misdiagnosed twice because nobody read one. (c)
  Walk concurrency 1 → 2 → 4 → 8 → 12 with a fixed short prompt, ten calls per
  rung, recording tokens/second, p50 and p95 latency, and any error.
- **Rationale:** every later step's cost, timeout and worker count is a function
  of these three numbers, and guessing them on llama.cpp is how a workstation
  becomes unusable for an afternoon. The knee — the rung where tokens/second
  stops rising while p95 climbs — is the concurrency every subsequent step uses.
- **Small test first:** the rung-1 pass alone, ten calls, before any higher rung
  runs. If p50 at one concurrent call is above 20 s, the model is too slow for
  the full bank and the plan says so at a cost of ten calls rather than a night.
- **Guard rails:** a hard stop if any rung's p95 exceeds 4× the rung-1 p50, if
  system load average passes the core count, or if any call errors. The probe
  never climbs past a rung that failed.
- **Validation:** `endpoint.json` records the served model id, the context
  ceiling with the server's own refusal text, and a per-rung table; the chosen
  concurrency is written once and read by every later step rather than retyped.
- **Action:** Undergo the verification/tests/validation process for this phase.
  Once validated, commit (do not push) stating: Small-model Generic (1/5)
  Complete: the local endpoint's identity, context ceiling and safe concurrency
  are measured and pinned.

### Step 2 — Does the planner need to run? (model-free, minutes, no small model)

- **Locations:** `utils/evaluation/experiment_untruncated.py` — the `ARMS`
  tuple (line ~45), `untruncated_env` (line ~86) and the runner map (line ~726);
  the new arm reuses `run_rewrite`, which drives the **real** pipeline with the
  planner in it, rather than `run_deterministic`, which replays the authored
  plan and is why this has never been measured. New arm: **`generic_planned`** —
  real planner, `SPECIALIST_GENERIC_ONLY=true`, every LLM seam off.
- **What it measures:** `generic_planned` against `generic_composed` on the same
  284 development questions. The two differ in exactly one thing: where the plan
  comes from. Scored with `scripts/paired_control_score.py`, which pairs per
  question and already reproduces the committed Step 6 figures.
- **Rationale:** this is the cheapest experiment in the programme and the one
  that decides how every other number is read. Both arms are model-free, so a
  full pass is seconds of wall clock, and the result either confirms that 0.92
  survives a real decomposition or reveals that the authored plan has been doing
  the work all along. Nothing else should be built on 0.92 until it is known.
- **Small test first:** the eight-question `--only` slice `scripts/repair_control_run.py`
  already defines (two per hard tier, one per easy), generated on both arms and
  diffed on claims. If `generic_planned` returns zero records where
  `generic_composed` returned some, the planner is the bottleneck and that is
  visible at a cost of sixteen answers.
- **Validation:** both arms `ok == count`; the paired difference per tier
  recorded whichever way it falls; `scripts/mechanism_check.py` contradiction
  count 0 on the new arm; gold-text recall reported for both. A judged pass only
  if the model-free difference exceeds 0.02, since below that the grader cannot
  resolve it and nine hours of judging would buy noise.
- **Action:** Undergo the verification/tests/validation process for this phase.
  Once validated, commit (do not push) stating: Small-model Generic (2/5)
  Complete: the planner runs for real and its cost against the authored plan is
  measured.

### Step 3 — The narrator on 2B (the safe seam)

- **Locations:** `utils/evaluation/experiment_untruncated.py` — new arm
  **`generic_local_narrator`**: `SYNTHESIS_LLM_ENABLED=true` pointed at
  `:4000` / `local`, `SPECIALIST_LLM_ENABLED=false`, generic primitives on,
  budgets from Step 1; `utils/synthesis/factory.py` (the fallback path that
  records `fallback_reason` when the narrator fails — the health signal this
  step reads); `utils/synthesis/verifier.py` unchanged and unconditional.
- **Rationale:** the narrator is where a small model is least dangerous and most
  useful. The composer is always deterministic, every claim carries citations,
  and the verifier grounds each asserted identifier, so a weak narrator produces
  worse prose rather than worse facts — and when it fails outright the system
  already falls back to composed text and records why. Measured on the shipped
  27B model today, the narrator changed only the wording in 235 of 284 answers.
- **Small test first:** eight questions, then forty, at the Step 1 concurrency.
  The gate is the fallback rate over ANSWERS (never over files — `EXP-2026-09-016`
  A-8), healthy at or below 0.14, and zero new unsupported verdicts from the
  verifier.
- **Validation:** full 284 at the pinned concurrency; fallback rate below 0.14;
  claims byte-identical to `generic_composed` (the narrator must not change
  them); wall-clock per answer recorded against the 27B arm's; a judged slice of
  the 40 hardest questions in one grading position.
- **Action:** Undergo the verification/tests/validation process for this phase.
  Once validated, commit (do not push) stating: Small-model Generic (3/5)
  Complete: the 2B narrator measured for fallback rate, faithfulness and latency.

### Step 4 — The specialist on 2B (the seam that can lose)

- **Locations:** new arm **`generic_local_full`** — as Step 3 plus
  `SPECIALIST_LLM_ENABLED=true` against the same endpoint;
  `utils/specialists/cypher/builder.py` and `utils/specialists/gremlin/builder.py`
  (the gate that rejects a malformed draft); the gate's rejection reasons in each
  result's `traces`, which is where the rejection rate is counted.
- **Rationale:** this is the seam with a measured downside. On today's control
  the 27B model rewrote the query on 49 of 284 questions, and at least one of
  those went backwards — `AN0662` was looked up by identifier by the model-free
  path and by *name search* by the model, which found nothing and abstained
  where the deterministic path answered fully. A 2B model is unlikely to do
  better at drafting a bounded Gremlin traversal, and `llm_query`'s 0.4039 on
  the holdout is the standing evidence for how expensive that seam can be.
- **Small test first:** the same eight questions, counting three things and
  nothing else — gate rejections naming `allowed_edge_patterns`, zero-record
  results, and queries that differ from the model-free arm's. If rejections
  exceed 25% of drafts, this seam is not viable at 2B and the step records that
  as its result rather than widening.
- **Validation:** full 284 only if the small slice clears the rejection gate;
  per-question comparison against `generic_composed` naming every question where
  the model's query retrieved *less*; the arm's figure reported beside its
  rejection rate, never alone.
- **Action:** Undergo the verification/tests/validation process for this phase.
  Once validated, commit (do not push) stating: Small-model Generic (4/5)
  Complete: the 2B specialist seam measured, with its rejection and regression
  rates beside its score.

### Step 5 — The two questions crossed, and the write-up

- **Locations:** a 2×2 over {authored plan, real planner} × {no model, 2B},
  reusing the arms from Steps 2–4 plus **`generic_planned_local`**;
  `scripts/paired_control_score.py` for the paired differences;
  `utils/specialists/evalset/latency.py` at one worker for single-user latency
  on each cell; the experiment folder scaffolded with
  `make new-experiment SLUG=small-model-generic`; `docs/research/CLAIMS.md` and
  `docs/research/OPEN_QUESTIONS.md` for the claim and the question this closes.
- **Rationale:** the two variables interact and the interesting cell is the one
  nobody has run — a real planner *and* a small model, which is what a laptop
  deployment actually is. Reporting the corners without the interaction would
  let a reader assume it is additive, and there is no reason to think it is: a
  weaker plan and a weaker query drafter fail on the same questions.
- **Small test first:** the eight-question slice through all four cells before
  any full pass, with the cost of the full 2×2 estimated from it and stated
  before it is spent.
- **Validation:** every cell `ok == count`; per-cell fallback and rejection
  rates; single-user latency per cell; the 2×2 written into `data/metrics.json`
  and the figures traced from it; `make validate-research`, `make index` and
  `make check-docs` green; `CURRENT.md` read before any number is quoted in
  prose.
- **Action:** Undergo the verification/tests/validation process for this phase.
  Once validated, commit (do not push) stating: Small-model Generic (5/5)
  Complete: plan source and model size crossed, measured, and recorded.

### Running it in order

Step 1 is a precondition for 3, 4 and 5 and takes minutes. **Step 2 needs no
small model at all** and should be run as soon as it is written — it is the
cheapest result in the programme and it reframes everything after it. Steps 3
and 4 are gated on the operator loading MiniCPM5-2B, and each refuses to widen
past its small slice unless that slice clears. Step 5 is the only expensive one
and it does not start until the four corners are known to be runnable.

The two human checkpoints are the model swap in Step 1 and the specialist
rejection gate in Step 4; both stop and report rather than proceeding.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Endpoint probe | Identity gate, context-ceiling bisect with the server's own refusal text, concurrency ladder with a knee and hard stops | `scripts/local_endpoint_probe.py` |
| Probe tests | Small-subset tests: the ladder stops at a failing rung, a wrong served id refuses, a refusal body is captured verbatim | `scripts/tests/test_local_endpoint_probe.py` |
| `generic_planned` arm | Real planner, generic primitives, no model — the arm that isolates the plan | `utils/evaluation/experiment_untruncated.py` |
| `generic_local_narrator` arm | 2B on the synthesis seam only, specialist off | `utils/evaluation/experiment_untruncated.py` |
| `generic_local_full` arm | 2B on both the specialist and synthesis seams | `utils/evaluation/experiment_untruncated.py` |
| Arm tests | Each new arm's env asserted seam by seam, so an arm cannot silently run model-free | `utils/evaluation/tests/test_experiment_arms.py` |
| Planner-cost result | `generic_planned` minus `generic_composed`, paired per question and per tier | `EXP-2026-09-019-small-model-generic/data/planner_cost.json` |
| Seam health | Fallback rate over answers, gate-rejection rate, and every question where the model's query retrieved less | `EXP-2026-09-019-small-model-generic/data/seam_health.json` |
| 2×2 result | Plan source crossed with model size, with single-user latency per cell | `EXP-2026-09-019-small-model-generic/data/metrics.json` |
| Experiment record | RESULTS, manifest, figures, and the claim this supports or refutes | `docs/research/experiments/EXP-2026-09-019-small-model-generic/` |
