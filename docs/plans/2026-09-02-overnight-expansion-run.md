# Overnight run — judge the expansion bank and write the morning report

**Filed 2026-09-01, to run unattended overnight.** Operator is asleep; nothing in
this plan may block on a prompt, and every phase must leave its results on disk
the moment they exist.

## 1. Introduction

The expansion bank exists: 572 questions across all 34 edge types the pinned
sources support, authored by Opus 5 subagents, split dev/holdout by hash before
anything was run, and scored once **without a grader** at 0.4522 pooled / 0.5060
reweighted (EXP-2026-09-001 A-5). That score answers "how much of the right
answer did retrieval find". It does not answer the questions the project
actually cares about: whether the answers are *good*, whether the arm
comparisons that have been stuck at 30 questions hold at 500, and which of the
five anomalies A-5 turned up are real.

This plan runs that work overnight and writes a report a newcomer can read. It
is ordered **by value, not by dependency**, so an interruption at 3am leaves the
most important questions answered rather than the first ones. Every phase writes
its own artifacts before the next begins, the holdout half stays sealed
throughout, and the report states plainly what ran and what did not — a partial
sweep presented as a complete one is worse than no sweep.

Nothing here changes the system under test. No code with design judgment in it
gets written while nobody is watching.

## 2. Gaps & Unanswered Questions

- **Which arms to judge.** The bank has been run through `deterministic` only.
  *Assumption*: run `generic` and `llm_query` as well — the first is the
  schema-driven arm the recent claims rest on, the second is the LLM-planned
  baseline. `merged` is out of scope: it needs a different data directory and a
  separate store.
- **How many judge passes.** EXP-2026-08-021 measured the grader's re-run spread
  at ~0.005 and EXP-2026-08-022 measured a ~0.01 position effect. *Assumption*:
  two passes with the grading order counterbalanced between them, which is the
  minimum that lets the position effect be subtracted rather than absorbed.
- **Dev only, or dev and holdout.** *Assumption*: **dev only.** The holdout is
  sealed until the dev half has been written up, per the plan's Step 7 gate.
  Breaking that overnight, unattended, for convenience is exactly how holdout v1
  stopped being blind.
- **Judge model.** *Assumption*: `skynet` (`qwen38-27B-v2`), the calibrated
  grader from EXP-2026-08-021 (r = 0.9612 against the Sonnet reference). Its
  identity is probed and recorded at the start of the run, because `skynet` is
  an alias that has served three models (D-028).
- **Whether the D1 anomaly is a defect or a property.** A-5 found property reads
  scoring below both single-hop tiers, which the difficulty hypothesis did not
  predict. *Human intervention may be needed*: the run will diagnose and report
  it, but deciding whether to change the composer is a design call and is
  deliberately left for the morning.
- **Wall-clock budget.** Unknown how long ~1,000 judgments take on the local
  relay; EXP-2026-08-021 suggests hours. *Assumption*: phases are independently
  restartable and the report renders from whatever exists at the deadline.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Preflight and freeze

- **Locations**: `scripts/expansion_overnight.py` (new, `Sweep.preflight`);
  `main.py --graph health`, `--graph fixture-qa`; `scripts/model_identity.py`;
  `docs/evaluation/composition/bank/bank.json`.
- **Rationale**: Every failure mode this project has recorded overnight came
  from starting against a store that was empty, stale, or serving a different
  model than the log claimed. Preflight reloads CAPEC, runs fixture-QA for both
  datasets, probes the grader alias and records the model it actually serves,
  and hashes the bank so the report can prove which file it graded. It also
  asserts the holdout half is untouched, and refuses to start if any check
  fails rather than producing a night of ungrounded numbers.
- **Action**: Undergo the verification process for this phase. Once validated,
  commit stating: `Overnight expansion run (1/7) Complete: preflight — stores
  verified, grader identified, bank hashed, holdout sealed.`

### Step 2: Run the remaining arms over the dev half

- **Locations**: `utils/evaluation/experiment_untruncated.py` (`--arm generic`,
  `--arm llm_query`); root `docs/evaluation/experiments/expansion-2026-09-01/`;
  driven from `scripts/expansion_overnight.py` (`Sweep.run_arm`).
- **Rationale**: Two arms is the minimum that makes the bank a comparison rather
  than a measurement. `generic` is the schema-driven arm the recent claims rest
  on; `llm_query` is the LLM-planned baseline C-012 compares against. Both run
  with `ORCH_MAX_HOPS=5`, because the local `.env` pins it to 1 and that starves
  the iterative arms — a recorded trap.
- **Action**: Undergo the verification process for this phase. Once validated,
  commit stating: `Overnight expansion run (2/7) Complete: generic and llm_query
  answered the dev half of the expansion bank.`

### Step 3: Judge all three arms, counterbalanced

- **Locations**: `utils/evaluation/judge_answers.py` (`JudgeConfig`, `position`);
  `utils/evaluation/grading_order.py` (`counterbalanced`, `position_of`);
  `scripts/expansion_overnight.py` (`Sweep.judge`).
- **Rationale**: The condition graded second scores ~0.01 lower whichever it is
  (EXP-2026-08-022). Two passes with the arm order reversed between them make
  that effect measurable and subtractable instead of silently loaded onto one
  arm. `max_tokens` is set to 32768 because EXP-2026-08-021 found ~7–8% of the
  largest answers fail to grade at smaller budgets, and the failures are
  concentrated in the thorough answers.
- **Action**: Undergo the verification process for this phase. Once validated,
  commit stating: `Overnight expansion run (3/7) Complete: three arms judged
  twice with grading order counterbalanced.`

### Step 4: Settle the direction tension

- **Locations**: `scripts/direction_contrast.py` (new);
  `docs/evaluation/composition/bank/score.json`;
  `utils/specialists/evalset/composition.py` (spec steps carry `reverse`).
- **Rationale**: A-4 compared *the same shape* asked from each end and found the
  forward side answered and the reverse side not. A-5's aggregate says the
  opposite, because it compares *different shapes* that happen to be forward or
  reverse. This step pairs specs by `(shape, anchor_key)` so only genuine
  forward/reverse pairs enter the contrast, which is the design that can
  actually answer it. This is the highest-value phase in the night: direction is
  the axis the blind holdout collapsed on, and the project currently holds two
  contradictory readings of it.
- **Action**: Undergo the verification process for this phase. Once validated,
  commit stating: `Overnight expansion run (4/7) Complete: paired direction
  contrast resolves the A-4 / A-5 tension.`

### Step 5: Diagnose the three anomalies

- **Locations**: `scripts/anomaly_triage.py` (new), reading
  `docs/evaluation/experiments/expansion-2026-09-01/*/answers/`.
- **Rationale**: A-5 left three findings unexplained, and all three are
  diagnosable without a model. (a) **Property reads** score below single-hop
  traversals — check whether the failures cluster on non-Technique anchors and
  whether the retrieved record simply lacks the field. (b) **Containment shapes**
  score 0.03–0.04 although the reconciliation proves the rows are loaded — check
  whether the query is built at all or built and returning nothing. (c)
  **Abstention** succeeds 60.7% of the time — classify the 24 failures by what
  was retrieved instead. Each becomes a named cause in the record rather than a
  number nobody can act on.
- **Action**: Undergo the verification process for this phase. Once validated,
  commit stating: `Overnight expansion run (5/7) Complete: property, containment
  and abstention failures classified by cause.`

### Step 6: Record everything in the research record

- **Locations**: `make new-experiment SLUG=expansion-bank-judged` →
  `docs/research/experiments/EXP-2026-09-002-expansion-bank-judged/`
  (`PROTOCOL.md`, `RESULTS.md`, `ISSUES.md`, `manifest.yaml`,
  `data/POINTERS.md`); `docs/research/OPEN_QUESTIONS.md`;
  `docs/research/CLAIMS.md`.
- **Rationale**: A number that exists only in a chat log does not exist. Every
  figure the report quotes must first be written to a `manifest.yaml` and a
  `RESULTS.md`, with full SHA-256 pointers to the artifacts it came from, and
  `make validate-research` must pass. The protocol is written before the
  analysis is read, from the hypotheses this plan already states.
- **Action**: Undergo the verification process for this phase. Once validated,
  commit stating: `Overnight expansion run (6/7) Complete: EXP-2026-09-002
  records the judged expansion results.`

### Step 7: Write the morning report as a PDF

- **Locations**: `scripts/morning_report.py` (new), rendering via `reportlab`
  to `docs/reports/2026-09-02-overnight-report.pdf`, with the Markdown source
  beside it at `docs/reports/2026-09-02-overnight-report.md`.
- **Rationale**: The report is the deliverable, and its audience is someone new
  to the field. Rules it must follow: no undefined term, no abbreviation without
  its expansion, every number stated with what it is out of, every comparison
  stated with what it is being compared to, and an explicit section listing what
  did **not** run. Numbers are read from the artifacts on disk — the script may
  not hardcode a figure, so a phase that failed cannot silently contribute a
  stale number. The Markdown is written first and is the fallback if rendering
  fails, so a PDF problem never costs the report.
- **Action**: Undergo the verification process for this phase. Once validated,
  commit stating: `Overnight expansion run (7/7) Complete: morning report
  rendered to PDF from the artifacts on disk.`

### Note on the commit wording

The planner template says to push. This repository's global rules say not to,
and the operator's standing instruction is commit-only. Every step above commits
and none pushes.

## 4. Deliverables Table

| Deliverable | Description | Location |
| --- | --- | --- |
| Overnight orchestrator | Value-ordered, restartable phase runner; writes `state.json` after every phase so a crash costs one phase | `scripts/expansion_overnight.py` |
| Direction contrast | Pairs specs by `(shape, anchor)` so only true forward/reverse pairs are compared | `scripts/direction_contrast.py` |
| Anomaly triage | Classifies property, containment and abstention failures by cause from answer artifacts | `scripts/anomaly_triage.py` |
| Morning report | Jargon-free PDF plus its Markdown source, every figure read from disk | `scripts/morning_report.py`, `docs/reports/2026-09-02-overnight-report.pdf` |
| Experiment record | Protocol, results, issues, manifest, hashed pointers | `docs/research/experiments/EXP-2026-09-002-expansion-bank-judged/` |
| Orchestrator tests | Phase ordering, restart-skips-completed, partial-state reporting, and that a failed phase cannot contribute a number | `utils/evaluation/tests/test_expansion_overnight.py` |
| Direction contrast tests | Pairing logic on a small fixture: unpaired specs excluded, sign convention fixed, paired mean differs from the confounded aggregate | `utils/evaluation/tests/test_direction_contrast.py` |
| Report tests | Renders from a fixture state with phases missing; asserts the "did not run" section is populated and no figure is hardcoded | `utils/evaluation/tests/test_morning_report.py` |

## 5. What this plan deliberately does not do

- **It does not touch the holdout half.** 288 questions stay sealed.
- **It does not change the system under test.** No composer fix, no builder
  change, no template edit — those carry design judgment and are not done
  unattended.
- **It does not push.**
- **It does not run the merged-graph arm**, which needs a separate data
  directory and store and cannot be set up safely without supervision.
