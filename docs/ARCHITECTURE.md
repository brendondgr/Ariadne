# Architecture

Ariadne is a **federated agentic graph-database access prototype**: one layer
that reads schema and metadata from several live graph databases, plans an
analyst's question across them, runs a native read-only query against each
engine, and synthesizes one provenance-linked answer. It exists because
cybersecurity knowledge graphs — adversary techniques, attack patterns,
mitigations, threat intelligence — live on different engines with different
schemas and query languages, so cross-source correlation today means manual
lookups or an offline merge into one graph.

Grounding comes from schema descriptions, source metadata, and executed graph
queries. **No vector index or embedding store** is built from the graph data.
The demonstration sources are MITRE ATT&CK Enterprise (STIX 2.1, loaded into
Neo4j and queried in Cypher) and MITRE CAPEC (XML, loaded into a Gremlin Server
and queried in Gremlin); both fixtures are rebuilt from pinned public downloads.
The governing principle at every seam is **the model drafts, deterministic code
grades**: every stage runs deterministically by default, every LLM seam is
opt-in and backstopped by the deterministic path, and no LLM sits on the
critical path of any safety check.

This document describes the pipeline stage by stage and carries **no
performance numbers**: for anything quantitative read
[`research/CURRENT.md`](research/CURRENT.md). Wire shapes: [`agent-interfaces.md`](agent-interfaces.md);
safety model: [`query-safety.md`](query-safety.md); card format: [`source_cards.md`](source_cards.md).

```
check_cards → probe → plan ─────────────────────────────┐
                        │ (classify → canonicalize → draft → gate)
                        ▼
              announce_querying → specialists → bundle → assess ──sufficient──▶ synthesize → END
                        ▲                                  │
                        └──────────── replan ◀── insufficient
```

## 1. Source cards and discovery

A **source card** is the per-database document everything downstream reads:
introspected node labels, relationship types, node properties and allowed edge
patterns, plus an authored layer of connection, provenance (`id_property`,
`id_scheme`, `source_name`, `dataset_version`), safety limits and one-line
entity glosses. `--build` generates the structural part under
`data/source_cards/` from the loaded graph; `utils/planner/card_enrichment.py`
layers the authored part on at load time. The planner reasons only over the
introspected structural fields; glosses are human context, not routing truth.

**Discovery** is a per-request **content probe**, not a socket open: connect,
confirm a non-trivial node count, confirm expected labels exist — each in its
own short-timeout thread, cached for a few seconds. A backend that is
unreachable, unauthorized, empty or timed out is reported *down with a reason*
so the planner marks the dependent part unsupported instead of failing.

Cross-source joins are only ever proposed on a **declared canonical key present
in both cards** (`utils/planner/join_keys.py`). The one declared bridge is the
ATT&CK technique id: CAPEC `AttackPattern -[MAPS_TO]-> TaxonomyEntry` (taxonomy
`ATTACK`) ↔ ATT&CK `Technique`/`SubTechnique.attack_id`. Anything else is
marked unsupported rather than invented. A third source (the identity schema
of EXP-2026-08-011 and EXP-2026-08-013) was added the same way: a card, a
declared bridge, and one registration line in `build_specialist`.

**Configuration**

| Variable | Default | Controls |
|---|---|---|
| `ARIADNE_DATA_DIR` | `data` | Where `source_cards/` and graph artifacts live |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | `bolt://localhost:5456` / `neo4j` / `password` | ATT&CK probe and connector |
| `GREMLIN_URI` | `ws://localhost:6455/gremlin` | CAPEC probe and connector |
| `ARIADNE_ENDPOINT_<DATASET>` | unset | Per-dataset URI override (two sources on one backend) |
| `PLANNER_PROBE_TIMEOUT_S` / `PLANNER_CACHE_TTL_S` / `PLANNER_MIN_LIVE_NODES` | `4.0` / `5.0` / `1` | Probe timeout, live-view cache, "loaded" threshold |

**Code:** `utils/planner/cards.py`, `utils/planner/discovery.py`, `utils/planner/card_enrichment.py`, `utils/planner/join_keys.py`, `utils/kg_builder/registry.py` (card generation).

## 2. Intent classification

The planner's first node classifies the request into a closed taxonomy
(`utils/planner/intent.py`): `correlation`, `remediation`, `traversal`,
`enumeration`, `lookup`, `definitional`, `unsupported`. Every label has a
concrete plan consequence — `correlation` pulls in a live join partner and
declares the canonical join; `remediation` selects the ATT&CK `MITIGATES` side;
an in-scope id routes a lookup — and a label that changed nothing would not be
carried. The gate (§4) stays the sole authority: intent *biases* the draft and
can never ship a schema-invalid plan, so a mis-classification is safe by
construction.

The default classifier is deterministic priority-cue rules over the request
text. `PLANNER_INTENT_LLM_ENABLED` swaps in a hybrid: an LLM classifier whose
label is validated against the taxonomy and which falls back to the
deterministic label (tagged `source="fallback"`) on any transport, parse or
out-of-taxonomy failure. The classification rides the emitted plan as
`Plan.intent` (omitted when absent), is scored as `intent_accuracy_rate` by the
planner evaluation, and is shown in the workbench's Intent card.

**Configuration**

| Variable | Default | Controls |
|---|---|---|
| `PLANNER_INTENT_LLM_ENABLED` | off | Hybrid LLM classifier instead of deterministic-only |
| `ARIADNE_LLM_BASE_URL` / `ARIADNE_LLM_MODEL` | `http://localhost:9090/v1` / `default-model` | Endpoint the hybrid classifier posts to (`PLANNER_LLM_*` overrides per stage) |

**Code:** `utils/planner/intent.py`, `utils/planner/intent_llm.py`, `utils/orchestration/agents/planner/nodes.py` (the `classify` node).

## 3. Canonicalize (the rewrite stage)

Between `classify` and `draft` sits a node that rewrites the question into a
**canonical tier-0 form in the source card's own vocabulary** — the wording the
deterministic engine answers best. An `IntentForm` reduces the question to a
closed set of slots (mode, anchor, relationship, direction, source); a
deterministic pass binds every slot that stems, exact names and the resolver
ladder can bind; `render` turns the filled form back into a request string.
Everything downstream still receives only a request string, and an unfilled
slot is reported as `unbound`, never replaced by a best guess.

The optional model half fills only the slots the deterministic pass left
unbound, and all it may do is **choose an index from a candidate list it cannot
add to**. Three checks enforce that: the prompt asks for indices, the parser
refuses anything that is not an in-range integer, and `gate_form` re-checks the
finished form against the same closed world. The model may also decline
(`ambiguous`), which abstains. Picks are cached by (prompt version, served
model, question) so evaluation re-runs are free and repeatable.

Both flags are **off by default** (DECISIONS D-032, from EXP-2026-09-014): the
stage missed its pre-registered ship rule. With both off the node is a
pass-through and the pipeline is byte-identical to the captured reference.

**Configuration**

| Variable | Default | Controls |
|---|---|---|
| `ARIADNE_REWRITE` | off | Deterministic fill + canonical renderer |
| `ARIADNE_REWRITE_MODEL` | off | Model fill of unbound slots (requires `ARIADNE_REWRITE`) |
| `ARIADNE_REWRITE_CACHE_DIR` | unset (process default) | Where model picks are cached |

**Code:** `utils/planner/canonical.py`, `utils/planner/rewrite_llm.py`, `utils/planner/rewrite_cache.py`, `utils/orchestration/agents/planner/nodes.py` (the `canonicalize` node).

## 4. Plan drafting and gate

The planner *routes*; it never queries. It emits a machine-readable `Plan`:
target sources, sub-questions with entities and per-sub-question `Limits`
(`max_traversal_depth`, `max_result_rows`, `query_timeout_ms`), declared joins,
explicitly `unsupported` parts, assumptions, and a per-iteration trace.

A **drafter** proposes; a fully deterministic **gate** grades. The default
drafter does card-grounded keyword routing (with stemming and exact-name
anchoring behind `ARIADNE_LEXICON` / `ARIADNE_EXACTNAME`, on by default) and
builds gate-valid plans by construction. When `ARIADNE_LLM_ENABLED` is on — or
`--plan-llm` / `--query-llm` is passed — a `HybridDrafter` posts to the
configured chat endpoint and falls back to the deterministic drafter on any
failure. The gate rejects any plan that names a non-live source, references a
label or edge absent from that source's card, declares a join that is not the
canonical bridge, omits per-sub-question limits or exceeds the card's bounds,
or is degenerate. Rejection reasons feed the next draft, capped at
`PLANNER_MAX_ITERATIONS`; on exhaustion the node **degrades** to an honest
partial plan (gate-valid parts kept, the rest named unsupported) — never an
infinite loop or a fabricated plan.

`PlanningAgent.replan(request, evidence, frontier, gaps)` is the evidence-aware
entry the retrieval loop (§6) calls between hops; its expansions are merged onto
the running plan with de-duplication on `(source, sorted(entities),
normalized_text)` and tagged with their `hop`.

**Configuration**

| Variable | Default | Controls |
|---|---|---|
| `PLANNER_MAX_ITERATIONS` | `3` | Draft → gate → revise cap |
| `ARIADNE_LLM_ENABLED` | `false` | LLM drafter (hybrid, deterministic fallback); `PLANNER_LLM_ENABLED` overrides per stage |
| `ARIADNE_LLM_BASE_URL` / `ARIADNE_LLM_MODEL` / `ARIADNE_LLM_TIMEOUT_S` / `ARIADNE_LLM_MAX_TOKENS` | see `.env.example` §8 | The single LLM group every stage inherits |
| `ARIADNE_LEXICON` / `ARIADNE_EXACTNAME` | on (leave unset) | Stemmed matching + anchor fix; exact-name anchoring |

**Code:** `utils/planner/drafter.py`, `utils/planner/llm_drafter.py`, `utils/planner/drafter_factory.py`, `utils/planner/gate.py`, `utils/planner/agent.py`, `utils/planner/schema.py`, `utils/orchestration/agents/planner/graph.py`.

## 5. Specialists

Each sub-question goes to the specialist serving its source, with that
source's card. Both specialists run **one shared scaffold**
(`utils/specialists/base.py`) — intake → resolve → draft → **pre-run gate** →
execute → assess → normalize → handoff — with **four language-specific swap
points**:

| Swap point | Cypher (ATT&CK / Neo4j) | Gremlin (CAPEC / Gremlin Server) |
|---|---|---|
| Query builder | `utils/specialists/cypher/builder.py` | `utils/specialists/gremlin/builder.py` |
| Validator | `utils/specialists/cypher/validator.py` | `utils/specialists/gremlin/validator.py` |
| Connector | `utils/specialists/cypher/connector.py` | `utils/specialists/gremlin/connector.py` |
| Normalizer | `utils/specialists/cypher/normalizer.py` | `utils/specialists/gremlin/normalizer.py` |

Resolve-to-schema (`utils/specialists/resolve/`) is shared code fed a different
card. The pre-run gate validates every draft deterministically *before* any
database call (read-only, card labels and edges, edge direction, bounded depth,
row cap injected), with the draft → gate loop capped at `SPECIALIST_MAX_RETRIES`.
Execution runs under a per-query timeout and row cap, Neo4j in `READ_ACCESS`
mode. Every `EvidenceRecord` carries full `Provenance` (source, dataset,
backend, executed query, record id, timestamp) and passes a contract check
before it ships. If a resolved task names an entity the card does not model, no
query is drafted: the specialist returns an honest empty with the boundary named.

Three query-construction paths exist. The **template cascade** is the shipped
default: a priority-ordered dispatcher over the resolved task's shape selects a
bounded, parameterized template. The **schema-derived primitives** are the
generic path the same builders route to when no question-shape applies, and
they are what every `generic` and `generic_composed` figure in the research
record is built from. Two live in `utils/specialists/primitives/`: `describe`
returns every property on an anchor plus a bounded *facet block* (a count per
relationship, direction and neighbour label, real zeros folded in from the
schema registry), and `expand` pages one facet's members with a bounded
description and an explicit `truncated` flag — never truncating silently. Four
more are emitted by the builders themselves as generic template identifiers —
`generic_walk`, `generic_chain`, `generic_bridge` and `generic_neighbors` — and
a fifth, `generic_intersect`, exists but is not exercised by any current bank.
All read `utils/specialists/schema/`, not catalogue knowledge.

The distribution is measured rather than asserted. Over the 282-question sealed
set of `EXP-2026-09-018`, the generic arm emitted `generic_walk` 138 times,
`generic_chain` 105, `generic_bridge` 40, `describe` 28 and `generic_neighbors`
4 — five identifiers covering every question, against the 29 shape-specific
templates the cascade carries. The **LLM query builder** (`utils/specialists/llm_builder.py`)
hands a model the schema, seeds and gate constraints and lets it write the query
string; the gate validates it exactly as a template, and it never falls back to
templates. It is **kept as a measured baseline only** and is off by default.

**Federation** (`utils/specialists/federation.py`) runs join-bound
sub-questions in dependency order — the producer (CAPEC via `MAPS_TO`) runs
first and its harvested join values seed the consumer (ATT&CK) as `seed_ids`; a
producer that yields nothing skips the consumer into a dependency abstention,
never a broad unseeded query — and bundles results into `FederatedEvidence`
with a `join_index`. It indexes the join; it does not compose the answer.

**Configuration**

| Variable | Default | Controls |
|---|---|---|
| `SPECIALIST_MAX_RESULT_ROWS` / `SPECIALIST_QUERY_TIMEOUT_MS` | `1000` / `5000` | Fallback row cap and timeout when a task carries no limit |
| `SPECIALIST_MAX_RETRIES` | `2` | Capped redraft loop after a gate rejection |
| `SPECIALIST_EXPAND_PAGE_SIZE` | `50` | Members per `expand` page |
| `SPECIALIST_LLM_QUERY_BUILDER` | `false` | A model writes the query string (baseline only) |
| `ARIADNE_NAMESEARCH` | `false` | Ranked (BM25) name anchoring; stays off, see `.env.example` §7b |

**Code:** `utils/specialists/base.py`, `utils/specialists/validation.py`, `utils/specialists/evidence.py`, `utils/specialists/federation.py`, `utils/specialists/primitives/describe.py`, `utils/specialists/primitives/expand.py`, `utils/specialists/llm_builder.py`, `utils/specialists/__init__.py` (`build_specialist`).

## 6. The retrieval loop

After `bundle`, an **`assess`** node judges whether the accumulated evidence
answers the question. The default judge is deterministic: evidence is
*sufficient* when nothing is left to productively chase — a join key is
chaseable when a producer surfaced it, it has not resolved across sources, and
the consumer side of its declared join has not been queried. When insufficient,
**`replan`** grafts only the missing sub-questions onto the plan and the loop
re-enters the specialists subgraph, which runs only the newly appended
sub-questions seeded from their already-run producers. `ORCH_CHASE_FACETS`
adds a second chase strategy: a question-relevant, unexpanded facet from a
`describe` result counts as a gap and gets a relevance-ranked `expand` hop.
The loop changes the *set* of queries, not the safety model.

Two caveats, both stated in `.env.example`:

* **The code default for `ORCH_MAX_HOPS` is 5, but `.env.example` pins it to
  1**, which makes the loop **inert on a default run**: the assess node
  force-terminates on the first pass (`hop >= max_hops` short-circuits the
  verdict to sufficient) and the graph collapses to bundle → synthesize. Every
  recorded arm not marked "+ loop" was run at 1; set the value explicitly so
  what you ran is recorded.
* **`ORCH_ASSESS_MODE=llm` currently degrades to the deterministic judge no
  matter what.** The LLM critic is an injected dependency and nothing injects
  it — `utils/orchestration/main.py` builds the assess node without a `critic`
  — so the `llm` branch records `"deterministic (llm fallback)"` and moves on.

Termination is guaranteed three ways: the hop cap, the `PIPELINE_TIMEOUT_S`
deadline (past-deadline specialists are skipped honestly), and the recursion limit.

**Configuration**

| Variable | Default | Controls |
|---|---|---|
| `ORCH_MAX_HOPS` | code `5`, `.env.example` `1` | Hard cap on assess → replan → specialists iterations; `1` = single pass |
| `ORCH_ASSESS_MODE` | `deterministic` | `llm` is accepted but degrades (see above) |
| `ORCH_CHASE_FACETS` / `ORCH_MAX_FACET_EXPANSIONS` | off / `4` | Facet-frontier chasing and its per-hop cap |
| `PIPELINE_TIMEOUT_S` | `120` | Total pipeline deadline in seconds |

**Code:** `utils/orchestration/agents/assess/policy.py`, `utils/orchestration/agents/assess/frontier.py`, `utils/orchestration/agents/assess/facets.py`, `utils/orchestration/config.py`, `utils/planner/agent.py` (`replan`).

## 7. Synthesis

Synthesis is a three-node chain — **compose → verify → narrate** — and the
verify edge is unconditional. The **deterministic composer** builds the answer
as structured claims-with-citations from the evidence bundle: every claim is
constructed from a retrieved record, and an empty-but-ok sub-question becomes an
enforced abstention ("the sources don't establish this") carrying the executed
query as proof. The **verifier** then checks every claim against the retrieved
records through four gates — cited, resolvable, grounded, correlated (a
correlation must be backed by the join index) — and cuts what fails from the
rendered prose while keeping it flagged. It also derives the provenance-exact
edges the workbench's network plot draws.

**Conflict detection** runs inside the same pass (`reconcile.py`). Groundedness
cannot catch two sources that both carry a canonical join value yet assert
incompatible facts about it, so a conservative allow-list of two contradiction
kinds is checked: `name` (materially different canonical names after
normalization) and `status` (the authoritative source marks the entity
deprecated or revoked while another source still maps to it as current).
Mapping contradictions are out of scope — the CAPEC → ATT&CK bridge is
single-sourced. A conflict names its `authoritative_source` but never picks a
winner; affected claims stay `supported` and rendered, marked `contested`, and
`conflicts` / `conflict_count` are omitted from the payload when empty.

The **LLM narrator** is the one seam `ARIADNE_LLM_ENABLED` opens here: it
writes a few sentences of plain prose *over the already-verified claims* and
cannot add one; on any failure the deterministic narrative stands. Separately,
`SYNTHESIS_LLM_CLAIMS` lets a model **propose the claims themselves** through
the hybrid composer. It is an instrument, not a default — it is the only
configuration in which the verifier's gates have anything to cut
(EXP-2026-08-014, EXP-2026-08-018) — and it stays off.

**Configuration**

| Variable | Default | Controls |
|---|---|---|
| `ARIADNE_LLM_ENABLED` | `false` | LLM narrator over verified claims (`SYNTHESIS_LLM_ENABLED` overrides per stage) |
| `SYNTHESIS_LLM_CLAIMS` | `false` | Model-proposed claims, verifier-gated; instrument only |
| `SYNTHESIS_MAX_CITATIONS` | `8` | Citations a single claim may carry |
| `VERIFY_GATE_CITED` / `_RESOLVABLE` / `_GROUNDED` / `_CORRELATED` | `true` | Ablation switches; every recorded figure assumes all four on |
| `ARIADNE_LLM_THINKING_BUDGET` | `0` (no cap) | Reasoning-token cap; must stay below `ARIADNE_LLM_MAX_TOKENS` |

**Code:** `utils/synthesis/composer.py`, `utils/synthesis/verifier.py`, `utils/synthesis/reconcile.py`, `utils/synthesis/narrator.py`, `utils/synthesis/factory.py` (`synthesize`, `select_composer`), `utils/orchestration/agents/synthesis/graph.py`.

## 8. Orchestration ownership

`utils/orchestration/main.py` **owns the graph.** `build_pipeline_graph` wires
the LangGraph `StateGraph` drawn at the top of this document — `check_cards`,
`probe`, `plan` (with a plan-only exit), `announce_querying`, the specialists
subgraph, `bundle`, `assess`, `replan`, `synthesize` — and `iter_pipeline`
streams the fixed `(event, payload)` vocabulary (`status`, `probe`, `plan`,
`skipped`, `specialist-start`, `specialist`, `evidence`, `assess`, `answer`,
`done`) that the CLI (`utils/specialists/cli.py`) and the API
(`api/services/query.py`) render without re-deriving status or exit semantics.
`run_pipeline` drains the stream into a `PipelineRun` with per-stage timings;
`state.py` wraps — never redefines — the frozen contracts, and `studio.py` plus
the root `langgraph.json` expose the compiled graph to `langgraph dev`.

`utils/specialists/pipeline.py` is a **compatibility shim**: it re-exports
`iter_pipeline`, `run_pipeline`, `PipelineRun` and `pipeline_timeout_s` from
`utils.orchestration.main` so older imports keep working. New code imports from
the orchestration module directly.

The specialists subgraph runs sub-questions sequentially in dependency order
(deliberately not a fan-out — deterministic ordering backs the committed
baselines). A second graph, `utils/conversation/`, wraps the pipeline for the
workbench's chat pane and reuses `iter_pipeline` verbatim.

**Configuration**

| Variable | Default | Controls |
|---|---|---|
| `ORCH_CHECKPOINTER` | `false` | Opt-in in-memory checkpointer for graph debugging |
| `ORCH_RECURSION_LIMIT` | `200` | LangGraph superstep bound |
| `PIPELINE_TIMEOUT_S` | `120` | Total pipeline deadline |
| `CONVERSATION_LLM_ENABLED` | `false` | Forces the conversational layer's agents on for every turn |

**Code:** `utils/orchestration/main.py`, `utils/orchestration/state.py`,
`utils/orchestration/agents/specialists/graph.py`,
`utils/specialists/pipeline.py` (shim), `utils/conversation/graph.py`.
