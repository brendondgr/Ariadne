# CAPEC XML Canonical Graph Builder Plan

### 1. Introduction

This plan turns the pinned CAPEC XML catalog into Ariadne's canonical graph artifact structure and then produces Neo4j and Gremlin exports from that canonical truth layer. The proposed architecture is feasible in this repository because the ATT&CK builder has already established the reusable boundary: raw source data becomes a `NormalizedGraph`, canonical files are written under `data/graphs/<dataset>/canonical/`, backend exports are generated under `data/graphs/<dataset>/exports/`, and runtime loads are recorded under `data/graphs/<dataset>/runtime/`.

The main adjustment to the proposed plan is that CAPEC should not be built as a separate one-off XML-to-Gremlin loader. It should extend the existing `utils/kg_builder` and `utils/graph_loader` contracts so CAPEC XML parsing, schema discovery, canonical graph writing, backend export generation, source-card registration, and Gremlin runtime loading all follow the same reproducible path as ATT&CK. The parser should be discovery-first and schema-drift tolerant, but the execution order must still start with the repository's pinned source file: `data/raw/capec/v3.9/capec_latest.xml`.

### 2. Gaps & Unanswered Questions

- **Overall feasibility**: The plan is possible with the current repo. CAPEC raw XML is already downloaded, `data/versions.json` pins CAPEC to `3.9`, `utils/kg_builder/preprocess/capec.py` exists as a reserved entry point, and the canonical/export/runtime graph structure already exists for ATT&CK. The work is an extension of the current builder, not a ground-up rewrite.
- **Pinned source versus mutable latest URL**: The user-provided breakdown mentions `capec_latest.xml`, but reproducible evaluations should use the pinned file and version metadata already present in `data/raw/capec/v3.9/metadata.json`. *Decision*: build from `data/raw/capec/v<capec_version>/capec_latest.xml` as resolved from `data/versions.json`; downloads may update that pinned file only through `uv run main.py --download`.
- **Full catalog versus ATT&CK-related slice**: `docs/goals.md` mentions a CAPEC ATT&CK-related slice, while the proposed plan describes parsing the whole CAPEC XML catalog. *Decision*: build canonical artifacts for the full pinned CAPEC catalog first, then let later query agents or optional export filters focus on ATT&CK-related mappings. This preserves source completeness and avoids throwing away categories, views, and references that may be useful for provenance.
- **Namespace-aware XML parsing**: The local XML uses the default namespace `http://capec.mitre.org/capec-3` and includes XHTML namespace content. *Decision*: the CAPEC loader must be namespace-aware and should preserve structured text deterministically. Use Python's standard XML tooling first unless a later implementation step proves that an extra dependency is needed.
- **Schema drift and unknown fields**: Discovery-first parsing is needed, but raw XML fragments can make canonical nodes large and noisy. *Decision*: preserve unknown content through `source_path`, `source_xml_path`, stable field paths, normalized unknown values, and optional sidecar discovery artifacts under `data/processed/discovery/`; store full `raw_xml_fragment` only for quarantined records or fields that cannot otherwise be represented.
- **Existing ATT&CK-specific code**: `utils/kg_builder/schema/attack.py`, `utils/kg_builder/exporters/jsonl.py`, `utils/kg_builder/exporters/cypher.py`, and `utils/kg_builder/validate.py` currently assume ATT&CK labels and relationship types. *Decision*: introduce dataset-aware schema and validation selection before CAPEC build wiring, while preserving ATT&CK behavior and test coverage.
- **Canonical metadata shape**: `GraphMetadata` currently contains `attack_version`, which is too dataset-specific for CAPEC. *Decision*: generalize graph metadata or add a CAPEC-specific metadata record that includes `dataset`, `source_version`, `source_date`, `source_path`, XML namespace, schema location, object counts, skipped counts, and quarantine counts.
- **Relationship direction**: CAPEC relationships have source-declared natures such as `ChildOf`, `ParentOf`, `CanPrecede`, and `CanFollow`. *Decision*: emit only the source-declared directed relationship by default. Do not synthesize inverse edges unless a later schema setting marks them as derived.
- **Queryable nested records**: Execution steps, skills, consequences, mitigations, weaknesses, taxonomy mappings, and external references are useful graph entities. Prerequisites, resources, indicators, alternate terms, examples, notes, and content history may start as structured properties unless query requirements justify promoting them to nodes.
- **Runtime backend priority**: The project demonstration uses CAPEC through Gremlin, but canonical artifacts should remain backend-neutral. *Decision*: generate both Neo4j and Gremlin exports from canonical CAPEC records when practical, but make Gremlin the runtime backend advertised by `data/source_cards/capec.json`.
- **XSD validation**: CAPEC publishes an XML schema reference, but full XSD validation is not required for the first working parser. *Assumption*: use structural discovery, semantic validation, and fixture tests first; add optional XSD validation later if schema drift or malformed input becomes a practical issue.

### 3. Hierarchical Step-by-Step Instructions

#### Step 1: Confirm the CAPEC Source Contract and Build Scope

- **Locations**: `data/versions.json`, `data/raw/capec/v3.9/metadata.json`, `data/raw/capec/v3.9/capec_latest.xml`, `utils/download/downloader.py`, `docs/goals.md`, `docs/references/graph_artifact_structure.md`.
- **Rationale**: Before parser work begins, implementation needs a clear source boundary. CAPEC is already pinned to version `3.9`, and the graph artifact contract already defines canonical, export, and runtime folders. This step records the expected XML root, namespace, catalog version/date, and the decision to build the full pinned catalog into `data/graphs/capec/`.
- **Validation**: Run a source inspection that confirms `Attack_Pattern_Catalog`, `Version`, `Date`, the CAPEC namespace, and the presence of `Attack_Patterns`, `Categories`, `Views`, and `External_References`. Confirm `uv run main.py --download` still writes the same versioned CAPEC path when not forced.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (1/12) Complete: Confirmed the pinned CAPEC XML source contract and full-catalog build scope.

#### Step 2: Add Dataset-Specific Build Paths Without Breaking ATT&CK

- **Locations**: `utils/kg_builder/config.py`, `BuildPaths`, `BuildConfig.paths`, `utils/kg_builder/main.py`, `KGBuildRunner`, tests in `utils/kg_builder/tests/test_cli_build.py`.
- **Rationale**: `BuildPaths` currently has ATT&CK graph output paths and only a reserved CAPEC processed-pairs path. CAPEC needs first-class paths for raw XML, processed discovery output, processed pairs, canonical artifacts, Neo4j exports, Gremlin exports, and source cards under the same `data/graphs/<dataset>/` pattern.
- **Validation**: Add path-resolution tests that prove ATT&CK paths are unchanged and CAPEC resolves to `data/raw/capec/v3.9/capec_latest.xml`, `data/processed/pairs/capec.json`, `data/processed/discovery/capec-*.json`, and `data/graphs/capec/`. Run existing ATT&CK builder tests to catch path regressions.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (2/12) Complete: Added dataset-specific CAPEC build paths while preserving the ATT&CK artifact contract.

#### Step 3: Build the XML Discovery Layer

- **Locations**: `utils/kg_builder/preprocess/capec.py`, optional new `utils/kg_builder/discovery/capec_xml.py`, new tests in `utils/kg_builder/tests/test_capec_discovery.py`, outputs under `data/processed/discovery/`.
- **Rationale**: The proposed schema-drift strategy depends on discovering the XML shape before applying semantic mapping. The discovery layer should parse the CAPEC XML namespace safely, inventory element paths, attributes, repeated structures, text-bearing nodes, reference fields, embedded XHTML content, and unknown fields.
- **Validation**: Use a minimal CAPEC XML fixture and the real pinned XML to verify the discovery report includes root metadata, path counts, repeated path detection, known collection detection, and unknown-path capture. Discovery must not fail just because a new element appears.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (3/12) Complete: Added namespace-aware CAPEC XML discovery and path inventory reporting.

#### Step 4: Normalize CAPEC XML Records Into Stable Intermediate Objects

- **Locations**: `utils/kg_builder/preprocess/capec.py`, new or updated CAPEC dataclasses near the preprocessor, `utils/kg_builder/io.py`, tests in `utils/kg_builder/tests/test_capec_preprocess.py`, output `data/processed/pairs/capec.json`.
- **Rationale**: Semantic extraction should operate on normalized records rather than raw XML nodes. This phase should normalize attack patterns, categories, views, weaknesses, taxonomy mappings, external references, execution steps, skills, consequences, mitigations, references, and unmapped fields into stable intermediate records.
- **Validation**: Fixture tests should cover trimmed text, repeated values, missing optional fields, namespaced structured text, `REF-*` external-reference links, CWE IDs, taxonomy mappings, relationship natures, and CAPEC IDs. Real-data preprocessing should report counts and write a deterministic `data/processed/pairs/capec.json` checkpoint.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (4/12) Complete: Normalized CAPEC XML entities and references into deterministic intermediate records.

#### Step 5: Define the CAPEC Canonical Schema and Mapping Rules

- **Locations**: new `utils/kg_builder/schema/capec.py`, `utils/kg_builder/exporters/jsonl.py`, `utils/kg_builder/validate.py`, tests in `utils/kg_builder/tests/test_capec_schema.py`.
- **Rationale**: CAPEC needs its own allowed labels, relationship types, required properties, enum vocabularies, and allowed source-target patterns. This prevents ATT&CK schema rules from rejecting valid CAPEC graph records and gives future Gremlin query agents a readable vocabulary.
- **Validation**: Schema tests should assert the CAPEC node labels include at least `AttackPattern`, `Category`, `View`, `Weakness`, `TaxonomyEntry`, `ExternalReference`, `ExecutionStep`, `Skill`, `Consequence`, and `Mitigation`. Relationship types should include CAPEC relationship natures plus `EXPLOITS_WEAKNESS`, `MAPS_TO`, `MEMBER_OF`, `IN_VIEW`, `HAS_EXECUTION_STEP`, `NEXT_STEP`, `REQUIRES_SKILL`, `HAS_CONSEQUENCE`, `HAS_MITIGATION`, and `HAS_REFERENCE`.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (5/12) Complete: Defined the CAPEC canonical graph schema, relationship vocabulary, and mapping rules.

#### Step 6: Implement Entity Resolution and Stable ID Strategy

- **Locations**: `utils/kg_builder/preprocess/capec.py`, `utils/kg_builder/models.py`, new CAPEC tests in `utils/kg_builder/tests/test_capec_entity_resolution.py`.
- **Rationale**: CAPEC XML contains local IDs, cross-reference attributes, external reference IDs, CWE IDs, taxonomy entries, and ordered execution steps. The graph must use stable canonical IDs that cannot collide with ATT&CK STIX IDs or future graph families.
- **Validation**: Tests should verify deterministic IDs such as CAPEC attack-pattern IDs, category IDs, view IDs, `cwe:<id>` weakness IDs, namespaced taxonomy IDs, `REF-*` external reference IDs, execution-step IDs scoped to the parent attack pattern, and stable relationship IDs. Tests should also verify forward and backward references resolve regardless of XML order.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (6/12) Complete: Added deterministic CAPEC entity resolution and stable graph identifiers.

#### Step 7: Materialize CAPEC Nodes and Relationships

- **Locations**: `utils/kg_builder/preprocess/capec.py`, `utils/kg_builder/models.py`, tests in `utils/kg_builder/tests/test_capec_graph_materialization.py`.
- **Rationale**: This phase translates normalized CAPEC entities into the existing `NormalizedGraph` boundary. Attack patterns, categories, views, weaknesses, taxonomy entries, references, execution steps, skills, consequences, and mitigations should become canonical `NodeRecord` objects where queryability matters. CAPEC semantic links should become directed `EdgeRecord` objects with deterministic IDs.
- **Validation**: Fixture tests should verify node counts, relationship counts, sorted deterministic ordering, relationship endpoints, execution-step ordering through `NEXT_STEP`, source-declared relationship direction, external reference linking, and preservation of unmapped fields. The real pinned XML build should produce nonzero counts for attack patterns, weaknesses, taxonomy mappings, references, and execution steps.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (7/12) Complete: Materialized CAPEC XML content into canonical node and relationship records.

#### Step 8: Make Canonical and Backend Exporters Dataset-Aware

- **Locations**: `utils/kg_builder/exporters/jsonl.py`, `utils/kg_builder/exporters/cypher.py`, `utils/kg_builder/exporters/neo4j_csv.py`, `utils/kg_builder/exporters/gremlin.py`, `utils/kg_builder/main.py`, tests in `utils/kg_builder/tests/test_jsonl_export.py`, `utils/kg_builder/tests/test_gremlin_export.py`, `utils/kg_builder/tests/test_cypher_csv_export.py`.
- **Rationale**: The exporters should be reusable, but several currently rely on ATT&CK schema helpers. CAPEC needs `schema.json` generated from `schema/capec.py`, Neo4j constraints generated for CAPEC labels, and Gremlin JSONL generated from canonical CAPEC records while preserving scalar-safe property serialization.
- **Validation**: Run export tests for both ATT&CK and CAPEC fixtures. Verify `data/graphs/capec/canonical/nodes.jsonl`, `relationships.jsonl`, `schema.json`, and `manifest.json` are written from canonical records, and verify Neo4j and Gremlin export counts match canonical counts.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (8/12) Complete: Made canonical, Neo4j, and Gremlin exporters work with CAPEC schema records.

#### Step 9: Add CAPEC Artifact and Semantic Validation

- **Locations**: `utils/kg_builder/validate.py`, new or updated `utils/kg_builder/schema/capec.py`, `utils/graph_loader/validation/`, tests in `utils/kg_builder/tests/test_capec_validate.py` and `utils/graph_loader/tests/test_semantic_validation.py`.
- **Rationale**: The graph should fail before export or load if it has duplicate IDs, missing relationship endpoints, invalid CAPEC relationship natures, unknown enum values, unresolved references, or illegal source-target label combinations. Records that cannot be safely mapped should be quarantined rather than silently dropped.
- **Validation**: Add positive and negative fixtures for duplicate CAPEC IDs, dangling external references, dangling related attack patterns, invalid relationship natures, invalid required attributes, unknown schema fields, and export-count mismatch. Real-data validation should report any quarantined records with enough source path information to debug them.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (9/12) Complete: Added CAPEC artifact and semantic validation with quarantine reporting.

#### Step 10: Wire `--build capec`, `--build all`, and the CAPEC Source Card

- **Locations**: `utils/kg_builder/main.py`, `KGBuildRunner.build_capec`, `KGBuildRunner.build_all`, `main.py`, `utils/kg_builder/registry.py`, `data/source_cards/capec.json`, tests in `utils/kg_builder/tests/test_cli_build.py` and `utils/kg_builder/tests/test_registry_contracts.py`.
- **Rationale**: CAPEC should become a first-class dataset in the existing CLI. `uv run main.py --build capec` should build only CAPEC artifacts, while `--build all` should build ATT&CK and CAPEC without treating CAPEC as future work. The source card should advertise CAPEC's canonical manifest, schema, exports, Gremlin runtime preference, endpoint placeholders, join keys, and traversal safety notes.
- **Validation**: CLI tests should verify `--build capec`, `--build all`, and `--dry-run` behavior. Registry tests should verify `data/source_cards/capec.json` resolves to the CAPEC canonical manifest, CAPEC exports, schema version, node labels, relationship types, and Gremlin runtime backend.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (10/12) Complete: Wired CAPEC artifact building and source-card registration into the CLI.

#### Step 11: Enable CAPEC Runtime Loading and Verification

- **Locations**: `utils/graph_loader/registry.py`, `utils/graph_loader/validation/rules.py`, `utils/graph_loader/validation/semantic.py`, `utils/graph_loader/loader.py`, `utils/graph_loader/stores/gremlin.py`, `data/graphs/capec/runtime/gremlin/load-manifest.json`, tests under `utils/graph_loader/tests/`.
- **Rationale**: The long-term plan includes live Gremlin loading and runtime manifests. The current graph loader explicitly reports CAPEC as not built. After canonical CAPEC artifacts exist, loader resolution should accept CAPEC source cards, run CAPEC semantic validation, load the Gremlin export idempotently, and write a runtime manifest after verification.
- **Validation**: Unit tests should verify CAPEC dataset resolution, preflight, semantic validation, fake-store loading, runtime manifest writing, no-load verify behavior, and stale-manifest detection. Add opt-in Docker integration tests for `uv run main.py --dataset capec --graph gremlin` after the canonical CAPEC build is stable.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (11/12) Complete: Enabled CAPEC Gremlin runtime loading, verification, and runtime manifests.

#### Step 12: Update Documentation and End-to-End Regression Tests

- **Locations**: `README.md`, `docs/goals.md`, `docs/structure.md`, `docs/changelog.jsonl`, `docs/plans/capec-xml-canonical-graph-builder-plan.md`, tests under `utils/kg_builder/tests/` and `utils/graph_loader/tests/`.
- **Rationale**: Future agents and developers need the CAPEC workflow documented with the same clarity as ATT&CK: download, build, validate, export, load, health, and verify. The documentation should explain that `data/graphs/capec/canonical/` is the truth layer, Gremlin is the intended CAPEC runtime backend, and CAPEC-to-ATT&CK correlation should use normalized taxonomy mappings and shared external IDs.
- **Validation**: Run `uv run main.py --download`, `uv run main.py --build attack`, `uv run main.py --build capec`, `uv run python -m pytest utils/kg_builder/tests`, and `uv run python -m pytest utils/graph_loader/tests`. Run Docker-backed load and verify commands when local infrastructure is available: `uv run main.py --docker start`, `uv run main.py --dataset capec --graph gremlin`, and `uv run main.py --dataset capec --graph verify`.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: CAPEC XML Canonical Graph Builder (12/12) Complete: Documented and regression-tested the CAPEC canonical graph build and Gremlin runtime workflow.

### 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| CAPEC build paths | Dataset-specific raw, processed, canonical, export, runtime, and source-card path resolution. | `utils/kg_builder/config.py` |
| CAPEC XML discovery layer | Namespace-aware XML inventory, path registry, repeated structure detection, unknown-field capture, and discovery reports. | `utils/kg_builder/preprocess/capec.py`, optional `utils/kg_builder/discovery/capec_xml.py`, `data/processed/discovery/` |
| CAPEC normalization layer | Converts XML entities and references into deterministic intermediate records. | `utils/kg_builder/preprocess/capec.py`, `data/processed/pairs/capec.json` |
| CAPEC schema module | Node labels, relationship types, enum vocabularies, required properties, and allowed edge patterns. | `utils/kg_builder/schema/capec.py` |
| CAPEC canonical graph records | Backend-neutral nodes and relationships for attack patterns, categories, views, weaknesses, taxonomy entries, external references, steps, skills, consequences, and mitigations. | `data/graphs/capec/canonical/nodes.jsonl`, `data/graphs/capec/canonical/relationships.jsonl` |
| CAPEC canonical schema and manifest | Schema vocabulary, counts, metadata, settings, hashes, source version/date, discovery summary, and export declarations. | `data/graphs/capec/canonical/schema.json`, `data/graphs/capec/canonical/manifest.json` |
| CAPEC Neo4j export | Generated CSV and Cypher projection from canonical CAPEC records. | `data/graphs/capec/exports/neo4j/` |
| CAPEC Gremlin export | Gremlin-ready JSONL projection with scalar-safe properties and preserved IDs. | `data/graphs/capec/exports/gremlin/nodes.jsonl`, `data/graphs/capec/exports/gremlin/relationships.jsonl` |
| Dataset-aware exporters | Exporters that can use ATT&CK or CAPEC schema without hardcoded ATT&CK vocabulary. | `utils/kg_builder/exporters/jsonl.py`, `utils/kg_builder/exporters/cypher.py`, `utils/kg_builder/exporters/neo4j_csv.py`, `utils/kg_builder/exporters/gremlin.py` |
| CAPEC artifact validation | Structural and semantic validation for CAPEC canonical artifacts and backend exports. | `utils/kg_builder/validate.py`, `utils/kg_builder/schema/capec.py` |
| CAPEC source card | Source registry entry for planner and specialist agents, with Gremlin runtime preference and CAPEC-to-ATT&CK join metadata. | `data/source_cards/capec.json` |
| CAPEC runtime loader support | Dataset resolution, semantic validation, Gremlin load, verify, and runtime manifest support. | `utils/graph_loader/registry.py`, `utils/graph_loader/validation/`, `utils/graph_loader/stores/gremlin.py`, `data/graphs/capec/runtime/gremlin/load-manifest.json` |
| CAPEC XML fixture tests | Small local XML fixtures that test discovery, normalization, mapping, validation, exports, and CLI build behavior. | `utils/kg_builder/tests/fixtures/minimal_capec_catalog.xml`, `utils/kg_builder/tests/test_capec_*.py` |
| Runtime loader tests | Tests for CAPEC resolution, semantic validation, fake-store loading, no-load verify, and runtime manifests. | `utils/graph_loader/tests/test_*capec*.py` |
| Documentation updates | User-facing workflow and repo map updates for CAPEC build, export, load, health, and verify commands. | `README.md`, `docs/goals.md`, `docs/structure.md`, `docs/changelog.jsonl` |
