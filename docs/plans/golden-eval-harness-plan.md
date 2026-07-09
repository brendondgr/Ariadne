# Golden Evaluation Harness — Decoupled Run → Judge → Report Agent System

## 1. Introduction

The analyst wants a way to run the golden question set (or the wider evaluation
set) through the **local AI**, have the local AI **judge how correct each answer
is**, and produce a **final report** of the results — and, crucially, wants the
three concerns to be handled by **separate agents that operate independently of
one another**.

Ariadne already has a coupled end-to-end evaluator (`utils/evaluation/score_e2e.py`)
that runs all 120 golden questions through the pipeline and scores four
deterministic metrics plus an opt-in LLM judge. But it does everything in **one
in-memory pass**, nothing is persisted between phases, and its LLM judge scores
*faithfulness / groundedness / evidence-sufficiency* (answer vs. its own
evidence) — **not** *how correct the answer is relative to the golden expected
answer*. This plan adds a new, **decoupled three-stage harness** under
`utils/evaluation/harness/` that reuses the existing pipeline drivers, judge
transport, and stats helpers, but splits the work into three separately-runnable
agents that hand off through persisted JSONL artifacts:

1. **Runner agent** — loads a chosen golden set, runs each question through the
   local Ariadne pipeline, writes `answers.jsonl`.
2. **Judge agent** — reads `answers.jsonl`, asks the **local LLM** to grade each
   answer's **correctness against the golden expected answer** (with a
   deterministic id-recall/precision backstop), writes `judgments.jsonl`.
3. **Reporter agent** — reads `judgments.jsonl`, aggregates overall / per-set /
   per-tier / per-source correctness, writes `golden-eval.{md,json}`.

Each stage can be run alone (`--stage run|judge|report`) or chained (`--stage
all`), so a slow live run can be done once and re-judged or re-reported cheaply.

## 2. Gaps & Unanswered Questions

- **What counts as "correct"?** *Assumption*: correctness is graded against each
  golden entry's `assertions` — for single-source entries the expected id set is
  `must_include_ids ∪ must_include_related`; for federated entries it is
  `must_correlate` (the required cross-source correlation ids). The LLM judge is
  given the question, the produced answer, and this golden expected set, and
  returns a correctness score `[0,1]` + a label (`correct` / `partial` /
  `incorrect`) + a short rationale. A deterministic backstop computes id
  recall/precision from the answer's claim entity-ids + citation ids vs. the gold
  set so the report is meaningful even with the LLM off.
- **Which set?** *Assumption*: support `attack`, `capec`, `federated`, and `all`;
  default `all`. `--limit N` and `--tier` allow small smoke runs.
- **Does "through the local AI" mean the pipeline itself must use the LLM
  drafters?** *Assumption*: the **judge** uses the local LLM by default (that is
  the core "judge how correct" ask). Pipeline LLM-drafting is opt-in via
  `--llm-pipeline`; by default the pipeline runs its deterministic (grounded)
  drafters, which is faster and reproducible, while the *judgment* is the local
  AI's. When `--no-llm` is passed the judge falls back to the deterministic
  correctness backstop only.
- **Live dependency.** The runner needs the live stack (Neo4j 5456, Gremlin 6455)
  and the judge needs the local LLM (:9090). All are currently up. When the stack
  is down the runner writes an honest hermetic artifact that scores nothing,
  mirroring the existing `score_e2e` `--no-live` discipline.
- **Build-process agents.** The session guidance suggests Agent Workflows
  (Opus plan / Haiku search / Sonnet implement). The implementation steps here
  form a dependency chain (contracts → runner → judge → reporter → wiring), so
  they are implemented sequentially with targeted subagent help rather than a
  parallel fan-out; the *delivered* system is the three-agent runtime harness.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Package scaffold, contracts, and golden loader
- **Locations**: `utils/evaluation/harness/__init__.py`,
  `utils/evaluation/harness/contracts.py` (`AnswerRecord`, `CorrectnessVerdict`,
  `HarnessReport` dataclasses + JSONL read/write helpers),
  `utils/evaluation/harness/golden.py` (`load_entries(sets)` normalizing the
  three banks into uniform entries with an extracted `gold_expected_ids` set),
  `utils/evaluation/harness/tests/test_contracts.py`,
  `utils/evaluation/harness/tests/test_golden.py`.
- **Rationale**: The persisted artifact schema and the gold-extraction logic are
  the contract every later stage depends on; fixing them first lets the three
  agents stay decoupled (they only share these dataclasses + files).
- **Action**: Undergo the verification/tests process for this phase
  (`uv run python -m pytest utils/evaluation/harness/tests/`). Once validated,
  commit stating: Golden Eval Harness (1/6) Complete: scaffolded the harness
  package with persisted contracts and a golden-set loader that extracts gold
  expected-id sets.

### Step 2: Runner agent
- **Locations**: `utils/evaluation/harness/run_stage.py` (`RunnerAgent.run` →
  drives each entry via the existing `run_single` / `run_federated` drivers,
  extracts `SynthesizedAnswer` into `AnswerRecord`, writes `answers.jsonl`;
  honest hermetic path when the stack is down),
  `utils/evaluation/harness/cli.py` (`--stage run` wiring),
  `utils/evaluation/harness/tests/test_run_stage.py` (hermetic: monkeypatched
  drivers; no DB).
- **Rationale**: Stage 1 of the pipeline — turns golden questions into persisted
  answers so judging/reporting never need to re-run the (slow, live) pipeline.
- **Action**: Undergo the verification/tests process
  (`pytest`; live smoke: `--stage run --set attack --limit 2` produces a
  non-empty `answers.jsonl`). Once validated, commit stating: Golden Eval Harness
  (2/6) Complete: the runner agent executes golden questions through the live
  pipeline and persists answers.jsonl.

### Step 3: Correctness judge (local-LLM + deterministic backstop)
- **Locations**: `utils/evaluation/harness/correctness_judge.py`
  (`build_correctness_messages` pure prompt builder; `DeterministicCorrectness`
  id recall/precision + label thresholds; `LocalLLMCorrectness` reusing
  `EvalConfig` + the `_post` / `extract_json_object` transport pattern;
  `HybridCorrectness` fallback), `utils/evaluation/harness/tests/test_correctness_judge.py`
  (prompt build + JSON parse + deterministic scoring; no HTTP).
- **Rationale**: This is the new capability — grading answers against the golden
  expected answer with the local AI, with a reproducible deterministic backstop
  so the number always exists.
- **Action**: Undergo the verification/tests process (`pytest`). Once validated,
  commit stating: Golden Eval Harness (3/6) Complete: added the correctness judge
  (local-LLM grading vs. gold with a deterministic recall/precision backstop).

### Step 4: Judge agent
- **Locations**: `utils/evaluation/harness/judge_stage.py` (`JudgeAgent.run` →
  reads `answers.jsonl`, applies the correctness judge per record, writes
  `judgments.jsonl`), `--stage judge` in `cli.py`,
  `utils/evaluation/harness/tests/test_judge_stage.py`.
- **Rationale**: Stage 2 — a standalone agent that consumes the runner's artifact
  and emits verdicts, independently re-runnable against a fixed `answers.jsonl`.
- **Action**: Undergo the verification/tests process (`pytest`; run the judge
  over the Step-2 smoke `answers.jsonl` both deterministic and against the live
  :9090 LLM). Once validated, commit stating: Golden Eval Harness (4/6) Complete:
  the judge agent grades persisted answers into judgments.jsonl via the local AI.

### Step 5: Reporter agent
- **Locations**: `utils/evaluation/harness/report_stage.py` (`ReporterAgent.run`
  → reads `judgments.jsonl` (+ `answers.jsonl` for context), aggregates
  overall/by-set/by-tier/by-source correctness + pass-rate with `stats.py` CIs,
  writes `golden-eval.md` + `golden-eval.json`), `--stage report` and
  `--stage all` in `cli.py`, `utils/evaluation/harness/tests/test_report_stage.py`.
- **Rationale**: Stage 3 — the final deliverable, produced purely from the
  persisted judgments so reporting is cheap and repeatable.
- **Action**: Undergo the verification/tests process (`pytest`; produce a report
  from the smoke judgments). Once validated, commit stating: Golden Eval Harness
  (5/6) Complete: the reporter agent aggregates judgments into golden-eval.{md,json}.

### Step 6: CLI wiring, full regression, live end-to-end, docs, merge
- **Locations**: `main.py` (`--golden-eval` flag + `--stage/--set/--llm/--limit/
  --no-live/--tier` passthrough to `utils.evaluation.harness.cli`),
  `docs/skills/global-project-rules/SKILL.md` commands note + `docs/structure.md`
  (new package), `docs/changelog.jsonl`.
- **Rationale**: Make the harness a first-class CLI entry, prove it green across
  the whole suite, and prove it live end-to-end (run → judge → report with the
  local AI) before landing.
- **Action**: Undergo the verification/tests process: full backend regression
  (`pytest utils/evaluation/ ...`), then a live end-to-end run
  (`uv run main.py --golden-eval --stage all --set attack --limit 3` with the
  local LLM judge on) producing all three artifacts. Once validated, commit,
  then merge `golden-eval-harness` into local `main` with `--no-ff`. Commit
  stating: Golden Eval Harness (6/6) Complete: wired the CLI, verified full
  regression + live run→judge→report, documented, and merged to main.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Harness contracts | Persisted `AnswerRecord` / `CorrectnessVerdict` / `HarnessReport` + JSONL IO | `utils/evaluation/harness/contracts.py` |
| Golden loader | Normalizes the three banks + extracts gold expected-id sets | `utils/evaluation/harness/golden.py` |
| Runner agent | Golden set → `answers.jsonl` via the live pipeline | `utils/evaluation/harness/run_stage.py` |
| Correctness judge | Local-LLM grading vs. gold + deterministic backstop | `utils/evaluation/harness/correctness_judge.py` |
| Judge agent | `answers.jsonl` → `judgments.jsonl` | `utils/evaluation/harness/judge_stage.py` |
| Reporter agent | `judgments.jsonl` → `golden-eval.{md,json}` | `utils/evaluation/harness/report_stage.py` |
| Harness CLI | `--stage run|judge|report|all` orchestrator | `utils/evaluation/harness/cli.py` |
| CLI entry | `uv run main.py --golden-eval ...` | `main.py` |
| Harness tests | Hermetic tests over a small subset (contracts, loader, deterministic scoring, report, prompt/parse) | `utils/evaluation/harness/tests/` |
| Artifacts | Persisted run/judge/report outputs | `docs/evaluation/golden/{answers,judgments}.jsonl`, `docs/evaluation/golden-eval.{md,json}` |
