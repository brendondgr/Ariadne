# Component-Level Evaluation — Implementation Plan (Wk 11–13)

## 1. Introduction

This plan turns Ariadne's existing pass/fail evaluation harnesses into **scored, reported
component metrics** for the three components the accepted proposal commits to scoring: the
**federated planner** and the two **query specialists** (Cypher/Neo4j, Gremlin). It
implements exactly the proposal's named metrics — planner (source-selection accuracy,
sub-question quality, unnecessary source calls, schema adherence) and specialists (query
validity, result correctness, safety-constraint adherence, latency) — and nothing outside
them. Synthesis faithfulness and cross-source end-to-end/LLM-judge scoring are the next
milestone (Wk 12–13) and are explicitly out of scope.

The governing discipline is unchanged: **the model drafts, deterministic code grades.**
Every metric here is computed by deterministic Python against snapshot-derived gold (ATT&CK
v19.0 / CAPEC v3.9), with LLM paths off by default so component scores are byte-reproducible.
We build on two existing assets — the 7-case planner scorer (`utils/planner/evaluation/`)
and the 53-question specialist golden banks (`utils/specialists/evalset/`) — rather than
rebuilding, adding the two named-but-unmeasured metrics (safety adherence, latency),
standard text-to-query framing (VA / EX), corpus expansion, statistical rigor (CIs), and a
single citable report.

## 2. Gaps & Unanswered Questions

- **Source for the expanded planner corpus.** The source plan says draw new cases "from the
  expanded Q&A catalogue," but the 120+ catalogue is a *later* milestone that does not exist
  yet. *Assumption*: derive the expanded planner corpus deterministically from the assets
  that DO exist — the 53 specialist golden questions (each single-source question → a
  one-source expected plan), the federated credential-theft gold (→ the two-source join
  case), plus explicitly authored adversarial cases (source-down → partial; out-of-scope →
  unsupported). This keeps "the planner is scored on the same questions the specialists are"
  and stays snapshot-derived/regenerable. Proceed on this assumption.
- **LLM drafter / composer availability.** Scoring "both drafters" needs the OpenAI-compatible
  endpoint (default `localhost:9090`), which is not guaranteed up in this environment.
  *Assumption*: the deterministic drafter is the reproducible **headline**; the LLM/hybrid
  drafter is scored **best-effort and guarded** — skipped with an honest note when the
  endpoint is unreachable, reported as a separate non-deterministic column when present.
  Proceed; do not block on the endpoint.
- **EX exact-set gold.** The golden questions carry only `must_include_*` subsets, not full
  result sets. *Assumption*: derive the full expected sets for EX from the already-committed
  `gold_bank.json` relationship maps (`technique_mitigations`, `group_techniques`, …) at
  bank-compile time, so exact-set EX stays snapshot-derived and never hand-keyed.
- **Latency n and live stack.** Percentiles need n≥200 per specialist and the live Docker
  stack. *Assumption*: reach n by repeat-running the catalogue subset; the harness is
  `@pytest.mark.live` and skips when the stack is down (same pattern as the golden suites).
  Raw latency numbers are environment-specific and are reported as an artifact, not asserted
  as a regression gate.
- **Stage-timing granularity.** Per-stage latency (draft→gate→execute→normalize) requires the
  specialist to record a `timing_ms` on each trace step; today only the `execute` step does.
  *Assumption*: add a minimal, additive `timing_ms` to the remaining trace steps in
  `base.py` (no behavioral change) — this is the only production-code touch in the plan.

## 3. Hierarchical Step-by-Step Instructions

### Step 1 — Shared statistics & evaluation scaffold
- **Locations**: new package `utils/evaluation/` with `__init__.py` and `stats.py`
  (functions: `percentiles` p50/p95/p99, `wilson_interval` binomial CI, `bootstrap_ci` for
  latency, `proportion` helper); tests in `utils/evaluation/tests/test_stats.py`.
- **Rationale**: every downstream metric (VA/EX proportions, latency percentiles) needs the
  same CI/percentile math; building it once as a pure, hermetic module keeps every scorer
  consistent and independently testable before any live data is involved.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run pytest utils/evaluation/tests/test_stats.py`, known-input percentile & CI
  assertions). Once validated, commit to GitHub stating: Component Evaluation (1/8) Complete:
  shared percentile/binomial/bootstrap statistics module with hermetic tests.

### Step 2 — Planner scorer: sub-question-quality sub-score + dev/holdout reporting + drafter plumbing
- **Locations**: `utils/planner/evaluation/scorer.py` (add `sub_question_quality` to
  `score_plan()`: expected sub-question count, correct per-source routing, dependency declared
  where multi-hop; fold into `aggregate()`); `utils/planner/evaluation/corpus.py`
  (`ExpectedCase`: add `expected_sub_questions`/`expects_dependency` fields, keep backward
  compatible); `utils/planner/evaluation/run_eval.py` (emit a dev-vs-holdout breakdown and an
  optional drafter selector); `utils/planner/tests/test_evaluation.py` (extend).
- **Rationale**: "sub-question quality" needs more than entity recall — it needs the
  decomposition check (right count, right routing, dependency where the gold is multi-hop).
  Adding it before corpus expansion means the new cases are scored on the complete metric set.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run pytest utils/planner/tests/test_evaluation.py` and
  `uv run python -m utils.planner.evaluation.run_eval` still 7/7). Once validated, commit to
  GitHub stating: Component Evaluation (2/8) Complete: planner sub-question-quality sub-score
  and dev/holdout reporting.

### Step 3 — Expand the planner corpus (7 → ~28), snapshot-derived
- **Locations**: new `utils/planner/evaluation/build_corpus.py` (generator: reads the
  specialist banks `utils/specialists/tests/golden/{attack,capec}_questions.json` and
  `federated_gold.json`, emits single-source and federated expected-plan cases into
  `expected_plans/`); the 7 existing curated cases retained; a frozen dev/holdout split marker
  on every case; `utils/planner/tests/test_evaluation.py` (assert corpus ≥ 25, split frozen,
  generated == committed).
- **Rationale**: a 7-case corpus is too small to be statistically defensible; deriving cases
  from the specialist banks (never hand-keyed) makes the planner and specialists answer the
  same questions and keeps regeneration disciplined.
- **Action**: Undergo the verification/tests/validation process for this phase (regenerate,
  `uv run python -m utils.planner.evaluation.run_eval` green on the expanded corpus, holdout
  reported separately). Once validated, commit to GitHub stating: Component Evaluation (3/8)
  Complete: expanded planner corpus to ~28 snapshot-derived cases with frozen holdout.

### Step 4 — Specialist Query Validity (VA) scorer
- **Locations**: new `utils/specialists/evalset/score_validity.py` (draft+gate each bank
  question via the deterministic builder + validator, compute **first-pass VA** and
  **post-retry VA** per specialist per tier from the gate traces, with Wilson CIs — hermetic,
  no DB); tests in `utils/specialists/tests/test_score_validity.py`.
- **Rationale**: VA is the "does it parse and conform to the schema/grammar" metric; because
  the gate runs before any DB call, VA is fully hermetic and reproducible, and near-ceiling VA
  is the evidence that the deterministic builder sidesteps generation-hallucination.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run pytest utils/specialists/tests/test_score_validity.py`). Once validated, commit to
  GitHub stating: Component Evaluation (4/8) Complete: hermetic first-pass/post-retry query
  validity scorer with CIs.

### Step 5 — EX gold targets + Execution Accuracy scorer + error taxonomy
- **Locations**: `utils/specialists/evalset/questions.py` + `compile_banks.py` (emit full
  expected id/related sets `ex_expected` per relationship-template question, derived from
  `gold_bank.json`); regenerate the committed banks; new
  `utils/specialists/evalset/score_execution.py` (live: run each question, compute
  **exact-set-match EX** and **precision/recall EX** vs the full gold set, bucket every failure
  into an error taxonomy: wrong-label / missing-hop / over-broad / wrong-join-value /
  empty-when-nonempty); tests `utils/specialists/tests/test_score_execution.py`
  (`@pytest.mark.live`, skips when stack down; a hermetic taxonomy-bucketing unit test with
  synthetic results).
- **Rationale**: EX (result-set correctness, phrasing-invariant) is the community-standard
  correctness metric; partial credit + a taxonomy turn a pass/fail bank into diagnostic
  findings and make near-misses visible.
- **Action**: Undergo the verification/tests/validation process for this phase (regenerate
  banks; hermetic taxonomy test always; live EX scorer when the stack is up). Once validated,
  commit to GitHub stating: Component Evaluation (5/8) Complete: snapshot-derived EX gold,
  exact/partial execution-accuracy scoring, and error taxonomy.

### Step 6 — Safety-constraint adherence audit + adversarial probes
- **Locations**: new `utils/specialists/evalset/score_safety.py` (per executed query: assert
  read-only, LIMIT present ≤ card cap, depth ≤ card cap, timeout ≤ card cap; report an
  adherence rate; a single breach is a hard fail reported separately); new adversarial-probe
  fixtures `utils/specialists/tests/fixtures/adversarial_probes.py` (drafts that tempt a write
  or unbounded scan) asserting the gate blocks 100%; tests
  `utils/specialists/tests/test_score_safety.py` (hermetic — probes go through the validator
  directly).
- **Rationale**: safety adherence is named in the proposal but never scored; the gate is the
  enforcement point, so probing it directly with malicious drafts is the honest hermetic test,
  and 100%-block is the headline safety claim.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run pytest utils/specialists/tests/test_score_safety.py`; probes 100% blocked). Once
  validated, commit to GitHub stating: Component Evaluation (6/8) Complete: bounded-execution
  safety-adherence score and adversarial gate probes.

### Step 7 — Per-stage timing instrumentation + latency harness
- **Locations**: `utils/specialists/base.py` (additively record `timing_ms` on the gate /
  assess / normalize trace steps, matching the existing `execute` timing — no behavioral
  change); new `utils/specialists/evalset/latency.py` (repeat-run the catalogue to n≥200 per
  specialist, discard warm-up, compute p50/p95/p99 + bootstrap CIs, segment by
  specialist/tier and cold-vs-warm, break down by stage, report the p50/p99 gap); tests
  `utils/specialists/tests/test_latency.py` (hermetic small-n harness shape test + a live n≥200
  run marked `@pytest.mark.live`).
- **Rationale**: latency is right-skewed, so means mislead; percentiles segmented and staged
  point at *which* stage/segment is slow. The stage timing must exist on the trace before the
  harness can attribute a tail.
- **Action**: Undergo the verification/tests/validation process for this phase (existing
  specialist/pipeline trace tests still green after the additive timing; hermetic latency shape
  test; live percentile run when stack up). Once validated, commit to GitHub stating: Component
  Evaluation (7/8) Complete: per-stage timing hooks and segmented latency-percentile harness.

### Step 8 — Unified report generator, CLI entry, docs, roadmap, full regression, merge
- **Locations**: new `utils/evaluation/component_report.py` (assemble planner ×4 + each
  specialist ×4 into `docs/evaluation/component-evaluation.md` + `.json` with dev/holdout, CIs,
  tiered breakdown, taxonomy counts, latency tables, and a "what this diagnoses" section) and
  `utils/evaluation/run_component_eval.py` (CLI orchestrating all scorers); a `--component-eval`
  hook wired in `main.py`; `docs/structure.md` (document `utils/evaluation/`), `docs/goals.md`
  and `README.md` (Wk 11–13 row status), `docs/changelog.jsonl`; report-shape test
  `utils/evaluation/tests/test_component_report.py` (hermetic, synthetic scores).
- **Rationale**: one citable artifact is the deliverable ReliaQuest and the pitch reference;
  wiring it behind one CLI + report keeps the numbers reproducible and the whole suite one
  green bar.
- **Action**: Undergo the verification/tests/validation process for this phase (full
  regression `uv run pytest utils/ api/` green incl. new hermetic tests and live suites where
  the stack is up; report generates). Once validated, commit to GitHub stating: Component
  Evaluation (8/8) Complete: unified component-evaluation report, CLI, docs, and roadmap;
  merge worktree to main.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Shared stats module | Percentiles, Wilson & bootstrap CIs | `utils/evaluation/stats.py` |
| Stats unit tests | Known-input CI/percentile checks | `utils/evaluation/tests/test_stats.py` |
| Planner sub-question-quality | Decomposition/routing/dependency sub-score | `utils/planner/evaluation/scorer.py`, `corpus.py` |
| Expanded planner corpus | ~28 snapshot-derived cases + generator | `utils/planner/evaluation/build_corpus.py`, `expected_plans/` |
| Planner eval tests | Metric + corpus + split tests | `utils/planner/tests/test_evaluation.py` |
| Query-validity (VA) scorer | First-pass/post-retry VA + CIs (hermetic) | `utils/specialists/evalset/score_validity.py` |
| EX gold + scorer + taxonomy | Full-set gold, exact/partial EX, failure buckets | `utils/specialists/evalset/{questions.py,compile_banks.py,score_execution.py}` |
| Safety-adherence scorer + probes | Bounded-execution audit, 100%-block probes | `utils/specialists/evalset/score_safety.py`, `tests/fixtures/adversarial_probes.py` |
| Stage timing + latency harness | Per-stage `timing_ms`, p50/p95/p99, segmented | `utils/specialists/base.py`, `utils/specialists/evalset/latency.py` |
| Component report + CLI | Markdown + JSON report, `--component-eval` | `utils/evaluation/{component_report.py,run_component_eval.py}`, `main.py` |
| Specialist scorer tests | VA/EX/safety/latency unit + live tests | `utils/specialists/tests/test_{score_validity,score_execution,score_safety,latency}.py` |
| Report-shape test | Hermetic report assembly test | `utils/evaluation/tests/test_component_report.py` |
| Evaluation artifact | The citable report | `docs/evaluation/component-evaluation.md` + `.json` |
| Docs & roadmap | structure/goals/README/changelog updates | `docs/structure.md`, `docs/goals.md`, `README.md`, `docs/changelog.jsonl` |
