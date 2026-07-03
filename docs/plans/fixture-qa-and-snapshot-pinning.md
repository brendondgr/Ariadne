# Plan: Fixture-QA Harness + Data Snapshot Pinning

## 1. Introduction

The literature on federated knowledge-graph systems (BRON, GraphKer) shows that most
downstream failures originate in the **fixtures**, not the agents: silent object drops or
dangling edges during ingestion poison every answer that follows, and no prompting fixes a
graph that was loaded wrong. Two safeguards close that gap for Ariadne. First, a
**fixture-QA harness** that independently reconciles the raw MITRE sources against the
canonical build manifest against the *live* Neo4j/Gremlin graphs — counts, referential
integrity, and revoked/deprecated handling. Second, a **pinned data snapshot**: sha256
checksums of the exact ATT&CK v19.0 STIX bundle and CAPEC v3.9 XML, recorded so every build
and every gold answer is reproducible and auditable.

This plan first proves the graphs currently running are correct (already verified live during
planning — all counts reconcile, zero dangling edges, zero revoked/deprecated leakage), then
codifies those checks as a repeatable harness with a CLI entry point and tests, and finally
pins the snapshot by recording source checksums in metadata, `versions.json`, and the source
cards.

### Verified live state (planning-time evidence)

| Check | ATT&CK (Neo4j) | CAPEC (Gremlin) |
|-------|----------------|------------------|
| Total nodes raw→DB | 2611 = 2611 ✓ | 4888 (AttackPattern 615=615, Category 78, View 13) ✓ |
| Total edges (manifest=live) | 21739 ✓ | 6917 ✓ |
| Dangling edges (live) | 0 ✓ | 0 (all endpoints have `id`) ✓ |
| Revoked/deprecated | excluded: 157 revoked + 251 deprecated, 0 leakage ✓ | loaded (56 Deprecated + 1 Obsolete) with filterable `Status` prop ✓ |
| Edge-label casing | n/a | live is `CHILD_OF` etc. (store normalizes CamelCase→SCREAMING_SNAKE); counts identical ✓ |

## 2. Gaps & Unanswered Questions

- **Independent recount source.** The existing `--graph verify` compares live DB against the
  *build manifest* only (DB == manifest), never against the raw source. *Assumption*: the
  harness recomputes counts directly from the raw STIX/XML with its own minimal logic (not by
  calling the build path) so the reconciliation is genuinely independent (raw == manifest == live).
- **CAPEC deprecated/obsolete policy.** ATT&CK excludes revoked+deprecated; CAPEC loads the
  full catalog including 56 Deprecated + 1 Obsolete patterns. *Assumption*: this is intentional
  (`build_scope: full_catalog`); the harness records the loaded-deprecated count and asserts a
  filterable `Status` property exists, and the CAPEC source card documents "filter on `Status`".
  This is the report's "load them, but tell specialists to filter" option — no data change needed.
- **Checksum backfill for existing raw files.** The two raw files already on disk were
  downloaded without checksums. *Assumption*: compute and backfill their sha256 in place
  (no re-download); future `--download` runs record checksums automatically.
- **Edge-count raw reconciliation.** Not every relationship type is cheaply derivable from raw
  independent of the build. *Assumption*: reconcile total edges + per-type counts manifest↔live,
  and raw-derive only the structurally cheap ones (e.g. HAS_SUBTECHNIQUE == subtechnique count,
  CAPEC ChildOf). Node counts get full three-way raw↔manifest↔live reconciliation.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Independent raw recount module
- **Locations**: new `utils/graph_loader/fixture_qa/raw_counts.py` (functions
  `attack_raw_counts(BuildConfig)`, `capec_raw_counts(BuildConfig)` returning node-label counts,
  excluded revoked/deprecated counts, and cheap edge anchors). Locates raw files via
  `BuildConfig.from_data_dir().paths()`.
- **Rationale**: A recount that does not reuse the build's `AttackPreprocessor` is the only way
  to catch a systematic build bug — if the harness called the same code that built the graph, a
  drop bug would be invisible to both.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated,
  commit changes to GitHub stating: Fixture-QA & Snapshot (1/5) Complete: Independent raw recount
  for ATT&CK STIX and CAPEC XML.

### Step 2: Referential-integrity store methods
- **Locations**: `utils/graph_loader/stores/base.py` (new `referential_integrity()` default +
  abstract count helper), `stores/neo4j.py` and `stores/gremlin.py` (backend queries:
  Neo4j dangling `MATCH (a)-[r]->(b) WHERE a.id IS NULL OR b.id IS NULL`; Gremlin vertices/edges
  missing `id`), `stores/memory.py` (in-memory equivalent for tests).
- **Rationale**: The harness must query the *live* graph for dangling edges; the store layer is
  the sanctioned place for backend-specific traversal so the harness stays backend-agnostic.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated,
  commit changes to GitHub stating: Fixture-QA & Snapshot (2/5) Complete: Live referential-integrity
  queries on Neo4j and Gremlin stores.

### Step 3: Fixture-QA harness + CLI
- **Locations**: new `utils/graph_loader/fixture_qa/harness.py` (`run_fixture_qa(dataset, config)`
  → three-way count reconciliation, referential integrity, revoked/deprecated assertions; writes
  `data/graphs/<ds>/runtime/fixture-qa-report.json`; raises on failure). Wire CLI: add
  `"fixture-qa"` to `GRAPH_ACTIONS` in `utils/graph_loader/config.py`, dispatch in
  `utils/graph_loader/main.py`, and document in `main.py` help text.
- **Rationale**: One command (`uv run main.py --graph fixture-qa --dataset attack`) turns the
  ad-hoc planning checks into a repeatable, auditable gate producing a report artifact.
- **Action**: Undergo the verification/tests/validation process for this phase (run live against
  both running graphs). Once validated, commit changes to GitHub stating: Fixture-QA & Snapshot
  (3/5) Complete: Fixture-QA harness with CLI and report artifact, green against live graphs.

### Step 4: Pin the data snapshot (checksums)
- **Locations**: `utils/download/downloader.py` (`write_metadata` records `sha256` + `size_bytes`;
  `write_versions_json` records per-source checksums; new `pin`/backfill helper to checksum files
  already on disk without re-download). Update `data/raw/*/metadata.json` and `data/versions.json`
  in place. Surface the checksum in `data/source_cards/*.json` `provenance` (via the source-card
  builder in `utils/kg_builder/`). Add a build-time assertion that the raw file's sha256 matches
  the pinned value.
- **Rationale**: Gold answers (`REF:<id>`) are computed against a specific data state; a pinned
  checksum makes every result reproducible and blocks silent upstream drift (v19.1) from shifting
  evaluation scores.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated,
  commit changes to GitHub stating: Fixture-QA & Snapshot (4/5) Complete: sha256-pinned ATT&CK
  v19.0 and CAPEC v3.9 snapshot in metadata, versions.json, and source cards.

### Step 5: Docs, full regression, merge
- **Locations**: `docs/structure.md` (harness + pinning described), `README.md` roadmap row,
  `docs/changelog.jsonl` (entry per step). Run full pytest suites + live fixture-qa; merge the
  working branch into `main`.
- **Rationale**: The canonical docs must reflect the new gate and the reproducibility guarantee;
  merge only when everything is 100% green.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated,
  commit changes to GitHub stating: Fixture-QA & Snapshot (5/5) Complete: docs, full regression,
  merged to main. (Commit only — not pushed, per session directive.)

## 4. Deliverables

| Deliverable | Description | Location |
| --- | --- | --- |
| Raw recount | Independent count of raw ATT&CK/CAPEC by node type + excluded counts | `utils/graph_loader/fixture_qa/raw_counts.py` |
| Referential integrity | Live dangling-edge queries per backend | `utils/graph_loader/stores/{base,neo4j,gremlin,memory}.py` |
| Fixture-QA harness | 3-way reconciliation + integrity + revoked/deprecated, report artifact | `utils/graph_loader/fixture_qa/harness.py` |
| CLI entry | `--graph fixture-qa --dataset <ds>` | `utils/graph_loader/{config,main}.py`, `main.py` |
| Snapshot pinning | sha256 in metadata, versions.json, source-card provenance + build assertion | `utils/download/downloader.py`, `utils/kg_builder/`, `data/versions.json` |
| Harness tests | pytest over recount, integrity (memory store), reconciliation | `utils/graph_loader/fixture_qa/tests/` |
| Pinning tests | pytest over checksum record/verify/backfill | `utils/download/tests/` or `utils/graph_loader/tests/` |
