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

## Top-Level Layout

```text
ariadne/
├── main.py              # CLI: --download, --build, --docker, --dataset, --graph
├── .env.example         # Central project config template (copy to .env)
├── pyproject.toml       # Python deps & scripts (uv)
├── data/                # Datasets & graph artifacts (mostly gitignored)
├── docker/              # Neo4j + Gremlin Compose stack
├── docs/                # Project docs, skills, plans
├── logs/                # Sequential job logs (gitignored)
├── utils/               # Python utilities by domain
└── web/                 # Analyst demo UI (React/Vite)
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
| `utils/download/` | MITRE ATT&CK & CAPEC dataset downloader |
| `utils/kg_builder/` | STIX → canonical graph artifacts → Neo4j/Gremlin exports |
| `utils/graph_loader/` | Runtime load, verify, and health checks for built graph artifacts |
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

## Data (`data/`)

Tracked in git: `data/versions.json` (pinned ATT&CK v19.0, CAPEC v3.9). Everything else is generated locally.

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

## Web Demo (`web/`)

React/Vite analyst-facing UI using the Woven Dusk design system.

| Path | Contents |
|------|----------|
| `src/App.tsx` | Root component |
| `src/styles/tokens.css` | Design tokens |
| `package.json` | Frontend deps & scripts |

Run `cd web && npm run dev`; build with `npm run build` after changes.

## Finding Things Fast

| Looking for… | Go to… |
|--------------|--------|
| Plan a question over live graphs | `utils/planner/`, `main.py --plan`, [`docs/planner_agent.md`](planner_agent.md) |
| Query live graphs end-to-end | `utils/specialists/`, `main.py --query`, [`docs/specialist_agents.md`](specialist_agents.md), `notebooks/planning-schematic-agents.ipynb` |
| Download MITRE data | `utils/download/downloader.py`, `main.py --download` |
| Build graph artifacts | `utils/kg_builder/`, `main.py --build` |
| Load live graph databases | `utils/graph_loader/`, `main.py --dataset --graph` |
| ATT&CK STIX normalization | `utils/kg_builder/preprocess/attack.py` |
| CAPEC XML normalization | `utils/kg_builder/preprocess/capec.py`, `utils/kg_builder/discovery/` |
| Neo4j / Gremlin exporters | `utils/kg_builder/exporters/` |
| Docker graph DB stack | `utils/infrastructure/docker_manager.py`, `docker/` |
| UI design rules | `docs/skills/woven-dusk-design/SKILL.md` |
| Website architecture | `docs/skills/website-architecture/SKILL.md` |
| Repo layout standards | `docs/skills/repository-structure/SKILL.md` |
| Future agent work | `docs/skills/planner/`, `docs/plans/` |

## Not Yet in Repo

Planned per roadmap: the synthesis/reporting agent and full end-to-end pipeline wiring + evaluation. ATT&CK and CAPEC canonical builds and runtime loading (`utils/kg_builder/`, `utils/graph_loader/`), the federated planning agent (`utils/planner/`), and the Cypher/Gremlin query specialists (`utils/specialists/`) are implemented; Gremlin is the primary CAPEC runtime backend.
