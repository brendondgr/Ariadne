# Source Card Format

Source cards are JSON files agents read at runtime to locate, route to, and
safely query a graph backend. One card per dataset lives in
`data/source_cards/<dataset>.json`, written by the build pipeline
(`uv run main.py --build attack|capec`). The planner routes **only** on what a
card declares; the specialists bound every query by it. This document is the
card's format specification: every field, where it comes from, who consumes
it, and what a new source's card must contain.

## Lifecycle: three layers

A card passes through three layers before an agent sees it:

```
--build  ─▶  generated card            utils/kg_builder/registry.py
             (structural truth from      build_*_source_card()
              schema.json + manifest)      │
             + overlay merge, if a         │  data/source_cards/overlays/
               local overlay file exists   │  <dataset>.overlay.json (untracked)
                    ▼
             data/source_cards/<dataset>.json
                    ▼
load time ─▶ enrichment                 utils/planner/card_enrichment.py
             (committed authored          enrich(), called by
              defaults fill any            SourceCardView.from_card_dict()
              empty authored section)      utils/planner/cards.py
                    ▼
             SourceCardView — what the planner, gate, and specialists consume
```

1. **Generation (build time).** `write_attack_source_card` /
   `write_capec_source_card` (`utils/kg_builder/registry.py`) build the card
   from the canonical artifacts: structural fields are introspected from
   `schema.json`, export paths from `manifest.json`, and the snapshot pin from
   `data/versions.json`. Generated fields are overwritten on every build.
2. **Overlay merge (build time, optional).** If
   `data/source_cards/overlays/<dataset>.overlay.json` exists on disk, its
   top-level sections are merged onto the card (`_load_overlay`). **Overlay
   files are git-ignored** (the `*.overlay.json` pattern) — they are a local
   authoring convenience, not the committed source of authored metadata. A
   fresh clone has no overlays and builds cards whose authored sections are
   empty. Overlay absence is never an error.
3. **Enrichment (load time).** When the planner loads cards
   (`load_source_cards` → `SourceCardView.from_card_dict` → `enrich()`), the
   **committed** authored metadata in `utils/planner/card_enrichment.py`
   fills any authored section that is still empty. This layer is version
   controlled and is what CI and a fresh clone actually run on.

Precedence per section: a non-empty section already on the card (generated or
overlay-supplied) wins; enrichment only fills gaps. `safety` is the exception —
it is a three-way merge: per-backend defaults as the base, the authored
enrichment values on top, then whatever safety keys the card already carries
(e.g. CAPEC's generated `allowed_edge_patterns`) last, so generated structural
constraints always survive.

## Field reference

### Generated structural fields (overwritten every build)

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `dataset` | string | build function | Registry key: `"attack"`, `"capec"` — the routing identity |
| `runtime_backend` | string | build function | `"neo4j"` \| `"gremlin"` — which specialist serves it |
| `node_labels` | list[str] | `schema.json` | Introspected node labels — routing truth |
| `relationship_types` | list[str] | `schema.json` | Introspected edge types — routing truth |
| `node_properties` | object | `schema.json` | Per-label property inventory (types, examples) |
| `schema_version` | string | `schema.json` | Canonical schema version |
| `canonical_dir` / `canonical_manifest` | string | build config | Paths to the canonical artifact and its manifest |
| `exports` | object | `manifest.json` | Per-backend export artifact paths (`neo4j`, `gremlin`) |
| `endpoints` | object | build function | Written empty; live endpoints come from env, never the card |
| `identity` (base) | object | build function | Join-key contract + measured collisions — see below |
| `safety.allowed_edge_patterns`, `safety.relationship_natures` | object / list | `schema.json` (CAPEC) | Generated structural constraints merged into `safety` at build |

### Authored sections (overlay at build; enrichment at load)

| Section | Carries | Committed source |
|---------|---------|------------------|
| `connection` | How a specialist would connect (informational — see below) | `card_enrichment.py` `ENRICHMENT` |
| `safety` | Numeric bounds + disallowed operations the gate and specialists enforce | `card_enrichment.py` (`_NEO4J_SAFETY` / `_GREMLIN_SAFETY`) |
| `provenance` | Citation metadata (joined with the generated snapshot pin) | `card_enrichment.py` + `_pinned_provenance` |
| `entity_descriptions` | One-line human glosses per label / relationship | `card_enrichment.py` |
| `identity` (policy) | Human-readable identity/join policy statements | overlay when present |

## Section specifications

### `connection`

| Field | Type | Description |
|-------|------|-------------|
| `backend` | string | `"neo4j"` or `"gremlin"` |
| `uri` | string | Driver URI (`bolt://…` or `ws://…/gremlin`) |
| `database` | string | (Neo4j) database name |
| `traversal_source` | string | (Gremlin) traversal-source name, e.g. `"g"` |
| `auth_env` | object | Credential roles → **env-var names** (never literal secrets) |
| `read_only` | bool | Whether the connection enforces read-only mode |
| `timeout_ms` | int | Connection-level timeout in milliseconds |

Two hard rules:

- **No literal secrets.** `auth_env` holds env-var *names* (e.g.
  `"NEO4J_PASSWORD"`). The contract test `test_*_no_literal_secrets` walks the
  whole card and rejects anything password-shaped.
- **The card's connection block is informational, not operative.** The
  specialists and the planner's liveness probe connect to the **env-driven**
  endpoints (`NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD`, `GREMLIN_URI` —
  `utils/specialists/config.py`), never to `connection.uri`. This keeps a
  stale card from silently pointing agents at the wrong database.

### `safety`

Guardrails the planner's gate checks at plan time and the specialists enforce
before and during every query.

| Field | Type | Description |
|-------|------|-------------|
| `read_only` | bool | Hard block on write operations |
| `max_result_rows` | int | Row cap (default 1000) — injected/clamped into every query |
| `max_traversal_depth` | int | Maximum hop depth (default 3) — over-depth queries are rejected |
| `query_timeout_ms` | int | Per-query timeout (default 5000) |
| `disallowed_clauses` | list[str] | (Cypher) clauses that must not appear in any query |
| `disallowed_steps` | list[str] | (Gremlin) steps that must not appear in any traversal |
| `allowed_edge_patterns` | object | (CAPEC, **generated**) relationship type → allowed `[source, target]` label pairs |
| `relationship_natures` | list[str] | (CAPEC, **generated**) CAPEC-native vs derived edge classification |

Enforcement is layered — see [`query-safety.md`](query-safety.md) for the full
model. In brief: the planner gate rejects any sub-question whose limits are
missing or exceed the card's bounds (`utils/planner/gate.py`); the specialist
validators reject disallowed clauses/steps, unknown labels/edges, wrong edge
directions, and over-depth traversals, and inject/clamp the row cap
(`utils/specialists/{cypher,gremlin}/validator.py`); the connectors apply the
timeout and row cap at execution (`.../connector.py`).

The numeric limits are deliberately pinned equal between the enrichment layer
and the specialist env defaults —
`test_card_limits_agree_with_specialist_env_defaults`
(`utils/planner/tests/test_card_enrichment.py`) fails if they drift.

### `provenance`

Identifies the dataset so evidence can be cited correctly. The generated part
(`dataset_version`, `raw_sha256`, `snapshot_pinned`) records the pinned raw
snapshot; the authored part names the scheme.

| Field | Type | Description |
|-------|------|-------------|
| `id_property` | string | Node property holding the dataset's primary identifier |
| `source_ref_property` | string | (ATT&CK) property holding external reference objects |
| `source_name` | string | Human-readable dataset name for citations |
| `dataset_version` | string | Pinned version string (e.g. `"v19.0"`) — generated |
| `raw_sha256` / `snapshot_pinned` | string / bool | Raw-source checksum pin — generated |
| `id_scheme` | string | Identifier format name (e.g. `"attack-id"`, `"capec-id"`) |

Every `EvidenceRecord.provenance.source` a specialist emits is
`provenance.source_name` from this section (`utils/specialists/evidence.py`
`make_provenance`).

### `entity_descriptions`

One-line glosses for each node label and relationship type, under `nodes` and
`relationships` keys. These improve the planner's source selection when a
question could plausibly route to either graph — but they are **human context,
not routing truth**: the planner's membership checks run only on the
introspected `node_labels` / `relationship_types`.

### `identity`

The join-key contract for the dataset — what makes a record *the same record*
across queries and sources.

| Field | Origin | Description |
|-------|--------|-------------|
| `join_key` | generated | The identity property list — ATT&CK: `["attack_id", "stix_type"]` (an ATT&CK id alone is **not** unique across STIX types); CAPEC: `["capec_id"]` |
| `unique_backstop` | generated | The always-unique fallback property (`"id"` — the STIX UUID / CAPEC object id) |
| `constraints` | generated | Live DB constraint names enforcing the identity (e.g. `attack_id_type_unique`) |
| `known_collisions` | generated | Measured from the canonical artifact by `_canonical_collision_set()` — ids appearing under >1 type (expected empty under exclude-at-load) |
| `policy`, `revoked_deprecated_policy`, `not_traversable` | overlay | Human-readable policy statements |

The fixture-QA harness (`utils/graph_loader/fixture_qa/composite_keys.py`)
independently re-derives the collision set and verifies the constraints live —
see `docs/structure.md`.

### Cross-source join keys (declared in code, prerequisites in the card)

Canonical join keys are **not** authored in cards. They are declared in code,
in `utils/planner/join_keys.py` (`CANONICAL_JOIN_KEYS`) — adding a bridge is a
deliberate, reviewed edit, never something the planner fabricates. What the
card contributes is the **structural prerequisite**: `resolve_join_key` binds
a declared key across two cards only when each card's introspected structure
carries its endpoint (the labels, and the `via_edge` when one is required).
A card missing the endpoint's label or edge makes the join unsupported, not
invented. The single declared bridge today is `attack-technique-id`
(CAPEC `AttackPattern -[MAPS_TO]-> TaxonomyEntry(taxonomy=ATTACK).entry_id` ↔
ATT&CK `Technique`/`SubTechnique.attack_id`).

## What the planner routes on

Routing truth is the introspected structure only:

- `dataset`, `runtime_backend` — source identity and executor type.
- `node_labels`, `relationship_types` (as `SourceCardView.has_label` /
  `has_relationship` / `has_entity`) — the gate rejects any sub-question
  naming an entity outside them.
- `safety` numeric bounds (via `SourceCardView.limits()`) — the gate rejects
  missing or over-bound limits.
- `allowed_edge_patterns` — the Gremlin validator's direction truth.

`entity_descriptions`, `provenance`, and `connection` are context: consulted
by humans and prompts, never by the gate's membership or bounds checks.
`load_source_cards(check_consistency=True)` additionally asserts internal
consistency: every `allowed_edge_patterns` entry must reference declared
relationship types and node labels (`assert_card_consistency`,
`utils/planner/cards.py`).

## CI contract guarantees

`utils/kg_builder/tests/test_registry_contracts.py` (build layer):

1. Cards resolve their manifest and per-backend exports.
2. With an overlay present, `connection` / `safety` / `provenance` are
   non-empty; **no literal credential value** appears anywhere in the card.
3. Overlay absence degrades gracefully to empty authored sections (the
   generated snapshot pin still populates `provenance`).
4. A rebuild produces identical authored sections (the overlay, when present,
   is authoritative — regeneration never erases authored values).
5. CAPEC's `safety` carries the generated `allowed_edge_patterns` and
   `relationship_natures`.
6. Written cards carry the identity contract (`join_key`,
   `unique_backstop`, `constraints`, an empty measured collision set, policy
   statements) — skipped when no cards have been built locally.

`utils/planner/tests/test_card_enrichment.py` (load layer):

1. Enrichment fills empty authored sections per backend (clauses for Neo4j,
   steps for Gremlin); a non-empty card section always wins.
2. Generated safety keys layer over the numeric defaults, never get lost.
3. An unknown dataset still receives backend safety defaults.
4. The enrichment numeric limits equal the specialist env defaults.

## Authoring a card for a new source

A new source's card needs no new mechanism — the format above is the whole
contract. What must exist, in dependency order:

1. **A canonical build that emits the structural truth.** The card generator
   reads `schema.json` / `manifest.json`, so the new dataset needs a build
   pipeline producing them (plus a `write_<dataset>_source_card` function in
   `utils/kg_builder/registry.py` following the existing two). The structural
   fields are the routing surface — if a label or edge is missing from
   `schema.json`, the planner will refuse to route to it (schema-boundary
   refusal), which is the honest failure mode.
2. **The identity block decisions.** What property (or property pair) is a
   record's identity? What DB constraints enforce it? Run the collision scan
   over the canonical artifact rather than asserting uniqueness by hand.
3. **The authored safety/connection/provenance metadata.** Add a
   `card_enrichment.py` `ENRICHMENT` entry (committed; required for a fresh
   clone to work) and/or a local overlay. Reuse the conservative numeric
   defaults unless there is measured reason not to; if you change them, keep
   the specialist env defaults in agreement or
   `test_card_limits_agree_with_specialist_env_defaults` will fail.
   For a **new backend** (neither Neo4j nor Gremlin), also decide the
   disallowed write-operation list for its query language and add a
   per-backend default in `card_enrichment.py`.
4. **Entity glosses.** One line per label/edge — these measurably help source
   selection between overlapping graphs.
5. **A join declaration, only if the source participates in cross-source
   questions.** Add the `JoinKey` with both endpoints to
   `CANONICAL_JOIN_KEYS`, and make sure each card's structure carries its
   endpoint. No declaration ⇒ the planner marks cross-source parts
   unsupported, by design.

The minimum viable card for the planner to route is: `dataset`,
`runtime_backend`, non-empty `node_labels`/`relationship_types`, and `safety`
numeric bounds (fillable by enrichment). Everything else improves citations,
routing quality, and safety specificity. The full walkthrough for standing up
the specialist behind such a card is
[`migration-guide.md`](migration-guide.md).

## Importing an external canonical graph

A graph built elsewhere in the same canonical contract — Synapse's
`export-ariadne` command writes one — becomes a source by being copied in.
The card is the whole registration: the loader accepts any dataset that has a
card (`utils/graph_loader/config.py` `is_supported_dataset`), the planner
discovers it the way it discovers the built-ins, and the specialist is chosen
by the card's `runtime_backend`, never by name (`utils/specialists/__init__.py`
`build_specialist`). Load validation reads labels, relationship types and legal
edge patterns from the shipped `schema.json` (`relationship_endpoints`), so an
import fails on a real defect — unknown label, dangling edge — and not on its
name.

What the export directory must contain, with every path relative to the
parent of Ariadne's data directory (they start with `data/`):

```
graphs/<dataset>/canonical/{nodes.jsonl,relationships.jsonl,schema.json,manifest.json}
graphs/<dataset>/exports/neo4j/{nodes.csv,relationships.csv,schema.cypher,constraints.cypher}
graphs/<dataset>/exports/gremlin/{nodes.jsonl,relationships.jsonl}
source_cards/<dataset>.json
```

`schema.json` carries `dataset`, `node_labels`, `relationship_types`,
`node_properties` (the per-label inventory this repository's own builds write)
and `relationship_endpoints`. `manifest.json` carries `counts` (`nodes`,
`relationships`, `nodes_by_label`, `relationships_by_type`), `canonical` and
`exports` with files named by role (`nodes_csv`, `constraints_cypher`, ...).
The card has the generated field set above with `endpoints` empty; `safety`,
`provenance` and `entity_descriptions` may be authored or left for enrichment
to fill from the backend defaults.

The procedure, for a dataset named `<dataset>`:

1. Copy the export's contents into `data/` (`graphs/<dataset>/` and
   `source_cards/<dataset>.json`).
2. Give it its own store: `docker compose --profile external up -d neo4j-external`
   (bolt 5461 by default; see `.env.example`).
3. Load and verify:
   `NEO4J_URI=bolt://localhost:5461 uv run main.py --dataset <dataset> --graph neo4j`,
   then `--graph verify`.
4. Route the planner to that store, not ATT&CK's:
   `ARIADNE_ENDPOINT_<DATASET>=bolt://localhost:5461` in `.env` (upper-case,
   hyphens as underscores).
5. Ask. The graph answers through the generic `describe`/`expand` path;
   anchors resolve by name, since an imported graph has no MITRE identifier
   scheme, and no cross-source join key is declared for it.

Removing it is the reverse: delete the two copied paths, stop the container
and remove `docker/neo4j-external/`.

## Key files

| Concern | Location |
|---------|----------|
| Card dataclass + build/write + overlay merge | `utils/kg_builder/registry.py` |
| Committed authored metadata (enrichment) | `utils/planner/card_enrichment.py` |
| Load-time view + consistency check | `utils/planner/cards.py` |
| Canonical join-key declarations | `utils/planner/join_keys.py` |
| Plan-time enforcement of card bounds | `utils/planner/gate.py` |
| Build-layer contract tests | `utils/kg_builder/tests/test_registry_contracts.py` |
| Load-layer contract tests | `utils/planner/tests/test_card_enrichment.py`, `utils/planner/tests/test_cards.py` |
