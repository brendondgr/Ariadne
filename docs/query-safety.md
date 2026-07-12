# Query Safety Model

This documents every point in Ariadne's request path where a query against a
live graph (Neo4j/Cypher for ATT&CK, Gremlin/TinkerPop for CAPEC) can be
narrowed, capped, or refused before it reaches an analyst. It is written for
someone deciding whether to trust the system with read access to their own
graph, who has not read the code. Enforcement is organized in the order a
request actually passes through it: **plan → pre-run gate → execution →
evidence contract → schema-boundary refusal.**

Two rules govern everything below: **the model drafts, deterministic code
grades**, and **no LLM sits on the critical path of any safety check**. Every
gate described here is plain Python — set-membership, regex, and arithmetic
comparisons against the source card — not a "does this look right?" prompt.

## 1. Plan-level limits (source card + planner gate)

Numeric bounds originate in the source card and are narrowed, never widened,
as they flow downstream.

**Card safety defaults** are authored in
`utils/planner/card_enrichment.py` and layered onto the generated card
at load time (`enrich()`, `card_enrichment.py`):

| Field | Default | Applies to |
|---|---|---|
| `read_only` | `True` | both backends |
| `max_result_rows` | `1000` | both backends |
| `max_traversal_depth` | `3` | both backends |
| `query_timeout_ms` | `5000` | both backends |
| `disallowed_clauses` | `CREATE, MERGE, DELETE, DETACH DELETE, SET, REMOVE, DROP, LOAD CSV, FOREACH, CALL {` | Cypher (ATT&CK) |
| `disallowed_steps` | `addV, addE, drop, property, sideEffect, io` | Gremlin (CAPEC) |

The merge rule (`enrich()`): a non-empty section already on the generated card
wins; for `safety` specifically, the per-backend defaults above are the base
and the generated card's own safety keys (e.g. CAPEC's
`allowed_edge_patterns`) are layered on top. There is no path by which a
generated card can widen these numeric bounds — it can only add structural
schema data.

**The planner's `Plan`** carries one `SubQuestion` per scoped task
(`utils/planner/schema.py`). Each carries its own `Limits`
(`utils/planner/schema.py`; three fields: `max_traversal_depth`,
`max_result_rows`, `query_timeout_ms`). The
deterministic **gate** (`utils/planner/gate.py`) — the planner's sole
authority, per `docs/intent-classification.md` — rejects any sub-question
whose limits are missing or exceed the source card's bound
(`gate.py`):

```
sub-question 1: max_traversal_depth 9 exceeds card bound 3
```

A plan with an out-of-bound sub-question does not ship; the LLM drafter gets
the rejection reason back and must redraft within bounds.

**Specialist config** (`utils/specialists/config.py`) holds a second,
independently-sourced set of defaults — `max_result_rows=1000`,
`query_timeout_ms=5000`, `max_retries=2` — read from the environment
(`SPECIALIST_MAX_RESULT_ROWS`, `SPECIALIST_QUERY_TIMEOUT_MS`,
`SPECIALIST_MAX_RETRIES`). Two independent fallback points use it:
`SpecialistTask.max_rows()`/`max_depth()`/`timeout_ms()` fall back to
hardcoded `1000`/`3`/`5000` (not the config object) if the task's own
`limits` dict is empty (`utils/specialists/contracts.py`); the
connectors' `run()` methods separately read `limits.get(key,
self._config.max_result_rows)` (`cypher/connector.py`) as a second-layer
fallback. In the normal flow the effective-limits dict passed to a connector
is always fully populated by `_effective_limits()`
(`utils/specialists/base.py`), so both fallbacks exist as defensive
redundancy rather than the primary path — but they converge on the same
conservative numbers (1000 / 3 / 5000) either way, so a task that somehow
arrives with a missing limit still resolves to the conservative default
rather than an unbounded query. `max_retries` bounds the specialist loop's
capped redraft attempts (§3).

## 2. Specialist pre-run gate (per-backend check table)

Before any query reaches a database, `BaseValidator.validate()`
(`utils/specialists/validation.py`) runs a fixed sequence of
deterministic checks and only returns `ok=True` — with the query capped — if
every one passes:

1. Structural checks (language-specific)
2. Read-only enforcement
3. Schema conformance
4. Cap rejection (hard depth/traversal violations that can't be fixed by
   capping)
5. Cap injection (append/clamp the row limit)

If any of checks 1–4 fails, the query is rejected outright with a specific
reason and never reaches step 5 or a database call.

### Cypher validator (`utils/specialists/cypher/validator.py`)

| Check | Mechanism | Rejects on |
|---|---|---|
| Structural | Single statement; `MATCH` and `RETURN` present | Multiple statements (`;` inside the body), missing `MATCH`/`RETURN` |
| Read-only | Rejects card `disallowed_clauses` plus `DETACH DELETE`, `LOAD CSV`, `FOREACH`, `CALL {` | e.g. `query contains disallowed write clause: 'CREATE'` |
| Schema: labels | Every `(:Label)` must exist in the card | Unknown node label |
| Schema: relationships | Every `[:TYPE]` must exist in the card | Unknown relationship type |
| Schema: `attack_id` ambiguity | A predicate on `attack_id` requires at least one node label present | `query filters on attack_id but contains no node label` |
| Cap: unbounded depth | Variable-length paths without an upper bound (`[:REL*]`, `[:REL*..]`) | `unbounded variable-length path […] is not allowed` |
| Cap: over-depth | Variable-length paths with upper bound above `max_traversal_depth` | `variable-length path […] exceeds max_traversal_depth 3` |
| Inject `LIMIT` | Appends `LIMIT {max_rows}` if absent; clamps an existing `LIMIT` above the cap | Not a rejection — injection only |

### Gremlin validator (`utils/specialists/gremlin/validator.py`)

Property graphs have no traversal-time schema enforcement, so this validator
is deliberately the heavier of the two — labels, edge direction, and depth are
all enforced in application code.

| Check | Mechanism | Rejects on |
|---|---|---|
| Structural | Query must start with `g.V(` or `g.E(` | Any other start |
| Read-only | Rejects card `disallowed_steps` (`addV`, `addE`, `drop`, `property`, `sideEffect`, `io`) | e.g. `disallowed mutating step '.addV(' found in query` |
| Schema: labels | Every `hasLabel('X')`/`hasLabel("X")` must exist in the card (both quote styles checked) | `hasLabel references unknown label 'X'` |
| Schema: edges | Every `.out('R')`/`.in('R')`/`.both('R')` must exist in the card | `.out('R') references unknown relationship type 'R'` |
| Schema: edge direction | For `.out(rel)` from an anchor label, the anchor must be a valid source in `allowed_edge_patterns`; `.in(rel)` requires a valid target; `.both(rel)` requires either | `.out('R') from 'Label' is not an allowed edge direction (allowed sources: […])` |
| Cap: over-depth | Chained `.out`/`.in`/`.both` steps counted; rejected if count exceeds `max_traversal_depth` (unbounded traversers multiply — a `.limit()` after the fact cannot fix this) | `traversal depth 4 exceeds max_traversal_depth 3 (too many chained out/in/both steps)` |
| Inject `.limit()` | Appends `.limit({max_rows})` if absent; clamps an existing `.limit()` above the cap | Not a rejection — injection only |

Only queries that clear every row in the applicable table are executed
against a database. Neither validator ever mutates a query beyond the
row-cap injection described above — a rejected query is not "fixed," it is
sent back to the builder as feedback for a redraft.

## 3. Execution layer

Even a gate-approved query runs under further, independent constraints — some
enforced by application code, some by the database itself.

| Enforcement | Backend | Mechanism | Who enforces it |
|---|---|---|---|
| Read-only access | Neo4j | Session opened in `neo4j.READ_ACCESS` mode (`cypher/connector.py`) | Neo4j server (protocol level) |
| Per-query timeout | Neo4j | `Query(query, timeout=timeout_s)`, `timeout_s = limits["query_timeout_ms"] / 1000` (`cypher/connector.py`) | Neo4j driver |
| Row capping | Neo4j | Result loop breaks once `len(rows) >= max_rows` (`cypher/connector.py`) | Application (Python loop) |
| Per-query timeout | Gremlin | `client.submit(...).all().result(timeout=timeout_s)` (`gremlin/connector.py`) | Gremlin client |
| Row capping | Gremlin | Retrieved rows sliced to `max_rows` after the call returns — a second cap even though the query already carries an injected `.limit()` (`gremlin/connector.py`) | Application (belt-and-suspenders) |
| Thread isolation | Gremlin | All gremlin-python calls run on a dedicated single-worker thread, isolating the driver's internal event loop from a host loop (e.g. a notebook kernel) | `ThreadPoolExecutor` |

Row and timeout limits are read from the task's own `limits` dict first,
falling back to `SpecialistConfig` defaults only if a task carries none
(`cypher/connector.py`, `gremlin/connector.py`) — the same
conservative numeric defaults as the card (§1).

**App vs. driver enforcement, summarized:** read-only access is the one check
enforced by the database itself (Neo4j's `READ_ACCESS` session mode); every
other execution-layer constraint — timeout and row capping on both backends —
is enforced by Ariadne's own connector code around the driver call, not by
the database.

Above execution, the specialist loop (`utils/specialists/base.py`) adds two
more checkpoints:

| Checkpoint | Enforcement | Outcome on failure |
|---|---|---|
| Intake | Task carries a `sub_question_id`; task's declared source matches this specialist's card dataset (`_intake()`, `base.py`) | `SpecialistResult(ok=False, partial=True, ...)` — no query drafted or executed |
| Gate loop | Capped redraft loop, `max_retries + 1` attempts (`_loop()`, `base.py`) | After exhausting retries: `ok=False, partial=True, error="pre-run gate rejected all drafts: ..."` |

## 4. Post-execution evidence contract

Passing the pre-run gate and executing successfully is not sufficient for a
result to ship. Two more deterministic checks run on the returned rows.

**Result-shape assessment** (`assess_rows()`, `utils/specialists/base.py`):

| Check | Failure mode |
|---|---|
| Result is a list | `ok=False`: "result is not a list of rows" |
| Every row is a mapping | Non-dict rows are flagged in `reasons` but do **not** fail the run |
| Emptiness | An empty result is a valid "none found" — never fails |
| Join-key integrity (ATT&CK joins) | Every join value must match `T\d{4}(?:\.\d{3})?`; mismatches are recorded in the trace, not silently dropped |

**Evidence contract** (`check_record()`/`check_contract()`,
`utils/specialists/evidence.py`) — every `EvidenceRecord` must satisfy:

| Required | Rule | Failure reason |
|---|---|---|
| `primary_id` or `name` | At least one present | "record has neither a primary_id nor a name" |
| `id_scheme` | Non-empty | "record {id} missing id_scheme" |
| `label` | Non-empty | "record {id} missing label" |
| `provenance` object | Present | "record {id} missing provenance" |
| `provenance.source` | Non-empty | "record {id} provenance missing 'source'" |
| `provenance.dataset` | Non-empty | "record {id} provenance missing 'dataset'" |
| `provenance.backend` | Non-empty | "record {id} provenance missing 'backend'" |
| `provenance.query` | Non-empty | "record {id} provenance missing 'query'" |
| `provenance.record_id` | Non-empty | "record {id} provenance missing 'record_id'" |
| `provenance.timestamp` | Non-empty ISO-8601 | "record {id} provenance missing 'timestamp'" |

The contract is checked once per result, right before it is returned
(`base.py`):

```python
contract = check_contract(records)
ok = not contract
return SpecialistResult(..., ok=ok, error="; ".join(contract) if contract else None)
```

A contract failure sets `ok=False` and surfaces the violation text as the
result's `error` — the result is not shipped silently degraded, and the
executed `query` is always part of every record's provenance, so any shipped
evidence is independently traceable back to the exact query that produced it.

## 5. Schema-boundary refusals

If a resolved task names an entity the source card does not model, no query
is drafted at all. This is a deliberate refusal, not a soft degradation
(`base.py`, the `resolve()` step before the gate loop):

```python
if resolved.unknown_entities:
    return SpecialistResult(
        ok=True, partial=False, records=[], query="",
        summary=f"The {dataset} source doesn't model {unknown} — "
                f"no query can express this question against its schema.",
    )
```

The rationale: answering with whatever the known entities *can* express would
silently answer a different question than the one asked. An honest empty
result — `ok=True`, zero records, no query text, the boundary named in the
trace — is preferred over a plausible-looking but wrong answer.

## 6. The two never-cut checkpoints

`docs/specialist_agents.md` (§ "Validation — where it lives") names exactly
two checkpoints as non-negotiable, and both are load-bearing for trust in
this system:

1. **Pre-run gate** (`utils/specialists/validation.py`, checked in the
   loop at `base.py`) — keeps a bad query off the database entirely.
   Covers syntax/shape, schema conformance, read-only enforcement, and
   depth-bound rejection, in that order, for every draft before it can touch
   a live connection.
2. **Normalize/contract check** (`utils/specialists/evidence.py`,
   checked in the loop at `base.py`) — keeps malformed or
   under-provenanced evidence out of synthesis, after execution.

Both gates set the pass/fail verdict directly; neither silently truncates or
downgrades a result to make it look like it passed. A rejection is always
visible as `ok=False` plus a specific reason string, recorded in an
`EvaluatorTrace` either way.

## 7. Defense in depth

No single layer above is the only thing standing between a request and an
unsafe outcome. If any one layer is disabled or misconfigured, others still
hold:

- **If the card's numeric safety defaults were ever loosened or omitted** —
  the pre-run gate still hard-rejects unbounded/over-depth traversals
  (`cap_reasons()` in both validators) independent of what limit value it was
  handed, and both connectors fall back to conservative defaults
  (1000 rows / 5000 ms) if a task's `limits` dict is empty
  (`contracts.py`).
- **If the pre-run gate were bypassed for a given draft** (e.g. a future LLM
  query builder that skips it) — execution still opens the Neo4j session in
  `READ_ACCESS` mode, so a write clause that slipped past the gate is refused
  by the database protocol itself, not just by application logic.
- **If a query somehow returned an unbounded row count from the database** —
  the connector's own loop still caps rows client-side
  (`cypher/connector.py`; `gremlin/connector.py` explicitly
  re-caps even though the query already carries an injected `.limit()`).
- **If a malformed or under-provenanced record slipped through normalization**
  — the evidence contract check still fails the result (`ok=False`) rather
  than letting it reach synthesis.
- **If an entity genuinely isn't modeled by a source** — the schema-boundary
  refusal fires before any query is drafted, regardless of what the gate or
  connector would have done with a plausible-looking substitute query.

The general shape: gate rejection and connector-side capping are independent
implementations of overlapping constraints (row caps and depth caps each
exist in two places — the gate and the connector), so a defect in one does
not remove the other.

## 8. Adversarial audit

**Harness:** `utils/specialists/evalset/score_safety.py`. Two independent,
hermetic (no live database) checks:

1. **Adherence audit** (`audit_query()`, `score_safety.py`) — an
   independent bounds check run against every query the gate *accepted* in
   the golden question bank: read-only (no write clause/step), a `LIMIT`
   present and ≤ the cap, no unbounded variable-length path. This re-checks
   the gate's own output text rather than trusting the gate's `ok=True`
   verdict — the audit does not call into the validator that produced the
   query.
2. **Adversarial probes** (`PROBES`,
   `utils/specialists/tests/fixtures/adversarial_probes.py`) — hand-crafted
   queries fed straight to the validator (bypassing the builder entirely).
   The validator must reject 100% of them; a probe that returns `ok=True` is
   recorded as a `leak` and is treated as a hard security failure, not a rate.

### What was probed

| Backend | Probe | Query | Tests |
|---|---|---|---|
| Cypher | `write_create` | `MATCH (t:Technique) CREATE (e:Evil) RETURN t` | CREATE rejection |
| Cypher | `write_detach_delete` | `MATCH (t:Technique) DETACH DELETE t` | DETACH DELETE rejection |
| Cypher | `write_set` | `MATCH (t:Technique) SET t.owned = true RETURN t` | SET rejection |
| Cypher | `write_merge` | `MERGE (t:Technique {attack_id:'T1'}) RETURN t` | MERGE rejection |
| Cypher | `call_subquery` | `MATCH (t:Technique) CALL { CREATE (x) } RETURN t` | CALL {} subquery rejection |
| Cypher | `load_csv` | `LOAD CSV FROM 'file:///etc/passwd' AS r RETURN r` | LOAD CSV rejection |
| Cypher | `unbounded_varlen` | `MATCH (t:Technique)-[:MITIGATES*]-(m) RETURN m` | Unbounded variable-length path |
| Cypher | `over_depth_varlen` | `MATCH (t:Technique)-[:MITIGATES*1..9]-(m) RETURN m` | Over-depth variable-length path (9 > 3) |
| Cypher | `unknown_label` | `MATCH (x:Secret) RETURN x` | Unknown node label |
| Cypher | `no_match` | `RETURN 1` | Missing MATCH clause |
| Gremlin | `write_addv` | `g.addV('Evil')` | addV rejection |
| Gremlin | `write_adde` | `g.V().addE('pwn')` | addE rejection |
| Gremlin | `write_drop` | `g.V().drop()` | drop() rejection |
| Gremlin | `write_property` | `g.V().property('owned', true)` | property() mutation rejection |
| Gremlin | `over_depth` | `g.V().out(...).out(...).out(...).out(...)` (4 chained `.out()`) | Over-depth traversal (4 > 3) |
| Gremlin | `unknown_label` | `g.V().hasLabel('Secret')` | Unknown label |
| Gremlin | `not_traversal` | `g.addE('x')` | Doesn't start with `g.V(`/`g.E(` |

A deliberate absence: a query missing a `LIMIT`/`.limit()` is not in this
probe list, because the gate *injects* a cap for that case rather than
rejecting it — that behavior is covered by the adherence audit, not the
probe suite.

### Results

Both checks report `100%`: `probe_block_rate = probes_blocked / probes_total
= 1.0`, and the adherence audit's `breaches` / probe suite's `leaks` lists
are both required to be empty (`score_safety.py`, `109-117`). A
non-empty `leaks` or `breaches` list is a hard failure of the safety score,
not a degraded rate.

### The real bypass it caught and fixed

The `unknown_label` Gremlin probe (`g.V().hasLabel('Secret')`) surfaced a
genuine gap the first time the probe suite ran: the schema-check regex for
`hasLabel(...)` only matched double-quoted string literals. A
single-quoted call — `hasLabel('Secret')` — is equally valid Gremlin/Groovy
syntax but evaded the schema check entirely, i.e. an unknown label could slip
past validation if phrased with single quotes.

Fix: the label/edge regexes in `utils/specialists/gremlin/validator.py`
(`_HAS_LABEL_RE` and the `.out()`/`.in()`/`.both()` equivalents) were hardened
to accept both quote styles (`gremlin/validator.py`). This was found
and fixed in the same commit that introduced the probe suite (`33c69157`,
"safety-adherence audit + adversarial gate probes") — the probe suite is why
the gap was found before it shipped as a silent bypass, not after.

## Configuration reference

### Environment variables

| Variable | Default | Effect |
|---|---|---|
| `SPECIALIST_MAX_RESULT_ROWS` | `1000` | Row cap fallback when a task carries no explicit limit |
| `SPECIALIST_QUERY_TIMEOUT_MS` | `5000` | Timeout fallback (ms) when a task carries no explicit limit |
| `SPECIALIST_MAX_RETRIES` | `2` | Max redraft attempts after a gate rejection (loop runs `max_retries + 1` total attempts) |
| `SPECIALIST_LLM_ENABLED` | off | Reserved LLM query-builder seam: parsed into `SpecialistConfig.llm_enabled` but not consumed by any builder yet — the deterministic template builder is currently the only query-drafting path, so this flag has no safety impact today |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | `bolt://localhost:5456` / `neo4j` / `password` | Neo4j connection (env is the source of truth — the card's `connection` block is informational and intentionally unused for connecting, see `docs/source_cards.md`) |
| `GREMLIN_URI` | `ws://localhost:6455/gremlin` | Gremlin connection |

### Card safety fields (authored defaults)

| Field | Default | Backend |
|---|---|---|
| `read_only` | `True` | both |
| `max_result_rows` | `1000` | both |
| `max_traversal_depth` | `3` | both |
| `query_timeout_ms` | `5000` | both |
| `disallowed_clauses` | `CREATE, MERGE, DELETE, DETACH DELETE, SET, REMOVE, DROP, LOAD CSV, FOREACH, CALL {` | Cypher (ATT&CK) |
| `disallowed_steps` | `addV, addE, drop, property, sideEffect, io` | Gremlin (CAPEC) |

All of the above are hard ceilings a plan's per-sub-question `Limits` may
narrow but never widen (`gate.py`); the pre-run gate independently
enforces the depth/read-only/schema constraints regardless of what value
reaches it.

## Key files

| Concern | Location |
|---|---|
| Card safety defaults + merge | `utils/planner/card_enrichment.py` |
| Sub-question `Limits`, `Plan.intent` | `utils/planner/schema.py` |
| Planner gate (limits vs. card bound) | `utils/planner/gate.py` |
| Specialist config (env-driven ceiling) | `utils/specialists/config.py` |
| Shared pre-run gate scaffold | `utils/specialists/validation.py` |
| Cypher validator | `utils/specialists/cypher/validator.py` |
| Gremlin validator | `utils/specialists/gremlin/validator.py` |
| Neo4j connector (read-only session, timeout, row cap) | `utils/specialists/cypher/connector.py` |
| Gremlin connector (timeout, row cap, thread isolation) | `utils/specialists/gremlin/connector.py` |
| Specialist scaffold loop (intake, gate loop, assess, contract) | `utils/specialists/base.py` |
| Evidence contract + provenance check | `utils/specialists/evidence.py` |
| Adversarial probes | `utils/specialists/tests/fixtures/adversarial_probes.py` |
| Safety audit harness | `utils/specialists/evalset/score_safety.py` |
| Architecture overview + never-cut checkpoints | `docs/specialist_agents.md` |
