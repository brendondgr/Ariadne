# Migration Guide: Adding a New Query-Language Specialist

Proposal Deliverable #6 — guidelines for migrating the specialist framework to
another graph query language. Ariadne ships two specialists today (Cypher over
Neo4j for ATT&CK, Gremlin over a Gremlin Server for CAPEC); this guide is
written for the third: an openCypher- or GQL-speaking backend added the same
way. It assumes no prior familiarity with the codebase.

## The architecture claim

**A new specialist is four language-specific implementations dropped onto one
shared, unchanged scaffold.** Precisely:

The shared scaffold is `QuerySpecialist.run()` (`utils/specialists/base.py`),
which executes a fixed loop — intake → resolve → draft → pre-run gate → execute
→ assess → normalize → handoff — plus the deterministic assessment helpers
(`assess_rows`, `join_integrity_problems`) and the shared `BaseValidator`
orchestration (`utils/specialists/validation.py`). None of this loop
code changes when a new backend is added.

The four swap points are the only things a new backend must supply:

| # | Swap point | Contract | Gremlin implementation (worked example) |
|---|---|---|---|
| 1 | **Query builder** | `QueryBuilder` protocol, `build(resolved, feedback) -> QueryDraft` | `utils/specialists/gremlin/builder.py` |
| 2 | **Validator** | `BaseValidator` abstract class, four required methods + one optional hook | `utils/specialists/gremlin/validator.py` |
| 3 | **Connector** | `Connector` protocol, `connect()` / `close()` / `run(query, params, limits)` | `utils/specialists/gremlin/connector.py` |
| 4 | **Normalizer** | `Normalizer` protocol, `normalize(...) -> list[EvidenceRecord]` + `summarize(...)` | `utils/specialists/gremlin/normalizer.py` |

These four are injected into one `QuerySpecialist` instance by a small factory
function (`utils/specialists/gremlin/specialist.py`,
`build_gremlin_specialist()`) — the pattern a new backend's `specialist.py`
mirrors.

This claim is real but narrower than "plug in a new backend and go": Section
V below lists every additional file a working specialist actually touches.
The four swap points are necessary and sufficient for the query-execution
loop itself; they are not sufficient for a specialist that is registered,
configured, tested, and evaluated end to end.

## Prerequisites

Before writing any of the four swap points, three things must exist:

1. **A loaded data fixture.** The new backend needs a running graph store with
   real data in it. `utils/graph_loader/stores/factory.py`
   (`create_graph_store`) dispatches by backend name to a concrete
   `GraphStore` implementation (`utils/graph_loader/stores/neo4j.py`,
   `utils/graph_loader/stores/gremlin.py` today); a new backend needs an
   equivalent store class that can load schema and upsert nodes/edges into a
   real instance of the new backend, plus an artifact exporter
   (`utils/kg_builder/exporters/`) if the on-disk serialization the loader
   consumes differs from the existing Cypher (`schema.cypher` /
   `constraints.cypher`, `utils/kg_builder/exporters/cypher.py`) or
   Gremlin (JSONL nodes/relationships, `utils/kg_builder/exporters/gremlin.py`)
   shapes. Nothing downstream can be validated against a schema that isn't
   actually loaded anywhere.
2. **A source card.** Every specialist is handed a `SourceCard` — introspected
   node labels, relationship types, node properties, and (after enrichment)
   safety/provenance/connection metadata. This is authored data, not code; see
   the walkthrough below and `docs/source_cards.md` for the card's full shape.
3. **A join-key bridge, if the new specialist correlates with an existing
   source.** `utils/planner/join_keys.py` (`CANONICAL_JOIN_KEYS`) is a
   hardcoded, hand-reviewed tuple — the planner will never invent a
   cross-source join, so if the new specialist needs to correlate with ATT&CK
   or CAPEC, the bridge must be declared here before planning can propose it.
   If the new specialist is single-source only, this prerequisite does not
   apply.

## Walkthrough (dependency order)

The steps below are ordered so that each one only depends on work already
done in a prior step.

### 1. Author the source card

`utils/kg_builder/registry.py` builds and writes the source card from the
loaded graph's introspected schema:

- `build_attack_source_card()` (`registry.py`) and
  `build_capec_source_card()` (`registry.py`) are the two existing
  examples — each reads a manifest and a `schema.json`, and assembles a
  `SourceCard` dataclass (`registry.py`) with `node_labels`,
  `relationship_types`, `node_properties`, `exports`, and an `identity` block
  (declared join key, uniqueness constraints, known id collisions).
- `write_capec_source_card()` / `write_attack_source_card()`
  (`registry.py`) call the build function and write the result as
  JSON under `source_registry_dir`.
- A new dataset needs its own `build_<dataset>_source_card()` and
  `write_<dataset>_source_card()`, plumbed into the build pipeline
  (`utils/kg_builder/main.py`) alongside the existing two calls.

Then author the card-enrichment block:

- `utils/planner/card_enrichment.py` (`ENRICHMENT`) is a dict keyed by
  dataset name, holding `connection` (backend, timeout, auth env var names),
  `provenance` (id property, source name, dataset version, id scheme), and
  `entity_descriptions` (per-label/per-relationship prose) for `attack` and
  `capec` today. A new dataset needs its own entry.
- Each backend also needs a safety-defaults block: `_NEO4J_SAFETY`
  (`card_enrichment.py`, `disallowed_clauses`: `CREATE`, `MERGE`,
  `DELETE`, `DETACH DELETE`, `SET`, `REMOVE`, `DROP`, `LOAD CSV`, `FOREACH`,
  `CALL {`) and `_GREMLIN_SAFETY` (`card_enrichment.py`,
  `disallowed_steps`: `addV`, `addE`, `drop`, `property`, `sideEffect`, `io`)
  are the two existing templates the new validator's `violates_read_only`
  will read from (via `card.safety`). `default_safety_for_backend()`
  (`card_enrichment.py`) is where a new backend name is added.
- **Card must have all four swap points' data before first run** — safety
  blocks are read at validator construction, not at query time, so an
  incomplete enrichment block fails closed rather than at some later request.

### 2. Implement each swap point

Do these in this order: validator first (it gates everything downstream),
then builder, then connector, then normalizer — matching the order the
scaffold actually calls them isn't required, but implementing the gate first
means every later query, real or fake, is checked against real rules from the
start.

#### 2a. Validator

**Interface** (`utils/specialists/validation.py`, `BaseValidator`):

| Method | Signature | Purpose |
|---|---|---|
| `structural_reasons` | `(query: str) -> list[str]` | Syntax/shape checks (e.g. single statement, expected start token) |
| `violates_read_only` | `(query: str, card: Any) -> list[str]` | Reject any write clause/step declared in the card's safety block |
| `schema_reasons` | `(query: str, card: Any) -> list[str]` | Every label/edge (and direction) referenced must exist in the card |
| `inject_caps` | `(query: str, limits: dict[str, int], card: Any) -> tuple[str, list[str]]` | Inject/clamp the row (and, where relevant, depth) limit; return `(query, injected-notes)` |
| `cap_reasons` (optional hook, default no-op) | `(query: str, card: Any, limits: dict[str, int]) -> list[str]` | Reject a query whose hard caps can't be satisfied by simple injection (e.g. a traversal already deeper than the max) |

`validate()` (`validation.py`) is not overridden — it calls the four
required methods plus the optional hook in a fixed order, and only calls
`inject_caps` once a query is otherwise clean, so nothing hits the database
until it passes.

**Worked example — `GremlinValidator`** (`utils/specialists/gremlin/validator.py`):

- `structural_reasons` requires the query to start with `g.V(` or `g.E(`.
- `violates_read_only` regex-matches `.step(` for every step name in
  `card.safety["disallowed_steps"]`.
- `schema_reasons` extracts every `hasLabel("X")` and every `.out(/.in(/.both("R")`
  occurrence (`_extract_edge_anchors`, `validator.py`) and checks each
  label against `card.node_labels` and each relationship (after normalizing
  through `gremlin_edge_label`, since the card stores CAPEC's source
  vocabulary — e.g. CamelCase `ChildOf` — while the loaded graph uses
  SCREAMING_SNAKE edge labels) against `card.relationship_types` and
  `card.allowed_edge_patterns`, including direction (source/target label
  pairs).
- `cap_reasons` counts chained `out/in/both` steps and rejects outright if the
  count exceeds `max_traversal_depth` — property-graph traversers multiply
  per hop, so a too-deep traversal cannot be made safe by appending a row
  `.limit()`; it must be refused before execution.
- `inject_caps` finds or appends a trailing `.limit(n)` and clamps it to
  `max_result_rows`.

**Language-specific concerns for a declarative language (openCypher/GQL):**
this validator's shape is closer to the *Cypher* validator
(`utils/specialists/cypher/validator.py`) than the Gremlin one — a
declarative pattern-match query has a syntactic depth signal (pattern length
in a `MATCH`) rather than a chain of imperative steps, and row capping is a
`LIMIT` clause rather than an appended traversal step. Read
`utils/specialists/cypher/validator.py` directly before writing this piece;
do not assume Gremlin's regex approach transfers unchanged.

#### 2b. Query builder

**Interface** (`utils/specialists/base.py`, `QueryBuilder` protocol):
`build(resolved: ResolvedTask, feedback: list[str] | None = None) -> QueryDraft`.
`QueryDraft` (`utils/specialists/validation.py`) carries the query
string, a `params` dict, a `template` name (for tracing), an
`expected_nonempty` flag, and a free-form `meta` dict.

**Worked example — `GremlinQueryBuilder`** (`utils/specialists/gremlin/builder.py`):
`build()` is a priority-ordered dispatcher over `resolved` task shape — a
hierarchy-chain template if two-or-more `ChildOf` entities are present, a
join template (`capec_maps_to` / `_cwe_chain` / `_capec_reverse_maps`
depending on seed id shape) if a cross-source join is in scope, a neighbor
template if seeds plus a known relationship are present, a lookup or dossier
template for bare seeds, a name-anchored dossier for a seedless definitional
question, and a bare label scan as the final fallback. Every template ends
with an injected `.limit(lim)` and puts every value into the `params`
(bindings) dict — never string-interpolated; only structural identifiers
(labels, relationship types), which have already passed the card's schema
check, are inlined as literals.

**Language-specific concerns:** a declarative language expresses the same
dispatch as parameterized `MATCH`/`RETURN ... LIMIT` templates rather than
chained traversal steps — see `utils/specialists/cypher/builder.py` for the
existing worked example of that shape before drafting templates for a new
declarative backend. The template-selection logic (which shape of resolved
task maps to which query shape) is very likely portable prose even where the
query text is not.

#### 2c. Connector

**Interface** (`utils/specialists/base.py`, `Connector` protocol):
`connect() -> None`, `close() -> None`,
`run(query: str, params: dict[str, Any], limits: dict[str, int]) -> list[dict[str, Any]]`.
Bounded, read-only execution; the scaffold expects an `ExecutionError`
(`utils/specialists/errors.py`) on any backend failure, never an uncaught
exception.

**Worked example — `GremlinConnector`** (`utils/specialists/gremlin/connector.py`):
wraps gremlin-python's `Client`, applies `query_timeout_ms` and
`max_result_rows` from `limits`, and defensively re-caps rows client-side even
though the query already carries a `.limit()`. Notably, every gremlin-python
call — connect, submit, close — runs inside a dedicated single-thread
`ThreadPoolExecutor`, because the driver's transport drives its own asyncio
event loop via `run_until_complete`, which collides with a host event loop
already running one (e.g. a Jupyter kernel). A new backend's driver may or
may not have this constraint; read its client library's threading/event-loop
model before assuming a plain synchronous call is safe.

**Language-specific concerns:** confirm whether the new backend's client
library is synchronous, thread-safe, and whether it exposes a native
read-only execution mode (the Cypher connector uses Neo4j's `READ_ACCESS`
session mode as a second, infra-level enforcement layer beyond the validator's
static check — see `utils/specialists/cypher/connector.py`). openCypher and
GQL drivers vary here by target database; there is no single answer.

#### 2d. Normalizer

**Interface** (`utils/specialists/base.py`, `Normalizer` protocol):
`normalize(rows, resolved, query, card) -> list[EvidenceRecord]` and
`summarize(records, resolved) -> str`. Every `EvidenceRecord` must carry full
`Provenance` and pass the shared contract check (`check_contract`,
`utils/specialists/evidence.py`) run by the scaffold immediately after
normalization.

**Worked example — `GremlinNormalizer`** (`utils/specialists/gremlin/normalizer.py`):
`normalize()` dispatches on the *shape* of the first result row (which keys
are present — `w`/`ap`/`tax` for a CWE chain, `ap`/`parent`/`grandparent` for
a hierarchy chain, `node`/`out`/`in` for a dossier, `ap`/`nbr` for a
neighbor pair, `ap`/`tax` for a maps-to, else a flat single-entity row) to one
of six per-shape helper methods, each of which groups raw rows by anchor
entity, converts backend-native ids into the card's `primary_id` scheme
(e.g. `capec:attack-pattern:66` → `CAPEC-66`), and populates `join_values`
only for `MAPS_TO` edges whose target `TaxonomyEntry.taxonomy_name == "ATTACK"`
(the live edge set also carries non-ATT&CK taxonomy entries that must not
leak into the join spine). `summarize()` produces one grounded sentence citing
the ids and any joined values.

**Language-specific concerns:** shape-dispatch-on-result-keys is a Gremlin
idiom (traversal `project()` steps name their own output keys); a declarative
language's result rows are typically named by the query's own `RETURN`
aliases, which is closer to how `utils/specialists/cypher/normalizer.py`
dispatches — read it directly rather than porting the Gremlin dispatch
pattern verbatim.

### 3. Wire configuration and registration

- **Config fields** — `SpecialistConfig` (`utils/specialists/config.py`)
  is a frozen dataclass holding, today, `neo4j_uri`/`neo4j_user`/`neo4j_password`
  and `gremlin_uri` alongside shared limits (`max_result_rows`,
  `query_timeout_ms`, `max_retries`, `expand_page_size`) and the
  `llm_query_builder` baseline switch. A new backend
  needs its own URI (and auth fields, if required) added to this dataclass
  and to `from_env()` (`config.py`), which reads each field from an env
  var via `utils.config.env_str`/`env_int`.
- **Endpoint lookup** — `endpoint_for(backend: str) -> str`
  (`config.py`) is a small if/elif that returns the URI for `"neo4j"` or
  `"gremlin"`; extend it for the new backend name.
- **Router entry** — `build_specialist(dataset, card, config)`
  (`utils/specialists/__init__.py`) is a hardcoded if/elif from dataset
  name to a lazy import of the backend's `build_<backend>_specialist()`
  factory. This is the one line that makes the new specialist reachable at
  all; nothing upstream (planner, federation) can route to a specialist that
  isn't registered here.
- **Factory function** — write `build_<backend>_specialist(card, config)`
  mirroring `build_gremlin_specialist()` (`utils/specialists/gremlin/specialist.py`):
  resolve the backend's URI via `config.endpoint_for(...)`, then construct
  `QuerySpecialist(card=card, builder=..., validator=..., connector=...,
  normalizer=..., max_retries=config.max_retries)`.
- **Federation discovery** — `SpecialistRouter._specialist_for(source)`
  (`utils/specialists/federation.py`) calls `build_specialist()`
  lazily and caches the result; no separate federation-side registration is
  needed once `build_specialist()` knows the new dataset name.

### 4. Declare joins (only if the new specialist correlates with an existing source)

If the new specialist is single-source, skip this step. If it needs to
correlate with ATT&CK or CAPEC on a shared id:

- Add a new `JoinKey` to `CANONICAL_JOIN_KEYS`
  (`utils/planner/join_keys.py`) with a `JoinKeyEndpoint`
  (`join_keys.py`) for each side declaring the dataset, the label(s)
  that carry the key, the property holding the value, and (if the key is
  reached through a mapping edge rather than a native property) the
  `via_edge` name.
- `resolve_join_key()` (`join_keys.py`) only binds a key when both
  cards are distinct datasets, together cover both of the key's endpoints,
  and each card's *introspected* structure actually exposes the declared
  label/edge — so an incomplete or wrong declaration here fails safely
  (the planner marks the join unsupported) rather than silently.
- Dependency-derived execution ordering
  (`utils/specialists/federation.py`, `dependency_map`/`execution_order`)
  and evidence bundling (`federation.py`) are dataset-agnostic — they
  read whichever join key resolves and need no changes for a new bridge.

## The two non-template paths a new backend must also serve

The four swap points above are described through the template builder, but the
shipped builders route to two further query-construction paths, and a new
backend's builder has to serve both or declare honestly that it does not.

**Schema-derived primitives** (`utils/specialists/primitives/describe.py`,
`utils/specialists/primitives/expand.py`). When no question-shape template
applies, both existing builders fall through to `describe` (every property on
an anchor node plus a bounded facet block — a count per relationship, direction
and neighbour label, with real zeros folded in from the schema registry) and
`expand` (one facet's members, paged, each with a bounded description and an
explicit `truncated` flag). The primitives are backend-agnostic *contracts*: a
`Facet` is a `(relationship, direction, neighbour label)` regardless of whether
the edge is walked in Cypher or Gremlin. A new builder implements the two query
shapes that satisfy them — see how `cypher/builder.py` and `gremlin/builder.py`
each render an `ExpandRequest` — and its normalizer must populate
`EvidenceRecord.facets` for a describe result. Both read the derived
`utils/specialists/schema/` registry (`DatasetSchema`, `SchemaRegistry`), so the
new dataset also needs its schema derived there; nothing in the primitives may
carry catalogue-specific knowledge.

**The LLM query builder** (`utils/specialists/llm_builder.py`,
`SPECIALIST_LLM_QUERY_BUILDER=true`). The measured baseline hands a model the
card's schema, the resolved seeds and the gate's constraints, and lets it write
the query string; the factory in each backend's `specialist.py` swaps it in for
the template builder when the flag is set. It is language-agnostic on the
prompt side but needs the new backend's language named, and its output is only
as safe as the new validator: the gate checks the query *string*, never the
draft's template name, so the validator written in step 2a is what stands
between a model-written query and the database. It stays off by default and
exists to be measured against, not run.

## Validating the new specialist

Run these suites/harnesses, in roughly this order, and what each one proves:

| Suite / harness | Command / entry point | What it proves |
|---|---|---|
| Validator unit tests | `utils/specialists/tests/test_<backend>_validator.py` | The pre-run gate's four checks (structural, safety, schema/direction, cap injection) are correct in isolation, with a fake card — no live backend needed |
| Specialist unit tests | `utils/specialists/tests/test_<backend>_specialist.py` | The four swap points wired together via a fake connector produce correct `EvidenceRecord`s for each query template, without touching a real database |
| Golden integration test | `utils/specialists/tests/test_golden_<dataset>.py` — marked `live`/`integration`; run with `uv run python -m pytest` against the running stack (skips automatically when unreachable) | The specialist executes real questions from the golden evalset bank against a live backend and returns the expected ids/names/properties — requires the live stack up |
| Acceptance test | `utils/specialists/tests/test_acceptance_federated.py` (if the new specialist joins across sources) | The full pipeline — planner, federation, both specialists, synthesis — produces a correct end-to-end answer for a cross-source question |
| Validity scoring | `utils/specialists/evalset/score_validity.py` | Every emitted record conforms to the evidence contract and join values are well-formed |
| Safety scoring | `utils/specialists/evalset/score_safety.py` | No disallowed clause/step ever reaches execution; read-only enforcement holds |
| Execution scoring | `utils/specialists/evalset/score_execution.py` | Queries execute within timeout and respect row caps |
| Golden test runner | `utils/specialists/tests/golden_runner.py` | Backend-agnostic driver that runs any registered specialist's questions against the live bank — reuse it rather than writing a new runner |

`utils/specialists/tests/golden/VERIFICATION.md` documents the independent
two-agent re-derivation of the existing ATT&CK/CAPEC gold banks directly from
the pinned raw snapshots; a new dataset's gold bank should get the same
treatment before it is trusted as ground truth.

## Beyond the four swap points

The four swap points are necessary and sufficient for the query-execution
loop itself. They are not sufficient to stand up a specialist that a planner
can route to, a build can produce a card for, and an evaluation harness can
score. This is a finding about how much fixed-dataset assumption is baked into
the surrounding scaffolding, not a defect in the four-swap-point design —
listed honestly, with an effort estimate for each additional touch point.

| Touch point | File | Effort | Why it's needed |
|---|---|---|---|
| Router entry in `build_specialist()` | `utils/specialists/__init__.py` | Trivial | Without this the new specialist is unreachable; nothing routes to it |
| Config fields (URI, auth) | `utils/specialists/config.py` | Trivial | Connector needs an endpoint from somewhere other than a hardcoded literal |
| `endpoint_for()` branch | `utils/specialists/config.py` | Trivial | One more `if` for the new backend name |
| Factory function (`specialist.py`) | new `utils/specialists/<backend>/specialist.py` | Trivial | Wires the four swap points together; ~15 lines, mirrors the Gremlin one |
| Card-enrichment block (`ENRICHMENT[dataset]`) | `utils/planner/card_enrichment.py` | Small | Safety defaults, provenance, connection metadata, entity descriptions — authored prose, not derived |
| Backend safety-defaults block | `utils/planner/card_enrichment.py` (`default_safety_for_backend`) | Small | The disallowed-clause/step list the validator's `violates_read_only` reads |
| Native seed-id extraction keying | `utils/specialists/resolve/` (`resolve()`) | Small | The resolver's text-to-seed-id extraction is keyed by `card.dataset` (`"attack"` extracts T-ids, `"capec"` prioritizes CAPEC → CWE → T-ids); a new dataset falls through to *no* native extraction until an entry is added, so bare-id questions would stop routing seeds |
| Source-card build + write functions | `utils/kg_builder/registry.py` | Real | New `build_<dataset>_source_card()` / `write_<dataset>_source_card()`, plus a call site in `utils/kg_builder/main.py` |
| Artifact exporter | `utils/kg_builder/exporters/` | Real (skip if an existing serialization format fits) | Only needed if the new backend's load format differs from the existing Cypher-script or JSONL shapes |
| GraphStore implementation | `utils/graph_loader/stores/` + `factory.py` | Real | Schema load, node/edge upsert, and verification against the actual new backend — no shortcut around standing up real infrastructure code |
| Validator + specialist unit test files | `utils/specialists/tests/test_<backend>_validator.py`, `test_<backend>_specialist.py` | Small–Real | Mandatory; the existing files run ~150-200 lines each with fake fixtures |
| Golden integration test + gold bank | `utils/specialists/tests/test_golden_<dataset>.py`, `utils/specialists/evalset/questions.py` | Real | New per-dataset question templates and anchors, independently re-derived against the raw snapshot per the `VERIFICATION.md` method |
| Join-key bridge (only if cross-source) | `utils/planner/join_keys.py` | Small | One `JoinKey` entry; only needed if the specialist correlates with an existing source |
| Federated question bank (only if cross-source) | `utils/specialists/evalset/federated_questions.py` | Real | Bridging questions that exercise the new join |
| Evaluation corpus + scoring hookups | `utils/planner/evaluation/build_corpus.py` (`BANK_FILES`), `utils/evaluation/score_e2e.py`, `utils/evaluation/harness/run_stage.py`, `utils/evaluation/harness/contracts.py` | Small–Real | Dataset-keyed dicts/comments (`BANK_FILES`, degradation scenarios like `"attack_down"`/`"capec_down"`, the `set_name` constraint) that assume the current two-dataset set; each needs a matching entry for the new dataset |

Total: roughly seven touch points that are effectively mandatory for any
working specialist (router, config, factory, card enrichment, safety
defaults, seed-id extraction keying, and the
two unit-test files), plus the source-card build/write functions and a
GraphStore implementation, which are unavoidable but scale with how different
the new backend's storage/serialization model is from Neo4j/Gremlin's. The
join-key bridge, federated questions, and evaluation-harness hookups are
optional in the sense that a single-source specialist that nobody scores in
aggregate can skip them — but a specialist meant to ship in the actual
evaluated pipeline needs all of them.

## openCypher notes

openCypher is closer to Neo4j's Cypher than any other choice on this list —
Neo4j's Cypher is a superset/dialect relationship of openCypher, not an
unrelated language. Concretely, for the swap points above:

- **Carries over largely unchanged:** the declarative `MATCH ... RETURN`
  pattern-matching shape the Cypher builder already targets
  (`utils/specialists/cypher/builder.py`), parameterized query construction
  (values as bound parameters, structural identifiers as validated literals),
  and a `LIMIT`-clause-based row cap in the validator's `inject_caps`. The
  Cypher validator's structural/schema-checking approach
  (`utils/specialists/cypher/validator.py`) is the nearer worked example than
  the Gremlin one for this reason.
- **Differs and needs verification per target database:** the exact set of
  disallowed write clauses may not be identical across openCypher
  implementations (Neo4j's `CREATE`/`MERGE`/`SET`/`REMOVE`/`DROP`/`LOAD CSV`/
  `FOREACH`/`CALL {` list in `_NEO4J_SAFETY`,
  `utils/planner/card_enrichment.py`, is Neo4j-specific syntax, not a
  guaranteed openCypher-wide clause list); the driver library, its
  connection-pooling/session model, and whether it exposes a native
  read-only execution mode all vary by target graph database (Amazon
  Neptune's openCypher support, for instance, is a distinct client surface
  from the Neo4j Python driver). Before reusing `_NEO4J_SAFETY` verbatim,
  confirm the target openCypher database's actual disallowed-clause set and
  read-only session mechanism against its own documentation — that decision
  cannot be made from this repo.

## GQL notes

GQL (ISO/IEC 39075:2024) is a new international standard, not a rebadging of
Cypher, though it was designed with substantial influence from openCypher's
pattern-matching syntax. Kept general, without inventing specifics this
codebase has no evidence for:

- **Likely carries over:** the same declarative pattern-matching shape as
  openCypher/Cypher at the builder level, and the same general validator
  architecture (structural check, read-only-clause rejection, schema/label
  conformance, cap injection) — GQL's core query model is graph-pattern-based
  like Cypher's.
- **Likely differs and needs its own verification pass, not an assumption:**
  the precise clause vocabulary for write/mutating operations, the standard's
  procedure-call and session semantics, and — most importantly — which
  concrete client library and which vendor's GQL implementation this
  specialist targets, since GQL is a standard with multiple independent
  implementations rather than one reference driver. This guide deliberately
  makes no claim about a specific GQL client library's API, session model, or
  clause set — take those from whichever vendor's GQL engine is actually
  targeted, read directly from its documentation and client library, not
  inferred from the Cypher/openCypher implementations in this repo.

## Key files

| Concern | Location |
|---|---|
| Shared scaffold loop, swap-point protocols | `utils/specialists/base.py` |
| Shared validator orchestration, `QueryDraft`/`ValidationResult` | `utils/specialists/validation.py` |
| Gremlin swap points (worked example throughout this guide) | `utils/specialists/gremlin/{builder,validator,connector,normalizer}.py` |
| Cypher swap points (nearer example for openCypher/GQL) | `utils/specialists/cypher/{builder,validator,connector,normalizer}.py` |
| Gremlin/Cypher specialist factories | `utils/specialists/gremlin/specialist.py`, `utils/specialists/cypher/specialist.py` |
| Router / registration | `utils/specialists/__init__.py` |
| Federation, dependency ordering, evidence bundling | `utils/specialists/federation.py` |
| Specialist configuration + env vars | `utils/specialists/config.py` |
| Card enrichment (safety, provenance, connection) | `utils/planner/card_enrichment.py` |
| Source-card dataclass + build/write functions | `utils/kg_builder/registry.py` |
| Graph artifact exporters | `utils/kg_builder/exporters/` |
| GraphStore implementations + factory | `utils/graph_loader/stores/` |
| Canonical join keys | `utils/planner/join_keys.py` |
| Golden evalset questions, banks | `utils/specialists/evalset/questions.py`, `federated_questions.py` |
| Validity / safety / execution scoring | `utils/specialists/evalset/score_{validity,safety,execution}.py` |
| Corpus + e2e evaluation hookups | `utils/planner/evaluation/build_corpus.py`, `utils/evaluation/score_e2e.py`, `utils/evaluation/harness/{run_stage,contracts}.py` |
| Unit + golden test suites | `utils/specialists/tests/` |
| Gold-bank independent verification report | `utils/specialists/tests/golden/VERIFICATION.md` |
| Schema-derived primitives + schema registry | `utils/specialists/primitives/`, `utils/specialists/schema/` |
| LLM query builder (baseline path) | `utils/specialists/llm_builder.py` |
| Pipeline architecture (broader context) | `docs/ARCHITECTURE.md` |
| Source-card shape reference | `docs/source_cards.md` |
