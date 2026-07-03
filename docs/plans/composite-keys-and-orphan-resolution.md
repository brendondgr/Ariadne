# Composite Join-Keys & Orphan Resolution — Implementation Plan

## 1. Introduction

This plan implements Steps 3 & 4 of the Ariadne fixture-layer roadmap (source: `~/Documents/Plans/Ariadne/2.ariadne-steps-3-4-implementation-plan.md`): **composite `(attack_id, stix_type)` join-key enforcement** so an ATT&CK ID can never resolve to the wrong object type, and **orphan/island resolution** so every disconnected node is correctly connected, correctly filtered, or explicitly declared unreachable. Everything is deterministic and LLM-free — loader corrections plus fixture-QA checks over the pinned ATT&CK v19.0 / CAPEC v3.9 snapshot.

Pre-planning verification against the pinned bundle established the ground truth: 224 raw `attack_id` collisions (all `attack-pattern` × `course-of-action`, all from deprecated pre-2019 mitigations, which the build already excludes at load, so the loaded-graph collision set is expected to be **empty**); the v19 detection remodel is real (**all 109** data components have `x_mitre_data_source_ref = null`, all 38 data sources are deprecated, and data components connect only via `x-mitre-analytic.x_mitre_log_source_references[].x_mitre_data_component_ref`); the current build loads **no Analytic nodes** and no matrix→tactic edges, so the Matrix (1) and all DataComponents (106) are orphans today; CAPEC-555 maps to exactly T1021 / T1114.002 / T1133 in the raw XML (272 ATT&CK taxonomy mappings total). Technique→Tactic (`kill_chain_phases`) is already wired (`HAS_TECHNIQUE`, 872 edges).

The approach: wire the missing v19 embedded references in `utils/kg_builder` (Matrix→Tactic; DetectionStrategy→Analytic→DataComponent, which requires loading Analytics as first-class nodes), add graph-wide identity constraints in the generated schema, and extend the existing `fixture-qa` harness (`utils/graph_loader/fixture_qa/`) with composite-key, orphan, and cross-database resolution checks gated by checked-in expected-value fixtures.

## 2. Gaps & Unanswered Questions

- **`stix_id` property**: the plan document asks for a `stix_id` property; the canonical node `id` *is* the STIX UUID and is already merged on and constrained per-label. *Assumption*: use `id` as the stix-id; add the graph-wide `AttackObject.id` uniqueness constraint rather than duplicating the value into a second property.
- **Cause-A policy**: the build already excludes revoked/deprecated at load and records excluded counts (manifest + fixture-qa). *Assumption*: keep **exclude-at-load** (MITRE's recommended default); record it explicitly in the source-card overlay. No `revoked-by` edges are kept (no Q&A item needs them yet).
- **DataComponent wiring mechanism**: v19 populates the analytic path, not `x_mitre_data_source_ref`. *Assumption*: load `x-mitre-analytic` as a new `Analytic` label (1758 live objects — matches MITRE's published v19 counts) and wire `DetectionStrategy -HAS_ANALYTIC-> Analytic -MONITORS-> DataComponent`, plus `Matrix -HAS_TACTIC-> Tactic`. Directions recorded in the source card.
- **Composite constraint edition support**: stack runs Neo4j 5.26; composite property-uniqueness constraints are supported in Community for 5.x. Verified live in Step 2; fallback is per-label `attack_id` uniqueness.
- **Residual live orphans** (e.g. a live Group whose only relationships pointed at deprecated objects): unknown until measured. *Assumption*: measure in Step 4; any legitimately isolated live nodes become a small, explicit allow-list in the expected fixture and are declared in the source card. No human intervention expected unless the allow-list turns out large or surprising.
- **Session override**: work is committed at every step but **not pushed** (session directive overrides the global push rule).

## 3. Hierarchical Step-by-Step Instructions

#### Step 1: Wire Cause-B embedded references (Analytic nodes + 3 edge kinds)
- **Locations**: `utils/kg_builder/preprocess/attack.py` (`STIX_TYPE_TO_LABEL`-equivalent map at :23-34, node pass, new second-pass edge derivation next to the `kill_chain_phases` logic at :223-249); `utils/kg_builder/schema/attack.py` (node labels, relationship types, generated constraints/schema lines); `utils/graph_loader/fixture_qa/raw_counts.py` (count `x-mitre-analytic`); `utils/kg_builder/tests/test_attack_preprocess.py` (new cases).
- **Rationale**: The Matrix and all 106 DataComponents are live orphans because their connections live in embedded references the loader never reads (`tactic_refs`, `x_mitre_analytic_refs`, `x_mitre_log_source_references`). Analytics must become nodes for the v19 detection chain to exist at all. This must land before any orphan check can pass.
- **Expected numbers**: +1758 `Analytic` nodes; `HAS_TACTIC` = 15; every live DataComponent reachable via `MONITORS`.
- **Action**: Rebuild (`uv run main.py --build attack`), assert manifest counts; run kg_builder + graph_loader test suites. Once validated, commit (no push): *Composite Keys & Orphans (1/6) Complete: wired Matrix→Tactic and DetectionStrategy→Analytic→DataComponent embedded references with Analytic as a first-class node.*

#### Step 2: Graph-wide identity constraints
- **Locations**: `utils/kg_builder/schema/attack.py` `constraints_cypher_lines()` (add `attack_stix_id_unique` on `AttackObject.id` and `attack_id_type_unique` on `(attack_id, stix_type)`); `utils/kg_builder/schema/capec.py` (parity: `CapecObject.id` uniqueness); `utils/graph_loader/stores/neo4j.py` (+`list_constraint_names()`), `stores/base.py`/`stores/memory.py` (contract + memory impl); tests in `utils/graph_loader/tests/`.
- **Rationale**: Constraints make duplicate identities impossible at the database layer; the composite constraint permits the legitimate cross-type case while forbidding true duplicates. `list_constraint_names()` lets the harness assert constraints exist (a missing constraint is a silent regression).
- **Action**: Rebuild artifacts, reload Neo4j + Gremlin (`--graph all` per dataset), confirm `SHOW CONSTRAINTS` lists the new names live. Run store test suites. Once validated, commit (no push): *Composite Keys & Orphans (2/6) Complete: added AttackObject stix-id and (attack_id, stix_type) composite uniqueness constraints plus constraint introspection.*

#### Step 3: Composite-key fixture-QA checks + collision-set fixture
- **Locations**: new `utils/graph_loader/fixture_qa/composite_keys.py`; expected fixture `utils/graph_loader/fixture_qa/expected/attack_collisions.json` (generated, checked in); `utils/graph_loader/fixture_qa/harness.py` (wire checks); tests under `utils/graph_loader/fixture_qa/tests/`.
- **Rationale**: Encodes A.3/A.4 — raw-bundle collision enumeration (expect 224, all `attack-pattern`+`course-of-action`) cross-checked against the canonical artifacts (expect empty after exclude-at-load), existence of `attack_id`/`stix_type`/`id` on every node, and live constraint presence. Exact-match against a checked-in fixture makes drift loud.
- **Action**: `uv run main.py --graph fixture-qa --dataset attack` passes live; fixture_qa tests green. Once validated, commit (no push): *Composite Keys & Orphans (3/6) Complete: collision-set fixture + composite-key existence and constraint checks in fixture-qa.*

#### Step 4: Orphan detection & resolution checks (both graphs)
- **Locations**: new `utils/graph_loader/fixture_qa/orphans.py` (canonical-artifact orphan scan, dead/live split logic, named assertions); `GraphStore` contract + `stores/neo4j.py` / `stores/gremlin.py` / `stores/memory.py` (+`orphan_counts()` zero-degree scan by label); expected fixture `fixture_qa/expected/{attack,capec}_orphans.json` (allow-list, possibly empty); `harness.py` wiring; tests.
- **Rationale**: Encodes B.2–B.7 and the Gremlin side of Part C: `bug_orphans == 0` or exactly the documented allow-list; `dead_orphans == 0` (exclude-at-load predicts zero); named assertions "Matrix connects to exactly 15 Tactics" and "every live DataComponent has ≥1 edge"; CAPEC stranded-vertex scan, `ChildOf` endpoint-label check, and hierarchy cycle check over canonical artifacts.
- **Action**: Run fixture-qa live for both datasets; investigate any residual live orphans and either fix the loader or record them in the allow-list with a reason. Suites green. Once validated, commit (no push): *Composite Keys & Orphans (4/6) Complete: orphan scans, dead/live split, and named Matrix/DataComponent regressions in fixture-qa for both graphs.*

#### Step 5: Cross-database join-key resolution (CAPEC → ATT&CK)
- **Locations**: new `utils/graph_loader/fixture_qa/cross_db.py`; expected fixture `fixture_qa/expected/capec_attack_resolution.json` (resolution rate baseline + CAPEC-555 case); `harness.py` (runs for `capec` when attack canonical artifacts exist); tests.
- **Rationale**: This is where the composite key earns its keep: every CAPEC `ATTACK` taxonomy mapping must resolve under the pair `(attack_id, stix_type='attack-pattern')`, never by digits alone. Baseline the resolution rate (legitimate misses: revoked/non-Enterprise techniques) so a drop between builds is a drift alarm. The named CAPEC-555 → {T1021, T1114.002, T1133} assertion catches mapping-direction bugs.
- **Action**: fixture-qa capec passes live with the new checks; tests green. Once validated, commit (no push): *Composite Keys & Orphans (5/6) Complete: CAPEC→ATT&CK composite-key resolution check with rate baseline and CAPEC-555 named regression.*

#### Step 6: Source cards, docs, full regression, merge
- **Locations**: `utils/kg_builder/registry.py` (auto-generated base gains an `identity` block: join-key contract fields, measured collision set, orphan allow-list refs); `data/source_cards/overlays/attack.overlay.json` + `capec.overlay.json` (policy: "joins must match on both `attack_id` and `stix_type`", Cause-A exclude-at-load statement, new entity/relationship descriptions for Analytic / HAS_TACTIC / HAS_ANALYTIC / MONITORS); `docs/structure.md`; `docs/changelog.jsonl` (every step already appends); README roadmap if applicable.
- **Rationale**: The source card is the contract the planner/synthesis agents read; the identity policy and declared-unreachable/allow-list live there. Docs must reflect the new labels, edges, and checks before merging.
- **Action**: Full Python regression (`utils/` + `api/` pytest), rebuild + reload + fixture-qa both datasets end-to-end, then merge the worktree branch into `main` (commit, no push): *Composite Keys & Orphans (6/6) Complete: source-card identity contract + docs + full regression, merged to main.*

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Analytic node + embedded-ref edges | Load `x-mitre-analytic`; derive `HAS_TACTIC`, `HAS_ANALYTIC`, `MONITORS` | `utils/kg_builder/preprocess/attack.py`, `utils/kg_builder/schema/attack.py` |
| Identity constraints | `AttackObject.id` unique + `(attack_id, stix_type)` composite; CAPEC id parity | `utils/kg_builder/schema/attack.py`, `schema/capec.py` |
| Constraint introspection | `list_constraint_names()` on the store contract | `utils/graph_loader/stores/{base,neo4j,memory}.py` |
| Composite-key checks | Raw vs canonical collision set, property existence, live constraints | `utils/graph_loader/fixture_qa/composite_keys.py` |
| Orphan checks | Zero-degree scan (canonical + live), dead/live split, named assertions | `utils/graph_loader/fixture_qa/orphans.py`, `stores/*.py` (`orphan_counts()`) |
| Cross-DB resolution check | CAPEC→ATT&CK pair resolution rate + CAPEC-555 regression | `utils/graph_loader/fixture_qa/cross_db.py` |
| Expected-value fixtures | Checked-in exact-match baselines | `utils/graph_loader/fixture_qa/expected/*.json` |
| Unit tests (small-subset) | Synthetic-fixture tests for every new module/store method | `utils/kg_builder/tests/`, `utils/graph_loader/fixture_qa/tests/`, `utils/graph_loader/tests/` |
| Source-card identity contract | Auto-gen `identity` block + hand-authored policy overlay | `utils/kg_builder/registry.py`, `data/source_cards/overlays/*.json` |
| Docs | Structure + changelog updates | `docs/structure.md`, `docs/changelog.jsonl` |
