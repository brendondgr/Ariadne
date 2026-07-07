# Step 11 — End-to-End Evaluation & LLM Evaluator (Wk 12–13)

## 1. Introduction

Ariadne today scores the planner and the two query specialists in isolation (`docs/evaluation/component-evaluation.{md,json}`, built by `utils/evaluation/run_component_eval.py`). Nothing yet scores the **whole pipeline end to end**, and the proposal's committed **LLM evaluator** (faithfulness, groundedness, evidence sufficiency, unsupported-claim rate) does not exist — every current metric is deterministic by design. This plan closes the last open evaluation deliverable on the roadmap ([`docs/goals.md`](../goals.md) Wk 12–13): a full-pipeline accuracy score covering the four end-to-end metrics (cross-source answer accuracy, CAPEC→ATT&CK mapping recall, provenance correctness, analyst inspectability) plus an opt-in LLM-as-judge, and then surfaces the results through the FastAPI backend into a new **Evaluation** view in the web workbench so the numbers can actually be inspected.

The approach reuses the machinery already in place rather than inventing a parallel harness. The end-to-end scorer drives the committed **120-question golden catalogue** (80 single-source + 40 federated, pinned by `utils/specialists/tests/test_banks.py`) through the real `run_pipeline` orchestrator, then grades each run against the same snapshot-derived gold the live golden suites already use (`FederatedEvidence.cross_source_join_values()` vs `must_correlate`, `gold_bank` `attack_mappings`, `EvidenceRecord.provenance`, `SynthesizedAnswer` citations/abstentions). The LLM judge mirrors the existing OpenAI-compatible client pattern (`utils/synthesis/llm_composer.py`) exactly, ships **off by default** with a deterministic proxy so the byte-reproducible LLM-off build stays green, and — when enabled — judges a configurable sample and records its non-reproducible scores in a clearly-labeled section. Results land in a **separate** `docs/evaluation/e2e-evaluation.{md,json}` report, served read-only over `GET /api/evaluation` and re-runnable live from the UI via an SSE endpoint that reuses the admin-runner worker pattern.

## 2. Gaps & Unanswered Questions

Confirmed with the user before planning (all resolved — no open human-intervention questions remain):

- **Report packaging** — *Resolved:* a **separate** `docs/evaluation/e2e-evaluation.{md,json}` report and a new `--e2e-eval` CLI flag; `component-evaluation.{md,json}` is left untouched. The read endpoint serves both.
- **Frontend scope** — *Resolved:* a read-only dashboard of the committed report **plus** a live "Run evaluation" button streaming SSE progress (needs the Docker stack up; slow).
- **LLM-judge posture** — *Resolved:* opt-in, **off by default**. Deterministic proxy fills the same metric keys so the LLM-off build is byte-reproducible; when enabled it judges a configurable sample (default 20) and its scores live in a labeled, non-reproducible block.

Assumptions made for simple gaps (stated, proceeding):

- **Judge endpoint** — reuses the same local OpenAI-compatible endpoint the other agents use (`http://localhost:9090/v1`, no API key), configured via new `EVAL_LLM_*` env vars mirroring `SYNTHESIS_LLM_*`. *Assumption: no external provider is introduced.*
- **Metric definitions** — the two novel metrics are defined concretely so they are executable: **provenance correctness** = fraction of rendered-claim citations that resolve to a retrieved `EvidenceRecord` whose `provenance` block is complete *and* whose `provenance.query` equals the executed specialist query, plus every abstention carrying a truthful proof; **analyst inspectability** = fraction of rendered claims with ≥1 citation whose full claim→citation→record→provenance chain is reconstructable, combined with abstention-proof completeness. *Assumption: these definitions are acceptable; they are surfaced in the report header for review and can be tuned in Step 6.*
- **Live cost/time** — running all 120 questions live is minutes-long, so the scorer accepts `--limit` / tier filters and the deterministic build (`--no-live`) uses stubbed evidence fixtures for hermetic tests. *Assumption: a `--no-live` hermetic path plus a live path is sufficient (mirrors `run_component_eval.py`).*
- **`.env.example` drift** — `SYNTHESIS_LLM_*` is currently missing from `.env.example` even though the code reads it; this plan adds both the `SYNTHESIS_LLM_*` and new `EVAL_LLM_*` blocks while touching that file.
- **Work isolation** — per repo memory, work happens on a git worktree reset onto local `main` with `data/` + `.env` symlinked; the final step merges back to `main`. Commits are made at every step but **not pushed** (standing user directive overrides the global-rules push requirement).

## 3. Hierarchical Step-by-Step Instructions

### Step 1: LLM-judge core package (deterministic proxy + LLM-as-judge)

- **Locations:**
  - New package `utils/evaluation/llm_judge/`:
    - `config.py` — `EvalConfig` dataclass + `from_env()` reading `EVAL_LLM_ENABLED` / `EVAL_LLM_BASE_URL` / `EVAL_LLM_MODEL` / `EVAL_LLM_TIMEOUT_S` / `EVAL_LLM_MAX_TOKENS` (mirror `utils/synthesis/config.py:32`).
    - `contracts.py` — `JudgeVerdict` and `JudgeReport` dataclasses (per-answer scores: `faithfulness`, `groundedness`, `evidence_sufficiency`, `unsupported_claim_rate`, `source` ∈ {`deterministic`, `llm`}, `reasons`) each with `to_dict()`.
    - `deterministic_judge.py` — `DeterministicJudge.judge(answer, evidence)` computing proxy scores from the existing verifier signal (`SynthesizedAnswer.verification`, grounding via `utils/synthesis/grounding.py`), so metric keys are always present and reproducible.
    - `llm_judge.py` — `OpenAICompatibleJudge` mirroring `utils/synthesis/llm_composer.py:181` (`requests.post` to `<base_url>/chat/completions`, `temperature=0`, parse `choices[0].message.content` as JSON), raising `JudgeUnavailable` on any transport/parse failure.
    - `factory.py` — `select_judge(config)` returning `HybridJudge(OpenAICompatibleJudge, DeterministicJudge)` when `config.llm_enabled` else the deterministic judge; `judge_answer()` single entry point (mirror `utils/synthesis/factory.py:61`).
    - `tests/` — hermetic unit tests: deterministic proxy produces stable scores on a fixture answer, `HybridJudge` falls back to deterministic on `JudgeUnavailable`, JSON-shape parsing of a canned LLM response.
  - `.env.example` — add the `EVAL_LLM_*` block and the currently-missing `SYNTHESIS_LLM_*` block (after the specialist section, lines ~113–123).
- **Rationale:** Every later step consumes the judge, so it must exist first with a rock-solid deterministic fallback. Building it as an isolated package mirroring the synthesis composer keeps the "no metric depends on an LLM judge" invariant intact (proxy fills the keys) while satisfying the proposal's LLM-evaluator commitment (real judge behind an env flag).
- **Action:** Undergo the verification/tests/validation process for this phase (`uv run python -m pytest utils/evaluation/llm_judge/tests/`). Once validated, commit to GitHub — **do not push** — stating: `E2E Eval (1/7) Complete: LLM-judge package with deterministic proxy + opt-in OpenAI-compatible judge and env config.`

### Step 2: End-to-end pipeline scorer

- **Locations:**
  - New `utils/evaluation/score_e2e.py`:
    - `run_question(entry, *, live, judge, ...)` — drives one catalogue entry through `run_pipeline` (`utils/specialists/pipeline.py:274`) and returns a per-question `E2ECase` capturing the four metrics.
    - `_cross_source_accuracy(evidence, entry)` — compares `FederatedEvidence.cross_source_join_values()` (`utils/specialists/federation.py:69`) against `entry["assertions"]["must_correlate"]`; exact-set-match + precision/recall/F1, honoring `expect_no_correlation` negatives.
    - `_mapping_recall(evidence, entry, gold)` — gold CAPEC→ATT&CK mappings from `gold_bank` `attack_mappings` (∩ ATT&CK existence); fraction surfaced in the live `join_index`.
    - `_provenance_correctness(answer, results)` — every rendered-claim citation resolves to a retrieved `EvidenceRecord` whose `provenance` is complete and whose `provenance.query` equals the executed specialist query; abstention proofs checked via the shared `golden_runner` helpers.
    - `_inspectability(answer)` — rendered-claim citation coverage + claim→record chain reconstructability + abstention-proof completeness.
    - `score_e2e(*, live, judge_config, limit=None, tiers=None)` — iterates the federated bank (and the single-source banks for synthesis-faithfulness coverage), aggregates with `utils/evaluation/stats.py` (`wilson_interval`, `bootstrap_ci`), returns `{"overall", "by_tier", "by_category", "cases", "judge"}`.
  - New `utils/evaluation/tests/test_score_e2e.py` — hermetic tests with a **stubbed pipeline** (inject `PipelineRun` fixtures) asserting each metric computes correctly on known-good and known-bad evidence; a `live`/`integration`-marked test runs a small subset through the real stack (skips when down).
  - Reuse (no change): `utils/specialists/tests/golden_runner.py` (`check_assertions`, `check_traces`), `utils/synthesis/grounding.py` (`normalize_id`).
- **Rationale:** This is the analytical core — the four `goals.md` end-to-end metrics as executable checks. Reusing the golden runner and snapshot-derived `must_correlate` guarantees the scorer grades against the *same* gold the pass/fail suites already trust, so a green e2e score cannot silently disagree with the golden tests.
- **Action:** Undergo the verification/tests/validation process for this phase (`uv run python -m pytest utils/evaluation/tests/test_score_e2e.py`; live subset when the stack is up). Once validated, commit to GitHub — **do not push** — stating: `E2E Eval (2/7) Complete: full-pipeline scorer for cross-source accuracy, mapping recall, provenance, and inspectability over the golden catalogue.`

### Step 3: E2E report assembly + CLI flag

- **Locations:**
  - New `utils/evaluation/e2e_report.py` — `collect_e2e(live, judge_config, ...)`, `build_json(e2e, judge, meta)`, `build_markdown(data)`, `write_report(data, md_path, json_path)` (mirror `utils/evaluation/component_report.py:108–234`); markdown sections: header (metric definitions + reproducibility note), End-to-End metrics (4 tables with CIs), LLM-Judge (labeled non-reproducible when LLM on; deterministic-proxy note when off), Diagnosis.
  - New `utils/evaluation/run_e2e_eval.py` — `main(argv)` entry point (mirror `run_component_eval.py:50`), args `--out-dir docs/evaluation`, `--no-live`, `--judge` (enable LLM judge), `--judge-sample N` (default 20), `--limit`, `--tier`; writes `docs/evaluation/e2e-evaluation.{md,json}`.
  - `main.py` — add `--e2e-eval` to the evaluation argument group (~line 316–330) and dispatch to `run_e2e_eval` (~line 360–361, import ~line 460), reusing `--no-live`.
  - New `utils/evaluation/tests/test_e2e_report.py` — hermetic: `build_json`/`build_markdown` are pure and byte-stable given fixed inputs; `--no-live` run produces a valid report with deterministic-proxy judge values.
- **Rationale:** Turning per-question cases into a single citable, reproducible artifact is what makes the milestone demonstrable. Keeping `build_json`/`build_markdown` pure (as the component report already does) is what lets the reproducibility test assert byte-stability with the LLM off.
- **Action:** Undergo the verification/tests/validation process for this phase (`uv run python -m pytest utils/evaluation/tests/`; `uv run main.py --e2e-eval --no-live` produces the report; run live when the stack is up). Once validated, commit to GitHub — **do not push** — stating: `E2E Eval (3/7) Complete: e2e report assembly + --e2e-eval CLI writing docs/evaluation/e2e-evaluation.{md,json}.`

### Step 4: Backend API — read report + live-run SSE + config groups

- **Locations:**
  - New `api/services/evaluation.py`:
    - `read_evaluation_report()` — reads the latest committed `docs/evaluation/e2e-evaluation.json` **and** `component-evaluation.json` from disk, returns a combined payload (mirror `api/services/graph.py:39` file-read pattern; never raises — returns an `available:false` marker if a report is absent).
    - `stream_eval_run(*, live, judge, ...) -> Iterator[str]` — runs `run_e2e_eval` in a worker thread, forwarding progress as SSE `log`/`progress` events and a terminal `done` (mirror `api/services/infra.py:116–151` admin-worker pattern; emits `_sse(event, data)` frames).
  - `api/models.py` — add `EvaluationReportResponse` (+ nested metric models) and `EvalRunRequest`; also add the missing `synthesis` and new `eval` `LLMGroup`/`LLMGroupUpdate` fields to `LLMConfig`/`ConfigUpdateRequest` (~lines 43–115).
  - `api/services/config.py` — add `"synthesis"` and `"eval"` entries to `_LLM_ENV_KEYS` (~lines 30–45) and thread them through `read_config()` / `collect_updates()` so the settings modal can view/edit them.
  - `api/main.py` — register `GET /api/evaluation` (read report) and `POST /api/eval-run` (SSE `StreamingResponse`) following the existing route pattern (~lines 49–119).
  - `api/tests/test_evaluation.py` — contract tests: `GET /api/evaluation` returns the combined shape (and the graceful `available:false` when files are absent); `POST /api/eval-run` streams `status → progress* → done` (stub the runner), mirror `api/tests/test_query.py` `TestClient` pattern.
- **Rationale:** The read endpoint is the always-available "check our results" surface (works with no Docker stack, since it just serves the committed JSON); the SSE run endpoint gives the live-regenerate capability the user asked for. Adding the synthesis/eval config groups closes the existing gap where those env vars can't be edited from the UI.
- **Action:** Undergo the verification/tests/validation process for this phase (`uv run python -m pytest api/tests/`). Once validated, commit to GitHub — **do not push** — stating: `E2E Eval (4/7) Complete: /api/evaluation read endpoint + /api/eval-run SSE + synthesis/eval config groups with contract tests.`

### Step 5: Frontend — Evaluation view (dashboard + live-run)

- **Locations:**
  - `web/components/workbench/WorkbenchContext.tsx` (~lines 34–35) — extend the `view` union with `"evaluation"`.
  - `web/components/header/ViewToggle.tsx` (~lines 6–9) — add the `{ value: "evaluation", label: "Evaluation" }` segment.
  - `web/components/workbench/Workbench.tsx` (~lines 59–72) — route `view === "evaluation"` to a new `<EvaluationDashboard />`; hide chat rails for this view (as Graphs already does via `AppShell hideRails`).
  - New `web/components/evaluation/` — `EvaluationDashboard.tsx` (loads `GET /api/evaluation` on mount; metric cards for the 4 e2e metrics + planner/specialist summary + LLM-judge block; a "Run evaluation" button that streams `POST /api/eval-run` progress), plus small `MetricCard.tsx` / `MetricsTable.tsx` / `JudgePanel.tsx` presentational components using the Woven Dusk tokens.
  - `web/lib/api.ts` (~lines 34–140) — add `getEvaluation(signal)` and `streamEvalRun(body, onEvent, signal)` (reuse `postSseStream`).
  - `web/lib/types.ts` — add `EvaluationReport`, `EvalMetric`, `JudgeResult`, and the `EvalEvent` SSE union mirroring the backend `to_dict()` shapes.
  - `web/lib/fixtures.ts` — a committed sample report so the dashboard renders without a live backend (mirrors the seeded demo run).
- **Rationale:** This is the deliverable the user explicitly asked for — being able to *see* the results. Following the existing three-region shell + `GraphExplorer` view template keeps it consistent with the workbench; the committed fixture means the dashboard demos even with the backend down.
- **Action:** Undergo the verification/tests/validation process for this phase (`cd web && npm run lint && npm run build && npm test`; preview-verify the Evaluation view renders the fixture and the live-run button streams). Once validated, commit to GitHub — **do not push** — stating: `E2E Eval (5/7) Complete: Evaluation workbench view — committed-report dashboard + live SSE run button.`

### Step 6: Docs, goals, census & changelog reconciliation

- **Locations:**
  - `docs/structure.md` — document `utils/evaluation/llm_judge/`, `score_e2e.py`, `e2e_report.py`, `run_e2e_eval.py`, the `--e2e-eval` flag, the `GET /api/evaluation` + `POST /api/eval-run` endpoints, and the new `web/components/evaluation/` view; update the "Not Yet in Repo" section.
  - `docs/goals.md` — check the Wk 12–13 "End-to-end evaluation and LLM evaluator" box (line ~40) with a one-line evidence note.
  - `README.md` — fix the stale synthesis "(in progress)" label and add the Evaluation view to the overview.
  - `docs/evaluation/e2e-evaluation.{md,json}` — commit the deterministic (`--no-live` or live-when-available) report as the checked-in baseline.
  - `docs/changelog.jsonl` — one entry per step already; add the final docs entry.
- **Rationale:** The global rules require a changelog entry per change and the roadmap/structure docs are the project's source of truth; leaving the goals box unchecked or `structure.md` stale would misrepresent project state at the pitch.
- **Action:** Undergo the verification/tests/validation process for this phase (docs render; links resolve; report file present). Once validated, commit to GitHub — **do not push** — stating: `E2E Eval (6/7) Complete: docs/structure + goals checkbox + README + committed baseline report.`

### Step 7: Full regression + merge to main

- **Locations:**
  - Full suite: `uv run python -m pytest utils/ api/` and `cd web && npm test && npm run build`; live golden + e2e when the Docker stack is up (`uv run main.py --docker start`, then `--e2e-eval`).
  - Git worktree — reconcile with any concurrent `main` movement (per repo memory, merges must regenerate derived evalset artifacts and re-pin census counts), fix conflicts, then merge onto `main`.
- **Rationale:** The global rules only permit merging to `main` when everything is 100% functional; a concurrent-session merge must regenerate derived artifacts so the committed banks/report don't drift from `main`.
- **Action:** Undergo the full verification/tests/validation process for the whole feature. Once 100% green, commit to GitHub — **do not push** — and merge the worktree onto `main`, stating: `E2E Eval (7/7) Complete: full regression green, merged to main.`

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| LLM-judge package | Config, contracts, deterministic proxy, OpenAI-compatible judge, hybrid factory | `utils/evaluation/llm_judge/{config,contracts,deterministic_judge,llm_judge,factory}.py` |
| LLM-judge unit tests | Hermetic: proxy stability, hybrid fallback, LLM JSON parsing | `utils/evaluation/llm_judge/tests/` |
| End-to-end scorer | 4 e2e metrics over the golden catalogue via `run_pipeline` | `utils/evaluation/score_e2e.py` |
| E2E scorer tests | Hermetic stubbed-pipeline tests + live subset | `utils/evaluation/tests/test_score_e2e.py` |
| E2E report + CLI | Report assembly (json/md) + `--e2e-eval` runner | `utils/evaluation/e2e_report.py`, `utils/evaluation/run_e2e_eval.py`, `main.py` |
| E2E report tests | Pure builder byte-stability + `--no-live` report | `utils/evaluation/tests/test_e2e_report.py` |
| Committed report | Checked-in deterministic baseline | `docs/evaluation/e2e-evaluation.{md,json}` |
| Backend endpoints | Read combined report + live-run SSE + synthesis/eval config groups | `api/services/evaluation.py`, `api/models.py`, `api/services/config.py`, `api/main.py` |
| Backend tests | Contract tests for read + SSE run | `api/tests/test_evaluation.py` |
| Frontend view | Evaluation dashboard + live-run button + client/types | `web/components/evaluation/`, `web/components/{workbench,header}/`, `web/lib/{api,types,fixtures}.ts` |
| Env config | `EVAL_LLM_*` + missing `SYNTHESIS_LLM_*` blocks | `.env.example` |
| Docs | Structure map, goals checkbox, README fix, changelog | `docs/structure.md`, `docs/goals.md`, `README.md`, `docs/changelog.jsonl` |
