# ATT&CK Canonical Graph Export Plan

### 1. Introduction

This plan upgrades the existing ATT&CK graph builder from a Neo4j-oriented artifact bundle into a backend-neutral graph interchange pipeline. The canonical source of truth will be JSONL graph records plus schema and manifest metadata under `data/graphs/attack/canonical/`; Neo4j/Cypher and Gremlin artifacts will be generated export targets under `data/graphs/attack/exports/`.

The implementation should preserve the current ATT&CK build behavior while making the boundary explicit: `raw STIX -> canonical graph model -> canonical artifacts -> generated backend exports -> future runtime/query adapters`. This keeps the truth and ground-truth data independent from any one query language and lets future experiments compare how agents traverse the same graph through Neo4j, Gremlin, or additional graph backends. The larger architecture is one canonical truth set per dataset or knowledge domain, with specialist query agents using source registry metadata to select the correct backend and an answering agent combining normalized results.

### 2. Gaps & Unanswered Questions

- **Existing artifact compatibility**: Current docs and tests reference files directly under `data/graphs/attack/`, such as `nodes.jsonl`, `relationships.jsonl`, `schema.cypher`, and `neo4j_csv/`. *Decision*: perform a full migration so `data/graphs/attack/canonical/` becomes the only ATT&CK source-of-truth path. Do not keep root-level canonical duplicates because that would preserve ambiguity; update docs, tests, manifests, and any downstream references to the new layout.
- **Canonical labels field**: The current model uses a single `label` string. *Decision*: canonical node records must support both a primary `label` and an ordered `labels` list so records can carry abstract classifications such as `Technique`, `AttackObject`, and `STIXObject`. Exporters may use `label` or `labels[0]` as the backend primary label, but canonical records retain all labels.
- **Generated Gremlin shape**: The project is not running Gremlin Server, Docker, Neo4j, or any live database in this phase. *Decision*: generate Gremlin-ready `nodes.jsonl` and `relationships.jsonl` under `data/graphs/attack/exports/gremlin/` only. These files should be load-ready for future Gremlin upsert logic, but no server startup, database connection, or live load validation belongs in this plan.
- **Canonical property preservation**: ATT&CK STIX properties can contain lists, dictionaries, and nested structures such as `external_references`. *Decision*: canonical JSONL keeps those structures intact. Backend-specific transformations, flattening, scalar filtering, or JSON-string serialization happen only in the Neo4j and Gremlin exporters.
- **DataSource label**: `DataSource` exists in schema but may not be populated in current build counts. *Decision*: keep `DataSource` in the canonical schema allowlist so later extraction rules can populate it without a schema-breaking migration.
- **Per-dataset truth model**: The goal is not one global database-specific graph. *Decision*: every dataset or knowledge domain should have its own canonical truth set, for example `data/graphs/attack/canonical/`, `data/graphs/capec/canonical/`, `data/graphs/cve/canonical/`, or `data/graphs/internal/canonical/`, with generated backend exports beneath each dataset.
- **Federated specialist-agent architecture**: Future query agents need to know which graph exists in which backend. *Decision*: source registry or source-card metadata should point to each dataset's canonical manifest, selected runtime backend, schema version, allowed labels and relationship types, and endpoint details. Specialist agents query backend-specific projections, return normalized evidence, and the answering agent combines those results; databases remain reproducible outputs, not truth sources.

### 3. Hierarchical Step-by-Step Instructions

#### Step 1: Audit the Current ATT&CK Builder Contract

- **Locations**: `utils/kg_builder/main.py`, `utils/kg_builder/models.py`, `utils/kg_builder/config.py`, `utils/kg_builder/exporters/jsonl.py`, `utils/kg_builder/exporters/cypher.py`, `utils/kg_builder/exporters/neo4j_csv.py`, `utils/kg_builder/schema/attack.py`, `utils/kg_builder/validate.py`, `utils/kg_builder/tests/`, `README.md`, `docs/goals.md`, `docs/plans/attack-neo4j-kg-builder-plan.md`.
- **Rationale**: The existing builder already produces portable artifacts, but the output layout and names still mix canonical JSONL with Neo4j export files. Before changing behavior, capture current artifact counts, file paths, manifest keys, and tests so the migration preserves the known ATT&CK build outcome.
- **Validation**: Run `uv run main.py --build attack` against the current pinned ATT&CK data and record the generated node count, relationship count, label counts, relationship-type counts, manifest paths, and current test failures or passes. Run `uv run python -m pytest utils/kg_builder/tests` to establish a baseline.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Canonical Graph Export (1/9) Complete: Audited the current ATT&CK builder contract and captured the baseline artifact behavior.

#### Step 2: Introduce Backend-Neutral Record Types

- **Locations**: `utils/kg_builder/models.py`, `utils/kg_builder/preprocess/attack.py`, `utils/kg_builder/exporters/jsonl.py`, `utils/kg_builder/validate.py`, tests in `utils/kg_builder/tests/test_attack_preprocess.py` and `utils/kg_builder/tests/test_jsonl_export.py`.
- **Rationale**: The canonical model should not expose Neo4j assumptions as the source of truth. Replace or alias `GraphNode` and `GraphRelationship` with explicit `NodeRecord` and `EdgeRecord` types containing `id`, `label`, `labels`, `name`, and `properties` for nodes, and `id`, `type`, `source_id`, `target_id`, and `properties` for edges. This supports abstract classifications and multi-label graph experiments while preserving a simple primary label for backend exporters.
- **Validation**: Add fixture tests proving canonical node records serialize with both `label` and `labels`, including examples such as `["Technique", "AttackObject", "STIXObject"]`. Verify ATT&CK identifiers and nested values such as `external_references` remain intact in canonical properties, and relationship endpoint fields stay stable.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Canonical Graph Export (2/9) Complete: Added backend-neutral node and edge record types for canonical graph output.

#### Step 3: Split Canonical Paths from Generated Export Paths

- **Locations**: `utils/kg_builder/config.py`, `utils/kg_builder/main.py`, `utils/kg_builder/io.py`, `README.md`, `docs/goals.md`, tests in `utils/kg_builder/tests/test_cli_build.py`, `utils/kg_builder/tests/test_validate.py`, and `utils/kg_builder/tests/test_cypher_csv_export.py`.
- **Rationale**: The directory layout must communicate what is source-of-truth data and what is disposable generated output. Update `BuildPaths` so canonical files live only under `data/graphs/attack/canonical/`, Neo4j files under `data/graphs/attack/exports/neo4j/`, and Gremlin files under `data/graphs/attack/exports/gremlin/`.
- **Validation**: Run the CLI in a temporary data directory and assert that canonical artifacts and export artifacts are written to separate directories. Confirm old root-level canonical paths are no longer written or referenced by tests, docs, or manifests.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Canonical Graph Export (3/9) Complete: Separated canonical graph artifacts from generated backend export directories.

#### Step 4: Make Canonical JSONL, Schema, and Manifest the Truth Layer

- **Locations**: `utils/kg_builder/exporters/jsonl.py`, `utils/kg_builder/schema/attack.py`, `utils/kg_builder/main.py`, `utils/kg_builder/validate.py`, output files `data/graphs/attack/canonical/nodes.jsonl`, `data/graphs/attack/canonical/relationships.jsonl`, `data/graphs/attack/canonical/schema.json`, `data/graphs/attack/canonical/manifest.json`.
- **Rationale**: Canonical artifacts must be complete enough to rebuild every backend export without reading Neo4j, Gremlin, generated Cypher, or generated traversal files. The schema should include stable node-label and relationship-type vocabularies, including reserved labels such as `DataSource`; the manifest should include source metadata, build settings, counts, hashes, and export provenance. Backend-specific files such as `schema.cypher` and `constraints.cypher` belong in exports, not canonical truth.
- **Validation**: Add tests that load only the canonical directory and verify all graph counts, label/type allowlists, hashes, source version metadata, nested property preservation, and relationship endpoint integrity. Confirm `manifest.json` points to canonical artifacts as truth and records exports as generated artifacts rather than as source files.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Canonical Graph Export (4/9) Complete: Promoted canonical JSONL, schema, and manifest files to the graph truth layer.

#### Step 5: Rework Neo4j/Cypher as an Export Target

- **Locations**: `utils/kg_builder/exporters/cypher.py`, `utils/kg_builder/exporters/neo4j_csv.py`, `utils/kg_builder/schema/attack.py`, `utils/kg_builder/main.py`, output files under `data/graphs/attack/exports/neo4j/`.
- **Rationale**: Neo4j output should be generated entirely from canonical records. The exporter should emit `nodes.csv`, `relationships.csv`, `constraints.cypher`, `schema.cypher`, and optionally `load.cypher` using `MERGE` on `id`, label-safe Cypher generation, and deterministic property handling. Any Neo4j-specific flattening or serialization happens here while the canonical JSON stays intact.
- **Validation**: Add exporter tests that build Neo4j CSV/Cypher from a small canonical fixture and verify row counts, uniqueness constraints for every canonical node label, valid relationship type names, deterministic output order, preservation of relationship endpoints, and backend-specific handling of nested properties.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Canonical Graph Export (5/9) Complete: Reworked Neo4j CSV and Cypher generation as a canonical-data export target.

#### Step 6: Add a Gremlin Export Target

- **Locations**: new `utils/kg_builder/exporters/gremlin.py`, `utils/kg_builder/exporters/__init__.py`, `utils/kg_builder/main.py`, `utils/kg_builder/validate.py`, tests in new or existing `utils/kg_builder/tests/test_gremlin_export.py`, output files under `data/graphs/attack/exports/gremlin/`.
- **Rationale**: ATT&CK needs a Gremlin-ready projection so the same canonical graph can be loaded into a TinkerPop-style property graph for traversal experiments. The exporter should write Gremlin `nodes.jsonl` and `relationships.jsonl`, map each node's primary `label` or `labels[0]` to the vertex label, preserve `id` as the future upsert key, emit edge records keyed by `source_id`, `target_id`, and `type`, and serialize or filter nested properties only in the export layer.
- **Validation**: Add tests using a small canonical fixture with scalar, list, and nested properties. Verify Gremlin export records include primary vertex labels, preserve edge direction, retain stable IDs, document any property serialization, and can be consumed by a future `fold().coalesce()` upsert loader. Do not require Gremlin Server, Docker, or a live database.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Canonical Graph Export (6/9) Complete: Added Gremlin-ready exports generated from canonical ATT&CK graph artifacts.

#### Step 7: Define Source Registry and Future Runtime Adapter Contracts

- **Locations**: new or existing source-card/registry location chosen by the repository, optional `utils/kg_builder/registry.py`, optional tests in `utils/kg_builder/tests/test_registry_contracts.py`, documentation in `README.md`.
- **Rationale**: The long-term goal is for specialist agents to know which graph is available in which backend and which schema they can query. Define a registry/source-card contract that references each dataset's canonical manifest, generated export locations, intended runtime backend, schema version, allowed labels and edge types, and future endpoint fields. This is metadata for routing and reproducibility, not a live loader implementation.
- **Validation**: Add contract tests with a minimal ATT&CK source-card fixture proving the registry can resolve the canonical manifest, backend type, schema version, allowed labels, and export paths. Do not require live database credentials, Docker, Gremlin Server, or Neo4j.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Canonical Graph Export (7/9) Complete: Added source registry contracts for future backend-specific specialist agents.

#### Step 8: Expand Validation for Cross-Backend Equivalence

- **Locations**: `utils/kg_builder/validate.py`, `utils/kg_builder/main.py`, tests in `utils/kg_builder/tests/test_validate.py`, `utils/kg_builder/tests/test_cypher_csv_export.py`, and `utils/kg_builder/tests/test_gremlin_export.py`.
- **Rationale**: The repository needs proof that Neo4j and Gremlin exports are equivalent projections of the same canonical graph. Validation should compare canonical counts to each export, verify every exported edge references exported vertices, check label/type allowlists, enforce deterministic ordering and file hashes, and ensure backend property transformations are documented in manifest metadata.
- **Validation**: Run validation against both a minimal fixture and the real ATT&CK build. Add a negative fixture where an export drops a node or relationship and verify validation fails with a clear error.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Canonical Graph Export (8/9) Complete: Added cross-backend validation proving Neo4j and Gremlin exports match the canonical ATT&CK graph.

#### Step 9: Update Documentation, Ground-Truth Guidance, and Regression Tests

- **Locations**: `README.md`, `docs/goals.md`, `docs/changelog.jsonl`, `docs/plans/attack-canonical-graph-export-plan.md`, `utils/kg_builder/tests/`, optional future source-card docs under the repo's chosen source-card location.
- **Rationale**: Developers and future agents must know that canonical JSONL/schema/manifest files are the ground truth, while Neo4j and Gremlin outputs are generated projections. Documentation should show the final folder structure, CLI commands, validation commands, per-dataset canonical directories, and how source registry entries let specialist query agents identify backend type and schema before returning normalized evidence to the answering agent.
- **Validation**: Run `uv run main.py --build attack`, `uv run python -m pytest utils/kg_builder/tests`, and a documentation consistency search for old root-level artifact paths. Confirm the docs describe `data/graphs/attack/canonical/`, `data/graphs/attack/exports/neo4j/`, and `data/graphs/attack/exports/gremlin/` consistently.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Canonical Graph Export (9/9) Complete: Documented canonical graph truth artifacts, backend exports, and regression validation for ATT&CK.

### 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Canonical graph model | Backend-neutral `NodeRecord`, `EdgeRecord`, metadata, counts, and serialization contracts. | `utils/kg_builder/models.py` |
| Canonical output paths | Explicit path configuration for canonical truth artifacts and generated export targets. | `utils/kg_builder/config.py` |
| Canonical JSONL artifacts | Source-of-truth node and edge records. | `data/graphs/attack/canonical/nodes.jsonl`, `data/graphs/attack/canonical/relationships.jsonl` |
| Canonical schema artifact | Stable node label and relationship type vocabulary, including reserved labels such as `DataSource`. | `data/graphs/attack/canonical/schema.json` |
| Canonical manifest artifact | Source metadata, build settings, counts, file hashes, export provenance, and validation status. | `data/graphs/attack/canonical/manifest.json` |
| Canonical JSONL exporter | Writes only backend-neutral truth artifacts. | `utils/kg_builder/exporters/jsonl.py` |
| Neo4j export artifacts | Generated Neo4j CSV and Cypher files derived from canonical records. | `data/graphs/attack/exports/neo4j/` |
| Neo4j exporters | CSV/Cypher generation using deterministic labels, relationship types, and `id`-based load semantics. | `utils/kg_builder/exporters/neo4j_csv.py`, `utils/kg_builder/exporters/cypher.py` |
| Gremlin export artifacts | Gremlin-ready node and relationship JSONL files with backend-specific property serialization and directed typed edges. | `data/graphs/attack/exports/gremlin/nodes.jsonl`, `data/graphs/attack/exports/gremlin/relationships.jsonl` |
| Gremlin exporter | Backend export module that maps canonical records to Gremlin/TinkerPop-compatible records. | `utils/kg_builder/exporters/gremlin.py` |
| Source registry contract | Metadata that maps each dataset's canonical manifest to generated exports, backend type, schema version, allowed labels, allowed relationship types, and future endpoint fields. | Source-card/registry path selected during implementation, optional `utils/kg_builder/registry.py` |
| Cross-backend validator | Checks canonical integrity, export equivalence, deterministic ordering, hashes, and property transformation rules. | `utils/kg_builder/validate.py` |
| Small fixture tests | Tests that run a minimal ATT&CK-like subset through canonical export, Neo4j export, Gremlin export, and validation. | `utils/kg_builder/tests/test_jsonl_export.py`, `utils/kg_builder/tests/test_cypher_csv_export.py`, `utils/kg_builder/tests/test_gremlin_export.py`, `utils/kg_builder/tests/test_validate.py` |
| CLI regression tests | Tests for `uv run main.py --build attack` writing the new canonical/export layout. | `utils/kg_builder/tests/test_cli_build.py` |
| User documentation | Updated command examples and folder contract explaining canonical truth versus generated exports. | `README.md`, `docs/goals.md` |
| Changelog entry | Short record explaining the canonical graph export migration plan. | `docs/changelog.jsonl` |
