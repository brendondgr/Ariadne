# Query Safety Model

This documents every point in Ariadne's request path where a query against a
live graph (Neo4j/Cypher for ATT&CK, Gremlin/TinkerPop for CAPEC) can be
narrowed, capped, or refused before it reaches an analyst. It is written for
someone deciding whether to trust the system with read access to their own
graph, who has not read the code. Enforcement is organized in the order a
request passes through it: **plan → pre-run gate → execution → evidence
contract → schema-boundary refusal.** How the stages fit together is in
[`ARCHITECTURE.md`](ARCHITECTURE.md); this page covers only what each one
refuses.

Two rules govern everything below: **the model drafts, deterministic code
grades**, and **no LLM sits on the critical path of any safety check**. Every
gate here is plain Python — set-membership, regex, and arithmetic comparisons
against the source card — not a "does this look right?" prompt. That holds for
every query-construction path, including the one where a model writes the query
(§9).

## 1. Plan-level limits (source card + planner gate)

Numeric bounds originate in the source card and are narrowed, never widened,
as they flow downstream. **Card safety defaults** are authored in
`utils/planner/card_enrichment.py` and layered onto the generated card at load
time (`enrich()`):

| Field | Default | Applies to |
|---|---|---|
| `read_only` | `True` | both backends |
| `max_result_rows` | `1000` | both backends |
| `max_traversal_depth` | `3` | both backends |
| `query_timeout_ms` | `5000` | both backends |
| `disallowed_clauses` | `CREATE, MERGE, DELETE, DETACH DELETE, SET, REMOVE, DROP, LOAD CSV, FOREACH, CALL {` | Cypher (ATT&CK) |
| `disallowed_steps` | `addV, addE, drop, property, sideEffect, io, mergeV, mergeE` | Gremlin (CAPEC) |

The merge rule: a non-empty section already on the generated card wins; for
`safety` the per-backend defaults above are the base and the generated card's
own keys (e.g. CAPEC's `allowed_edge_patterns`) are layered on top. A generated
card can add structural schema data; it cannot widen a numeric bound.

**Authoritative lists live in the validators, not the cards.** Source cards
are generated artifacts; a fix that lived only in a card would be lost on the
next `--build`. So the Cypher validator carries `_EXTRA_WRITE_CLAUSES`
(`DETACH DELETE`, `LOAD CSV`, `FOREACH`, `CALL {`) and the Gremlin validator
carries `_EXTRA_WRITE_STEPS` (`mergeV`, `mergeE`), each unioned with whatever
the card lists. `mergeV`/`mergeE` are TinkerPop's merge steps: they mutate, were
added to the language after the cards were written, and EXP-2026-08-016 found
eight live bypasses through exactly that gap before the code list existed.

**The planner's `Plan`** carries one `SubQuestion` per scoped task, each with
its own `Limits` (`utils/planner/schema.py`: `max_traversal_depth`,
`max_result_rows`, `query_timeout_ms`). The deterministic gate
(`utils/planner/gate.py`) rejects any sub-question whose limits are missing or
exceed the card's bound — `sub-question 1: max_traversal_depth 9 exceeds card
bound 3` — and an LLM drafter gets that reason back and must redraft.

**Specialist config** (`utils/specialists/config.py`) holds a second,
independently sourced set of defaults read from `SPECIALIST_MAX_RESULT_ROWS`,
`SPECIALIST_QUERY_TIMEOUT_MS`, `SPECIALIST_MAX_RETRIES`. `_effective_limits()`
(`utils/specialists/base.py`) fully populates the limits a connector receives;
`SpecialistTask.max_rows()/max_depth()/timeout_ms()` and the connectors' own
`limits.get(key, default)` are two further fallbacks that converge on
1000 / 3 / 5000, so a task without a limit still resolves conservatively.

## 2. Specialist pre-run gate (per-backend check table)

Before any query reaches a database, `BaseValidator.validate()`
(`utils/specialists/validation.py`) runs a fixed sequence — structural checks,
read-only enforcement, schema conformance, cap rejection, cap injection — and
returns `ok=True` only if every check passes. A failure at any of the first four
rejects the query with a specific reason; it never reaches injection or a
database call.

### Cypher validator (`utils/specialists/cypher/validator.py`)

| Check | Mechanism | Rejects on |
|---|---|---|
| Structural | Single statement; `MATCH` and `RETURN` present | Multiple statements, missing `MATCH`/`RETURN` |
| Read-only | Card `disallowed_clauses` ∪ `_EXTRA_WRITE_CLAUSES` | `query contains disallowed write clause: 'CREATE'` |
| Structural: `USE` | `USE <db>` re-targets the statement at a database the card cannot vouch for | `USE` present |
| Schema: labels | Every label in every node pattern (multi-label, backtick-quoted included) must exist in the card | Unknown node label |
| Schema: relationships | Every `[:TYPE]` must exist in the card | Unknown relationship type |
| Schema: `attack_id` ambiguity | A predicate on `attack_id` requires a node label | `query filters on attack_id but contains no node label` |
| Cap: unbounded depth | `[:REL*]`, `[:REL*..]` | `unbounded variable-length path […] is not allowed` |
| Cap: over-depth | Upper bound above `max_traversal_depth`, or a literal chain of more hops than the cap | `variable-length path […] exceeds max_traversal_depth 3` |
| Inject `LIMIT` | Appends `LIMIT {max_rows}` if absent; clamps a larger one | Injection only |

### Gremlin validator (`utils/specialists/gremlin/validator.py`)

Property graphs have no traversal-time schema enforcement, so this validator is
deliberately the heavier of the two — labels, edge direction, and depth are all
enforced in application code.

| Check | Mechanism | Rejects on |
|---|---|---|
| Structural | Query must start with `g.V(` or `g.E(` | Any other start |
| Read-only | Card `disallowed_steps` ∪ `_EXTRA_WRITE_STEPS` (`addV`, `addE`, `drop`, `property`, `sideEffect`, `io`, `mergeV`, `mergeE`) | `disallowed mutating step '.addV(' found in query` |
| Groovy closure | Any `{ … }` block — arbitrary code on the server, not a query | Closure present |
| Schema: labels | Every `hasLabel(…)` (either quote style) must exist in the card | `hasLabel references unknown label 'X'` |
| Schema: edges | Every `.out/.in/.both('R')` must exist in the card | `.out('R') references unknown relationship type 'R'` |
| Schema: edge direction | `.out(rel)` needs a valid source anchor in `allowed_edge_patterns`; `.in(rel)` a valid target; `.both` either | `.out('R') from 'Label' is not an allowed edge direction` |
| Cap: over-depth | Chained `.out/.in/.both` counted against `max_traversal_depth`; `repeat(…)` must carry a `.times(n)` within the bound | `traversal depth 4 exceeds max_traversal_depth 3` |
| Inject `.limit()` | Appends `.limit({max_rows})` if absent; clamps a larger one | Injection only |

Neither validator mutates a query beyond the row-cap injection — a rejected
query goes back to the builder as redraft feedback, capped by `SPECIALIST_MAX_RETRIES`.

## 3. Execution layer

Even a gate-approved query runs under further, independent constraints:

| Enforcement | Backend | Mechanism | Who enforces it |
|---|---|---|---|
| Read-only access | Neo4j | Session opened in `neo4j.READ_ACCESS` mode (`cypher/connector.py`) | Neo4j server (protocol level) |
| Per-query timeout | Neo4j | `Query(query, timeout=…)` from `limits["query_timeout_ms"]` | Neo4j driver |
| Row capping | Neo4j | Result loop breaks at `max_rows` | Application |
| Per-query timeout | Gremlin | `.result(timeout=…)` (`gremlin/connector.py`) | Gremlin client |
| Row capping | Gremlin | Rows sliced to `max_rows` after return, on top of the injected `.limit()` | Application (belt-and-suspenders) |
| Thread isolation | Gremlin | All gremlin-python calls on a dedicated single-worker thread | `ThreadPoolExecutor` |

Read-only access is the one check enforced by the database itself; every other
execution-layer constraint is Ariadne's connector code around the driver call.
Above execution, the specialist loop (`utils/specialists/base.py`) adds intake
(the task targets this specialist's source and carries an id) and the capped
gate loop (`max_retries + 1` attempts, then `ok=False, partial=True`).

## 4. Post-execution evidence contract

Passing the gate and executing is not sufficient for a result to ship.
`assess_rows()` (`utils/specialists/base.py`) requires a list of mapping rows
(an empty list is a valid "none found"), and for ATT&CK joins every join value
must match `T\d{4}(?:\.\d{3})?` — mismatches are recorded in the trace, not
silently dropped. `check_contract()` (`utils/specialists/evidence.py`) then
requires every `EvidenceRecord` to carry `primary_id` or `name`, `id_scheme`,
`label`, and a `provenance` object with non-empty `source`, `dataset`,
`backend`, `query`, `record_id`, and ISO-8601 `timestamp`. A contract failure
sets `ok=False` with the violation as the result's `error`; because the
executed query is part of every record's provenance, shipped evidence is always
traceable to the exact query that produced it.

## 5. Schema-boundary refusals

If a resolved task names an entity the source card does not model, no query is
drafted at all (`base.py`, the `resolve()` step before the gate loop): the
specialist returns `ok=True`, zero records, an empty query, and a summary naming
the boundary. Answering with whatever the known entities *can* express would
silently answer a different question than the one asked.

## 6. The two never-cut checkpoints

1. **Pre-run gate** (`utils/specialists/validation.py`) — keeps a bad query off
   the database entirely, for every draft.
2. **Normalize/contract check** (`utils/specialists/evidence.py`) — keeps
   malformed or under-provenanced evidence out of synthesis, after execution.

Both set the pass/fail verdict directly; a rejection is always visible as
`ok=False` plus a specific reason, recorded in an `EvaluatorTrace`.

## 7. Defense in depth

- **Card numeric defaults loosened or omitted** — the gate still hard-rejects
  unbounded/over-depth traversals (`cap_reasons()`), and both connectors fall
  back to 1000 rows / 5000 ms.
- **A write clause slipped past the gate** — Neo4j's `READ_ACCESS` session
  refuses it at the protocol level.
- **An unbounded row count came back** — the connector caps rows client-side;
  Gremlin re-caps on top of the injected `.limit()`.
- **A malformed record slipped through normalization** — the evidence contract
  fails the result before synthesis.
- **An entity is not modeled by a source** — the refusal fires before any query
  is drafted.

Row caps and depth caps each exist in two places (gate and connector), so a
defect in one does not remove the other.

## 8. Adversarial audit

**Harness:** `utils/specialists/evalset/score_safety.py`, hermetic (no live
database), two checks:

1. **Adherence audit** (`audit_query()`) — an independent bounds check on every
   query the gate *accepted* in the golden question bank: read-only, a
   `LIMIT`/`.limit()` present and ≤ the cap, no unbounded variable-length path.
   It re-checks the gate's output text; it does not call the validator.
2. **Adversarial probes** (`PROBES`,
   `utils/specialists/tests/fixtures/adversarial_probes.py`) — queries fed
   straight to the validator, bypassing the builder. A probe that returns
   `ok=True` is recorded as a `leak` and treated as a hard failure, not a rate.

**Result (EXP-2026-08-016, `docs/research/experiments/EXP-2026-08-016-tenant-isolation/`).**
The suite grew from 17 hand-written probes to **240 generated probes**. On first
contact the larger suite found **15 live bypasses** the small one had never
reached — 8 `mergeV`/`mergeE` placements no card named, 1 Groovy closure, 2
unbounded or over-depth `repeat(…)`, 1 literal four-hop chain past a cap of
three, 1 `USE <db>` re-target, and 2 backtick/multi-label patterns that rode an
undeclared label in beside a declared one — all closed in the validators before
the experiment completed. After the fix the block rate is **1.0000 over 240
probes**, with zero leaks and zero breaches. The earlier 17-probe suite had
found the project's first bypass the same way (`hasLabel('Secret')` with single
quotes evaded a double-quote-only regex). A gate tested only against its own
author's queries partly grades against its own answer key.

The experiment's second phase measured cross-tenant leakage, a property no
gate can see; those figures are in the same manifest and in
[`research/CURRENT.md`](research/CURRENT.md).

## 9. When a model writes the query

`SPECIALIST_LLM_QUERY_BUILDER=true` replaces the template builder with
`utils/specialists/llm_builder.py`: a model is handed the card's schema, the
resolved seed ids, and the constraints the gate enforces, and writes the Cypher
or Gremlin itself. **The gate is not relaxed for this path.** `BaseValidator`
operates on the query string, never on the draft's template name, so a
model-written query passes exactly the checks in §2 — and `test_llm_builder.py`
asserts that a model emitting `DETACH DELETE` is refused by the same code. It
does not fall back to templates on failure; an unreachable model yields an
empty draft the gate rejects with a recorded reason. It is **off by default**
and exists to be measured against (EXP-2026-08-008, EXP-2026-09-002); leave it
false on any path whose answer anybody will read.

## Configuration reference

| Variable | Default | Effect |
|---|---|---|
| `SPECIALIST_MAX_RESULT_ROWS` | `1000` | Row cap fallback when a task carries no explicit limit |
| `SPECIALIST_QUERY_TIMEOUT_MS` | `5000` | Timeout fallback (ms) when a task carries no explicit limit |
| `SPECIALIST_MAX_RETRIES` | `2` | Max redraft attempts after a gate rejection (`max_retries + 1` total attempts) |
| `SPECIALIST_LLM_QUERY_BUILDER` | `false` | A model writes the query string; the gate still validates it (§9). Baseline only |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | `bolt://localhost:5456` / `neo4j` / `password` | Neo4j connection (env is the source of truth; the card's `connection` block is informational, see `docs/source_cards.md`) |
| `GREMLIN_URI` | `ws://localhost:6455/gremlin` | Gremlin connection |

## Key files

| Concern | Location |
|---|---|
| Card safety defaults + merge | `utils/planner/card_enrichment.py` |
| Sub-question `Limits` | `utils/planner/schema.py` |
| Planner gate (limits vs. card bound) | `utils/planner/gate.py` |
| Specialist config (env-driven ceiling) | `utils/specialists/config.py` |
| Shared pre-run gate scaffold | `utils/specialists/validation.py` |
| Cypher validator | `utils/specialists/cypher/validator.py` |
| Gremlin validator | `utils/specialists/gremlin/validator.py` |
| Neo4j connector (read-only session, timeout, row cap) | `utils/specialists/cypher/connector.py` |
| Gremlin connector (timeout, row cap, thread isolation) | `utils/specialists/gremlin/connector.py` |
| Specialist scaffold loop (intake, gate loop, assess, contract) | `utils/specialists/base.py` |
| Evidence contract + provenance check | `utils/specialists/evidence.py` |
| LLM query builder (baseline path) | `utils/specialists/llm_builder.py` |
| Adversarial probes (hand-written + generated) | `utils/specialists/tests/fixtures/adversarial_probes.py` |
| Safety audit harness | `utils/specialists/evalset/score_safety.py` |
| Pipeline stages and the never-cut checkpoints in context | `docs/ARCHITECTURE.md` |
