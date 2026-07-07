# Repository Structure

Quick map of the Ariadne repo — where things live and what to open first.

## Start Here

| Need | Location |
|------|----------|
| Project overview & quick start | [`README.md`](../README.md) |
| Mission, architecture, data sources | [`docs/purpose.md`](purpose.md) |
| Roadmap, milestones, evaluation | [`docs/goals.md`](goals.md) |
| Change history | [`docs/changelog.jsonl`](changelog.jsonl) |
| Agent rules (read before coding) | [`docs/skills/global-project-rules/SKILL.md`](skills/global-project-rules/SKILL.md) |
| CLI entry point | [`main.py`](../main.py) |
| Web workbench launcher (API + UI) | [`app.py`](../app.py) |

## Top-Level Layout

```text
ariadne/
├── main.py              # CLI: --download, --build, --docker, --dataset, --graph
├── app.py               # Launch the web workbench: FastAPI api/ + Next.js web/
├── .env.example         # Central project config template (copy to .env)
├── pyproject.toml       # Python deps & scripts (uv)
├── api/                 # FastAPI service wrapping utils/ for the web UI
├── data/                # Datasets & graph artifacts (mostly gitignored)
├── docker/              # Neo4j + Gremlin Compose stack
├── docs/                # Project docs, skills, plans
├── logs/                # Sequential job logs (gitignored)
├── utils/               # Python utilities by domain
└── web/                 # Analyst workbench UI (Next.js App Router)
```

Agent tool folders (`.cursor/`, `.claude/`, `.agents/`) are **pointers only** — canonical instructions live under `docs/skills/`.

## Documentation (`docs/`)

| Path | Contents |
|------|----------|
| `purpose.md`, `goals.md` | Grant context, architecture, roadmap |
| `planner_agent.md` | Planning agent contract: discovery, gate, drafters, plan schema |
| `specialist_agents.md` | Query specialists: loop, four swap points, validation, evidence schema, federation, `--query` |
| `changelog.jsonl` | One JSON line per significant change |
| `structure.md` | This file |
| `skills/` | Canonical agent instructions (global rules, UI, planner, etc.) |
| `plans/` | Implementation plans for upcoming work |
| `proposal/` | Grant proposal and RFP |
| `references/` | External reference notes (ATT&CK, Neo4j) |

## Python Utilities (`utils/`)

| Package | Role |
|---------|------|
| `utils/download/` | MITRE ATT&CK & CAPEC dataset downloader; records a sha256 snapshot pin (`--pin` backfills existing files) |
| `utils/kg_builder/` | STIX → canonical graph artifacts → Neo4j/Gremlin exports; `snapshot.py` gates builds on the pinned raw-source checksum |
| `utils/graph_loader/` | Runtime load, verify, and health checks; `fixture_qa/` reconciles raw==manifest==live + referential integrity |
| `utils/infrastructure/` | Docker Compose lifecycle for local graph DBs |
| `utils/planner/` | Federated planning agent: live-source discovery, plan schema, deterministic self-eval gate, deterministic + OpenAI-compatible drafters, ReAct loop, evaluation |
| `utils/specialists/` | Source-specific query specialists: shared scaffold + four swap points (builder, validator, connector, normalizer), shared evidence schema, Cypher (ATT&CK/Neo4j) + Gremlin (CAPEC/Gremlin) specialists, federation router with join-derived dependent sequencing (producer's join values seed the consumer's `seed_ids`), committed concept vocabulary (`concepts.py`), and the single pipeline orchestrator (`pipeline.py`: `iter_pipeline`/`run_pipeline` — probe → plan → sequenced specialists → bundle → synthesize with per-stage timings and `PIPELINE_TIMEOUT_S`) shared by the CLI and the API |
| `utils/specialists/evalset/` | Step 5 golden evalset: `gold_bank.py` materializes gold answers from the pinned raw snapshot (independent of `kg_builder`, mirrors the exclude-at-load policy); `questions.py` + `compile_banks.py` compile 53 single-source questions into machine-checkable banks (SpecialistTask payload + ID-set assertions + expected builder template), including Step 7 campaign relationship coverage (`campaign_techniques` / `campaign_attribution` gold maps) and negative Asset boundary questions (Assets are ICS-only). Committed artifacts live in `utils/specialists/tests/golden/` (`gold_bank.json`, `attack_questions.json`, `capec_questions.json`, `VERIFICATION.md` — two-way independent AI re-derivation reports: 45/45 Step 5 + 8/8 Step 7, all agree). Wk 11–13 adds the component scorers here: `score_validity.py` (query validity VA — draft+gate each question hermetically, first-pass/post-retry rates), `score_execution.py` (execution accuracy EX — live result set vs the full snapshot gold each question now carries in an `ex_gold` block, exact-set-match + precision/recall with an error taxonomy), `score_safety.py` (bounded-execution adherence audit + adversarial gate probes), and `latency.py` (segmented, staged p50/p95/p99 with bootstrap CIs) |
| `utils/synthesis/` | Synthesis agent (Step 6): composes the final answer as structured claims-with-citations (`composer.py` deterministic always-on; `llm_composer.py` OpenAI-compatible behind `SYNTHESIS_LLM_*` env vars with hybrid fallback in `factory.py`), then an **always-deterministic** verification pass (`verifier.py`) checks every claim against the retrieved evidence records — uncited, unresolvable, or ungrounded claims are cut from the rendered prose and kept flagged; empty-but-ok sub-questions yield enforced abstentions ("the sources don't establish this") with the executed query as proof. `synthesize()` in `factory.py` is the single compose+verify entry point; `grounding.py` holds the shared backend-agnostic id normalization |
| `utils/evaluation/` | Component-level evaluation (Wk 11–13): `stats.py` shared percentile / Wilson-binomial / seeded-bootstrap CIs; `component_report.py` + `run_component_eval.py` assemble the planner ×4 and specialist ×4 scores into one citable report (`docs/evaluation/component-evaluation.{md,json}`, via `uv run main.py --component-eval`) |
| `utils/recovery.py` | Pipeline recovery primitives: backup/clean/restore of existing artifacts, failure classification (`stale_state` / `transient` / `needs_human`), bounded retry-with-backoff |
| `utils/yolo.py` | `--yolo-all` single-command pipeline runner (download → build → docker → load → verify) with self-healing error handling |

Tests live alongside each package (e.g. `utils/kg_builder/tests/`, `utils/graph_loader/tests/`, `utils/planner/tests/`); `utils/recovery.py` and `utils/yolo.py` are tested under `utils/graph_loader/tests/` (`test_recovery.py`, `test_yolo.py`). Run with `uv run python -m pytest utils/kg_builder/tests/`, `uv run python -m pytest utils/graph_loader/tests/`, and `uv run python -m pytest utils/planner/tests/`.

The golden live suites (`utils/specialists/tests/test_golden_attack.py`, `test_golden_capec.py`) parameterize every bank question through the real specialists against the live Docker stack (marked `live`/`integration`, skipped when unreachable); `utils/specialists/evalset/tests/` holds the no-DB layer (gold-bank anchor regressions, per-entry routing checks, bank staleness guards). The runner (`tests/golden_runner.py`) asserts answer *correctness* — ID-set containment, exact names/properties, bounded scans, honest empties, and `expect_boundary` schema refusals (empty, ok, NO query executed, gate/execute never reached) — not merely that the query ran. The shared specialist refuses at the schema boundary: a task naming an entity the source card doesn't model (e.g. `Asset`) returns an honest empty with a `boundary` trace instead of silently answering a different question. Gremlin queries speak the loaded graph's SCREAMING_SNAKE edge convention via `utils.graph_loader.stores.gremlin.gremlin_edge_label()`; the specialist builder and validator translate card vocabulary (e.g. CAPEC `ChildOf` → `CHILD_OF`) through that single function. Regenerate golden artifacts with `uv run python -m utils.specialists.evalset.gold_bank` and `... .compile_banks`.

The Wk 10–11 integration layer sits on top: `utils/specialists/tests/test_seams.py` guards the four integration-frozen seams (Plan→SpecialistTask field preservation, provenance completeness + ATTACK-only Gremlin join values, the single shared `partial`/status rule in `federation.bundle_evidence()`/`status_and_exit()`, and synthesis claim/abstention resolution); `test_sequencing.py` + `test_pipeline.py` cover dependent sequencing, every degradation mode (source down, specialist failure, empty-but-clean abstention, unsupported part, no cards), end-to-end citation→Provenance resolution, per-stage timings, the total-pipeline deadline, and LLM-off reproducibility — all hermetic. `test_acceptance_federated.py` (live, skips when the stack is down) is the proposal's flagship gate: the credential-theft flow graded against the snapshot-derived federated gold (`evalset/federated_gold.py` + `grade_federated.py`, committed as `tests/golden/federated_gold.json` with the A-vs-B verdicts `optionA_verdict.json`/`optionB_verdict.json`) plus a small cross-source federated golden set (seeded CAPEC→technique→mitigation questions, the deprecated-pattern double abstention, a nonexistent-pattern abstention).

The Wk 11–13 component evaluation reuses the same banks and corpus for *scored* metrics (distinct from the pass/fail suites above). The planner scorer (`utils/planner/evaluation/`) is expanded: a snapshot-derived corpus generator (`build_corpus.py`) grows the 7 curated anchors to 31 cases by deriving single-source expected plans from the specialist banks (kept only when the deterministic planner selects the gold source and the plan is schema-valid; every exclusion — unroutable bare lookups, template caps, adversarial — reported, not silently dropped), and the scorer adds a sub-question-quality decomposition (count / routing / dependency) beside source precision/recall and schema adherence, reported dev-vs-holdout and by origin. The specialist scorers (`utils/specialists/evalset/score_*.py`, `latency.py`) grade VA, EX, safety, and latency; their tests (`utils/specialists/tests/test_score_validity.py`, `test_score_execution.py`, `test_score_safety.py`, `test_latency.py`, plus `fixtures/adversarial_probes.py`) keep the hermetic layer (taxonomy bucketing, pool extraction, clock-injected latency shaping, gate probes) green without a database and run the live EX/latency paths when the stack is up. `utils/evaluation/` assembles all of it into one report via `uv run main.py --component-eval`; the deterministic build is byte-reproducible (LLM off) and no metric depends on an LLM judge. An adversarial gate probe in this milestone surfaced and fixed a single-quoted-label schema-validation bypass in the Gremlin validator.

The synthesis layer reuses the same banks one level up: `utils/synthesis/tests/test_golden_synthesis.py` runs all 53 questions through specialist → `synthesize()` live and asserts the *answer* layer — unsupported-claim rate 0%, every rendered claim cited, every `expect_empty` negative producing exactly one abstention whose query proof equals the executed query, and every `expect_boundary` negative abstaining without an invented query proof (the statement names what the source doesn't model) (the goals.md faithfulness/groundedness/unsupported-claim-rate metrics as executable checks). The hermetic synthesis tests (`utils/synthesis/tests/`) include adversarial verifier cases: fabricated identifiers, citations to never-retrieved records, claims against empty sources, and false abstentions over real evidence must all be cut or repaired.

### Pipeline error handling

The `--yolo-all` runner is resilient by design. When a step fails because of an
artifact that already exists on disk (a stale or partially written canonical
graph), the existing copy is moved to `data/graphs/<dataset>/_backups/canonical-<UTC>`
and the artifact is rebuilt clean — never silently skipped or left broken.
Transient errors (connection refused, timeouts) are retried with exponential
backoff; non-recoverable errors are surfaced as a `NEEDS INPUT` step in the
summary table with a remediation hint rather than an opaque crash. The `_backups/`
directories live under the git-ignored `data/` tree.

### Fixture QA and snapshot pinning

Two safeguards keep the fixtures trustworthy before agents ever touch them.

**Fixture-QA harness** (`utils/graph_loader/fixture_qa/`, `uv run main.py --graph
fixture-qa --dataset <ds>`) independently reconciles three views of a graph —
raw MITRE source, canonical build manifest, and the live database. It recounts
node labels straight from the raw STIX/XML (deliberately not via the build
preprocessors, so a systematic drop is catchable), asserts `raw == manifest ==
live`, runs a live referential-integrity check (zero dangling edges, zero id-less
nodes) via `GraphStore.referential_integrity()`, and verifies revoked/deprecated
handling (both ATT&CK and CAPEC exclude retired objects at load and record the
counts — ATT&CK via `revoked`/`x_mitre_deprecated`, CAPEC via `Status` in
{Deprecated, Obsolete}; the harness reconciles the raw retired total against the
manifest `skipped_count` and asserts zero retired nodes leak into the artifact).
It writes `data/graphs/<ds>/runtime/fixture-qa-report.json` and exits non-zero on
any mismatch. Verified state: ATT&CK 4369 nodes / 27669 edges (14 checks), CAPEC
4769 / 6972 (11 checks; 114 retired entries excluded — 57 AttackPattern + 57
Category), both with zero dangling edges.

**Composite join-key enforcement** (`fixture_qa/composite_keys.py`). An ATT&CK
ID is never an identity on its own — the identity is the pair `(attack_id,
stix_type)`, or equivalently the STIX UUID (`id`); the raw v19 bundle has 224
IDs that appear under two types (live `attack-pattern` + deprecated
`course-of-action`). Neo4j enforces this with graph-wide constraints
(`attack_stix_id_unique`, `attack_id_type_unique` on `:AttackObject`); the
harness enumerates the collision set independently from the raw bundle and the
canonical artifact and exact-matches both against the checked-in fixture
`fixture_qa/expected/attack_collisions.json`, asserts identity-property
existence, and verifies the constraints live via
`GraphStore.list_constraint_names()`. The contract is published in each source
card's `identity` block (auto-generated join key + measured collisions;
hand-authored policy in the overlay).

**Orphan / island resolution** (`fixture_qa/orphans.py`). Every zero-degree
node must be explained: dead objects match the recorded policy (both ATT&CK and
CAPEC exclude-at-load → zero dead orphans), and
live orphans must exactly equal the checked-in allow-lists
(`fixture_qa/expected/{attack,capec}_orphans.json` — ATT&CK: 8 DataComponents
unreferenced anywhere in v19; CAPEC: 9 implicit filter views + 52 uncited
ExternalReferences). The v19 embedded references are wired at build time
(`Matrix -HAS_TACTIC-> Tactic`, `DetectionStrategy -HAS_ANALYTIC-> Analytic
-MONITORS-> DataComponent`, CAPEC `IN_VIEW` from `Has_Member`), and named
regressions assert Matrix→15 Tactics, every live DataComponent connected, and
a ChildOf hierarchy that is AttackPattern-only and acyclic. Live orphan sets
(`GraphStore.orphan_ids()`) must equal the canonical scan exactly.

**Cross-database resolution** (`fixture_qa/cross_db.py`). Every CAPEC `ATTACK`
taxonomy mapping must resolve under `(attack_id, stix_type='attack-pattern')`
— never digits alone. The baseline (`fixture_qa/expected/capec_attack_resolution.json`)
records 179/189 unique technique ids resolving (the 10 misses are the
revoked-in-v19 T1562 family and Mobile-only T1513); the named CAPEC-555
regression asserts it maps to exactly T1021, T1114.002, T1133.

**Snapshot pinning** records the sha256 of each raw source in `data/versions.json`
(and per-source `metadata.json`), so builds run only from the exact ATT&CK v19.0
and CAPEC v3.9 files. `utils/kg_builder/snapshot.py` recomputes and compares the
checksum at the top of every build and fails fast if MITRE silently shipped a new
revision; the pin also surfaces in source-card `provenance.raw_sha256`. Pin an
existing on-disk snapshot with `uv run main.py --pin`.

## Data (`data/`)

Tracked in git: `data/versions.json` (pinned ATT&CK v19.0, CAPEC v3.9, with sha256 source checksums). Everything else is generated locally.

| Path | Contents |
|------|----------|
| `raw/attack/v{version}/` | Downloaded Enterprise STIX JSON |
| `raw/capec/v{version}/` | Downloaded CAPEC XML |
| `processed/pairs/` | Preprocessing checkpoints (`enterprise-attack.json`, `capec.json`) |
| `processed/discovery/` | CAPEC XML discovery inventories |
| `graphs/attack/canonical/` | ATT&CK source-of-truth JSONL, schema, manifest |
| `graphs/capec/canonical/` | CAPEC source-of-truth JSONL, schema, manifest |
| `graphs/attack/exports/neo4j/` | CSV + Cypher for Neo4j import |
| `graphs/attack/exports/gremlin/` | JSONL for Gremlin import |
| `graphs/capec/exports/gremlin/` | Primary CAPEC Gremlin JSONL export |
| `graphs/capec/exports/neo4j/` | Optional CAPEC Neo4j export |
| `graphs/attack/runtime/{neo4j,gremlin}/` | Runtime load manifests after successful live loads |
| `graphs/capec/runtime/gremlin/` | CAPEC runtime load manifest after successful Gremlin load |
| `source_cards/` | Source registry cards for planner agents (`attack.json`, `capec.json`) |

Populate with `uv run main.py --download` then `uv run main.py --build attack` and/or `uv run main.py --build capec`. Load into Docker graph databases with `uv run main.py --docker start` then `uv run main.py --dataset attack --graph neo4j|gremlin|all` or `uv run main.py --dataset capec --graph gremlin`.

## Infrastructure (`docker/`)

| Path | Contents |
|------|----------|
| `docker-compose.yml` | Neo4j + Gremlin services (parameterized via `${VAR:-default}`) |
| `.env` | Committed fallback for image versions; overridden by the root [`.env`](../.env.example) |
| `neo4j/data/` | Persistent Neo4j volume (gitignored) |

Managed via `uv run main.py --docker start|stop|status`. Image versions, host ports, and credentials are configured centrally in the root `.env` — see the [Configuration](../README.md#configuration) section.

## Backend API (`api/`)

A thin **FastAPI** service that exposes the `utils/` capabilities to the web UI
without re-implementing any logic. The Next.js app proxies `/api/*` here (same
origin, no CORS — see `web/next.config.ts` `rewrites`).

| Endpoint | Wraps | Notes |
|----------|-------|-------|
| `GET /api/health` | `graph_loader` TCP probe + `infrastructure.docker_status` | Per-backend live/down/starting; never raises |
| `GET·PUT /api/config` | `PlannerConfig`/`SpecialistConfig.from_env` + `config.set_env_values` | View/edit LLM + connection env; password redacted |
| `POST /api/query` | `PlanningAgent.plan` → `SpecialistRouter.run_plan` | SSE stream: probe → plan → specialist* → evidence → answer → done. Each event carries the full `to_dict()` payload (plan trace, raw query, every record + provenance, evaluator traces) |
| `POST /api/admin` | `docker_*`, `run_graph_command`, `docker_stop_service`, `YoloRunner`, `download`, `kg_builder` | SSE log stream for every remaining main.py mode — docker start/stop/status, graph health/load/verify/**stop**, data download/build, and **`--yolo-all`** |
| `GET /api/graph/{dataset}` | Canonical `nodes.jsonl` + `relationships.jsonl` for `attack`\|`capec` | Full node/edge payload for the graph view — strips `external_references` and truncates `description` to keep it light; 404 if canonical files are absent |

| Path | Contents |
|------|----------|
| `api/main.py` | FastAPI app + route handlers |
| `api/models.py` | Pydantic request/response models |
| `api/services/` | `health.py`, `config.py`, `query.py`, `infra.py`, `graph.py` |
| `api/tests/` | Contract tests (`uv run python -m pytest api/tests/`) |

The query pipeline is synchronous, so the SSE endpoints run it in a worker
thread and emit a real event at each boundary; the answer is composed
deterministically from the per-source summaries + join index (the pipeline emits
evidence, not prose).

## Web Workbench (`web/`)

Next.js (App Router) + TypeScript + Tailwind v4 + Motion analyst UI using the
Woven Dusk design system — the three-region workbench (header infra pills ·
conversations rail · **multi-turn** chat thread with Answer Cards · step-by-step
inspector). The composer submits questions to `POST /api/query`; the event-driven
run machine appends a new turn per question (the rail lists real turns; selecting
one drives the inspector) and advances the animated trace from the real SSE
events, retaining the literal ordered event log + raw plan/probe/answer per turn.
The inspector surfaces the **full** pipeline: the Trace tab shows the planner
iteration history and, per specialist, the six evaluator steps with their
reasons/detail, the task metadata, and the validated query; the Evidence tab
shows every record (filter + incremental reveal, no cap) expandable to full
properties + provenance query; the Raw JSON tab switches across Plan / Probe /
Evidence / Answer / the literal **event stream**. A settings modal edits
LLM/connection config and runs every infra action. TypeScript types
(`lib/types.ts`) mirror the backend `to_dict()` shapes; `lib/fixtures.ts` is the
idle/demo run.

Each Answer Card renders the Step 6/7 **verified answer** from
`answer.synthesis` (`SynthesisBlock` in `components/center/AnswerCard.tsx`,
adapted by `buildSynthesis` in `lib/adapt.ts`): a verification pill
(`N/M claims verified · X% unsupported`, teal when clean, amber when the
verifier cut claims or repaired abstentions), the rendered claims with
clickable citation chips, honest abstentions with their proof — the executed
query in mono, or the named schema boundary ("no query executed") for
Step 7 refusals such as ICS-only Assets — plus struck-through
cut-by-verifier claims with reasons and the composer-fallback note. Both
seeded demo turns carry synthesis views, so the trust surface shows without a
live backend; payloads without `synthesis` (pre-Step-6) simply omit the block.

A header **Chat / Graphs** toggle (`components/header/ViewToggle.tsx`, view state
in `workbench/WorkbenchContext.tsx`) switches the main region between the chat
workbench and a dedicated **graph explorer** (`components/graph/`). The explorer
loads a whole graph from `GET /api/graph/{dataset}`, switches between the
ATT&CK (Neo4j) and CAPEC (Gremlin) datasets, and renders **every node and edge**
on a canvas via `react-force-graph-2d` (`GraphCanvas`, dynamically imported
`ssr:false`). Nodes are colored by label and each relationship type gets a
**unique** color. The layout is two sidebars: the **left** (`GraphSidebar`) is
filters-only — node-type + relationship-type toggles (each with a color swatch
and count) — and the **right** (`GraphDetailsSidebar`) appears only when a node
or edge is clicked, showing that element's full properties via `ElementInspector`
with a close control. A top `GraphSearchBar` filters the graph by node
name/description and edge type, committing its query 1s after the last keystroke
(debounced) or immediately on the Search button / Enter. Pure transforms live in
`lib/graph.ts` (`labelColor`, `edgeTypeColorMap` — unique color per sorted
relationship type, `nodeMatchesQuery`, `toForceGraphData` — applies the search +
filters and drops dangling links). When Graphs is active the shell hides the
conversations rail and chat inspector (`AppShell` `hideRails`).

| Path | Contents |
|------|----------|
| `app/page.tsx`, `app/layout.tsx` | App Router root + workbench composition |
| `app/globals.css` | Woven Dusk tokens (`@theme`) + keyframes |
| `components/` | `shell/`, `header/`, `left/`, `center/`, `inspector/`, `settings/`, `graph/`, `ui/`, `workbench/` |
| `components/graph/` | `GraphExplorer`, `GraphSecondaryNav`, `GraphSearchBar`, `GraphSidebar` (filters), `GraphDetailsSidebar` (on-select), `GraphCanvas`, `ElementInspector` |
| `lib/api.ts` | Typed client + SSE helpers (`getHealth`, `getConfig`, `getGraph`, `streamQuery`, `streamAdmin`) |
| `lib/graph.ts` | Pure graph-view transforms (`labelColor`, `toForceGraphData`) |
| `lib/adapt.ts` | Backend payloads → `WorkbenchRun` view-model |
| `lib/runMachine.ts`, `lib/motion.ts` | Event-driven run controller + animation variants; stamps every SSE event with elapsed-ms at arrival and tracks per-lane `LaneArrival` (started/arrived/seeds/order) off the `specialist-start` event |
| `lib/ticker.ts` | Pure SSE-event → narration projection for the live activity ticker (`describeEvent`, `tickerLines`, `currentPhaseMessage`) |
| `lib/types.ts`, `lib/fixtures.ts` | Trace-object + API types, idle/demo run |

The live run is visibly animated end to end: `LiveTicker`
(`components/center/LiveTicker.tsx`) narrates every pipeline event
terminal-style with its arrival time inside the answer skeleton (collapsing to
an "activity log" disclosure once done), the `MiniStepper` shows a crossfading
phase caption with a ticking elapsed counter, routed sub-questions surface
immediately as shimmer placeholder lanes ("queued" → "querying <backend>…",
with the seeded-with-N-ids note for sequenced consumers) until their result
arrives, and records then reveal with a staggered pop-in carrying `#k`
emission-order badges plus an "arrived #order at +X.Xs" caption — all gated on
`statusOf`/`replaying` so past turns render statically.

Launch the whole workbench (API + web) from the repo root with `python app.py`
(`--prod` for a production build, `--port`/`--api-port`/`--host` to override).
For the web app alone: `cd web && npm run dev`; build with `npm run build`, lint
with `npm run lint`, and test with `npm test` (adapter + fixture contracts).

## Finding Things Fast

| Looking for… | Go to… |
|--------------|--------|
| Plan a question over live graphs | `utils/planner/`, `main.py --plan`, [`docs/planner_agent.md`](planner_agent.md) |
| Query live graphs end-to-end | `utils/specialists/`, `main.py --query`, [`docs/specialist_agents.md`](specialist_agents.md), `notebooks/planning-schematic-agents.ipynb` |
| Download MITRE data | `utils/download/downloader.py`, `main.py --download` |
| Build graph artifacts | `utils/kg_builder/`, `main.py --build` |
| Load live graph databases | `utils/graph_loader/`, `main.py --dataset --graph` |
| Fixture-QA (raw==manifest==live) | `utils/graph_loader/fixture_qa/`, `main.py --graph fixture-qa --dataset <ds>` |
| Pin the data snapshot (sha256) | `utils/kg_builder/snapshot.py`, `utils/download/downloader.py`, `main.py --pin` |
| ATT&CK STIX normalization | `utils/kg_builder/preprocess/attack.py` |
| CAPEC XML normalization | `utils/kg_builder/preprocess/capec.py`, `utils/kg_builder/discovery/` |
| Neo4j / Gremlin exporters | `utils/kg_builder/exporters/` |
| Docker graph DB stack | `utils/infrastructure/docker_manager.py`, `docker/` |
| UI design rules | `docs/skills/woven-dusk-design/SKILL.md` |
| Website architecture | `docs/skills/website-architecture/SKILL.md` |
| Repo layout standards | `docs/skills/repository-structure/SKILL.md` |
| Future agent work | `docs/skills/planner/`, `docs/plans/` |

## Not Yet in Repo

Planned per roadmap: analyst-facing tables, figures, and network diagrams from
the synthesis layer, and the web UI rendering of the verified claims
(`answer.synthesis` is already in the API payload; the workbench still renders
the deterministic sections). ATT&CK and CAPEC canonical builds and runtime
loading (`utils/kg_builder/`, `utils/graph_loader/`), the federated planning
agent (`utils/planner/`), the Cypher/Gremlin query specialists
(`utils/specialists/`), the synthesis agent with claim verification and
abstention (`utils/synthesis/`), the FastAPI service (`api/`), and the wired
Next.js workbench (`web/`) are implemented; Gremlin is the primary CAPEC runtime
backend.
