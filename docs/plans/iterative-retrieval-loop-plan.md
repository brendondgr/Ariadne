# Iterative Retrieval Loop Plan

> **Commit policy:** Per the standing user directive, every step ends with a local `git commit` + a `docs/changelog.jsonl` entry — **never push**.

> **Scope note:** This adds a *bounded evidence-gathering cycle* between the specialists and synthesis. It does not change the query-safety model — specialists still fill read-only templates through the existing gates. Only the *set* of queries becomes dynamic.

## 1. Introduction

Today the pipeline is plan-once-then-execute: `check_cards → probe → plan → specialists → bundle → synthesize → END` (`utils/orchestration/main.py`). The `PlanningAgent` fixes the full set of sub-questions up front, the specialist subgraph walks that fixed list in dependency order (`utils/orchestration/agents/specialists/graph.py`), and synthesis is terminal. A question whose answer only becomes reachable *after* seeing intermediate results — e.g. "expand the techniques these CAPEC patterns map to, then pull the mitigations for whatever we find" — cannot be fully answered, because nothing feeds discovered nodes back into planning.

This plan closes that loop. After the specialists run, a new **`assess`** node judges whether the accumulated evidence answers the original question. If not, it feeds the evidence gathered so far (plus the entities/join-keys discovered this hop) back into a **re-plan**, which emits only the *missing* sub-questions; those run through the same specialists, and the cycle repeats. A hop counter caps the loop at **5 iterations**, after which the pipeline is forced out to synthesis regardless. The loop reuses the machinery already in place — LangGraph `StateGraph`, the `operator.add` reducers on `results`/`by_id`, the `cursor`, and the generous `recursion_limit` — so the change is additive and gated behind config for a safe rollout.

## 2. Gaps & Unanswered Questions

- **Definition of "enough".** The stopping predicate needs a precise rule. *Assumption*: the deterministic default declares sufficiency when (a) every declared cross-source join in the plan has resolved to at least one record, **and** (b) the most recent hop discovered no new join-keys or entities (novelty exhausted). Either condition failing (with hops remaining) triggers a re-plan.
- **Deterministic vs. LLM sufficiency judge.** *Assumption*: default to the deterministic novelty/join-closure check (keeps the LLM-off build byte-reproducible, consistent with `utils/evaluation/llm_judge/`'s deterministic proxy). An LLM sufficiency critic is opt-in behind `ORCH_ASSESS_MODE=llm` and, when on, produces a natural-language "what's missing" string that seeds the re-plan.
- **Re-plan de-duplication.** Re-planning must not re-ask answered sub-questions. *Assumption*: dedupe candidate sub-questions against the answered set by the tuple `(source, sorted(entities), normalized_text)`; already-answered or already-visited seeds are dropped before the hop runs.
- **Backward compatibility with committed goldens.** The snapshot-derived component/e2e baselines assume a single pass. *Assumption*: ship with the loop default **off** (`ORCH_MAX_HOPS=1`, reproducing today's behavior exactly), land all code + tests, then flip the default to `5` only in Step 7 after multi-hop goldens are pinned.
- **Expansion strategy for the first cut.** *Assumption*: the first expansion is deterministic **join-key chasing** (enqueue the other source for join-keys surfaced this hop). Relevance-scored neighbor/relation expansion (Think-on-Graph style) is left as a follow-on the re-planner can grow into, not part of this plan.
- **Per-hop persistence in the conversation store.** Whether each hop's intermediate evidence should be persisted to `data/conversations.sqlite3` for replay is unresolved and product-facing. **Human intervention is needed to answer this question.**
- **LLM critic model availability.** The controlled-LLM comparison hardware is not always attached; if `llm_enabled` is false and `ORCH_ASSESS_MODE=llm` is requested, behavior must degrade cleanly. *Assumption*: fall back to the deterministic judge and record the fallback in the trace; confirm this is acceptable. **Human intervention is needed to confirm the fallback policy.**

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Config knobs + loop guardrails
- **Locations**: `utils/orchestration/config.py` (`OrchestrationConfig`: add `max_hops: int = 1` read from `ORCH_MAX_HOPS`, and `assess_mode: str = "deterministic"` read from `ORCH_ASSESS_MODE`; extend `from_env`). Reuse the existing `env_int`/`_env_flag` helpers.
- **Rationale**: Every downstream node reads these. Introducing the hop cap and judge-mode switch first — defaulting to `max_hops=1` — means the whole feature can land dark, changing no observable behavior until deliberately enabled. The cap plus the existing `PIPELINE_TIMEOUT_S` deadline and `recursion_limit` form the triple guard against runaway loops.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit locally with a `docs/changelog.jsonl` entry (**never push**): Iterative Retrieval Loop (1/8) Complete: Added `max_hops` and `assess_mode` orchestration config with env plumbing.

### Step 2: Extend pipeline state for the cycle
- **Locations**: `utils/orchestration/state.py` (`PipelineState`: add `hop: int`, `frontier` and `visited` as reduced collections, and an `assessment` field carrying the last verdict; add a set-union reducer alongside the existing `merge_dicts`). Keep the existing `results`/`by_id`/`cursor` accumulators unchanged.
- **Rationale**: The loop needs a hop counter, a `frontier` of entities discovered-but-not-yet-expanded, and a `visited` set of `(entity, source)` pairs to prevent re-querying and cycles. Wrapping them in the graph state (not the frozen contracts) keeps the 98 contract-shape tests and the SSE `to_dict()` JSON stable, matching the state module's stated design.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit locally with a `docs/changelog.jsonl` entry (**never push**): Iterative Retrieval Loop (2/8) Complete: Added hop/frontier/visited/assessment envelope with reducers to `PipelineState`.

### Step 3: Evidence-delta extraction (frontier & visited)
- **Locations**: new `utils/orchestration/agents/assess/frontier.py` (`extract_frontier(results, plan)`, `update_visited(visited, results)`), reading `utils/specialists/contracts.py::SpecialistResult`, `utils/specialists/federation.py::FederatedEvidence`, and the `join_key` fields from `utils/planner/schema.py::SubQuestion`.
- **Rationale**: The assessment and the re-planner both need a precise, deterministic answer to "what new nodes and join-keys did this hop surface?" Isolating this in a pure, testable helper keeps the graph nodes thin and the novelty check honest.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit locally with a `docs/changelog.jsonl` entry (**never push**): Iterative Retrieval Loop (3/8) Complete: Added deterministic frontier/visited extraction from specialist evidence.

### Step 4: The `assess` node and sufficiency policy
- **Locations**: new package `utils/orchestration/agents/assess/` — `contracts.py` (`Assessment`: `sufficient: bool`, `gaps: list[str]`, `missing_entities: list[str]`), `policy.py` (deterministic join-closure + novelty predicate; optional LLM critic wired through `utils/evaluation/llm_judge/factory.py`), and `node.py` (the `assess` graph node that reads `hop`/`frontier`/`plan`/evidence and writes an `Assessment`). Honors `OrchestrationConfig.max_hops` and `assess_mode` from Step 1.
- **Rationale**: This is the decision point the whole feature turns on. Keeping the predicate deterministic by default preserves reproducibility; the hop-cap short-circuit (force `sufficient=True` when `hop >= max_hops`) guarantees termination even if the predicate never converges.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit locally with a `docs/changelog.jsonl` entry (**never push**): Iterative Retrieval Loop (4/8) Complete: Added the `assess` node with deterministic sufficiency policy and optional LLM critic.

### Step 5: Re-plan entry on the planner
- **Locations**: `utils/planner/agent.py` (`PlanningAgent.plan` gains an optional prior-context argument, or a sibling `replan(request, evidence, frontier, gaps)`), `utils/orchestration/agents/planner/graph.py` (`build_planning_graph` accepts prior evidence/feedback in its input state), `utils/planner/drafter.py` and `utils/planner/llm_drafter.py` (drafters incorporate answered sub-questions + discovered nodes + gaps and emit only *new* sub-questions), and `utils/planner/schema.py` (`SubQuestion` gains a `hop` tag; add a plan-merge/dedupe helper keyed on `(source, sorted(entities), normalized_text)`).
- **Rationale**: Re-planning is the "go rationalize what else it needs" behavior. It must consume accumulated evidence and the frontier, drop anything already answered/visited, and route only the remaining gaps — otherwise the loop repeats work or never shrinks.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit locally with a `docs/changelog.jsonl` entry (**never push**): Iterative Retrieval Loop (5/8) Complete: Added evidence-aware re-plan entry that emits only missing, de-duplicated sub-questions.

### Step 6: Wire the loop into the super-graph
- **Locations**: `utils/orchestration/main.py` (`build_pipeline_graph`): add an `assess` node after `bundle`; replace the straight `bundle → synthesize` edge with `bundle → assess`; add a conditional edge `route_sufficiency` sending `assess → synthesize` (sufficient or hop-capped) or `assess → replan`; wire `replan → announce_querying → specialists` and increment `hop`; advance `cursor` so each hop runs only the newly appended sub-questions. Update `iter_pipeline`'s documented event order.
- **Rationale**: This physically closes the cycle at the `specialists → bundle → assess → plan` boundary described in the architecture. The accumulate-reducers already merge per-hop deltas, so the wiring is mostly edges and the hop increment; `recursion_limit=200` remains the backstop.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit locally with a `docs/changelog.jsonl` entry (**never push**): Iterative Retrieval Loop (6/8) Complete: Closed the assess→re-plan→specialists cycle in the pipeline super-graph.

### Step 7: Streaming events + evaluation rollout (flip the default)
- **Locations**: `utils/orchestration/main.py` (emit `assess` and `hop`/`replan` stream events via the writer), `api/` SSE layer and `web/components/` (surface a hop indicator + sufficiency verdict, reusing the live-animation pattern); then `utils/evaluation/score_e2e.py`, `utils/specialists/evalset/`, `docs/evaluation/*` and the snapshot gold — add multi-hop cases, confirm `ORCH_MAX_HOPS=1` still reproduces the pinned baselines byte-for-byte, re-pin multi-hop goldens, and change the `ORCH_MAX_HOPS` default to `5`.
- **Rationale**: The loop must be *inspectable* (analyst can see each hop) and *evaluated* (multi-hop questions prove it works) before it becomes the default. Gating the default flip behind re-pinned goldens protects the committed reproducibility story.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit locally with a `docs/changelog.jsonl` entry (**never push**): Iterative Retrieval Loop (7/8) Complete: Surfaced hop events in CLI/web, added multi-hop eval cases, and defaulted `ORCH_MAX_HOPS` to 5.

### Step 8: Regression, termination proofs, and docs
- **Locations**: tests under `utils/orchestration/agents/assess/tests/`, `utils/orchestration/tests/`, and `utils/planner/tests/`; regenerate `docs/evaluation/component-evaluation.{md,json}` and `docs/evaluation/e2e-evaluation.{md,json}`; update `docs/structure.md`, `docs/specialist_agents.md`/`docs/planner_agent.md`, and add `docs/iterative-retrieval-loop.md`; append the standard `docs/changelog.jsonl` entries.
- **Rationale**: The dominant risk of an iterative retriever is non-termination and overspending; explicit tests for the hop cap, deadline exit, novelty stop, and re-plan dedup are the safety net. Documentation keeps the four-component migration story coherent.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, commit locally with a `docs/changelog.jsonl` entry (**never push**): Iterative Retrieval Loop (8/8) Complete: Full regression green, termination proven by tests, evaluation artifacts and docs regenerated.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Loop config knobs | `max_hops` / `assess_mode` with env plumbing and defaults | `utils/orchestration/config.py` |
| Loop state envelope | `hop`, `frontier`, `visited`, `assessment` with reducers | `utils/orchestration/state.py` |
| Frontier/visited extractor | Pure helpers deriving new nodes + join-keys per hop | `utils/orchestration/agents/assess/frontier.py` |
| Assess node + policy | Sufficiency contract, deterministic + optional LLM judge, hop-cap short-circuit | `utils/orchestration/agents/assess/{contracts,policy,node}.py` |
| Re-plan entry | Evidence-aware planner path emitting only de-duplicated missing sub-questions | `utils/planner/agent.py`, `utils/planner/drafter.py`, `utils/planner/llm_drafter.py`, `utils/orchestration/agents/planner/graph.py` |
| Sub-question hop tagging | `hop` field + plan-merge/dedupe helper | `utils/planner/schema.py` |
| Loop wiring | `assess`/`replan` nodes and conditional cycle edges in the super-graph | `utils/orchestration/main.py` |
| Hop stream events + UI | `assess`/`hop` events surfaced in CLI and web workbench | `utils/orchestration/main.py`, `api/`, `web/components/` |
| Multi-hop eval cases + reports | New cases + regenerated component/e2e reports, re-pinned goldens | `utils/evaluation/`, `utils/specialists/evalset/`, `docs/evaluation/` |
| Assess unit tests | Sufficient / insufficient / hop-cap / novelty-stop cases (small fixtures) | `utils/orchestration/agents/assess/tests/test_policy.py` |
| Frontier extractor tests | New-node/join-key extraction on a minimal evidence fixture | `utils/orchestration/agents/assess/tests/test_frontier.py` |
| Loop integration test | A 2-hop question that fails single-pass and passes with the loop; asserts termination ≤ 5 hops | `utils/orchestration/tests/test_iterative_loop.py` |
| Re-plan dedup test | Confirms answered sub-questions are not re-issued | `utils/planner/tests/test_replan_dedup.py` |
| Feature doc | How the loop works, config, guardrails | `docs/iterative-retrieval-loop.md` |
