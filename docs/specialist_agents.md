# Source-Specific Query Specialists

The query specialists (`utils/specialists/`) sit between the **planning agent**
(`utils/planner/`) and the future synthesis agent. Each receives one *filtered
task* (a planner sub-question) plus its **source card**, drafts a bounded,
read-only query, validates it deterministically **before** touching the
database, executes it under hard caps, normalizes the evidence into a **shared
schema with provenance**, and hands grounded evidence (not prose) onward.

There are two specialists built on **one shared scaffold** with **four
language-specific swap points**:

| | Cypher specialist | Gremlin specialist |
|---|---|---|
| Source | MITRE ATT&CK | MITRE CAPEC |
| Backend | Neo4j (Cypher) | Gremlin Server (TinkerPop) |
| Dataset key | `attack` | `capec` |

Governing principle, inherited from the planner: **the model drafts,
deterministic code grades.** A deterministic query builder is the always-on
default (it produces gate-valid queries by construction); an optional LLM seam
can be enabled later without changing the scaffold.

## Run it

```bash
# Plan a question, then run the specialists over the plan (end-to-end):
uv run main.py --query "Which CAPEC patterns related to credential theft map to ATT&CK techniques, and what mitigations appear for those techniques?"
uv run main.py --query-llm --query "<question>"   # draft the plan with the local LLM

# Step-by-step notebook (planner -> specialists -> evidence, runnable):
uv run --with jupyterlab jupyter lab notebooks/planning-schematic-agents.ipynb
```

`--query` probes the live graphs, prints the routing plan, runs each specialist,
and prints the validated query, normalized records, grounded summary, and the
cross-source join index. Exit code: `0` fully answered, `1` partial (a source
down / a part unsupported / a specialist failure), `2` no source cards built.

## The internal loop (both specialists)

```
intake → resolve → draft → PRE-RUN GATE → execute → assess → normalize → handoff
                              (cheap, before any DB call)      (judge the rows)
```

Two distinct checkpoints, never cut: the **pre-run gate** (keeps a bad query off
the DB) and the post-execution **assess + evidence-contract** check (keeps bad
evidence out of synthesis). Both are deterministic Python. The draft→gate loop
is **capped** (`SPECIALIST_MAX_RETRIES`, default 2) so a failing draft cannot
loop forever. Every checkpoint is recorded in an `EvaluatorTrace`.

## Shared scaffold + four swap points

Shared (build once): the source-card reader, the task intake, the
resolve-to-schema step, the ReAct loop with its evaluator traces, the evidence
emitter + contract check, and the validator-base orchestration.

| Swap point | Cypher (ATT&CK / Neo4j) | Gremlin (CAPEC / Gremlin) |
|---|---|---|
| **Query builder** | bounded `MATCH` templates (`cypher/builder.py`) | bounded `g.V()` traversals (`gremlin/builder.py`) |
| **Validator** | STIX type + label/clause checks (`cypher/validator.py`) | vertex/edge label + edge-direction + depth checks (`gremlin/validator.py`) |
| **Connector** | read-only Neo4j driver (`cypher/connector.py`) | TinkerPop client (`gremlin/connector.py`) |
| **Normalizer** | rows → evidence schema (`cypher/normalizer.py`) | traversal results → evidence schema (`gremlin/normalizer.py`) |

> **Resolve-to-schema is shared code, different data** (`resolve.py`): the only
> thing that changes is which source card is fed in. **Query construction is
> different code** — Cypher is declarative pattern-matching; Gremlin is
> imperative traversal — so the two are separate implementations.

## Validation — where it lives

| Checkpoint | What it checks | Type |
|---|---|---|
| Intake | Task targets this specialist's source; required fields | Deterministic |
| Resolve | Entities map to card labels/edges; ID format; STIX-type / taxonomy pairing | Deterministic |
| **Pre-run gate** | Syntax/shape; every label/edge exists in the card; **edge direction** (Gremlin); read-only (write-clause/step rejection); **unbounded/over-depth traversal rejection**; inject/clamp row limit | Deterministic |
| Execute | DB-level read-only role (Neo4j `READ_ACCESS`); per-query timeout; row cap | Infra |
| Assess | Result shape; emptiness (a valid "none found"); **join-key integrity** | Deterministic |
| **Normalize / contract** | Output conforms to the evidence schema; provenance present on every record | Deterministic |

Two checks are **never cut**: the pre-run gate and the normalize/contract check.
The Gremlin validator is deliberately the heavier one — property-graph
traversals have no traversal-time schema enforcement and unbounded traversers
multiply, so labels, edge direction, and depth are enforced in application logic.
The full safety model — every enforcement point in execution order, the
defense-in-depth argument, and the adversarial audit — is in
[`query-safety.md`](query-safety.md).

## Evidence schema (the synthesis contract)

Every record both specialists emit conforms to `EvidenceRecord`:

```json
{
  "primary_id": "T1574.010",          // join-relevant id (T-number or CAPEC-N)
  "id_scheme": "attack-id",
  "label": "SubTechnique",
  "name": "Services File Permissions Weakness",
  "properties": { "...": "..." },
  "related": [ {"id": "M1047", "name": "Audit"} ],
  "join_values": ["T1574.010"],        // the cross-source spine
  "provenance": {
    "source": "MITRE ATT&CK Enterprise", "dataset": "attack", "backend": "neo4j",
    "query": "MATCH (t:SubTechnique)<-[:MITIGATES]-(m:Mitigation) WHERE ... LIMIT 1000",
    "record_id": "T1574.010", "timestamp": "2026-06-29T19:00:00+00:00"
  }
}
```

The canonical **join key** is the ATT&CK technique id. The Gremlin specialist
emits it `T`-prefixed and **only** for `MAPS_TO` edges whose `TaxonomyEntry` is
in the `ATTACK` taxonomy (the live `MAPS_TO` set also contains `WASC` entries).
A `SpecialistResult` carries the validated query, the records, a grounded
summary, the evaluator traces, and (per record) full provenance.

> **Integration-frozen seams (Wk 10–11).** The four boundary contracts are frozen as the
> end-to-end integration seams and guarded by contract tests: `Plan → SpecialistTask`
> (`from_sub_question`, no silent field drops), `Specialist → SpecialistResult`
> (`EvidenceRecord` + non-null `Provenance`, ATTACK-only join values from Gremlin),
> `results → FederatedEvidence` (one shared `partial` rule), and
> `FederatedEvidence → SynthesizedAnswer` (every rendered claim resolves to a retrieved
> record; empties abstain with query proof). Changes to these shapes require updating the
> seam tests deliberately. Each seam is documented field-by-field — wire shapes,
> omit-when-empty rules, consumer guidance — in [`agent-interfaces.md`](agent-interfaces.md).

## Federation (weaving into the planner)

`federation.py` takes a planner `Plan` and routes each sub-question to the
specialist serving its source, returning a `FederatedEvidence` bundle with a
`join_index` over the shared key (a value reported by two sources is a
cross-source candidate). The handoff is **evidence, not prose**: the federation
indexes the join; it does **not** perform the cross-source join or compose the
final answer — that remains the synthesis agent's job.

**Dependent sequencing (Wk 10–11).** Sub-questions bound by a declared join run
in dependency order, derived from the canonical key's endpoints — the endpoint
that reaches the key via a mapping edge (CAPEC via `MAPS_TO`) *produces* join
values; the endpoint whose records natively carry the key (ATT&CK `attack_id`)
*consumes* them. The producer runs first; its T-prefixed `join_values` are
harvested, deduped, sorted, capped at the consumer's `max_result_rows` (honest
truncation, recorded), and injected as the consumer task's `seed_ids`. A
producer that fails or yields zero join values skips the consumer into a
dependency abstention (ok, zero records, NO query executed, the dependency
named in the trace) — never a broad unseeded query. Each seeded/skipped
consumer is recorded in `FederatedEvidence.sequencing`. Independent
sub-questions run exactly as before. The A-vs-B decision (parallel+join vs
sequencing) was made on evidence: the parallel run failed the snapshot-derived
credential-theft gold (0/64 mitigation pairs, 84-vs-18 correlation set); the
sequenced run reproduces it exactly (see `docs/changelog.jsonl` and
`utils/specialists/tests/golden/option{A,B}_verdict.json`).

**One pipeline orchestrator.** `pipeline.py` owns the whole composition —
probe → plan → sequenced specialists → bundle → synthesize — as
`iter_pipeline()`, a synchronous generator yielding raw-object events at every
boundary; `run_pipeline()` drains it into a `PipelineRun`. The CLI
(`cli.py::run_query_command`) and the API (`api/services/query.py`) are pure
presentation over the same events, so status/exit semantics cannot diverge
(`bundle_evidence()`/`status_and_exit()` in `federation.py` are the single
partial/exit rule). The run records per-stage wall-clock timings (`plan_ms`,
per-specialist `ms`, `synthesis_ms`, `total_ms`) for the Wk 11–13 evaluation,
and `PIPELINE_TIMEOUT_S` (default 120 s) bounds multi-hop runs by honestly
skipping specialists that would start past the deadline.

**Concept vocabulary.** `concepts.py` holds the committed concept→anchor-term
map (e.g. "credential theft" → credential/password/authentication). The
Gremlin `capec_maps_to` template scopes its name filter with these terms, and
`evalset/federated_gold.py` selects the expected pattern set with the *same*
terms — one source of truth, so the pipeline and its gold cannot drift.

## Configuration

All via the central `.env` (`utils.config` helpers); real env vars win. The
specialists connect to the **env-driven** endpoints, not the card's
`connection.uri`.

| Variable | Default | Controls |
|---|---|---|
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | `bolt://localhost:5456` / `neo4j` / `password` | Cypher connector |
| `GREMLIN_URI` | `ws://localhost:6455/gremlin` | Gremlin connector |
| `SPECIALIST_QUERY_TIMEOUT_MS` | `5000` | Per-query timeout |
| `SPECIALIST_MAX_RESULT_ROWS` | `1000` | Hard row cap |
| `SPECIALIST_MAX_RETRIES` | `2` | Capped redraft loop |
| `SPECIALIST_LLM_ENABLED` | `false` | Reserved LLM seam (deterministic always works) |

## Tests

```bash
uv run python -m pytest utils/specialists/tests/
```

Covers the contracts/evidence/resolve/validator base, the scaffold loop, both
validators (write/label/direction/depth negatives), both specialists (unit with
fake connectors + live `@pytest.mark.live`/`integration` tests that skip when the
stack is unreachable), and the federation router. The live tests exercise real
records against the running Neo4j/Gremlin stack (e.g. `T1047` → `M1038`, `CAPEC-66`
→ `CWE-89`/`CWE-1286`, `CAPEC-1` → `T1574.010`).

## Multi-hop execution (iterative-retrieval loop)

The specialist subgraph is unchanged by the
[iterative-retrieval loop](iterative-retrieval-loop.md): when a hop is
insufficient, the re-plan appends new sub-questions and the loop re-enters the
same subgraph with `cursor` left where it stopped. Because `execution_order`
keeps appended sub-questions after the originals, each hop runs **only** the
newly added sub-questions — seeded from their already-run producers through the
existing declared-join `harvest_seed_ids` path. No new query surface, no change
to the honesty guarantees (dependency skips, deadline skips, boundary refusals);
only the *set* of sub-questions is dynamic.
