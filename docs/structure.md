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
├── main.py              # CLI: --download, --build, --docker
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
| `utils/infrastructure/` | Docker Compose lifecycle for local graph DBs |

Tests live alongside each package (e.g. `utils/kg_builder/tests/`). Run with `uv run python -m pytest utils/kg_builder/tests/`.

## Data (`data/`)

Tracked in git: `data/versions.json` (pinned ATT&CK v19.0, CAPEC v3.9). Everything else is generated locally.

| Path | Contents |
|------|----------|
| `raw/attack/v{version}/` | Downloaded Enterprise STIX JSON |
| `raw/capec/v{version}/` | Downloaded CAPEC XML |
| `processed/pairs/` | Preprocessing checkpoints |
| `graphs/attack/canonical/` | Source-of-truth JSONL, schema, manifest |
| `graphs/attack/exports/neo4j/` | CSV + Cypher for Neo4j import |
| `graphs/attack/exports/gremlin/` | JSONL for Gremlin import |
| `source_cards/` | Source registry cards for planner agents |

Populate with `uv run main.py --download` then `uv run main.py --build attack`.

## Infrastructure (`docker/`)

| Path | Contents |
|------|----------|
| `docker-compose.yml` | Neo4j + Gremlin services |
| `.env` | Pinned image versions (Neo4j 5.26, Gremlin 3.8.0) |
| `neo4j/data/` | Persistent Neo4j volume (gitignored) |

Managed via `uv run main.py --docker start|stop|status`.

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
| Download MITRE data | `utils/download/downloader.py`, `main.py --download` |
| Build graph artifacts | `utils/kg_builder/`, `main.py --build` |
| ATT&CK STIX normalization | `utils/kg_builder/preprocess/attack.py` |
| Neo4j / Gremlin exporters | `utils/kg_builder/exporters/` |
| Docker graph DB stack | `utils/infrastructure/docker_manager.py`, `docker/` |
| UI design rules | `docs/skills/woven-dusk-design/SKILL.md` |
| Website architecture | `docs/skills/website-architecture/SKILL.md` |
| Repo layout standards | `docs/skills/repository-structure/SKILL.md` |
| Future agent work | `docs/skills/planner/`, `docs/plans/` |

## Not Yet in Repo

Planned per roadmap: federated planner, Cypher/Gremlin specialist agents, synthesis agent, CAPEC graph build, and full evaluation harness. These will land under `utils/` (and possibly `libs/`) as phases complete.
