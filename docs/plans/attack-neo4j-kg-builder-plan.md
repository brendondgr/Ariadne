# ATT&CK Portable Graph Artifact Builder Plan

### 1. Introduction

This plan defines the next data-layer goal for Ariadne: convert the pinned MITRE ATT&CK Enterprise dataset under `data/raw/attack/` into a portable, reproducible graph artifact bundle. The immediate goal is not to load Neo4j directly. The immediate goal is to normalize ATT&CK STIX into a graph model and write durable components that can later feed Neo4j, another property graph database, or future experiments.

The build flow should follow this shape: `ATT&CK JSON -> Normalized Graph Model -> Graph Artifacts -> optional downstream loader`. The CLI will expose `uv run main.py --build attack`, `uv run main.py --build capec`, and `uv run main.py --build all`; for now, `attack` builds the portable graph artifacts and `capec` remains a future placeholder. The ATT&CK output should include `nodes.jsonl`, `relationships.jsonl`, graph schema files, Neo4j-compatible CSV/Cypher files, and `manifest.json` under `data/graphs/attack/`, with `data/processed/pairs/enterprise-attack.json` retained as the preprocessing checkpoint.

### 2. Gaps & Unanswered Questions

- **Python package path**: The requested path is `utils/kg-builder/`, but hyphenated directories are not importable Python packages with normal `import` syntax. *Assumption*: implement the package as `utils/kg_builder/` for Python compatibility, with the CLI treating it as the KG builder component. If the exact hyphenated path is mandatory, human intervention is needed to answer this question.
- **Primary output target**: The primary output is now answered: build portable graph components first, not a live Neo4j database. *Decision*: Phase 1 outputs normalized model files, JSONL node/relationship files, schema files, constraints, Neo4j CSV/Cypher compatibility artifacts, and a manifest.
- **Neo4j role**: Neo4j is not the primary build target in this phase. *Decision*: generate Neo4j-compatible artifacts such as `schema.cypher`, `constraints.cypher`, and CSV import files, but defer any live Neo4j loader to a later plan or implementation phase.
- **Artifact directory contract**: The desired output bundle is now clear. *Decision*: use `data/graphs/attack/` for graph artifacts, with stable subdirectories such as `jsonl/`, `cypher/`, and `neo4j_csv/` if implementation needs organization.
- **CAPEC scope**: `--build capec` and `--build all` are still required for the CLI surface, but CAPEC is explicitly out of scope now. *Assumption*: keep `capec` as a clear not-yet-implemented build target and reserve `data/processed/pairs/capec.json` for the later CAPEC pipeline.
- **Deprecated and revoked ATT&CK content**: The ATT&CK reference says to filter deprecated and revoked objects for a clean KG. *Assumption*: default to filtering both, while recording filtered counts in preprocessing metadata for auditability.

### 3. Hierarchical Step-by-Step Instructions

#### Step 1: Define the Portable Build Goal and CLI Contract

- **Locations**: `main.py`, `setup_logging`, `main`, new `utils/kg_builder/__init__.py`, new `utils/kg_builder/main.py`, `README.md`, `docs/goals.md`.
- **Rationale**: The public workflow must start from `main.py` using `--build attack`, `--build capec`, and `--build all`. The CLI contract should describe `attack` as an artifact-building job, not a direct Neo4j loading job. This makes the data-layer milestone reproducible and leaves room to target other graph databases later.
- **Validation**: Run `uv run main.py --help` and verify the `--build` choices are visible. Run `uv run main.py --build capec` and confirm it exits predictably with a future-work message. Run `uv run main.py --build attack --dry-run` if a dry-run flag is introduced in this phase.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Portable Graph Artifact Builder (1/8) Complete: Added the portable build CLI contract and documented the active data-layer goal.

#### Step 2: Establish the Builder Package Layout Around Artifact Generation

- **Locations**: `utils/kg_builder/main.py`, `utils/kg_builder/config.py`, `utils/kg_builder/io.py`, `utils/kg_builder/models.py`, `utils/kg_builder/preprocess/attack.py`, `utils/kg_builder/preprocess/capec.py`, `utils/kg_builder/schema/attack.py`, `utils/kg_builder/exporters/jsonl.py`, `utils/kg_builder/exporters/cypher.py`, `utils/kg_builder/exporters/neo4j_csv.py`, `utils/kg_builder/validate.py`.
- **Rationale**: The user requested multiple Python files with a main orchestration file and subdirectories organized by purpose. The package should center on raw input, normalized graph modeling, and artifact exporters. Neo4j-specific files should be exporters only in this phase, not database loaders.
- **Validation**: Run import checks such as `uv run python -c "from utils.kg_builder.main import KGBuildRunner"` and run any existing project smoke checks. Confirm no package import errors occur from the chosen directory name.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Portable Graph Artifact Builder (2/8) Complete: Added the artifact-focused KG builder package structure and orchestration entry point.

#### Step 3: Implement ATT&CK Raw Dataset Discovery and JSON Loading

- **Locations**: `utils/kg_builder/config.py`, `utils/kg_builder/io.py`, `utils/kg_builder/preprocess/attack.py`, existing `data/versions.json`, existing `data/raw/attack/v19.0/enterprise-attack.json`.
- **Rationale**: The builder must locate the pinned ATT&CK dataset reproducibly instead of relying on ad hoc paths. It should read `data/versions.json` or mirror the downloader's pinned version constants, then load the top-level STIX `bundle` and its `objects` array. Include gzip-aware fallback behavior because the ATT&CK reference warns about binary-looking gzip data.
- **Validation**: Add a small fixture-based unit test that loads a minimal STIX bundle and a local smoke test that verifies the real raw file parses as JSON and has an `objects` array. Confirm the loader reports source path, bundle id, object count, and ATT&CK version.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Portable Graph Artifact Builder (3/8) Complete: Added reproducible ATT&CK raw dataset discovery and STIX bundle loading.

#### Step 4: Build the Normalized Graph Model and Processed Pairs Checkpoint

- **Locations**: `utils/kg_builder/models.py`, `utils/kg_builder/preprocess/attack.py`, `utils/kg_builder/schema/attack.py`, `utils/kg_builder/io.py`, output `data/processed/pairs/enterprise-attack.json`.
- **Rationale**: The normalized graph model is the database-neutral boundary of the pipeline. Follow `docs/references/ATT&CK_structure.md`: convert relevant STIX objects into nodes, use `id` as the stable key, preserve ATT&CK human IDs from `external_references`, filter `revoked == true` and `x_mitre_deprecated == true`, convert STIX `relationship` objects into directed edges, and derive `Tactic` to `Technique` `HAS_TECHNIQUE` edges from `kill_chain_phases`.
- **Validation**: Add unit tests with a minimal STIX fixture covering `Technique`, `Tactic`, `Group`, `Software`, `Mitigation`, a STIX `relationship`, a sub-technique, and a deprecated object. Run the real ATT&CK preprocessing and verify `data/processed/pairs/enterprise-attack.json` contains deterministic sections such as `metadata`, `nodes`, `relationships`, and `counts`.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Portable Graph Artifact Builder (4/8) Complete: Added the normalized ATT&CK graph model and processed pairs checkpoint.

#### Step 5: Export Database-Neutral JSONL Graph Artifacts

- **Locations**: `utils/kg_builder/exporters/jsonl.py`, `utils/kg_builder/io.py`, outputs `data/graphs/attack/nodes.jsonl`, `data/graphs/attack/relationships.jsonl`, optional `data/graphs/attack/schema.json`, `data/graphs/attack/manifest.json`.
- **Rationale**: JSONL node and relationship files are the most portable build output. They provide a stable interchange format for later loaders, validation tools, source-card generation, and experiments with graph databases beyond Neo4j.
- **Validation**: Run `uv run main.py --build attack` and confirm it writes `nodes.jsonl`, `relationships.jsonl`, and `manifest.json`. Verify that every JSONL line is valid JSON, every relationship endpoint exists in `nodes.jsonl`, and the manifest counts match the processed pairs checkpoint.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Portable Graph Artifact Builder (5/8) Complete: Added database-neutral JSONL node and relationship graph artifacts.

#### Step 6: Export Schema, Constraints, and Neo4j-Compatible Build Files

- **Locations**: `utils/kg_builder/schema/attack.py`, `utils/kg_builder/exporters/cypher.py`, `utils/kg_builder/exporters/neo4j_csv.py`, outputs `data/graphs/attack/schema.cypher`, `data/graphs/attack/constraints.cypher`, `data/graphs/attack/neo4j_csv/`, optional `data/graphs/attack/load.cypher`.
- **Rationale**: Neo4j remains the planned ATT&CK demonstration backend, so the artifact bundle should include Neo4j-compatible files. These files should be generated from the normalized graph model, not from database state, so they can be recreated and inspected without running Neo4j. `schema.cypher` should describe labels and relationship types, `constraints.cypher` should create uniqueness constraints and indexes, and CSV files should support a future `LOAD CSV` import.
- **Validation**: Verify generated Cypher is deterministic and contains constraints for every implemented node label. Review that relationship type names are normalized into valid Neo4j relationship labels, for example `USES`, `MITIGATES`, `ATTRIBUTED_TO`, `HAS_SUBTECHNIQUE`, and `HAS_TECHNIQUE`. Verify CSV row counts match the JSONL artifacts.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Portable Graph Artifact Builder (6/8) Complete: Added schema, constraints, Cypher, and Neo4j-compatible CSV build artifacts.

#### Step 7: Add Artifact Validation and Reproducibility Checks

- **Locations**: `utils/kg_builder/validate.py`, `utils/kg_builder/main.py`, `utils/kg_builder/tests/`, output `data/graphs/attack/manifest.json`.
- **Rationale**: Since artifacts are the primary output, validation must prove that they are internally consistent and reproducible. Validation should check node uniqueness, relationship endpoint integrity, label/type allowlists, count consistency, deterministic ordering, stable manifest hashes, and filtered deprecated/revoked counts.
- **Validation**: Run the artifact validator against the real ATT&CK output. Confirm that repeated `uv run main.py --build attack` runs produce the same counts and stable file hashes when the input data has not changed. Confirm validation fails clearly when a fixture includes a relationship with a missing endpoint.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Portable Graph Artifact Builder (7/8) Complete: Added artifact validation and reproducibility checks for ATT&CK graph outputs.

#### Step 8: Add Tests, Documentation, and Deferred Loader Notes

- **Locations**: new tests under `utils/kg_builder/tests/` or the repo's chosen test directory, `README.md`, `docs/goals.md`, `docs/changelog.jsonl`, `data/processed/pairs/.gitkeep` if needed, `data/graphs/attack/.gitkeep` if generated artifacts remain untracked.
- **Rationale**: The builder becomes part of the reproducible data layer, so it needs tests that exercise a small subset of information and documentation for repeatable use. Documentation should make clear that the current phase builds graph components first and that any live Neo4j loader is a downstream phase after artifact generation is stable.
- **Validation**: Run the full relevant suite, including `uv run python -m pytest` if pytest is added, `uv run main.py --build attack` against the real downloaded dataset, and `uv run main.py --build all` to confirm ATT&CK artifacts build while CAPEC is reported as future work. Confirm generated files are either intentionally tracked or intentionally ignored.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Portable Graph Artifact Builder (8/8) Complete: Added tests, documentation, and deferred loader notes for the portable graph artifact workflow.

### 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Active portable graph builder goal | Documentation tying the Wk 3-4 data-layer goal to portable graph artifact generation before database loading. | `docs/goals.md`, `docs/plans/attack-neo4j-kg-builder-plan.md` |
| Build CLI contract | `--build attack`, `--build capec`, and `--build all` dispatch from the project CLI. | `main.py` |
| KG builder orchestrator | Main Python entry point that coordinates raw loading, normalization, artifact export, and validation. | `utils/kg_builder/main.py` |
| Builder configuration | Dataset version/path resolution and output directory definitions. | `utils/kg_builder/config.py` |
| Normalized graph model | Database-neutral node, relationship, schema, and metadata structures. | `utils/kg_builder/models.py` |
| I/O utilities | JSON/gzip-aware loading, deterministic writing, JSONL writing, manifest writing, and directory creation. | `utils/kg_builder/io.py` |
| ATT&CK preprocessor | Converts STIX bundle objects into normalized nodes and relationships, including derived tactic edges. | `utils/kg_builder/preprocess/attack.py` |
| CAPEC placeholder | Future build target stub that keeps CLI compatibility and reserves `data/processed/pairs/capec.json` without implementing CAPEC now. | `utils/kg_builder/preprocess/capec.py` |
| ATT&CK schema definitions | Node-label, relationship-label, property, and constraint mapping for portable artifacts and Neo4j compatibility files. | `utils/kg_builder/schema/attack.py` |
| Processed pairs artifact | Stable preprocessing checkpoint for debugging and reproducibility. | `data/processed/pairs/enterprise-attack.json` |
| Node JSONL artifact | Database-neutral normalized node records. | `data/graphs/attack/nodes.jsonl` |
| Relationship JSONL artifact | Database-neutral normalized relationship records. | `data/graphs/attack/relationships.jsonl` |
| Manifest artifact | Counts, source metadata, artifact paths, hashes, filter counts, and build settings. | `data/graphs/attack/manifest.json` |
| Schema Cypher artifact | Neo4j-compatible schema description generated from the normalized graph model. | `data/graphs/attack/schema.cypher` |
| Constraints Cypher artifact | Neo4j-compatible uniqueness constraints and indexes generated from the normalized graph model. | `data/graphs/attack/constraints.cypher` |
| Neo4j CSV artifacts | CSV files suitable for a future Neo4j `LOAD CSV` importer. | `data/graphs/attack/neo4j_csv/` |
| JSONL exporter | Writes portable `nodes.jsonl` and `relationships.jsonl`. | `utils/kg_builder/exporters/jsonl.py` |
| Cypher exporter | Writes `schema.cypher`, `constraints.cypher`, and optional future `load.cypher`. | `utils/kg_builder/exporters/cypher.py` |
| Neo4j CSV exporter | Writes Neo4j-compatible CSV node and relationship files without loading a database. | `utils/kg_builder/exporters/neo4j_csv.py` |
| Artifact validator | Count checks, missing endpoint checks, label/type checks, deterministic ordering checks, and manifest hash checks. | `utils/kg_builder/validate.py` |
| Small fixture tests | Tests that run a small ATT&CK-like subset through normalization and artifact generation. | `utils/kg_builder/tests/` or repo-standard test path |
| CLI regression tests | Tests for `--build attack`, `--build capec`, and `--build all` behavior. | `utils/kg_builder/tests/test_cli_build.py` or repo-standard test path |
| User documentation | Commands, generated artifacts, output directory contract, and deferred Neo4j loader notes. | `README.md` |
