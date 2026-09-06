# PROTOCOL — EXP-2026-09-009 — three seeded runs of the query-writing arm

**Written 2026-09-06, before any run.** Hypotheses below are pre-registered. Do
not edit them after data exists; append an AMENDMENTS section instead.

---

## The question

Every published figure for the `llm_query` arm rests on **one draw**. `D-010`
pins `n_runs: 1` across several experiments and the `seeds` field is empty. Two
things follow, and only the second is interesting:

1. The paper cannot state a variance for the arm. That is a reporting gap.
2. **`C-012` — that hand-written templates beat a model writing the queries —
   may not be established at all.** Its holdout margin is `+0.0831`, the second
   grader family's interval already includes zero, and if run-to-run spread is of
   the same order as the margin, one draw did not establish the sign.

This experiment answers 2. It is the first kill gate of the Phase 2 programme
(`docs/research/top-tier-programme-2026-09.md`, Step 0.1) and it is owed to the
paper regardless of whether that programme is ever scheduled.

---

## Prior evidence that shapes the design

`EXP-2026-08-019` tested whether pinning the client seed reduces spread:

| condition | seed | workers | across-repeat SD |
|---|---|---|---|
| A | off | 16 | **0.0207** |
| B | on (1729) | 16 | **0.0212** |

**Pinning the seed did not reduce spread.** This is expected of a batched
inference server, where request interleaving is not seed-controlled. Therefore:

- We do **not** claim these runs are reproducible.
- We vary the seed across the three runs and **record it**, so that the run is
  described rather than merely repeated. The measurement of interest is the
  across-run spread, not agreement between runs.
- A reader who repeats this with our seeds should expect our *distribution*, not
  our *values*.

---

## Design

**Arm.** `llm_query` only. The `deterministic` and `generic` arms contain no
language model on this path and do not vary across seeds; their figures are
reused from `EXP-2026-09-005` (`deterministic` = 0.4946, `generic` = 0.6569,
n=284).

**Population.** The expansion-bank **dev half**, n=284 — the same population and
the same file as `EXP-2026-09-002` and `EXP-2026-09-005`, so the new runs are
directly comparable to the recorded figure. **The 288-question holdout is not
used.** It is spent, it is one-shot, and re-running it would destroy the property
that makes it worth having.

**Runs.** Three, `LLM_SEED` ∈ {1729, 20260906, 424242}. Seed 1729 reproduces the
configuration of every recorded run; the other two are arbitrary and were chosen
before any run.

**Configuration**, held identical to the recorded runs:

| Setting | Value | Why |
|---|---|---|
| `ORCH_MAX_HOPS` | 5 | Local `.env` pins 1, which starves the iterative arms. Every recorded run used 5 |
| `--llm-max-tokens` | 32768 | `EXP-2026-08-021`: smaller budgets fail on the largest answers, and the failures land on the thorough ones |
| thinking cap | **off** | `EXP-2026-09-008` measured a 512-token cap at 0/30 retrieved and 28/30 gate-rejected. Enabling it tests a configuration the paper does not describe |
| workers | 32 | Operator-authorised for this run |

**Grading.** Both families, both named and probed at launch, not trusted from the
alias (`D-028`):

- family 1 — `qwen38-27B-v2` via `default-model`
- family 2 — `gemma4-31B-mtp` via `default-model-2`

`max_tokens` 32768, position-major, per-grader probe guard.

**Statistics.** Across-run SD is reported directly (n=3; no interval is claimed
from three points). Paired contrasts against the fixed `deterministic` figure use
the standing method: percentile bootstrap, 2000 resamples, seed 1729.

---

## Pre-registered hypotheses

**H1 — the ordering holds.** `generic > deterministic > llm_query` in all three
runs, under both grader families.
*Falsified by:* any run in which the ordering does not hold under either family.

**H2 — spread is small relative to the margin.** Across-seed SD of
`llm_query` judged correctness is **below 0.03**.
*Falsified by:* SD ≥ 0.03. That outcome means one draw could not have
established a `+0.0831` margin, and `C-012` weakens from `partial` to
`unsupported` pending more runs.

**H3 — the contrast keeps its sign.** `deterministic − llm_query` is positive in
all three runs under **both** grader families.
*Falsified by:* any run/family cell in which the sign flips.

**On H3 being falsified.** That outcome is **publishable and more interesting
than the alternative.** It would mean `C-012` was never established, that the
paper's §6 must be rewritten as an undetermined contrast, and that a
single-draw claim of this size is unsafe in this literature generally. It is
recorded here, before the data exists, that we will report it.

---

## Stopping and guard conditions

- **Pre-flight, before any request:** assert both stores at their pinned counts
  (Neo4j 4,369/27,669; Gremlin 6,374/8,582) and probe each endpoint for a real
  completion. A relay that lists a model is not a model that answers — this
  project has already driven 288 cases into a dead endpoint behind a healthy
  alias, producing ~1,968 HTTP 502s.
- **A run writing fewer than 284 answers is recorded `not_run`.** A partially
  answered run is not a draw.
- **`served_model` is recorded per run and per grading pass.** If it does not
  match the string in the record, the pass is discarded rather than reconciled.
  The endpoint reported `gemma4-31B` rather than `gemma4-31B-mtp` during a
  startup window on 2026-09-06; the record contains only the latter.

---

## What this does not do

- It does not repeat the `deterministic` or `generic` arms; they are model-free
  on this path.
- It does not re-open the holdout.
- It does not address the absence of an external system baseline, which remains
  the largest gap in the record.
- Three runs is the minimum that gives a spread at all. It is not enough to
  characterise a distribution, and the results file must say so.
