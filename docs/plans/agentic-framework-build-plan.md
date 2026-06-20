# Agentic Framework Build Plan

### 1. Introduction

The data layer is done (canonical ATT&CK and CAPEC graphs, runtime loaders, live Neo4j and Gremlin fixtures, source cards). This plan covers the **agent layer** and fixes the single most important sequencing decision: **build deterministic before probabilistic, bottom-up, and prove one vertical slice end-to-end before adding the second backend.**

The reason is **failure localization**. If we build the planner first — it feels like the brain, so it is tempting — then when a question returns garbage we cannot tell whether the planner, the specialist, the validator, or the connector is at fault. Building from the bottom validates every layer in isolation before anything sits on top of it, and lets the LLM enter as late as possible so that most of the safety logic is reproducibly testable without a model in the loop.

The phases below map onto the **Agents (Wk 6–11)** and **Evaluation (Wk 11–13)** rows in [goals.md](../goals.md). Note the implementation order here is deliberately *not* the roadmap's listing order: the planner is a feature deliverable, but it is built **after** the specialists it routes to.

### 2. Cross-Cutting Habits

Two habits make this work:

1. **Every layer keeps its own test corpus** and must pass before the next layer is built on it. This is what guarantees we can always localize a failure.
2. **Stubs decouple the build.** A stubbed planner lets us finish specialists; canned evidence lets us test synthesis early if needed.

The through-line: by the time the LLM touches anything (Phase 4+), the connector, validator, and safety logic underneath it are already proven, so any new failure is the model's, not the plumbing's.

### 3. Build Phases

#### Phase 1 — Connectors + safety enforcement (no LLM)

Before any agent exists, build the thing that takes a *hand-written* query, runs it read-only against one fixture, and returns rows. Wire in the source card's safety limits as **real enforcement, not documentation**: read-only session, `timeout_ms`, injected `LIMIT` / `max_result_rows`, `max_traversal_depth`.

- **Validate:** Run a handful of known-good queries and confirm correct rows. Run known-bad ones — a `CREATE`, an `addV`, an unbounded traversal — and confirm each is rejected or capped.
- **Pass bar:** Zero disallowed operations reach the database.

#### Phase 2 — Static validator (no LLM)

Check a query *string* against the card: every label/edge/property exists, edge endpoints match `allowed_edge_patterns`, no `disallowed_clauses` / `disallowed_steps`, a bound is present. This is the safety backbone, and it is entirely testable without an LLM — which is exactly why it comes before the specialists.

- **Validate:** Hand-write a corpus of ~20–30 valid and invalid queries per backend; require 100% correct accept/reject.

#### Phase 3 — Dry-run validator + normalizer + evidence schema (no LLM)

Add the cheap live check (Cypher `EXPLAIN`, Gremlin `.limit(1)` probe) and define the shared evidence format **once** — records keyed on ATT&CK/CAPEC IDs, each carrying `source`, `query`, `timestamp`. Thread provenance from here outward; do not bolt it on at synthesis.

- **Validate:** The same logical answer pulled from either backend should normalize to structurally identical evidence objects.

#### Phase 4 — One specialist, in isolation (first LLM)

Wrap generation around the proven plumbing for a *single* backend — start with **Cypher/ATT&CK**: schema-slice selection → template-fill generation (with the card's example queries as few-shot) → static validate → dry-run → execute → normalize → summarize → trace, with one or two self-correction retries on validation failure. Crucially, **stub the planner** — feed the specialist hand-written sub-questions so we are testing only the specialist.

- **Validate:** Against the specialist metrics — query validity, result correctness, safety adherence, latency.
- **Pass bar before continuing:** High validity and correctness on a fixed sub-question set.

#### Phase 5 — Second specialist (the migration test)

Only now bring up **Gremlin/CAPEC** by replacing the four swappable pieces the proposal names — **prompt, validator, connector, normalizer**. Doing the second backend *second* is itself the validation of the migration claim: if it drops in cleanly, the architecture's separation of concerns is real.

- **Validate:** Same isolated harness, paying special attention to edge **direction** and `allowed_edge_patterns` — that is where Gremlin breaks.

#### Phase 6 — Planning agent

With working specialists to route to, build the planner that reads all source cards and emits a machine-readable plan (target sources, sub-questions, join keys, limits, unsupported parts).

- **Validate:** Score its *plan output* against a set of expected plans — decoupled from whether specialists then succeed — using source-selection accuracy, sub-question quality, unnecessary calls, schema adherence. Score the plan, not the eventual answer.

#### Phase 7 — Orchestrator

A thin layer: planner → fan out to specialists in parallel → collect.

- **Validate:** The wiring and partial-failure handling specifically — one specialist failing should still return the others' evidence, not crash the run.

#### Phase 8 — Synthesis / reporting agent

Last, because it depends on everything above producing evidence. It joins on the shared IDs (the ATT&CK `technique-id` ↔ CAPEC `MAPS_TO` → `TaxonomyEntry` declaration), flags missing/conflicting evidence, and assembles the grounded answer plus table/figure with provenance behind each claim.

- **Validate:** Deterministic checks (join correctness, provenance completeness) **and** the LLM evaluator the proposal commits to — faithfulness, groundedness, evidence sufficiency, unsupported-claim rate.

#### Phase 9 — End-to-end harness

Stand up the ground-truth question set (published CAPEC→ATT&CK mappings, ATT&CK relationship objects, benchmark traversals, manually reviewed questions) and run the whole stack against it, tracking cross-source accuracy, mapping recall, provenance correctness, and analyst inspectability. **Freeze these as regression tests** so later changes cannot silently break a passing case.

### 4. Highest-Leverage Starting Point

The **static validator and its test corpus (Phase 2)** is the highest-leverage place to begin: it is the safety backbone, fully testable without an LLM, and a prerequisite for both specialists.
