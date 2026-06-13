# ATT&CK Neo4j KG Builder Plan

### 1. Introduction

This plan defines the new data-layer goal for Ariadne: convert the pinned MITRE ATT&CK Enterprise dataset under `data/raw/attack/` into a reproducible Neo4j knowledge graph fixture. The implementation should follow `docs/references/ATT&CK_structure.md` for STIX object and relationship mapping, and `docs/references/Neo4J.md` for graph schema design, constraints, node-first imports, relationship creation, and verification.

The approach is staged around reproducibility. The CLI will expose `uv run main.py --build attack`, `uv run main.py --build capec`, and `uv run main.py --build all`; the ATT&CK builder will first preprocess raw STIX into deterministic node/edge pairs at `data/processed/pairs/enterprise-attack.json`, then build or export the Neo4j graph artifacts under `data/graphs/attack/`. CAPEC build options remain present for future work, with `data/processed/pairs/capec.json` reserved as the later preprocessing boundary, but this plan should not implement the CAPEC graph.

### 2. Gaps & Unanswered Questions

- **Python package path**: The requested path is `utils/kg-builder/`, but hyphenated directories are not importable Python packages with normal `import` syntax. *Assumption*: implement the package as `utils/kg_builder/` for Python compatibility, with the CLI treating it as the KG builder component. If the exact hyphenated path is mandatory, human intervention is needed to answer this question.
- **Neo4j execution target**: The repo does not yet define whether graph building should connect to a live Neo4j instance, emit Cypher files, create CSV import files, or do both. *Assumption*: implement both a deterministic local artifact path and a driver-backed load mode later, starting with generated Cypher/import artifacts in `data/graphs/attack/` so graph construction can be debugged without a running database.
- **Neo4j credentials and connection handling**: No secret-management pattern exists yet for Neo4j URI, user, and password. *Assumption*: use environment variables such as `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD`, and fail with a clear message when live loading is requested without credentials.
- **Exact graph artifact format**: `data/graphs/attack/` could contain Cypher, CSV files for `LOAD CSV`, a Neo4j dump, or a manifest combining these. *Assumption*: produce a schema/constraints Cypher file, node CSV/JSONL artifacts, relationship CSV/JSONL artifacts, and a manifest; defer a database dump until a live Neo4j workflow exists.
- **CAPEC scope**: `--build capec` and `--build all` are required for the CLI surface, but CAPEC is explicitly out of scope now. *Assumption*: keep `capec` as a clear not-yet-implemented build target and make `all` run ATT&CK now while reporting CAPEC as skipped until its Gremlin fixture plan exists.
- **Deprecated and revoked ATT&CK content**: The ATT&CK reference says to filter deprecated and revoked objects for a clean KG. *Assumption*: default to filtering both, while recording counts in preprocessing metadata for auditability.

### 3. Hierarchical Step-by-Step Instructions

#### Step 1: Define the Builder Goal and CLI Contract

- **Locations**: `main.py`, `setup_logging`, `main`, new `utils/kg_builder/__init__.py`, new `utils/kg_builder/main.py`, `README.md`, `docs/goals.md`.
- **Rationale**: The public workflow must start from `main.py` using `--build attack`, `--build capec`, and `--build all`. Defining the contract first prevents later builder modules from drifting away from the commands users and evaluators will run. Update `docs/goals.md` to point the Wk 3-4 data-layer task at this builder plan as the active goal.
- **Validation**: Run `uv run main.py --help` and verify the `--build` choices are visible. Run `uv run main.py --build capec` and confirm it exits predictably with a future-work message rather than silently doing nothing. Run `uv run main.py --build attack --dry-run` if a dry-run flag is introduced in this phase.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Neo4j KG Builder (1/8) Complete: Added the build CLI contract and documented the active data-layer goal.

#### Step 2: Establish the Builder Package Layout

- **Locations**: `utils/kg_builder/main.py`, `utils/kg_builder/config.py`, `utils/kg_builder/io.py`, `utils/kg_builder/preprocess/attack.py`, `utils/kg_builder/preprocess/capec.py`, `utils/kg_builder/schema/attack.py`, `utils/kg_builder/neo4j/export.py`, `utils/kg_builder/neo4j/load.py`, `utils/kg_builder/validate.py`.
- **Rationale**: The user requested multiple Python files with a main orchestration file and sub-directories organized by purpose. This layout separates orchestration, configuration, raw/processed I/O, STIX preprocessing, Neo4j schema/export behavior, optional live loading, and validation.
- **Validation**: Run import checks such as `uv run python -c "from utils.kg_builder.main import KGBuildRunner"` and run any existing project smoke checks. Confirm no package import errors occur from the chosen directory name.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Neo4j KG Builder (2/8) Complete: Added the KG builder package structure and importable orchestration entry point.

#### Step 3: Implement ATT&CK Raw Dataset Discovery and JSON Loading

- **Locations**: `utils/kg_builder/config.py`, `utils/kg_builder/io.py`, `utils/kg_builder/preprocess/attack.py`, existing `data/versions.json`, existing `data/raw/attack/v19.0/enterprise-attack.json`.
- **Rationale**: The builder must locate the pinned ATT&CK dataset reproducibly instead of relying on ad hoc paths. It should read `data/versions.json` or mirror the downloader's pinned version constants, then load the top-level STIX `bundle` and its `objects` array. Include gzip-aware fallback behavior because the ATT&CK reference warns about binary-looking gzip data.
- **Validation**: Add a small fixture-based unit test that loads a minimal STIX bundle and a local smoke test that verifies the real raw file parses as JSON and has an `objects` array. Confirm the loader reports source path, bundle id, object count, and ATT&CK version.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Neo4j KG Builder (3/8) Complete: Added reproducible ATT&CK raw dataset discovery and STIX bundle loading.

#### Step 4: Preprocess ATT&CK Nodes and Relationships Into Pairs

- **Locations**: `utils/kg_builder/preprocess/attack.py`, `utils/kg_builder/schema/attack.py`, `utils/kg_builder/io.py`, output `data/processed/pairs/enterprise-attack.json`.
- **Rationale**: Preprocessing creates a stable debugging boundary before any Neo4j-specific build work. Follow `docs/references/ATT&CK_structure.md`: convert relevant STIX objects into nodes, use `id` as the stable key, preserve ATT&CK human IDs from `external_references`, filter `revoked == true` and `x_mitre_deprecated == true`, convert STIX `relationship` objects into directed edges, and derive `Tactic` to `Technique` `HAS_TECHNIQUE` edges from `kill_chain_phases`.
- **Validation**: Add unit tests with a minimal STIX fixture covering `Technique`, `Tactic`, `Group`, `Software`, `Mitigation`, a STIX `relationship`, a sub-technique, and a deprecated object. Run the real ATT&CK preprocessing and verify `data/processed/pairs/enterprise-attack.json` contains deterministic top-level sections such as `metadata`, `nodes`, `relationships`, and `counts`.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Neo4j KG Builder (4/8) Complete: Added deterministic ATT&CK node and relationship preprocessing output.

#### Step 5: Define the Neo4j Graph Schema and Constraints

- **Locations**: `utils/kg_builder/schema/attack.py`, `utils/kg_builder/neo4j/export.py`, output `data/graphs/attack/schema.cypher`, output `data/graphs/attack/manifest.json`.
- **Rationale**: Neo4j loading should begin with a schema model and uniqueness constraints before nodes or edges are imported. Use labels from the ATT&CK reference: `Tactic`, `Technique`, `Group`, `Software`, `Mitigation`, `Campaign`, `DataSource`, `DataComponent`, `Asset`, and `Matrix`. Define unique constraints on stable identifiers such as `stix_id` and optional indexes for `attack_id`, `name`, and label-specific lookup fields.
- **Validation**: Verify generated Cypher is deterministic and contains constraints for every implemented node label. Review that relationship type names are normalized into valid Neo4j relationship labels, for example `USES`, `MITIGATES`, `ATTRIBUTED_TO`, `HAS_SUBTECHNIQUE`, and `HAS_TECHNIQUE`.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Neo4j KG Builder (5/8) Complete: Added Neo4j schema constraints and graph manifest generation for ATT&CK.

#### Step 6: Export Neo4j Load Artifacts Under data/graphs/attack/

- **Locations**: `utils/kg_builder/neo4j/export.py`, `utils/kg_builder/io.py`, outputs under `data/graphs/attack/` such as `nodes/*.csv`, `relationships/*.csv`, `load.cypher`, `schema.cypher`, and `manifest.json`.
- **Rationale**: Exporting artifacts before live database loading makes failures reproducible. Neo4j guidance says to import nodes before relationships, use `MERGE`, and create relationships in a second pass. Generated artifacts should be stable, inspectable, and tied back to the processed pairs file.
- **Validation**: Run `uv run main.py --build attack` and confirm it writes `data/processed/pairs/enterprise-attack.json` and `data/graphs/attack/` artifacts. Verify artifact counts match preprocessing metadata and that every relationship endpoint appears in the exported node set.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Neo4j KG Builder (6/8) Complete: Added reproducible Neo4j load artifacts for the ATT&CK graph.

#### Step 7: Add Optional Live Neo4j Loading and Verification

- **Locations**: `utils/kg_builder/neo4j/load.py`, `utils/kg_builder/validate.py`, `utils/kg_builder/main.py`, `pyproject.toml`, optional `README.md` Neo4j setup section.
- **Rationale**: Once artifacts are stable, add the live Neo4j path using the official Python driver. The loader should apply constraints first, load nodes before relationships, use `MERGE`, batch writes, and then run verification queries for node counts, relationship counts, and sample paths.
- **Validation**: Add a `--load-neo4j` or similarly explicit option so default builds do not require a running database. Against a local Neo4j instance, run schema creation, node loading, relationship loading, and validation queries. Without credentials, verify the command fails clearly before partial writes.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Neo4j KG Builder (7/8) Complete: Added optional live Neo4j loading and graph verification checks.

#### Step 8: Add Tests, Documentation, and Regression Guardrails

- **Locations**: new tests under `utils/kg_builder/tests/` or the repo's chosen test directory, `README.md`, `docs/goals.md`, `docs/changelog.jsonl`, `data/processed/pairs/.gitkeep` if needed, `data/graphs/attack/.gitkeep` if generated artifacts remain untracked.
- **Rationale**: The builder becomes part of the reproducible data layer, so it needs tests that exercise a small subset of information and documentation for repeatable use. The tests should protect STIX parsing, node mapping, relationship mapping, tactic derivation, filtering, artifact generation, and CLI behavior.
- **Validation**: Run the full relevant suite, including `uv run python -m pytest` if pytest is added, `uv run main.py --build attack` against the real downloaded dataset, and `uv run main.py --build all` to confirm ATT&CK builds while CAPEC is reported as future work. Confirm generated files are either intentionally tracked or intentionally ignored.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Neo4j KG Builder (8/8) Complete: Added tests, documentation, and regression guardrails for the ATT&CK Neo4j build workflow.

### 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Active KG builder goal | Documentation tying the Wk 3-4 data-layer goal to the ATT&CK Neo4j builder work. | `docs/goals.md`, `docs/plans/attack-neo4j-kg-builder-plan.md` |
| Build CLI contract | `--build attack`, `--build capec`, and `--build all` dispatch from the project CLI. | `main.py` |
| KG builder orchestrator | Main Python entry point that coordinates preprocessing, artifact export, optional loading, and validation. | `utils/kg_builder/main.py` |
| Builder configuration | Dataset version/path resolution and output directory definitions. | `utils/kg_builder/config.py` |
| I/O utilities | JSON/gzip-aware loading, deterministic writing, manifest writing, and directory creation. | `utils/kg_builder/io.py` |
| ATT&CK preprocessor | Converts STIX bundle objects into deterministic nodes and relationships, including derived tactic edges. | `utils/kg_builder/preprocess/attack.py` |
| CAPEC placeholder | Future build target stub that keeps CLI compatibility and reserves `data/processed/pairs/capec.json` without implementing CAPEC now. | `utils/kg_builder/preprocess/capec.py` |
| ATT&CK schema definitions | Node-label, relationship-label, property, and constraint mapping for Neo4j. | `utils/kg_builder/schema/attack.py` |
| Processed pairs artifact | Stable preprocessing boundary for debugging and reproducibility. | `data/processed/pairs/enterprise-attack.json` |
| Neo4j graph artifacts | Schema, load scripts, node artifacts, relationship artifacts, and manifest for ATT&CK. | `data/graphs/attack/` |
| Optional Neo4j loader | Driver-backed live loading into Neo4j using constraints, `MERGE`, node-first loading, and relationship batching. | `utils/kg_builder/neo4j/load.py` |
| Neo4j export generator | Generates Cypher/import artifacts from processed pairs. | `utils/kg_builder/neo4j/export.py` |
| Graph validator | Count checks, missing endpoint checks, label checks, and sample graph query checks. | `utils/kg_builder/validate.py` |
| Small fixture tests | Tests that run a small ATT&CK-like subset through preprocessing and artifact generation. | `utils/kg_builder/tests/` or repo-standard test path |
| CLI regression tests | Tests for `--build attack`, `--build capec`, and `--build all` behavior. | `utils/kg_builder/tests/test_cli_build.py` or repo-standard test path |
| User documentation | Commands, outputs, Neo4j environment variables, and troubleshooting notes. | `README.md` |
