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
| `utils/specialists/` | Source-specific query specialists: shared scaffold + four swap points (builder, validator, connector, normalizer), shared evidence schema, Cypher (ATT&CK/Neo4j) + Gremlin (CAPEC/Gremlin) specialists, federation router |
| `utils/recovery.py` | Pipeline recovery primitives: backup/clean/restore of existing artifacts, failure classification (`stale_state` / `transient` / `needs_human`), bounded retry-with-backoff |
| `utils/yolo.py` | `--yolo-all` single-command pipeline runner (download → build → docker → load → verify) with self-healing error handling |

Tests live alongside each package (e.g. `utils/kg_builder/tests/`, `utils/graph_loader/tests/`, `utils/planner/tests/`); `utils/recovery.py` and `utils/yolo.py` are tested under `utils/graph_loader/tests/` (`test_recovery.py`, `test_yolo.py`). Run with `uv run python -m pytest utils/kg_builder/tests/`, `uv run python -m pytest utils/graph_loader/tests/`, and `uv run python -m pytest utils/planner/tests/`.

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
handling (ATT&CK excludes them and records the counts; CAPEC loads the full
catalog with a filterable `Status` property). It writes
`data/graphs/<ds>/runtime/fixture-qa-report.json` and exits non-zero on any
mismatch. Verified state: ATT&CK 2611 nodes / 21739 edges, CAPEC 4888 / 6917,
both with zero dangling edges.

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

A header **Chat / Graphs** toggle (`components/header/ViewToggle.tsx`, view state
in `workbench/WorkbenchContext.tsx`) switches the main region between the chat
workbench and a dedicated **graph explorer** (`components/graph/`). The explorer
loads a whole graph from `GET /api/graph/{dataset}`, switches between the
ATT&CK (Neo4j) and CAPEC (Gremlin) datasets, and renders **every node and edge**
on a canvas via `react-force-graph-2d` (`GraphCanvas`, dynamically imported
`ssr:false`). Nodes are colored by label; a sidebar (`GraphSidebar`) carries the
label legend, node-type + relationship-type filters, and an `ElementInspector`
that shows the full properties of a clicked node or edge. Pure transforms live in
`lib/graph.ts` (`labelColor`, `toForceGraphData` — drops dangling links when
filtering). When Graphs is active the shell hides the conversations rail and
inspector (`AppShell` `hideRails`).

| Path | Contents |
|------|----------|
| `app/page.tsx`, `app/layout.tsx` | App Router root + workbench composition |
| `app/globals.css` | Woven Dusk tokens (`@theme`) + keyframes |
| `components/` | `shell/`, `header/`, `left/`, `center/`, `inspector/`, `settings/`, `graph/`, `ui/`, `workbench/` |
| `components/graph/` | `GraphExplorer`, `GraphSecondaryNav`, `GraphSidebar`, `GraphCanvas`, `ElementInspector` |
| `lib/api.ts` | Typed client + SSE helpers (`getHealth`, `getConfig`, `getGraph`, `streamQuery`, `streamAdmin`) |
| `lib/graph.ts` | Pure graph-view transforms (`labelColor`, `toForceGraphData`) |
| `lib/adapt.ts` | Backend payloads → `WorkbenchRun` view-model |
| `lib/runMachine.ts`, `lib/motion.ts` | Event-driven run controller + animation variants |
| `lib/types.ts`, `lib/fixtures.ts` | Trace-object + API types, idle/demo run |

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

Planned per roadmap: the synthesis/reporting **agent** (an LLM that turns the
federated evidence into prose). The web workbench currently composes its answer
**deterministically** from the specialists' grounded summaries + join index — no
fabrication — which is the seam that agent would later replace. ATT&CK and CAPEC
canonical builds and runtime loading (`utils/kg_builder/`, `utils/graph_loader/`),
the federated planning agent (`utils/planner/`), the Cypher/Gremlin query
specialists (`utils/specialists/`), the FastAPI service (`api/`), and the wired
Next.js workbench (`web/`) are implemented; Gremlin is the primary CAPEC runtime
backend.
