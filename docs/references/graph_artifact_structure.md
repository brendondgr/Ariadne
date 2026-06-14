# Graph Artifact Structure Reference

This document defines the reusable file structure for graph builder agents that receive already accepted node and relationship records from an upstream extraction and validation process. It is intentionally graph-domain neutral: ATT&CK is the current example, but the same contract should work for cybersecurity, document, business, research, entity, or mixed-domain knowledge graphs.

The graph builder agent is not responsible for deciding whether a proposed fact is true. Its job is to take accepted graph facts, normalize them into a reproducible artifact set, generate backend-specific projections, and record enough metadata for future agents to verify and reload the graph.

## Required Folder Layout

Every graph should be written under a graph-specific root:

```text
graphs/
  <graph_id>/
    canonical/
    exports/
    runtime/
```

Use a stable lowercase `graph_id` that identifies the graph family or dataset, such as `attack`, `capec`, `contracts`, `incident_reports`, or `product_docs`. The graph id should not include a backend name because one canonical graph can produce multiple backend exports.

## Folder Responsibilities

### `canonical/`

`canonical/` is the source of truth for the graph after upstream validation. It should be backend-neutral and should preserve all accepted semantic content needed to rebuild exports.

Required files:

```text
canonical/
  nodes.jsonl
  relationships.jsonl
  schema.json
  manifest.json
```

Optional files:

```text
canonical/
  chunks.jsonl
  sources.jsonl
  evidence.jsonl
```

Use optional evidence or source files when the upstream agent provides chunk-level provenance, source spans, confidence scores, or validation notes that are too large to repeat on every node or relationship. The canonical node and relationship records may reference those records by id.

### `exports/`

`exports/` contains generated projections of the canonical graph for specific storage engines, query languages, or downstream consumers. Export files must be reproducible from `canonical/` and should not contain facts that are absent from the canonical files.

Recommended layout:

```text
exports/
  neo4j/
    nodes.csv
    relationships.csv
    schema.cypher
    constraints.cypher
  gremlin/
    nodes.jsonl
    relationships.jsonl
```

Additional backend folders may be added as needed:

```text
exports/
  networkx/
  rdf/
  postgres/
  vector_index/
```

The backend folder name should describe the target format or loader. Each backend export must be declared in `canonical/manifest.json`.

### `runtime/`

`runtime/` records what happened after artifacts were loaded into a live graph backend. It should not be treated as canonical graph truth.

Recommended layout:

```text
runtime/
  <backend>/
    load-manifest.json
```

Each runtime manifest should identify the canonical manifest that was loaded, the hash of that manifest, the backend target, the adapter or loader version, load counts, and verification results. This lets future agents detect stale live databases when canonical artifacts have changed.

## Canonical File Structures

### `nodes.jsonl`

One JSON object per line. Each line represents one canonical graph node.

Required shape:

```json
{
  "id": "stable-node-id",
  "label": "PrimaryLabel",
  "labels": ["PrimaryLabel", "OptionalSharedLabel"],
  "name": "Human readable name",
  "properties": {}
}
```

Rules:

- `id` is the stable primary key across builds and backends.
- `label` is the primary semantic type for the node.
- `labels[0]` must match `label`.
- `labels` may include shared or inherited categories, but the first label remains the primary label.
- `name` is optional but should be present when a human-readable label exists.
- `properties` contains domain-specific attributes, provenance pointers, source ids, timestamps, descriptions, scores, and other non-structural data.
- Nested values are allowed in canonical properties if they are valid JSON.

The graph builder should sort node records deterministically, normally by `id`, so repeated builds from unchanged accepted facts produce stable files.

### `relationships.jsonl`

One JSON object per line. Each line represents one canonical directed edge.

Required shape:

```json
{
  "id": "stable-relationship-id",
  "type": "RELATIONSHIP_TYPE",
  "source_id": "stable-source-node-id",
  "target_id": "stable-target-node-id",
  "properties": {}
}
```

Rules:

- `id` is the stable primary key for the relationship.
- `type` is the semantic relationship label.
- `source_id` and `target_id` must reference existing node ids in `nodes.jsonl`.
- Direction must be meaningful and consistent with the schema.
- `properties` may include confidence, source references, evidence ids, dates, extraction method, or other relationship-level attributes.
- Relationship ids should be deterministic. A common pattern is a namespaced hash of `source_id`, `type`, `target_id`, and any disambiguating source or evidence id.

The graph builder should sort relationship records deterministically, normally by `(type, source_id, target_id, id)`.

### `schema.json`

`schema.json` declares the allowed graph vocabulary. It should be small, explicit, and easy for other agents to read before loading or querying the graph.

Required shape:

```json
{
  "schema_version": "1.0",
  "node_labels": ["LabelA", "LabelB"],
  "relationship_types": ["RELATES_TO", "PART_OF"]
}
```

Recommended optional fields:

```json
{
  "node_label_descriptions": {
    "LabelA": "Description of the node class."
  },
  "relationship_type_descriptions": {
    "RELATES_TO": "Description of the edge meaning and direction."
  },
  "allowed_relationships": [
    {
      "source_label": "LabelA",
      "type": "RELATES_TO",
      "target_label": "LabelB"
    }
  ],
  "required_node_properties": {
    "LabelA": ["source_id"]
  },
  "required_relationship_properties": {
    "RELATES_TO": ["evidence_id"]
  }
}
```

At minimum, every `label` in `nodes.jsonl` must appear in `node_labels`, and every `type` in `relationships.jsonl` must appear in `relationship_types`.

### `manifest.json`

`manifest.json` is the build ledger for the canonical graph and all generated exports.

Required shape:

```json
{
  "build_timestamp": "2026-06-14T00:00:00+00:00",
  "graph_id": "example_graph",
  "schema_version": "1.0",
  "settings": {},
  "metadata": {},
  "counts": {
    "nodes": 0,
    "relationships": 0,
    "nodes_by_label": {},
    "relationships_by_type": {}
  },
  "canonical": {
    "nodes_jsonl": "graphs/example_graph/canonical/nodes.jsonl",
    "relationships_jsonl": "graphs/example_graph/canonical/relationships.jsonl",
    "schema_json": "graphs/example_graph/canonical/schema.json"
  },
  "exports": {},
  "property_transformations": {},
  "hashes": {}
}
```

Rules:

- `metadata` should identify the accepted input batch, source collection, graph version, or upstream validation run.
- `settings` should record graph builder filters and normalization choices.
- `counts` must match the canonical files exactly.
- `canonical` must list the canonical artifact paths.
- `exports` must list every generated backend artifact grouped by backend name.
- `hashes` should include SHA-256 hashes for canonical and export files so future agents can detect drift.
- `property_transformations` should explain any backend-specific serialization changes, such as nested JSON converted to strings for CSV or Gremlin properties.

## Optional Provenance Files

Use these files when the graph builder needs chunk-level traceability without bloating every node and relationship record.

### `chunks.jsonl`

Stores normalized text chunks or source fragments used by the upstream extraction process.

Suggested shape:

```json
{
  "id": "chunk-id",
  "source_id": "source-id",
  "text": "Chunk text or extracted content.",
  "metadata": {}
}
```

### `sources.jsonl`

Stores one record per source document or input item.

Suggested shape:

```json
{
  "id": "source-id",
  "uri": "relative/or/external/path",
  "media_type": "text/markdown",
  "metadata": {}
}
```

### `evidence.jsonl`

Stores validation evidence, citations, or accepted extraction decisions.

Suggested shape:

```json
{
  "id": "evidence-id",
  "source_id": "source-id",
  "chunk_id": "chunk-id",
  "supports": {
    "nodes": ["stable-node-id"],
    "relationships": ["stable-relationship-id"]
  },
  "metadata": {}
}
```

If these files are present, declare them in `manifest.json` under `canonical`.

## Export File Structures

### Neo4j Export

Recommended files:

```text
exports/neo4j/
  nodes.csv
  relationships.csv
  schema.cypher
  constraints.cypher
```

`nodes.csv` should contain one row per canonical node. A general CSV header is:

```csv
id:ID,label:LABEL,name,properties_json
```

Additional columns may be added for high-value scalar properties. Nested canonical properties should be serialized into `properties_json` or another clearly named JSON string column.

`relationships.csv` should contain one row per canonical relationship. A general CSV header is:

```csv
:START_ID,:END_ID,:TYPE
```

Additional relationship property columns may be added when the loader supports them.

`schema.cypher` should describe or create backend schema features needed by the graph. `constraints.cypher` should define uniqueness constraints on canonical ids for each primary node label.

### Gremlin Export

Recommended files:

```text
exports/gremlin/
  nodes.jsonl
  relationships.jsonl
```

The Gremlin JSONL structure should mirror canonical records but may serialize nested property values into JSON strings because many Gremlin/TinkerPop property stores expect scalar values.

The export must preserve:

- Node ids.
- Primary labels.
- Relationship ids.
- Relationship types.
- Source and target ids.
- Enough properties to support the intended Gremlin workload.

## Runtime File Structure

### `runtime/<backend>/load-manifest.json`

Required shape:

```json
{
  "loaded_timestamp": "2026-06-14T00:00:00+00:00",
  "dataset": "example_graph",
  "backend": "neo4j",
  "endpoint": "backend endpoint or logical target",
  "adapter_version": "0.1.0",
  "canonical_manifest": "graphs/example_graph/canonical/manifest.json",
  "canonical_manifest_hash": "sha256",
  "semantic_validation_passed": true,
  "nodes_loaded": 0,
  "edges_loaded": 0,
  "expected_counts": {},
  "verification": {
    "passed": true,
    "actual_counts": {},
    "errors": []
  }
}
```

Rules:

- The runtime manifest should be written only after the loader validates canonical artifacts and verifies the live backend.
- `canonical_manifest_hash` must match the current hash of `canonical/manifest.json`; otherwise the runtime state is stale.
- `expected_counts` should come from the canonical manifest.
- `actual_counts` should come from the live backend after loading.

## Build Process

The graph builder should follow this sequence:

1. Receive accepted nodes, relationships, schema vocabulary, and optional provenance records from the upstream agent process.
2. Normalize ids, labels, relationship types, property names, and property values into the canonical record shapes.
3. Reject or quarantine records that violate the schema, duplicate ids, missing endpoint references, or invalid direction rules.
4. Sort nodes and relationships deterministically.
5. Write `canonical/nodes.jsonl`, `canonical/relationships.jsonl`, and `canonical/schema.json`.
6. Write optional `canonical/chunks.jsonl`, `canonical/sources.jsonl`, or `canonical/evidence.jsonl` if provenance was provided.
7. Generate backend exports under `exports/<backend>/` from canonical records only.
8. Validate every export against canonical counts and endpoint references.
9. Write `canonical/manifest.json` with paths, counts, metadata, transformations, and hashes.
10. When a backend load occurs, write `runtime/<backend>/load-manifest.json` after verification passes.

## Validation Logic

The graph builder should enforce these checks before declaring artifacts complete:

- Every node has a unique `id`.
- Every node has a primary `label`.
- Every node primary label exists in `schema.json`.
- Every relationship has a unique `id`.
- Every relationship type exists in `schema.json`.
- Every relationship source and target id exists in `nodes.jsonl`.
- Relationship direction is consistent with any declared `allowed_relationships`.
- Manifest counts match the canonical files.
- Export row counts match canonical counts.
- Export endpoints reference canonical node ids.
- File hashes in `manifest.json` match the written artifacts.
- Repeated builds from unchanged accepted input produce the same canonical files, except for timestamps if timestamps are intentionally regenerated.

## Why The Structure Works

This structure separates meaning from deployment.

`canonical/` is backend-neutral, so it can be reviewed, diffed, validated, and reused without Neo4j, Gremlin, or any other database. It preserves the accepted graph facts in the most direct form: nodes, relationships, schema, and manifest.

`exports/` keeps backend-specific compromises out of canonical truth. CSV headers, Cypher constraints, scalar-only property conversions, RDF triples, vector index records, and other projections can change without changing what the graph means.

`runtime/` records live database state separately. A graph can be built without being loaded, and a loaded database can be checked for staleness by comparing its runtime manifest to the current canonical manifest hash.

This separation lets many graph types share one build pattern. Upstream agents can specialize in extraction and validation, while the graph builder specializes in deterministic artifact generation, backend projection, and reproducible verification.
