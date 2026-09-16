# Synapse graph transfer — a Synapse export is an Ariadne data directory

**Created:** 2026-09-16. **Mode:** direct on `main` in both repositories, explicit
`git add` only, commit per validated step, no push. **Scope guard:** Ariadne's
focus stays the cybersecurity graphs for at least the next month; every change
here is additive, defaults for `attack` and `capec` are byte-identical, and the
generalised-engine work is a later plan.

## 1. Introduction

Synapse (`~/Agents/Synapse`) builds typed knowledge graphs from document corpora
and writes them in the same canonical contract Ariadne's loader reads: `nodes.jsonl`,
`relationships.jsonl`, `schema.json`, `manifest.json`, plus Neo4j and Gremlin
exports. Record shapes match field for field. What stops a Synapse graph from
being loaded and queried in Ariadne today is not format but registration: a
missing `dataset` key in the schema, a card in a different shape, manifest paths
rooted at Synapse's project tree, and four places in Ariadne where dataset names
are literals (the loader's supported set, the specialist constructor, the API's
dataset types, and the web client's backend inference).

The approach is a one-way export on the Synapse side and card-driven discovery on
the Ariadne side. Synapse gains an `export-ariadne` command that writes a
directory laid out exactly like Ariadne's `data/` (`graphs/<dataset>/canonical`,
`graphs/<dataset>/exports`, `source_cards/<dataset>.json`) with paths rewritten
relative to that root. Ariadne learns to accept any dataset that has a source
card, dispatch its specialist on the card's `runtime_backend`, validate its load
from the schema it ships, and carry the backend in the SSE stream so the web
client stops guessing. The plan closes with a real transfer of one Synapse graph
into a profile-gated Neo4j container, one question answered through the
pipeline, and the deletion of everything the test created.

## 2. Gaps & Unanswered Questions

- **Dataset name.** Synapse graph ids can carry characters Ariadne's paths and
  env override (`ARIADNE_ENDPOINT_<DATASET>`) do not expect. *Assumption*: the
  exporter derives the dataset name by lower-casing the graph id and replacing
  every character outside `[a-z0-9_-]` with `-`; `--dataset` overrides it.
- **Backend.** *Assumption*: Neo4j. The card declares `runtime_backend: neo4j`;
  Gremlin exports are still written so the layout is complete, but only the
  Neo4j load path is exercised by this plan.
- **Synapse's canonical files stay byte-identical.** Adding `dataset` to
  Synapse's own `schema.json` would change canonical hashes that Synapse's
  research record pins. *Decision*: the exporter writes an augmented **copy**
  of the schema into the export directory; Synapse's tree is untouched.
- **Cross-source joins.** A Synapse graph has no MITRE identifiers. *Assumption*:
  no join key is declared; the graph answers as a standalone source. Anchors
  resolve by name only, since Synapse ids are opaque hashes.
- **Evidence quotes.** Synapse's per-triple quotes live in nested properties
  that Ariadne stores in `properties_json`. They survive the load but are not
  surfaced as citations by Ariadne's composer. Out of scope here.
- **Graph explorer tab.** `web/components/graph/GraphSecondaryNav.tsx` lists
  ATT&CK and CAPEC tabs by literal. The explorer stays MITRE-only in this plan;
  the ask path is what becomes generic. *Human intervention is needed* if the
  explorer should also list imported graphs.
- **Test container lifetime.** *Assumption*: the external Neo4j service is
  profile-gated and not started by `--docker start`; the end-to-end step stops
  it and removes its volume directory when done.

## 3. Hierarchical Step-by-Step Instructions

#### Step 1: Synapse `export-ariadne` command
- **Locations (Synapse):** new `utils/synapse_agent/exporters/ariadne.py`
  (`export_ariadne_layout`, `ariadne_schema`, `ariadne_source_card`,
  `dataset_name_for`); new `utils/synapse_agent/cli/export_ariadne.py`
  (`run_export_ariadne`); `main.py` subparser + dispatch; new
  `utils/tests/unit/test_export_ariadne.py`; `docs/workflow.md` command row.
- **Rationale:** the export must produce, from canonical artifacts alone, a
  directory Ariadne can point `ARIADNE_DATA_DIR` at or copy into `data/`. The
  schema copy gains `dataset`, per-label `node_properties` in Ariadne's
  type-and-example shape, and `relationship_endpoints` derived from
  `allowed_relationships` so Ariadne's schema-derived validator has edge
  patterns. The manifest is rewritten with paths relative to the export root.
  The card is Ariadne's `SourceCard` field set with glosses mapped to
  `entity_descriptions` and safety carrying `allowed_edge_patterns`. Existing
  exporters are reused for the backend files.
- **Action:** run the new unit test and the existing exporter tests. Once
  validated, commit in Synapse stating: Synapse Graph Transfer (1/6) Complete:
  export-ariadne writes an Ariadne-shaped data directory from canonical
  artifacts without touching Synapse's own files.

#### Step 2: Ariadne loader accepts card-backed datasets
- **Locations (Ariadne):** `utils/graph_loader/config.py`
  (`is_supported_dataset`, `discover_card_datasets`); `utils/graph_loader/registry.py`
  `resolve_dataset`; `utils/graph_loader/validation/semantic.py` generic
  schema-derived branch for datasets outside the three MITRE rule sets;
  `main.py` `--dataset` accepts any name (choices become a validated string);
  new `utils/graph_loader/tests/test_external_dataset.py`.
- **Rationale:** the frozen set is the loader's only reason to reject a dataset
  whose card and canonical files are present. The identity branch already
  validates from the shipped schema; making that the fallback for unknown
  datasets keeps the MITRE branches untouched and lets the external load fail
  loudly on real defects (unknown label, dangling edge) rather than on the name.
- **Action:** run `utils/graph_loader/tests/` and `utils/kg_builder/tests/`.
  Once validated, commit stating: Synapse Graph Transfer (2/6) Complete: the
  loader resolves and validates any dataset that ships a source card.

#### Step 3: Ariadne runtime dispatches on the card
- **Locations (Ariadne):** `utils/specialists/__init__.py` `build_specialist`
  (fallback on `card.runtime_backend`); `utils/specialists/resolve/resolver.py`
  (unknown datasets keep the empty-seed path, asserted by test); new
  `utils/specialists/tests/test_external_dataset_specialist.py` using a
  temporary card; `utils/planner/tests/` case that `load_source_cards` accepts
  the exported card and `assert_card_consistency` passes on it.
- **Rationale:** the specialist constructor is the last name-keyed dispatch on
  the query path. The Cypher specialist reads labels, relationships and id
  schemes from its card, which is why the merged counterfactual needed no new
  specialist; an external Neo4j card is the same situation.
- **Action:** run `utils/specialists/tests/` and `utils/planner/tests/`. Once
  validated, commit stating: Synapse Graph Transfer (3/6) Complete: a card's
  runtime_backend selects its specialist; no dataset name is consulted.

#### Step 4: API and web stop assuming two names
- **Locations (Ariadne):** `api/models.py` (`GraphDataset`,
  `AdminActionRequest.dataset` widen to validated strings); `api/services/graph.py`
  and `api/services/query.py` backend maps read from source cards with the old
  literals as fallback; `utils/orchestration/agents/specialists/nodes.py` both
  `specialist-start` emissions gain `backend`; `utils/orchestration/tests/test_event_parity.py`
  key set; `web/lib/runMachine.ts` `backendOf` and the `specialist-start` case
  read `backend` from the payload before falling back; `web/lib/types.ts`
  event type; `web/lib/__tests__/runMachine.test.ts`; `api/tests/`.
- **Rationale:** the web client infers the lane from `source === "capec"`, which
  puts any third source in the Neo4j lane by accident. Carrying the backend in
  the event is the smallest change that makes the lane correct for every source
  and leaves ATT&CK and CAPEC exactly where they were.
- **Action:** run `api/tests/`, `utils/orchestration/tests/`, `npm test`,
  `npm run lint`, `npm run build`. Once validated, commit stating: Synapse Graph
  Transfer (4/6) Complete: dataset names are validated strings in the API and
  the SSE stream carries each lane's backend.

#### Step 5: Infrastructure and documentation
- **Locations (Ariadne):** `docker/docker-compose.yml` profile-gated
  `neo4j-external` service (ports `NEO4J_EXTERNAL_HTTP_PORT`/`NEO4J_EXTERNAL_BOLT_PORT`,
  volume `docker/neo4j-external/data`); `.gitignore`; `.env.example` section
  for the external store and the `ARIADNE_ENDPOINT_<DATASET>` override;
  `docs/source_cards.md` new section "Importing an external canonical graph";
  `docs/commands.md` graph-databases section.
- **Rationale:** an imported graph needs its own store, and the operator needs
  one documented path from a Synapse export to a live source. The profile keeps
  the service out of the ordinary stack.
- **Action:** `docker compose config` validates; `make check-docs`. Once
  validated, commit stating: Synapse Graph Transfer (5/6) Complete: a
  profile-gated external Neo4j and the documented import path.

#### Step 6: End-to-end transfer, regression gate, and cleanup
- **Locations:** Synapse `uv run main.py export-ariadne` into the scratchpad;
  copy into Ariadne `data/graphs/<dataset>` and `data/source_cards/<dataset>.json`;
  `docker compose --profile external up -d neo4j-external`; `main.py --dataset
  <dataset> --graph neo4j` then `--graph verify`; one question through
  `main.py --query` and the API stream; the deterministic recorded-answer
  regression over both banks; then stop the container, delete its volume
  directory, the copied data, and the scratch export.
- **Rationale:** the plan's claim is that a Synapse graph loads and answers
  without a code change per graph. That is verified by doing it once, and the
  regression diff is what proves ATT&CK and CAPEC did not move.
- **Action:** the two regression counts (identifiers, bytes) are 60/60 on both
  banks; `pytest utils/ api/` matches the baseline; the test data and container
  are gone. Once validated, commit stating: Synapse Graph Transfer (6/6)
  Complete: one Synapse graph loaded, answered a question, and was removed; both
  MITRE banks byte-identical.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Ariadne exporter | Writes an Ariadne data-directory layout from canonical artifacts | Synapse `utils/synapse_agent/exporters/ariadne.py` |
| `export-ariadne` CLI | Command wiring and argument parsing | Synapse `utils/synapse_agent/cli/export_ariadne.py`, `main.py` |
| Exporter unit tests | Small in-memory graph exported to `tmp_path`, layout and card asserted | Synapse `utils/tests/unit/test_export_ariadne.py` |
| Card-backed dataset resolution | Loader accepts any dataset with a card; schema-derived validation | Ariadne `utils/graph_loader/config.py`, `registry.py`, `validation/semantic.py` |
| Loader tests | External dataset resolves, validates, and rejects a bad label | Ariadne `utils/graph_loader/tests/test_external_dataset.py` |
| Specialist by backend | Constructor falls back to `runtime_backend` | Ariadne `utils/specialists/__init__.py` |
| Specialist tests | Temporary card builds a Cypher specialist; resolver yields no seeds | Ariadne `utils/specialists/tests/test_external_dataset_specialist.py` |
| API dataset widening | Validated strings and card-driven backend maps | Ariadne `api/models.py`, `api/services/graph.py`, `api/services/query.py` |
| SSE backend field | `specialist-start` carries `backend`; parity test updated | Ariadne `utils/orchestration/agents/specialists/nodes.py`, tests |
| Web lane by backend | Client reads backend from the event | Ariadne `web/lib/runMachine.ts`, `web/lib/__tests__/runMachine.test.ts` |
| External Neo4j service | Profile-gated container and env entries | Ariadne `docker/docker-compose.yml`, `.env.example`, `.gitignore` |
| Import documentation | Operator path from Synapse export to live source | Ariadne `docs/source_cards.md`, `docs/commands.md` |
| Transfer verification | Recorded outcome of the one-graph transfer and the regression diff | Ariadne `docs/changelog.jsonl` (step 6 entry) |
