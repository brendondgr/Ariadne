# Plan: Exclude Deprecated/Obsolete CAPEC Nodes at Canonical Build

## 1. Introduction

Analysts viewing the graph in the web workbench see many single-node "islands"
floating free of the main graph. Every one is a **retired CAPEC entry** — an
`AttackPattern`, `Category`, or `View` whose `Status` is `Deprecated` or
`Obsolete`. Today CAPEC uses a **load-and-tag** policy: the full catalog is
materialized into the canonical graph and retired entries are merely tagged with
a `Status` property, so they persist through the canonical files, the live
Gremlin fixture, and the graph view — with no edges, hence the islands. ATT&CK,
by contrast, already **excludes** deprecated/revoked objects at build.

This plan flips CAPEC to the same **exclude-at-load** policy: retired
`Deprecated`/`Obsolete` nodes (across all node types) are dropped during the
canonical build — the "universal form" conversion — so they never enter the
canonical dataset, the live database, the specialists, or the graph view.
Because CAPEC's load-and-tag behavior is a *documented, verified contract* (the
fixture-QA harness, source cards, golden evalset, manifests, and `docs/structure.md`
all assert it), the change ripples outward: every downstream contract that
encodes "CAPEC loads the full catalog" must be updated to "CAPEC excludes retired
entries" with freshly measured counts. Removing 57 retired `AttackPattern`s + 57
retired `Category`s also cascades: their exclusive child nodes (ExecutionStep,
Consequence, Mitigation, Skill) and their `MAPS_TO`/`EXPLOITS_WEAKNESS` edges
disappear too, so all new counts are **measured empirically after the rebuild**,
never assumed.

## 2. Gaps & Unanswered Questions

- **Removal point** — *Resolved by user*: at the canonical build (universal
  form), not a cosmetic view-only filter.
- **Scope of removal** — *Resolved by user*: `Deprecated` **and** `Obsolete`,
  across **all** node types (AttackPattern, Category, View).
- **Config toggle**: Should exclusion be gated on a config flag or unconditional?
  *Assumption*: reuse the existing `BuildConfig.filter_deprecated` flag (already
  governs ATT&CK) so CAPEC honors the same switch and tests can toggle it.
- **Stub nodes for cross-references**: A live pattern may relate to (or a
  view/category may list) a now-excluded retired id. *Assumption*: build a
  retired-id set first and skip creating stub nodes and edges that point at
  excluded entries — no dangling edges, no resurrected islands.
- **Live stack for golden suites**: The Ariadne Neo4j/Gremlin stack is not
  currently running, so `live`/`integration` golden suites will skip.
  *Assumption*: gate acceptance on the offline rebuild, fixture-QA raw/manifest
  reconciliation, and the full hermetic test suite; note live suites as skipped.
- **External references cited only by retired patterns**: these already fall
  under the existing "uncited ExternalReference" orphan allow-list; the
  regenerated allow-list (Step 3) absorbs any change. No special handling.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Exclude retired CAPEC entries in the materializer + rebuild
- **Locations**:
  - `utils/kg_builder/preprocess/capec_graph.py`, `materialize_capec_graph()` —
    accept a `filter_deprecated: bool` argument; compute a `retired_ids` set from
    `checkpoint.attack_patterns`/`categories`/`views` where `Status ∈ {Deprecated,
    Obsolete}`; skip retired patterns/categories/views when emitting nodes, and
    guard `ensure_attack_pattern_node`, `MEMBER_OF`, `IN_VIEW`, related-pattern,
    and `MAPS_TO`/child edges so nothing is created for or points at a retired id.
  - `utils/kg_builder/preprocess/capec.py`, `build_capec_graph()` — pass
    `config.filter_deprecated` into `materialize_capec_graph()`.
  - `utils/kg_builder/models.py`, `CapecGraphMetadata` — record a
    `skipped_count`/`filtered_deprecated` tally for the manifest.
  - Define the retired-status set as a single module-level constant
    (`{"Deprecated", "Obsolete"}`) mirroring `fixture_qa`'s `_CAPEC_DEAD_STATUSES`.
- **Rationale**: This is the core "universal form" change — the one place where
  the canonical CAPEC graph is assembled. Excluding here removes the islands
  everywhere downstream (canonical files, exports, live DB, graph view,
  specialists) in one edit, and the retired-id guard prevents dangling edges.
- **Validation**: New/updated unit tests in
  `utils/kg_builder/tests/` (a CAPEC materializer test asserting retired
  patterns/categories/views and their exclusive children/edges are absent, and
  that a live pattern relating to a retired id emits no stub/edge). Then rebuild:
  `uv run main.py --build capec`; assert the canonical `nodes.jsonl` contains
  **zero** nodes with `Status ∈ {Deprecated, Obsolete}`, zero dangling edges
  (every edge endpoint resolves to an emitted node), and capture the new
  node/edge totals + `nodes_by_label` for the downstream steps.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit to GitHub (no push) stating: CAPEC Deprecated Exclusion
  (1/5) Complete: Excluded Deprecated/Obsolete CAPEC nodes at canonical build with
  retired-id edge guards and rebuilt the canonical graph.

### Step 2: Update fixture-QA contracts to exclude-at-load
- **Locations**:
  - `utils/graph_loader/fixture_qa/raw_counts.py` — CAPEC now excludes retired
    entries at load: subtract the retired count from the expected loaded total and
    update the human-readable note (from "loaded with their Status property" to
    "excluded at load, mirroring ATT&CK").
  - `utils/graph_loader/fixture_qa/orphans.py` — CAPEC dead-object policy changes
    from load-and-tag (known deprecated counts) to exclude-at-load (zero dead
    orphans), matching ATT&CK; update `is_dead_object`/policy wiring and comments.
  - `utils/graph_loader/fixture_qa/expected/capec_orphans.json` — regenerate the
    live orphan allow-list from the rebuilt canonical graph.
  - `utils/graph_loader/fixture_qa/expected/capec_attack_resolution.json` —
    regenerate the cross-DB CAPEC→ATT&CK resolution baseline (retired patterns'
    `MAPS_TO` mappings are gone).
  - Tests: `utils/graph_loader/fixture_qa/tests/test_orphans.py`,
    `test_raw_counts.py` — update expectations for the new CAPEC policy.
- **Rationale**: The fixture-QA harness is the trust gate that independently
  reconciles raw == manifest == live and explains every orphan. It currently
  *asserts* load-and-tag; leaving it unchanged would fail the build on the very
  behavior we intend. The regenerated expected files re-anchor the contract.
- **Validation**: `uv run python -m pytest utils/graph_loader/fixture_qa/tests/`
  green; if the live stack is up, `uv run main.py --graph fixture-qa --dataset
  capec` exits zero, else note it as skipped.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit to GitHub (no push) stating: CAPEC Deprecated Exclusion
  (2/5) Complete: Re-anchored the CAPEC fixture-QA contracts (raw counts, orphan
  policy, orphan + cross-DB baselines) to exclude-at-load.

### Step 3: Update the golden evalset gold bank + source card
- **Locations**:
  - `utils/specialists/evalset/gold_bank.py` — the gold bank materializes answers
    from the pinned raw snapshot and "mirrors the exclude-at-load policy"; extend
    that mirror so CAPEC retired entries are excluded from gold answers.
  - `utils/specialists/evalset/compile_banks.py` + committed artifacts under
    `utils/specialists/tests/golden/` (`gold_bank.json`, `capec_questions.json`) —
    regenerate via `uv run python -m utils.specialists.evalset.gold_bank` and
    `... .compile_banks`.
  - `data/source_cards/capec.json` (+ `overlays/`) — update the retired-entry
    policy statement and any node/relationship counts in the card. (Regenerated at
    build time where auto-generated; hand-authored policy edited in the overlay.)
  - Any evalset no-DB tests under `utils/specialists/evalset/tests/` whose
    expectations reference retired entries or counts.
- **Rationale**: The golden evalset is the answer-layer metric gate; its gold
  answers must reflect the graph the specialists now query. A stale gold bank
  would flag correct answers as wrong. The source card is what the planner reads,
  so its policy text and counts must state the new exclusion.
- **Validation**: `uv run python -m pytest utils/specialists/evalset/tests/`
  green; source-card consistency test
  (`utils/kg_builder/tests/test_source_card_consistency.py`) green. Live golden
  suites (`test_golden_capec.py`, `test_golden_synthesis.py`) noted as skipped if
  the stack is down.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit to GitHub (no push) stating: CAPEC Deprecated Exclusion
  (3/5) Complete: Regenerated the CAPEC gold bank/question banks and updated the
  source card to the exclude-at-load policy.

### Step 4: Documentation + changelog
- **Locations**:
  - `docs/structure.md` — update the CAPEC fixture-QA counts (currently "CAPEC
    4888 / 6984"), the orphan/island resolution paragraph (CAPEC load-and-tag →
    exclude-at-load), the cross-DB resolution baseline description, and the
    `utils/kg_builder`/`fixture_qa` narrative that says CAPEC loads the full
    catalog.
  - `docs/goals.md` — the Wk 4–5 "Build Gremlin CAPEC fixture" row note, if it
    references load-and-tag.
  - `docs/changelog.jsonl` — append one entry describing the policy change and why.
- **Rationale**: Canonical docs must describe the new policy before/at merge;
  `docs/structure.md` is the map agents read and currently states the old
  contract verbatim with the old counts.
- **Validation**: Grep `docs/` for stale "load-and-tag"/"full catalog"/old CAPEC
  counts and confirm none remain that describe current behavior incorrectly.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit to GitHub (no push) stating: CAPEC Deprecated Exclusion
  (4/5) Complete: Documented the CAPEC exclude-at-load policy and refreshed counts.

### Step 5: Full regression + merge to main
- **Locations**: whole repo — `uv run python -m pytest utils/ api/`; if web
  touched, `cd web && npm run build` (not expected — no web changes planned).
  Merge `worktree-capec-deprecated-exclude` into `main`.
- **Rationale**: A cross-cutting data-contract change must pass the full hermetic
  suite before landing; the established workflow merges the worktree into main
  (commit-only, not pushed) once everything is green.
- **Validation**: Full `utils/` + `api/` suite green (live/integration suites
  skipped when the stack is down, reported explicitly). Clean merge to main; spot
  re-run of the fixture-QA and kg_builder CAPEC tests on main.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit to GitHub (no push) stating: CAPEC Deprecated Exclusion
  (5/5) Complete: Full regression green; merged the CAPEC exclude-at-load change
  into main.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| CAPEC build-time exclusion | Drop Deprecated/Obsolete nodes + guard retired-id stubs/edges in the materializer | `utils/kg_builder/preprocess/capec_graph.py`, `preprocess/capec.py`, `models.py` |
| Materializer unit tests | Assert retired nodes/children/edges absent and no stubs to retired ids | `utils/kg_builder/tests/` |
| Rebuilt canonical CAPEC | Regenerated canonical/exports with zero retired nodes | `data/graphs/capec/` (gitignored; verified in-place) |
| Fixture-QA contract updates | Exclude-at-load raw counts + orphan policy | `utils/graph_loader/fixture_qa/raw_counts.py`, `orphans.py` |
| Regenerated fixture baselines | New orphan + cross-DB expected files | `utils/graph_loader/fixture_qa/expected/capec_orphans.json`, `capec_attack_resolution.json` |
| Fixture-QA tests | Updated CAPEC policy expectations | `utils/graph_loader/fixture_qa/tests/test_orphans.py`, `test_raw_counts.py` |
| Gold bank + question banks | Retired entries excluded from gold answers, banks recompiled | `utils/specialists/evalset/gold_bank.py`, `compile_banks.py`, `utils/specialists/tests/golden/*.json` |
| Source card update | Exclude-at-load policy + counts | `data/source_cards/capec.json`, `overlays/` |
| Docs + changelog | Policy + count refresh | `docs/structure.md`, `docs/goals.md`, `docs/changelog.jsonl` |
