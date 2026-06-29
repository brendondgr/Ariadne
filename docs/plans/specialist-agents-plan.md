# Source-Specific Query Specialists — Implementation Plan

**Project:** Ariadne (FSU × ReliaQuest, Challenge 3 — Knowledge Graph Integration)
**Roadmap slots:** Wk 7–8 Cypher specialist (ATT&CK/Neo4j) and Wk 8–9 Gremlin specialist (CAPEC/Gremlin).
**Source briefing:** `~/Documents/Plans/Ariadne/1.specialist-agents-plan.md` (the two specialists, one shared scaffold, four swap points).

---

## 1. Introduction

This plan builds the two **source-specific query specialists** that sit between the existing
federated **planning agent** (`utils/planner/`) and the future synthesis agent. The Cypher
specialist queries MITRE ATT&CK in Neo4j; the Gremlin specialist queries CAPEC in a Gremlin
Server. Each receives a *filtered task* (one planner sub-question) plus its *source card*,
drafts a bounded read-only query, validates it deterministically **before** touching the
database, executes it under hard caps, self-assesses the result, normalizes the evidence into a
**shared evidence schema** with full provenance, and hands that evidence off. The synthesis
agent is out of scope here and is honored only as an output **interface contract**.

The approach follows the briefing's architecture literally: **one shared scaffold, four
language-specific swap points** (query builder, validator, connector, normalizer). It also
mirrors the planning agent's proven discipline — *the model drafts, deterministic code grades* —
so a **deterministic query builder** is the always-available default (gate-valid by
construction) and the LLM is an optional seam reserved for the soft "did this answer the task"
judgment. We co-author the shared scaffold and the input/output contracts once (Phase 1), then
bring each specialist up **green against its real, already-running database in isolation**
(Phases 2–3) before weaving them into the planner workflow (Phase 4) and exposing the whole
flow in a step-by-step notebook (Phase 5).

---

## 2. Gaps & Unanswered Questions

- **Connection endpoint source of truth.** The enriched source cards carry a stale
  `connection.uri` (`bolt://localhost:7687`, `ws://localhost:8182`), but the planner actually
  connects via `PlannerConfig`/`.env` (`bolt://localhost:5456`, `ws://localhost:6455`).
  *Assumption*: the specialists reuse the same env-driven config (a new `SpecialistConfig` that
  reads `NEO4J_*`/`GREMLIN_*` exactly like `PlannerConfig`), **not** the card's `connection.uri`.
  The card remains the *schema/safety* oracle only.
- **LLM availability.** No Anthropic/OpenAI SDK is installed; the planner uses a raw HTTP
  OpenAI-compatible endpoint (`localhost:9090`) that may be offline. *Assumption*: deterministic
  query building + deterministic assessment are the always-on path; the LLM query/assess seam is
  optional, off by default, and behind a protocol (mirroring `HybridDrafter`). Tests and the
  notebook never depend on the LLM being up.
- **CAPEC numeric id.** CAPEC `AttackPattern` nodes expose `id="capec:attack-pattern:N"` but no
  bare `CAPEC-N` property. *Assumption*: the Gremlin normalizer derives the `CAPEC-N` display id
  from the `id` string; provenance keeps the raw backend id.
- **Join-key direction & taxonomy filter.** Live data confirms `MAPS_TO` reaches both `ATTACK`
  and `WASC` `TaxonomyEntry` nodes, and `entry_id` lacks the `T` prefix. *Assumption*: when a
  sub-question carries `join_key="attack-technique-id"`, the Gremlin path filters
  `taxonomy_name == "ATTACK"` and the normalizer emits the join value with the `T` prefix; the
  Cypher path matches ATT&CK ids on the `attack_id` property (e.g. `T1047`).
- **GraphSON list-wrapping.** Gremlin `valueMap(true)` returns every property as a list and
  injects `T.id`/`T.label` enum keys. *Assumption*: the Gremlin normalizer unwraps single-element
  lists and resolves the enum keys deterministically (prefer `project()`/`valueMap()` shapes that
  are stable to parse).
- **Orphan ATT&CK labels** (`Matrix`, `DataComponent`) flagged in the briefing. *Assumption*:
  they are valid resolution targets only if present in the card's `node_labels` (they are), and
  the validator treats label membership in the card as the oracle; no special-casing.
- **Retry cap value.** *Assumption*: assessment redraft cap = 2 (briefing's 2–3 range, planner
  uses 3), tunable via `SPECIALIST_MAX_RETRIES`.
- **Synthesis output shape.** The synthesis agent does not exist yet. *Human intervention may be
  needed later* to finalize cross-source join ergonomics, but the briefing fixes the required
  fields (validated query, normalized records, grounded summary, evaluator traces, per-record
  provenance), which is enough to lock the contract now.

---

## 3. Hierarchical Step-by-Step Instructions

> Validation note: the global rules say "push at every step," but for this engagement the user
> directive is **commit only, do not push**. Every step below ends with a *local commit* on the
> `specialist-agents` branch; the branch is merged into `main` at the end (Step 6). Each step
> also appends a `docs/changelog.jsonl` entry.

### Step 1 — Shared scaffold, contracts & evidence schema (build once)

- **Locations (new package `utils/specialists/`):**
  - `contracts.py` — `SpecialistTask` (from a planner `SubQuestion` + dataset), `Provenance`,
    `EvidenceRecord`, `Evidence`, `EvaluatorTrace`, `SpecialistResult`. Pure dataclasses with
    `to_dict`/`from_dict` (mirrors `utils/planner/schema.py`).
  - `config.py` — `SpecialistConfig.from_env()` reading `NEO4J_*`/`GREMLIN_*` and
    `SPECIALIST_MAX_RETRIES`, `SPECIALIST_QUERY_TIMEOUT_MS`, `SPECIALIST_LLM_*` via
    `utils.config` helpers.
  - `evidence.py` — `emit_record(...)`, `check_contract(result)` (deterministic: required fields
    + provenance present; the "keep bad evidence out of synthesis" gate).
  - `resolve.py` — **shared** resolve-to-schema: map a task's `entities` to real card
    labels/edges, extract `seed_ids` from the task text (ATT&CK `T####[.###]`, `M####`, `G####`,
    `S####`; CAPEC `CAPEC-####`), pair an ATT&CK id with its STIX type, and surface the
    canonical join target. Parameterized only by the source card (briefing §2.3 "shared code,
    different data").
  - `validation.py` — **shared** validator base: `QueryDraft`, `ValidationResult`, read-only
    enforcement against `safety.disallowed_*`, limit/timeout injection, and the contract check
    hook. Language parser + traversal/depth rules are abstract (filled by each swap point).
  - `base.py` — `QuerySpecialist` scaffold implementing the briefing §3 loop
    (intake → resolve → draft → **pre-run gate** → execute → **assess** → normalize → handoff),
    a capped redraft loop, and `EvaluatorTrace` logging. Holds four injected swap points
    (`QueryBuilder`, `QueryValidator`, `Connector`, `Normalizer`) + the card.
  - `errors.py` — `SpecialistError`, `ValidationError`, `ExecutionError`, `IntakeError`.
  - `__init__.py` — package exports.
  - `cypher/__init__.py`, `gremlin/__init__.py` — empty subpackage placeholders for Phases 2–3.
  - Tests: `utils/specialists/tests/_fixtures.py`, `test_contracts.py`, `test_evidence.py`,
    `test_resolve.py`, `test_validation_base.py`, plus a `tests/fixtures/source_cards/` copy of
    the committed planner fixtures.
- **Rationale:** The contract boundary between "shared" and "language-specific" must be
  stress-tested from both directions before either engine is built (briefing §1). Locking the
  evidence schema + provenance fields now is what lets synthesis join later; building the
  pre-run gate and contract check as shared deterministic Python is the briefing's
  "never cut two checks" rule (§4.2).
- **Action:** Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest utils/specialists/tests/`). Once validated, commit to GitHub **(do
  not push)** stating: Specialist Agents (1/6) Complete: Shared scaffold, input/output contracts,
  shared evidence schema, resolver, and deterministic validator base with unit tests.

### Step 2 — Cypher specialist (ATT&CK / Neo4j) in isolation

- **Locations (`utils/specialists/cypher/`):**
  - `builder.py` — `CypherQueryBuilder`: bounded `MATCH` templates keyed by the resolved task
    (single-node lookup by `attack_id`; technique→mitigations via `(t:Technique)<-[:MITIGATES]-
    (m:Mitigation)`; group→techniques via `USES`; tactic→techniques; generic label scan). Emits
    parameterized Cypher; no string interpolation of values.
  - `validator.py` — `CypherValidator(QueryValidator)`: single-statement parse, must start
    `MATCH`/`OPTIONAL MATCH`/`WITH` and contain `RETURN`; reject `safety.disallowed_clauses`
    (word-boundary, case-insensitive); every `:Label` ∈ card `node_labels`, every `[:REL]` ∈
    card `relationship_types`; STIX-type pairing for id matches; inject/clamp `LIMIT
    max_result_rows`.
  - `connector.py` — `CypherConnector`: a read-only Neo4j driver (`default_access_mode=READ`,
    `tx` timeout from limits), reusing `SpecialistConfig` endpoints; returns plain row dicts;
    enforces a belt-and-suspenders row cap.
  - `normalizer.py` — `CypherNormalizer`: rows → `EvidenceRecord`s (primary_id = `attack_id`,
    id_scheme `attack-id`, related mitigations/techniques nested), provenance per record.
  - `specialist.py` — `CypherSpecialist` = scaffold + the four swap points + the ATT&CK card;
    `build_cypher_specialist(config)` factory.
  - Tests: `test_cypher_validator.py` (pure-unit, negative cases: write clause, unknown label,
    missing RETURN, over-limit), `test_cypher_specialist.py` (unit with a fake connector + a
    `@pytest.mark.integration`/`skipif` live test hitting Neo4j on the running stack).
- **Rationale:** Neo4j rejects some malformed Cypher for us, so the Cypher side is the lighter
  validator; bringing it up first on the already-loaded ATT&CK graph (2611 nodes, `T1047` →
  M1038/M1040/M1018/M1026 confirmed) proves the shared scaffold end-to-end before the harder
  Gremlin side (briefing §6 Phase 1).
- **Action:** Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest utils/specialists/tests/` + the live integration test). Once
  validated, commit to GitHub **(do not push)** stating: Specialist Agents (2/6) Complete: Cypher
  specialist (builder, validator, connector, normalizer) green against the live ATT&CK Neo4j graph
  with pre-run gate and evidence-contract checks enforced.

### Step 3 — Gremlin specialist (CAPEC / Gremlin Server) in isolation

- **Locations (`utils/specialists/gremlin/`):**
  - `builder.py` — `GremlinQueryBuilder`: bounded `g.V()` traversals keyed by the resolved task
    (CAPEC lookup by `id`; attack-pattern→weaknesses via `out('EXPLOITS_WEAKNESS')`; →mitigations;
    →execution steps; the **join path** `out('MAPS_TO').has('taxonomy_name','ATTACK')`). Every
    traversal ends with an injected `.limit()`.
  - `validator.py` — `GremlinValidator(QueryValidator)`: must start `g.V(`/`g.E(`; reject
    `safety.disallowed_steps`; every `hasLabel('X')` ∈ card `node_labels`; every `out/in/both
    ('R')` ∈ card `relationship_types`; **edge-direction & endpoint check** against
    `safety.allowed_edge_patterns`; enforce a present `.limit(n)` with `n ≤ max_result_rows` and
    traversal depth ≤ `max_traversal_depth` (inject if missing). This is the heavier validator
    (briefing §4 point 2).
  - `connector.py` — `GremlinConnector`: TinkerPop client (`GraphSONSerializersV3d0`),
    `bindings` for values, `.all().result(timeout=…)`; returns raw GraphSON maps.
  - `normalizer.py` — `GremlinNormalizer`: unwrap single-element lists, resolve `T.id`/`T.label`,
    derive `CAPEC-N` from `id`, emit join values (`T`-prefixed `entry_id`) for `ATTACK`
    taxonomy entries; provenance per record.
  - `specialist.py` — `GremlinSpecialist` + `build_gremlin_specialist(config)`.
  - Tests: `test_gremlin_validator.py` (negative cases: `addV`/`drop`/`property`, unknown label,
    wrong edge direction, missing/over `.limit`, over-depth), `test_gremlin_specialist.py` (unit
    with a fake connector + live `skipif` test on the running CAPEC graph, 4888 nodes).
- **Rationale:** Property-graph traversals have no built-in schema validation and can multiply
  exponentially without explicit caps, so this validator must enforce labels, edge direction, and
  depth/limit in application logic (briefing §4). The live `MAPS_TO` data mixing `ATTACK`/`WASC`
  taxonomies makes the taxonomy filter a correctness requirement, not a nicety.
- **Action:** Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest utils/specialists/tests/` + the live integration test). Once
  validated, commit to GitHub **(do not push)** stating: Specialist Agents (3/6) Complete: Gremlin
  specialist green against the live CAPEC graph with label/edge-direction validation, depth/limit
  caps injected, and ATTACK-taxonomy join values normalized.

### Step 4 — Weave specialists into the planner workflow (federation)

- **Locations:**
  - `utils/specialists/federation.py` — `SpecialistRouter`/`run_plan(plan, config)`: take a
    `utils.planner.schema.Plan`, dispatch each `SubQuestion` to the specialist matching
    `sq.source` (build per dataset once), collect `SpecialistResult`s, and assemble a
    `FederatedEvidence` bundle keyed by `join_key` for the (future) synthesis agent. Skip
    sub-questions whose source is unsupported/down; preserve provenance.
  - `utils/specialists/cli.py` — `run_query_command(question, …)`: plan the question with
    `PlanningAgent`, then run the specialists over the plan and print each validated query,
    record counts, grounded summary, and the evidence JSON.
  - `main.py` — add a `--query "<question>"` flag (and `--query-llm`) dispatching to
    `run_query_command`, mirroring the existing `--plan` wiring (`job_type`, dispatch branch).
  - Tests: `utils/specialists/tests/test_federation.py` (unit: a stub plan over fake specialists
    routes correctly, marks down sources, bundles by join key; one `skipif` live end-to-end).
- **Rationale:** Individual specialists in isolation do not prove the pipeline; routing a real
  planner `Plan` through them surfaces join-key and format mismatches (briefing §6 Phase 3). The
  handoff is **evidence, not prose** — the cross-source join stays the synthesis agent's job.
- **Action:** Undergo the verification/tests/validation process for this phase (full
  `uv run python -m pytest utils/specialists/tests/` + `uv run main.py --query "<credential-theft
  question>"` against the live stack). Once validated, commit to GitHub **(do not push)** stating:
  Specialist Agents (4/6) Complete: Federation router + `--query` CLI route a planner plan
  through both specialists end-to-end with provenance intact.

### Step 5 — Step-by-step notebook & documentation

- **Locations:**
  - `notebooks/planning-schematic-agents.ipynb` — the requested runnable demo. Sections:
    (1) repo-root path setup + `.env`; (2) live-source probe; (3) inspect both source cards
    (the "schematic" — labels/edges/safety/join key); (4) plan the credential-theft question with
    the planning agent; (5) show the Cypher specialist on its sub-question — resolved params,
    drafted query, **pre-run gate trace**, execution, normalized evidence; (6) same for the
    Gremlin specialist incl. the `MAPS_TO`/ATTACK join path; (7) run the full federation over the
    plan and print the evidence bundle JSON; (8) deliberately invalid drafts to show the gate
    rejecting writes/over-limit/wrong-direction. Executed headlessly to verify exit 0.
  - `docs/specialist_agents.md` — contract, the four swap points, validation table, evidence
    schema, config table, CLI/notebook usage (mirrors `docs/planner_agent.md`).
  - `README.md`, `docs/structure.md`, `docs/goals.md` — document `utils/specialists/`, the
    `--query` command, and check off the Wk 7–8 / Wk 8–9 roadmap rows.
- **Rationale:** The user explicitly needs a notebook that shows the full workflow step-by-step;
  docs make the four-swap-point design legible and check off the roadmap milestones.
- **Action:** Undergo the verification/tests/validation process for this phase (execute the
  notebook headlessly; `uv run python -m pytest utils/specialists/tests/utils/planner/tests/`).
  Once validated, commit to GitHub **(do not push)** stating: Specialist Agents (5/6) Complete:
  `planning-schematic-agents.ipynb` runnable end-to-end plus specialist docs and roadmap updates.

### Step 6 — Full-suite regression, review & merge to main

- **Locations:** whole repo. Run the full Python suite
  (`uv run python -m pytest utils/`), an adversarial review pass over the new package, fix any
  findings, then `git checkout main && git merge --no-ff specialist-agents`, resolving conflicts.
- **Rationale:** The branch merges to `main` only when everything is 100% functional (global
  rule 3). A final regression + review guards against integration drift in the planner/loader
  suites the specialists import from.
- **Action:** Undergo the verification/tests/validation process for this phase (full suite green,
  live `--query` works). Once validated, commit/merge **(do not push)** stating: Specialist
  Agents (6/6) Complete: full regression green, branch merged into main.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Shared contracts & evidence schema | Task/Evidence/Provenance/Result dataclasses + contract check | `utils/specialists/contracts.py`, `utils/specialists/evidence.py` |
| Specialist config | Env-driven connection + caps + retry/LLM config | `utils/specialists/config.py` |
| Shared resolver | Entities→card, seed-id extraction, STIX/taxonomy pairing | `utils/specialists/resolve.py` |
| Shared validator base + loop | Read-only/limit injection base; ReAct scaffold with traces | `utils/specialists/validation.py`, `utils/specialists/base.py` |
| Cypher specialist (4 swap points) | Builder, validator, connector, normalizer + assembly | `utils/specialists/cypher/` |
| Gremlin specialist (4 swap points) | Builder, validator, connector, normalizer + assembly | `utils/specialists/gremlin/` |
| Federation router + CLI | Plan→specialists dispatch + `--query` command | `utils/specialists/federation.py`, `utils/specialists/cli.py`, `main.py` |
| Specialist unit + live tests | Contracts/evidence/resolve/validators/specialists/federation; live `skipif` | `utils/specialists/tests/` |
| Step-by-step workflow notebook | Planner→specialists end-to-end, runnable | `notebooks/planning-schematic-agents.ipynb` |
| Specialist documentation | Contract, swap points, evidence schema, config, usage | `docs/specialist_agents.md` + README/structure/goals updates |

> **Tests requirement satisfied:** every phase ships focused unit tests under
> `utils/specialists/tests/` that run a small subset of real schema/data (committed fixture
> cards for deterministic unit tests; `@pytest.mark.integration` + `skipif` tests that exercise a
> handful of records against the live Neo4j/Gremlin stack).
