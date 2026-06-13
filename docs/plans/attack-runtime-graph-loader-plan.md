# ATT&CK Runtime Graph Loader Plan

### 1. Introduction

This plan defines the next Ariadne data-layer phase: load the already-built ATT&CK canonical graph into either Neo4j, Gremlin, or both through a common graph abstraction layer. The requested load command surface is `uv run main.py --dataset attack --graph neo4j`, `uv run main.py --dataset attack --graph gremlin`, and `uv run main.py --dataset attack --graph all`.

The important boundary is that `--dataset/--graph` must not download raw files or rebuild the dataset implicitly. It should only load from validated canonical artifacts and generated backend exports that already exist under `data/graphs/<dataset>/`. If `data/graphs/attack/canonical/manifest.json`, canonical JSONL, schema, source card metadata, backend export files, or semantic validation rules are missing or stale, the loader must fail with a clear message telling the operator to run `uv run main.py --build attack` first or repair the graph contract.

### 2. Gaps & Unanswered Questions

- **Command ownership**: The repository already uses `--build` for artifact creation and `--docker` for infrastructure. *Decision*: add `--dataset attack|capec|all` and `--graph neo4j|gremlin|all` as the live graph loading command pair. This keeps artifact building and database loading separate.
- **No-load verification command**: Operators need to check graph health without performing a load. *Decision*: add `uv run main.py --dataset attack --graph verify` as a no-load dataset verification path that checks built artifact validity, manifest hashes, runtime load manifests, backend reachability, and live node/edge counts. Add `uv run main.py --graph health` as a lighter infrastructure-only reachability check for Neo4j and Gremlin endpoints.
- **Dataset precondition**: The user emphasized that the dataset must be built, not merely downloaded. *Decision*: loading requires a validated canonical manifest and backend export files generated from the canonical graph. Raw files under `data/raw/` are not sufficient.
- **Semantic graph validation**: Existing validation checks counts, hashes, file existence, and endpoint integrity, but runtime loading also needs graph meaning checks. *Decision*: add `utils/graph_loader/validation/` with semantic validators for legal node labels, legal edge types, allowed source-target label pairs, required properties, duplicate semantic keys, and cross-reference consistency before any database write begins.
- **CAPEC behavior**: The desired long-term command pattern includes future datasets such as `capec`, but the repo currently has ATT&CK canonical artifacts only. *Decision*: implement the loader contract generically, but have `capec` fail with a not-yet-built dataset error until CAPEC canonical artifacts and semantic rules exist.
- **Backend drivers**: The current `pyproject.toml` does not include Neo4j or Gremlin Python drivers. *Assumption*: add `neo4j` for Bolt and `gremlinpython` for TinkerPop/Gremlin Server when implementation begins.
- **Connection configuration**: Docker exposes Neo4j Bolt at `bolt://localhost:5456` and Gremlin at `ws://localhost:6455/gremlin`. *Decision*: default to those endpoints, but read endpoint overrides from source cards, environment variables, or explicit future CLI options.
- **Load semantics**: Repeated runs should not create duplicate graph content. *Decision*: loaders must use idempotent upsert semantics keyed on canonical `id` for nodes and canonical edge identity for relationships.
- **Database cleanup policy**: It is unclear whether loading should wipe previous graph content or merge into it. *Assumption*: default to idempotent merge without destructive deletion. Add an explicit future `--replace` or `--clear-first` option only after human approval.
- **Gremlin compatibility target**: The Docker Gremlin service is Apache TinkerPop Gremlin Server, while future work may target Neptune-style Gremlin. *Decision*: keep Gremlin adapter logic within a backend adapter and restrict the loader contract to portable TinkerPop traversals first.
- **Agent query layer**: This phase prepares the dataset and graph layers, but not the future agent query layer. *Decision*: reserve `GraphQueryEngine` for a later plan above `GraphStore`, where agents can call domain methods such as `find_technique("Credential Dumping")` without writing Cypher or Gremlin directly.

### 3. Hierarchical Step-by-Step Instructions

#### Step 1: Confirm the Current Build Artifact Contract

- **Locations**: `utils/kg_builder/main.py`, `utils/kg_builder/config.py`, `utils/kg_builder/registry.py`, `utils/kg_builder/validate.py`, `data/graphs/attack/canonical/`, `data/graphs/attack/exports/neo4j/`, `data/graphs/attack/exports/gremlin/`, `data/source_cards/attack.json`, `README.md`, `docs/structure.md`.
- **Rationale**: The loader must consume the existing canonical graph boundary instead of inventing a second truth model. This step records the files that are mandatory before live loading: canonical `nodes.jsonl`, `relationships.jsonl`, `schema.json`, `manifest.json`, source card metadata, Neo4j CSV/Cypher exports, and Gremlin JSONL exports.
- **Validation**: Run `uv run main.py --build attack`, then run `uv run python -m pytest utils/kg_builder/tests`. Confirm `validate_canonical_artifacts` and `validate_cross_backend_exports` pass before any runtime loader work begins.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (1/12) Complete: Confirmed the canonical artifact contract that runtime graph loading will consume.

#### Step 2: Add a Dataset and Backend Resolution Layer

- **Locations**: new `utils/graph_loader/__init__.py`, new `utils/graph_loader/config.py`, new `utils/graph_loader/registry.py`, existing `utils/kg_builder/config.py`, existing `utils/kg_builder/registry.py`, tests under new `utils/graph_loader/tests/test_registry_resolution.py`.
- **Rationale**: Future datasets should use the same loader pathway. A dataset resolver should map `attack` to `data/source_cards/attack.json`, verify that the canonical manifest exists, verify that the manifest references existing canonical and backend export files, and return a structured load target for the requested backend.
- **Validation**: Add fixture tests where `attack` resolves successfully from a temporary source card and where missing `manifest.json`, missing export files, unsupported backend choices, or unsupported `capec` produce clear failures. Do not connect to live databases in this phase.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (2/12) Complete: Added dataset and backend resolution over built canonical graph artifacts.

#### Step 3: Extend the CLI Without Changing Build Semantics

- **Locations**: `main.py`, `setup_logging`, `main`, new `utils/graph_loader/main.py`, tests under `utils/graph_loader/tests/test_cli_load.py`, `README.md`.
- **Rationale**: The requested command shape should become the public live-load surface while `--build` remains the artifact generation surface. `uv run main.py --dataset attack --graph neo4j` should load only Neo4j, `--graph gremlin` should load only Gremlin, `--graph all` should load both in a deterministic order, `--dataset attack --graph verify` should verify without loading, and `--graph health` should check backend reachability without requiring a dataset.
- **Validation**: Run `uv run main.py --help` and confirm `--dataset` and `--graph` are documented. Add CLI tests for missing `--graph`, missing `--dataset` when required, invalid combinations, `attack/neo4j`, `attack/gremlin`, `attack/all`, `attack/verify`, `health`, and `capec` not-yet-built behavior.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (3/12) Complete: Added the dataset, graph loading, verification, and health CLI contract without changing artifact build behavior.

#### Step 4: Define the Common GraphStore Contract

- **Locations**: new `utils/graph_loader/stores/base.py`, new `utils/graph_loader/models.py`, existing `utils/kg_builder/models.py`, tests under `utils/graph_loader/tests/test_graph_store_contract.py`.
- **Rationale**: Neo4j and Gremlin should be backend implementations behind one graph contract. Define operations such as `connect`, `close`, `ensure_schema`, `upsert_nodes`, `upsert_edges`, `count_nodes`, `count_edges`, `count_by_label`, `count_by_relationship_type`, `sample_node`, `healthcheck`, and `verify_loaded_graph`. Keep canonical graph records as the input model and backend query details inside adapters.
- **Validation**: Add a fake in-memory GraphStore implementation for contract tests. Verify that the dataset loader can call only the base contract and does not import Neo4j or Gremlin adapters directly except through a backend factory.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (4/12) Complete: Defined the common GraphStore contract for backend-independent graph loading and verification.

#### Step 5: Add a Graph Semantic Validation Layer

- **Locations**: new `utils/graph_loader/validation/__init__.py`, new `utils/graph_loader/validation/semantic.py`, new `utils/graph_loader/validation/rules.py`, new `utils/graph_loader/validation/references.py`, existing `utils/kg_builder/schema/attack.py`, tests under `utils/graph_loader/tests/test_semantic_validation.py`.
- **Rationale**: Artifact validation proves that files are internally consistent, but semantic validation proves that the graph makes domain sense before it is loaded. The semantic layer should validate node types, edge types, allowed source-target label pairs, required properties such as canonical `id`, ATT&CK IDs where expected, STIX type preservation, and references such as relationship endpoints and derived tactic links.
- **Validation**: Add fixture tests where valid relationships such as `Group USES Technique`, `Software USES Technique`, `Mitigation MITIGATES Technique`, `Tactic HAS_TECHNIQUE Technique`, and `Technique HAS_SUBTECHNIQUE Technique` pass. Add negative fixture tests where illegal combinations such as `Technique USES Mitigation`, missing required properties, unknown labels, unknown edge types, or dangling references fail before any backend adapter is called.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (5/12) Complete: Added semantic graph validation as a hard gate before Neo4j or Gremlin loading.

#### Step 6: Implement Infrastructure and Artifact Preflight Checks

- **Locations**: new `utils/graph_loader/preflight.py`, existing `utils/infrastructure/docker_manager.py`, new semantic validation package under `utils/graph_loader/validation/`, new `utils/graph_loader/tests/test_preflight.py`, source card `data/source_cards/attack.json`.
- **Rationale**: The loader must fail early when prerequisites are missing. Preflight should check that Docker services are reachable, the selected backend endpoint is configured, the canonical manifest exists, manifest hashes match current files, source card schema metadata is available, the selected backend export exists, and semantic validation passes.
- **Validation**: Add tests for missing canonical files, hash mismatch, missing Neo4j exports, missing Gremlin exports, endpoint not configured, backend not reachable, and semantic validation failure. Live endpoint checks should be isolated behind functions so unit tests can mock them.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (6/12) Complete: Added preflight validation for built artifacts, source cards, semantic graph rules, and graph backend readiness.

#### Step 7: Add the Neo4jGraphStore Adapter

- **Locations**: new `utils/graph_loader/stores/neo4j.py`, existing `data/graphs/attack/exports/neo4j/nodes.csv`, existing `data/graphs/attack/exports/neo4j/relationships.csv`, existing `data/graphs/attack/exports/neo4j/constraints.cypher`, tests under `utils/graph_loader/tests/test_neo4j_store.py`, `pyproject.toml`.
- **Rationale**: Neo4j is the reference runtime backend for ATT&CK. The adapter should connect over Bolt, apply constraints, upsert nodes by canonical `id`, upsert relationships by endpoint and type, and verify counts against the canonical manifest. It should use the Python Neo4j driver for repeatable programmatic loading.
- **Validation**: Add unit tests for query generation without requiring Neo4j. Add an integration test marker that starts from `uv run main.py --docker start`, runs `uv run main.py --dataset attack --graph neo4j`, and verifies `MATCH (n) RETURN count(n)` plus representative label counts match the manifest. Keep live integration tests opt-in if they require Docker.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (7/12) Complete: Added the Neo4j GraphStore adapter and count validation for ATT&CK loads.

#### Step 8: Add the GremlinGraphStore Adapter

- **Locations**: new `utils/graph_loader/stores/gremlin.py`, existing `data/graphs/attack/exports/gremlin/nodes.jsonl`, existing `data/graphs/attack/exports/gremlin/relationships.jsonl`, tests under `utils/graph_loader/tests/test_gremlin_store.py`, `pyproject.toml`.
- **Rationale**: Gremlin should load the same ATT&CK canonical graph through a backend-specific projection. The adapter should connect to `ws://localhost:6455/gremlin`, upsert vertices by `id`, preserve primary vertex labels, upsert directed typed edges, serialize properties according to the Gremlin export contract, and verify counts against the canonical manifest.
- **Validation**: Add unit tests for generated traversals and idempotent upsert behavior. Add an opt-in Docker integration test that runs `uv run main.py --dataset attack --graph gremlin` and verifies `g.V().count()` plus representative label counts match the manifest.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (8/12) Complete: Added the Gremlin GraphStore adapter and count validation for ATT&CK loads.

#### Step 9: Implement the Dataset Load Orchestrator

- **Locations**: new `utils/graph_loader/main.py`, new `utils/graph_loader/loader.py`, new `utils/graph_loader/stores/factory.py`, new `utils/graph_loader/results.py`, new semantic validation package under `utils/graph_loader/validation/`, tests under `utils/graph_loader/tests/test_loader_orchestration.py`.
- **Rationale**: The orchestrator should coordinate dataset resolution, preflight, semantic validation, backend selection, canonical artifact reading, backend export reading, schema setup, batched node loading, batched edge loading, post-load verification, and load result reporting. `--graph all` should run Neo4j and Gremlin through the same orchestrator path and return a combined result.
- **Validation**: Add tests proving `--graph all` calls both adapters, reports independent success/failure, and does not mark the whole dataset loaded if one backend fails. Verify repeated loads are idempotent by running the same small fixture twice against fake stores. Verify semantic validation failure prevents both Neo4j and Gremlin writes.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (9/12) Complete: Added the dataset load orchestrator for semantic validation, Neo4j loading, Gremlin loading, and all-backend loading.

#### Step 10: Add Runtime Load Manifests

- **Locations**: new `data/graphs/attack/runtime/neo4j/load-manifest.json`, new `data/graphs/attack/runtime/gremlin/load-manifest.json`, new `utils/graph_loader/manifest.py`, tests under `utils/graph_loader/tests/test_load_manifest.py`, `README.md`.
- **Rationale**: A built canonical dataset and a loaded live database are different states. After a successful load, write runtime load manifests recording dataset, backend, source canonical manifest hash, semantic validation result, node count, edge count, endpoint, loaded timestamp, adapter version, and verification query results. Future agents can inspect these manifests before assuming a live graph is ready.
- **Validation**: Add tests that load manifests are written only after successful semantic validation and post-load verification. Confirm the runtime manifest points back to the canonical manifest hash and records the backend adapter that performed the load.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (10/12) Complete: Added runtime load manifests for verified Neo4j and Gremlin projections.

#### Step 11: Add No-Load Verify and Health Commands

- **Locations**: new `utils/graph_loader/verify.py`, existing `utils/infrastructure/docker_manager.py`, `main.py`, tests under `utils/graph_loader/tests/test_verify_commands.py`, `README.md`.
- **Rationale**: Operators and future agents need a cheap way to answer whether graph infrastructure and loaded datasets are ready. `uv run main.py --graph health` should check Neo4j and Gremlin endpoint reachability only. `uv run main.py --dataset attack --graph verify` should check canonical manifest hashes, semantic validation, runtime load manifests, backend reachability, node counts, edge counts, representative label counts, and representative relationship-type counts without performing writes.
- **Validation**: Add unit tests for healthy, unreachable, missing runtime manifest, stale runtime manifest, count mismatch, semantic validation failure, and manifest hash mismatch cases. Add an opt-in Docker integration test where `--graph verify` passes after successful `--graph all` loading and fails after a mocked count mismatch.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (11/12) Complete: Added no-load graph health and dataset verification commands.

#### Step 12: Update Documentation, Examples, and End-to-End Tests

- **Locations**: `README.md`, `docs/goals.md`, `docs/structure.md`, `docs/changelog.jsonl`, new `utils/graph_loader/tests/`, optional `docs/references/Gremlin.md`.
- **Rationale**: The repo needs clear separation between download, build, infrastructure, load, health, and verify commands. Documentation should show the full operator sequence: `uv run main.py --download`, `uv run main.py --build attack`, `uv run main.py --docker start`, `uv run main.py --dataset attack --graph neo4j|gremlin|all`, `uv run main.py --graph health`, and `uv run main.py --dataset attack --graph verify`.
- **Validation**: Run unit tests for `utils/kg_builder/tests` and `utils/graph_loader/tests`. Run opt-in Docker integration tests for Neo4j and Gremlin on a small fixture first, then on ATT&CK if runtime is acceptable. Confirm docs consistently describe canonical artifacts as source of truth, semantic validation as a pre-load gate, runtime databases as reproducible projections, and verify commands as no-load checks.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: ATT&CK Runtime Graph Loader (12/12) Complete: Documented the runtime graph loading, semantic validation, health, and verification workflow.

### 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Runtime graph load CLI | Adds `--dataset attack|capec|all` and `--graph neo4j|gremlin|all` for live database loading from built artifacts. | `main.py` |
| No-load graph commands | Adds `--graph health` for endpoint checks and `--dataset attack --graph verify` for no-load dataset/runtime verification. | `main.py`, `utils/graph_loader/verify.py` |
| Graph loader package | Runtime loading package separated from artifact building. | `utils/graph_loader/` |
| Dataset resolver | Resolves dataset names to source cards, canonical manifests, and backend exports. | `utils/graph_loader/registry.py` |
| Loader config | Holds default endpoints, batch sizes, dataset paths, and environment override handling. | `utils/graph_loader/config.py` |
| Preflight checks | Validates built canonical artifacts, manifest hashes, source cards, backend export existence, semantic validation, and endpoint readiness. | `utils/graph_loader/preflight.py` |
| Semantic validation package | Validates node labels, edge types, allowed source-target pairs, required properties, and domain references before loading. | `utils/graph_loader/validation/` |
| Semantic rule definitions | Encodes legal ATT&CK graph patterns such as `Group USES Technique`, `Mitigation MITIGATES Technique`, and `Tactic HAS_TECHNIQUE Technique`. | `utils/graph_loader/validation/rules.py` |
| Common graph contract | Backend-independent interface used by the loader, verifier, and future agents. | `utils/graph_loader/stores/base.py` |
| Graph store models | Runtime load target, load result, count summary, semantic validation result, and adapter metadata structures. | `utils/graph_loader/models.py`, `utils/graph_loader/results.py` |
| Neo4j adapter | Connects over Bolt, applies constraints, upserts ATT&CK nodes and relationships, and verifies counts. | `utils/graph_loader/stores/neo4j.py` |
| Gremlin adapter | Connects over Gremlin WebSocket, upserts vertices and edges, and verifies counts. | `utils/graph_loader/stores/gremlin.py` |
| Backend factory | Maps `neo4j`, `gremlin`, and `all` to concrete GraphStore implementations. | `utils/graph_loader/stores/factory.py` |
| Dataset load orchestrator | Coordinates preflight, semantic validation, store selection, batched loading, post-load validation, and result reporting. | `utils/graph_loader/loader.py`, `utils/graph_loader/main.py` |
| Runtime load manifests | Records successful backend loads separately from canonical build manifests. | `data/graphs/attack/runtime/neo4j/load-manifest.json`, `data/graphs/attack/runtime/gremlin/load-manifest.json` |
| Verification utilities | Compares live graph counts, representative labels, relationship types, runtime manifests, and canonical manifest expectations without loading. | `utils/graph_loader/verify.py` |
| Semantic validation tests | Tests legal and illegal ATT&CK graph patterns before any database adapter is called. | `utils/graph_loader/tests/test_semantic_validation.py` |
| Neo4j query tests | Unit tests for generated Cypher, idempotent upsert behavior, and count verification. | `utils/graph_loader/tests/test_neo4j_store.py` |
| Gremlin traversal tests | Unit tests for generated traversals, idempotent upsert behavior, and count verification. | `utils/graph_loader/tests/test_gremlin_store.py` |
| Registry and preflight tests | Tests that missing, stale, or semantically invalid built artifacts fail before live loading starts. | `utils/graph_loader/tests/test_registry_resolution.py`, `utils/graph_loader/tests/test_preflight.py` |
| Verify command tests | Tests for graph health, no-load dataset verification, stale manifests, count mismatch, and backend reachability failure. | `utils/graph_loader/tests/test_verify_commands.py` |
| CLI regression tests | Tests for `attack/neo4j`, `attack/gremlin`, `attack/all`, `attack/verify`, `health`, missing dataset artifacts, and not-yet-built CAPEC. | `utils/graph_loader/tests/test_cli_load.py` |
| Orchestration tests | Tests that `--graph all` loads both backends through the same contract and reports independent outcomes. | `utils/graph_loader/tests/test_loader_orchestration.py` |
| Optional Docker integration tests | Opt-in tests that load a small fixture and ATT&CK into running Neo4j and Gremlin services, then run `--graph verify`. | `utils/graph_loader/tests/test_integration_neo4j.py`, `utils/graph_loader/tests/test_integration_gremlin.py` |
| Dependency updates | Adds live graph client libraries when implementation begins. | `pyproject.toml`, `uv.lock` |
| User documentation | Documents download/build/docker/load/health/verify command sequence and the distinction between canonical builds, semantic validation, and live backend projections. | `README.md`, `docs/goals.md`, `docs/structure.md` |
| Future agent query layer note | Reserves `GraphQueryEngine` as a later layer above `GraphStore` for domain-level agent queries. | Future plan under `docs/plans/` |
| Changelog entry | Records the runtime graph loader implementation once completed. | `docs/changelog.jsonl` |
