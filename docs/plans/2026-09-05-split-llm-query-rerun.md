# Split the llm_query re-run across two GPUs

*2026-09-05. Operator directive: 16 concurrency on `default-model-2` and
`default-model-3`, both on `:9090`, each its own GPU. 32 slots total.*

## 1. Introduction

The 2026-09-04 run produced 284 answers of which 140 built a query; the other
144 returned empty content, which the gate correctly refused. Two candidate
causes look identical downstream — the 900 s clock, or the 8,192-token budget
that a single easy probe question was used to justify. This run removes both by
raising each well past anything measured, and halves the wall clock by splitting
the question set across two GPUs.

## 2. Gaps & Unanswered Questions

- **Clock or budget?** Not resolved by argument. Phase 1 records
  `finish_reason` and `completion_tokens` per call, so the artifacts answer it
  whichever way it goes.
- **Budget.** 8,192 was chosen from one easy question that needed 4,134 tokens;
  the same probe produced 10,493 when given room. *Assumption*: **32,768**, the
  largest the probe exercised.
- **Timeout.** *Assumption*: **2,700 s**, three times the previous ceiling.
  Generous on purpose — this run exists to stop being instrument-bound.
- **Split fairness.** A naive first-half/second-half split would put the hard
  tiers unevenly across GPUs. *Assumption*: **stratify by `d_tier`**, alternating
  within each tier, so both halves carry the same difficulty mix.
- **Does judging interfere?** The judging of the previous run is on `:4000`.
  *Assumption*: different endpoint, no contention — but Phase 1 checks rather
  than assumes.
- **What if one GPU dies mid-run?** *Assumption*: the halves are independent
  roots, so one surviving half is still 142 usable answers, and the merge takes
  whatever exists and records what is missing.

## 3. Steps

#### Step 1: Probe both aliases and split the bank — 10 min
- **Locations**: new `scripts/split_llm_query_run.py`; ids to
  `logs/2026-09-05/split-{a,b}.txt`.
- **Rationale**: record what each alias serves from the response envelope, not
  the name. Confirm both answer, then write a tier-stratified split so neither
  GPU gets the easy half. Ten probe calls at 16-way with
  `finish_reason`/`completion_tokens` recorded settle clock-versus-budget before
  three hours are spent on the assumption.
- **Action**: validate, then commit: *Split Re-run (1/4): both GPUs identified,
  bank split by tier, clock-vs-budget probed.*

#### Step 2: Two runs in parallel, one per GPU — ~1.5–3 h
- **Locations**: `utils.evaluation.experiment_untruncated --arm llm_query`,
  `--llm-model default-model-2` / `default-model-3`, `--workers 16`,
  `--llm-max-tokens 32768`, `SPECIALIST_LLM_BASE_URL=http://localhost:9090/v1`,
  `SPECIALIST_LLM_TIMEOUT_S=2700`, roots `llm-query-split-2026-09-05/{a,b}`.
- **Rationale**: independent processes and independent roots, so a failure on
  one GPU costs half the run and not all of it. Each is watched by its own PID —
  a name match killed a launcher yesterday and then reported it as running.
- **Action**: validate, then commit: *Split Re-run (2/4): 284 answers across two
  GPUs at 16 concurrency each.*

#### Step 3: Merge and gate — 5 min
- **Locations**: merge into `llm-query-split-2026-09-05/llm_query/answers/`.
- **Rationale**: report answers, queries built, and the empty-cause split from
  the recorded `finish_reason`. **Refuses to judge** if fewer than 284 answers,
  or if the built-query count has not clearly beaten 140 — a re-run that did not
  move the thing it was for is not judged into a number.
- **Action**: validate, then commit: *Split Re-run (3/4): merged, with the
  empty-query cause named from the artifacts.*

#### Step 4: Judge, roll up, report — ~1.5 h
- **Locations**: `judge_answers` positions 1 and 2 on `:4000`/`skynet`, 16
  workers, 32,768 — the same instrument as the other two arms. Report + PDF.
- **Rationale**: a three-way comparison is only worth having if the third arm
  was graded like the other two. Report both the overall figure and the figure
  conditional on a query being built; they answer different questions and only
  the second is about the model.
- **Action**: validate, then commit: *Split Re-run (4/4): judged and recorded,
  with coverage and conditional correctness reported separately.*

## 4. Deliverables

| Deliverable | Where |
|---|---|
| Split runner + PID-based supervision | `scripts/split_llm_query_run.py` |
| Tier-stratified split, both halves | `logs/2026-09-05/split-{a,b}.txt` |
| Clock-vs-budget probe | `docs/evaluation/composition/bank/split-probe-2026-09-05.json` |
| 284 answers | `docs/evaluation/experiments/llm-query-split-2026-09-05/` |
| Judged rollup, three arms | `docs/evaluation/composition/bank/three-arm-judged.json` |
| Report + PDF | `docs/reports/2026-09-05-split-rerun.md` / `.pdf` |
