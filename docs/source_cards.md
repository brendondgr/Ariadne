# Source Cards

Source cards are JSON files that agents read at runtime to locate and safely query a graph backend.
They live in `data/source_cards/` and are written by the build pipeline (`--build attack|capec`).

## Generated vs. Authored fields

Each card has two kinds of fields:

| Kind | Written by | Survives rebuild? | Examples |
|------|-----------|-------------------|---------|
| Generated | Build pipeline | No — overwritten each build | `node_labels`, `relationship_types`, `canonical_dir`, `exports`, `schema_version` |
| Authored | Overlay file | Yes — merged from overlay | `connection`, `safety`, `provenance`, `entity_descriptions` |

Generated fields are derived from the build artifacts (schema.json, manifest.json).  
Authored fields are human decisions that belong in version control and must never be regenerated.

## The overlay mechanism

Authored sections are stored in `data/source_cards/overlays/`:

```
data/source_cards/overlays/
  attack.overlay.json
  capec.overlay.json
```

At card-write time the builder loads the matching overlay (if present) and merges its top-level
sections onto the card. Overlay absence is not an error — authored sections default to `{}`.

Because overlays live in the repo (excluded from `.gitignore` via explicit allow-list), a `git pull`
followed by a rebuild always produces a card with the authored values intact.

## Authored fields

### `connection`

How the specialist agent connects to the backend.

| Field | Type | Description |
|-------|------|-------------|
| `backend` | string | `"neo4j"` or `"gremlin"` |
| `uri` | string | Driver URI (`bolt://…` or `ws://…/gremlin`) |
| `database` | string | (Neo4j) database name |
| `traversal_source` | string | (Gremlin) traversal-source name, e.g. `"g"` |
| `auth_env` | object | Maps credential roles to **env-var names** (never literal secrets) |
| `read_only` | bool | Whether the connection enforces read-only mode |
| `timeout_ms` | int | Connection-level timeout in milliseconds |

**Important:** `auth_env` must contain env-var names only (e.g. `"NEO4J_PASSWORD"`), never
literal passwords. The contract test `test_*_no_literal_secrets` enforces this.

### `safety`

Guardrails the query specialist must enforce before executing any query.

| Field | Type | Description |
|-------|------|-------------|
| `read_only` | bool | Hard block on write operations |
| `max_result_rows` | int | Row cap before truncation (default: 1000) |
| `max_traversal_depth` | int | Maximum hop depth for graph traversals (default: 3) |
| `query_timeout_ms` | int | Per-query timeout in milliseconds (default: 5000) |
| `disallowed_clauses` | list[str] | (Neo4j/Cypher) clauses that must not appear in any query |
| `disallowed_steps` | list[str] | (Gremlin) steps that must not appear in any traversal |
| `allowed_edge_patterns` | object | (CAPEC, generated) maps relationship type → allowed `[source, target]` label pairs |
| `relationship_natures` | list[str] | (CAPEC, generated) CAPEC-native relationship types vs. derived edges |

`allowed_edge_patterns` and `relationship_natures` in the CAPEC card are populated automatically
from `schema.json` — they are generated, not authored.

Numeric limits (`max_result_rows`, `max_traversal_depth`, `query_timeout_ms`) use conservative
defaults now and will be tuned against the Wk 11–13 latency/safety evaluations.

### `provenance`

Identifies the dataset so agents can cite sources correctly.

| Field | Type | Description |
|-------|------|-------------|
| `id_property` | string | Node property that holds the dataset's primary identifier |
| `source_ref_property` | string | (ATT&CK) node property holding external reference objects |
| `source_name` | string | Human-readable dataset name for citations |
| `dataset_version` | string | Pinned version string (e.g. `"v19.0"`) |
| `id_scheme` | string | Identifier format description (e.g. `"technique-id"`, `"capec-id"`) |

### `entity_descriptions`

One-line glosses for each node label and relationship type.  
These improve planner source-selection accuracy when the planner must choose between
ATT&CK and CAPEC for a given analyst question.

```json
{
  "nodes": {
    "Technique": "An adversary action or behavior at the atomic level (T-ID).",
    ...
  },
  "relationships": {
    "USES": "A Group or Software uses a Technique.",
    ...
  }
}
```

## CI gate

`utils/kg_builder/tests/test_registry_contracts.py` asserts that:

1. Each written card has non-empty `connection`, `safety`, and `provenance` sections (when an overlay is present).
2. No literal credential value appears anywhere in the card — only env-var names.
3. Overlay absence degrades gracefully to empty dicts (no exception).
4. A rebuild produces identical authored sections (overlay is the authoritative source).
5. CAPEC's `safety` section includes `allowed_edge_patterns` and `relationship_natures` from schema.
