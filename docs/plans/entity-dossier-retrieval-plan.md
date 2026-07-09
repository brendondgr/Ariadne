# Entity Dossier Retrieval Mode

## 1. Introduction

When an analyst asks about a single entity by id ("Could you provide me more
details on M1049?"), the pipeline today runs the deterministic `node_lookup`
Cypher template, which returns only `n.attack_id AS id, n.name AS name`. It never
projects the node's description (which lives inside a serialized `properties_json`
blob on Neo4j nodes) and never traverses any edges. The verified failure: M1049
actually has a rich description **and 23 outgoing `MITIGATES` edges**, but the
answer said "no further details or related records available." The answer layer
is not the problem — `utils/conversation/agents/answer.py::evidence_brief()`
already reads `record.properties["description"]` and `record.related`; it simply
receives empty ones because the single-entity normalizer emits `properties={}`
and `related=[]`.

This plan adds an **entity dossier** retrieval path: for a single-entity lookup,
fetch the node's full properties (parsing the description out of
`properties_json`) plus a **capped, typed 1-hop neighborhood**, populate the
existing `EvidenceRecord.properties`/`related` fields, and format a compact
adjacency block into conversational memory so follow-ups are cheap. The memory
representation the analyst requested is:

```
adjacent:
* Edge Title (Type) -> Node Title (ID)
```

Design principles (from the prior good-idea/bad-idea discussion):

- **Additive & gated, no golden churn.** A new deterministic template
  (`node_dossier`) triggers only for single-entity "describe/details" lookups and
  **falls back to today's `node_lookup`** otherwise, so every existing pipeline
  golden stays byte-identical.
- **Cap the fan-out.** High-degree hub nodes must not blow up memory/context —
  the neighborhood is capped with a per-entity limit and marked partial ("+N
  more") when truncated.
- **Hybrid memory: keyed cache + on-demand injection (chosen).** Dossiers are
  stored per-turn keyed by entity id (in the assistant payload), NOT dumped into
  the always-on facts. Each later turn gets (a) a tiny always-on **index** line
  naming which entity ids are held in memory, and (b) the **full detail block**
  only for entities relevant to that turn — entities named by id in the current
  question, plus the most-recently-hydrated entity (to catch pronoun follow-ups
  like "what does it mitigate?"). This keeps per-turn context lean and scales with
  long conversations; if the reference is missed it falls back to re-querying the
  graph (which Steps 1–2 fix). Crucially, the injection is assembled in the
  API/persistence layer as synthetic `history` entries the agents already consume
  (`known_facts` reads `facts`; empty-`content` entries are skipped by
  `render_history_messages`), so **no LangGraph agent/state changes** are needed —
  no new tables, no schema migration.

## 2. Gaps & Unanswered Questions

- **Dossier trigger signal.** The deterministic Cypher builder routes on resolved
  task features. *Assumption*: trigger `node_dossier` when there is ≥1 seed id, no
  compound relationship intent (the current `node_lookup` condition), and a
  "describe/detail/about/more/information" intent term is present in the resolved
  task text/concept terms; otherwise fall back to `node_lookup`. Falling back is
  always safe (today's behavior).
- **"Edge Title" for Neo4j.** Confirmed live: Neo4j edges carry only a STIX `id`,
  no human title. *Assumption*: "Edge Title" = a humanized form of the
  relationship type (`MITIGATES` → "Mitigates"); the line becomes
  `* Mitigates (MITIGATES) -> Phishing (T1566)`. Direction is encoded (outgoing
  vs incoming) so the map is not misleading.
- **Neighbor cap size.** *Assumption*: cap at 25 typed neighbors per entity
  (M1049 has 23), grouped/ordered deterministically, with a "+N more" marker.
  Configurable constant.
- **Gremlin/CAPEC parity.** The analyst's case is ATT&CK/Neo4j. *Assumption*:
  land Neo4j first (Phases 1–2); Gremlin dossier parity is a separate, lower-risk
  phase (Phase 3) since `elementMap()` already returns all properties.
- **Golden/evalset artifacts.** *Assumption*: because the dossier is a new gated
  template, existing goldens are untouched; still run the full backend suite and,
  only if any pinned output legitimately changed, regenerate deliberately with
  reviewed diffs (per repo convention). No human input required unless an
  unexpected golden diff appears.

No blocking unknowns; all gaps have safe fallbacks.

## 3. Hierarchical Step-by-Step Instructions

### Step 1 — Cypher dossier query template (retrieval)

- **Locations**: `utils/specialists/cypher/builder.py`
  (`CypherQueryBuilder.build` routing near line 160; new `_node_dossier` method
  beside `_node_lookup` at line 306). `utils/specialists/resolve.py` /
  `ResolvedTask` if a describe-intent flag/terms must be surfaced for the trigger.
- **What**: Add `_node_dossier(resolved)` returning a `QueryDraft`
  (template=`"node_dossier"`) that projects `n.attack_id, n.name,
  n.properties_json` and an `OPTIONAL MATCH (n)-[r]-(m)` collecting neighbor
  `type(r)`, direction (`startNode(r)=n`), `m.attack_id`, `m.name`, `m` labels,
  bounded by a neighbor cap. Route to it from `build()` under the gated condition;
  otherwise keep calling `_node_lookup` unchanged.
- **Rationale**: Retrieval is the root cause — the description and edges must be
  fetched before anything downstream can surface them. Gating + fallback keeps
  existing behavior/goldens intact.
- **Action**: Undergo the verification/tests/validation for this phase
  (`uv run python -m pytest utils/specialists/tests -q`, plus new builder tests
  asserting the dossier query shape and that non-triggering inputs still emit
  `node_lookup`). Once validated, commit (no push) stating: `Entity Dossier (1/6)
  Complete: added the gated node_dossier Cypher template with capped 1-hop
  traversal.`

### Step 2 — Dossier normalizer (populate properties + typed related)

- **Locations**: `utils/specialists/cypher/normalizer.py` (dispatch at lines
  39–79; new `_normalize_dossier`). Reuse `utils/specialists/evidence.py::emit_record`.
- **What**: Detect the `node_dossier` template / `properties_json` column; parse
  `properties_json`, extract `description` (+ a few key attributes) into
  `properties`; build `related` as `[{type, direction, id, name, label}]` from the
  neighbor rows, deduped, capped, with a `properties["neighbors_truncated"]`/count
  marker when over the cap. Emit one `EvidenceRecord` per primary entity.
- **Rationale**: `evidence_brief()` already consumes `properties["description"]`
  and `related`; populating them is what makes the graph-path answer include the
  description and the mitigated techniques — directly fixing the M1049 answer.
- **Action**: Undergo verification/tests (new normalizer tests: description parsed
  out of a `properties_json` fixture; typed/directional related built; cap +
  partial marker; empty-neighbor node still yields a description record). Once
  validated, commit (no push): `Entity Dossier (2/6) Complete: dossier normalizer
  populates description + capped typed 1-hop neighbors on the evidence record.`

### Step 3 — Dossier model + formatters (index line + detail block)

- **Locations**: `utils/conversation/persistence.py` (new pure helpers beside
  `facts_from_synthesized` at line 23).
- **What**: (a) `dossiers_from_records(records) -> dict[id, EntityDossier]` where
  an `EntityDossier` holds `id`, `name`, a truncated `description` summary, capped
  typed `adjacency` (each neighbor = type/direction/id/name), and a
  `truncated_count`. (b) `dossier_index_line(dossiers) -> str` — the tiny
  always-on "Entities held in memory: M1049 (Antivirus/Antimalware), …" line.
  (c) `dossier_detail_block(dossier) -> str` — the full on-demand block: an entity
  line + `adjacent:` + one `* Edge Title (Type) -> Node Title (ID)` line per
  neighbor (with a "+N more" tail). (d) `entity_ids_in(text) -> set[str]` reusing
  the ATT&CK/CAPEC id regexes.
- **Rationale**: Isolating the model + formatting as tested pure functions pins
  the exact requested memory format and the index/detail split the hybrid strategy
  needs, while keeping the API layer thin.
- **Action**: Undergo verification/tests (unit tests: detail-block exact line
  format + direction + cap/"+N more"; index line; id detection; empty input).
  Once validated, commit (no push): `Entity Dossier (3/6) Complete: dossier model
  + index-line and "adjacent: * Edge (Type) -> Node (ID)" detail-block formatters.`

### Step 4 — Persist keyed dossiers + hybrid on-demand injection

- **Locations**: `api/services/conversations.py` (`stream_conversation_events`
  accumulator ~lines 143–196 to capture the `evidence` event and assemble the
  injection; `_persist_turn` at lines 221–256 to store keyed dossiers).
  `utils/conversation/persistence.py` (`dossiers_from_turns(turns)` cache builder;
  `memory_injection(question, turns)` assembler).
- **What**: (a) Capture federated evidence into `acc["evidence"]`; in
  `_persist_turn` store `payload["entity_dossiers"] = {id: dossier}` (keyed cache),
  leaving `facts` as verified-claim strings only. (b) Build the per-conversation
  cache via `dossiers_from_turns` (latest wins per id). (c) Before
  `iter_conversation`, append ONE synthetic assistant history entry
  (`content=""`, `facts=[index_line] + [detail_block for ids named in the current
  question ∪ the most-recently-hydrated entity]`) so `known_facts` surfaces it and
  `render_history_messages` skips it — no agent changes. Cap total injected blocks.
- **Rationale**: This realizes the chosen hybrid: an always-on index tells the
  model what memory holds, and only the relevant entity's full adjacency is spent
  per turn — cheap follow-ups without context bloat, graceful fallback to re-query.
- **Action**: Undergo verification/tests (`uv run python -m pytest
  api/tests/test_conversations.py utils/conversation/tests -q`; tests: dossiers
  persist keyed by id; a follow-up naming a held entity injects its detail block;
  an unrelated turn injects only the index; recency covers a pronoun follow-up).
  Once validated, commit (no push): `Entity Dossier (4/6) Complete: keyed dossier
  cache with always-on index + on-demand detail injection into next-turn memory.`

### Step 5 — Gremlin/CAPEC dossier parity (secondary)

- **Locations**: `utils/specialists/gremlin/builder.py` (`_capec_lookup` / a
  `_capec_dossier` near lines 115–160), `utils/specialists/gremlin/normalizer.py`
  (`_normalize_single` at line 143 → populate `properties`/`related` from
  `elementMap`).
- **What**: For a single CAPEC entity, keep the `elementMap()` result's
  properties (description is a first-class Gremlin property) into `properties`, and
  add a capped typed neighbor traversal into `related`, mirroring Step 2's shape so
  the same formatter and answer path work unchanged.
- **Rationale**: Cross-source parity so "tell me about CAPEC-98" is as rich as the
  ATT&CK path; lower risk because `elementMap` already returns everything.
- **Action**: Undergo verification/tests (`uv run python -m pytest
  utils/specialists/tests -q`; Gremlin normalizer test populating
  properties/related). Once validated, commit (no push): `Entity Dossier (5/6)
  Complete: Gremlin single-entity path populates description + capped typed
  neighbors for CAPEC.`

### Step 6 — Full-suite regression, live E2E, changelog, merge

- **Locations**: repo-wide backend suite; `web/` (only if any web fixture is
  touched — expected none); `docs/changelog.jsonl`; live stack on fallback ports.
- **What**: Run the full non-live backend suite; assess golden/evalset impact and
  regenerate deliberately only if a pinned output legitimately changed (expected:
  none, since the template is additive/gated). Live-verify against the running
  Neo4j: re-ask "provide more details on M1049" and confirm the answer now
  includes the description and names specific mitigated techniques, and that the
  persisted turn carries the `adjacent:` memory block; confirm a hub node is
  capped with "+N more". Append a changelog entry.
- **Rationale**: The change only counts as done when the real failing question is
  fixed end-to-end over live graphs and nothing else regressed.
- **Action**: Undergo full verification (backend pytest suites green; live E2E
  captured; `web` build only if web changed). Once validated, commit (no push):
  `Entity Dossier (6/6) Complete: full regression + live E2E green; documented.`
  Then, from a clean 100%-green state, merge `worktree-entity-dossier-mode` into
  `main` and re-run the suite post-merge.

## 4. Deliverables

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Dossier Cypher template | Gated single-entity query: full node + capped typed 1-hop | `utils/specialists/cypher/builder.py` |
| Dossier normalizer | Parse description from `properties_json`; build capped typed `related` | `utils/specialists/cypher/normalizer.py` |
| Dossier model + formatters | Index line + `adjacent: * Edge Title (Type) -> Node Title (ID)` detail block | `utils/conversation/persistence.py` |
| Hybrid memory wiring | Persist keyed dossiers; inject index always-on + detail on-demand | `api/services/conversations.py` |
| Gremlin parity | Populate properties/related for single CAPEC entity | `utils/specialists/gremlin/{builder,normalizer}.py` |
| Builder tests | Dossier query shape + non-trigger falls back to `node_lookup` | `utils/specialists/tests/` |
| Normalizer tests | description parse, typed/directional related, cap + "+N more" | `utils/specialists/tests/` |
| Formatter tests | Exact line format, direction, cap, dedupe, empty | `utils/conversation/tests/` |
| Memory persistence test | Dossier facts persist and rehydrate into next-turn history | `api/tests/test_conversations.py` |
| Live E2E note + changelog | M1049 answer enriched; adjacency in memory; hub capped | `docs/changelog.jsonl` |
