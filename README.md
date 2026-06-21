# Ariadne

Ariadne is a federated agentic graph-database system that threads together cybersecurity knowledge graphs to guide analysts through the labyrinth of interconnected adversary techniques, patterns, and mitigations. Named after Ariadne who guided Theseus through a maze to escape the Minotaur.

This repository implements a proof-of-concept for **ReliaQuest Innovation Challenge Fund — Challenge Three: Knowledge Graph Integration**. The prototype federates queries across MITRE ATT&CK Enterprise STIX (Neo4j/Cypher) and MITRE CAPEC attack patterns (Gremlin Server, Neptune-style), using an orchestrator and source-specific agents to plan, query, and synthesize analyst-facing answers with full provenance.

**Award period:** June 8, 2026 – October 23, 2026

## Roadmap

| Status | Weeks | Phase | Task | Difficulty |
| :---: |-------|-------|------|------------|
| [x] | Wk 1–2 | Setup | Environment and tooling setup | Low |
| [x] | Wk 2–3 | Setup | Download and validate public data sources | Low |
| [x] | Wk 3–4 | Data layer | Build portable ATT&CK graph artifacts (JSONL, schema, Neo4j CSV/Cypher) | Medium |
| [x] | Wk 4 | Data layer | Runtime ATT&CK graph loader (Neo4j/Gremlin load, verify, health) | Medium |
| [x] | Wk 4–5 | Data layer | Build Gremlin CAPEC fixture | Medium |
| [ ] | Wk 5 | Data layer | Author source cards (ATT&CK card auto-generated; endpoints & safety limits pending) | Low |

**ITS check-in** — Both graph fixtures live, source cards complete, environment reproducible.

| Status | Weeks | Phase | Task | Difficulty |
| :---: |-------|-------|------|------------|
| [ ] | Wk 6–7 | Agents | Federated planning agent | High |
| [ ] | Wk 7–8 | Agents | Cypher specialist agent | High |
| [ ] | Wk 8–9 | Agents | Gremlin specialist agent | High |

**Midpoint review** — All three agents functional end-to-end on the credential-theft example query flow.

| Status | Weeks | Phase | Task | Difficulty |
| :---: |-------|-------|------|------------|
| [ ] | Wk 10 | Agents | Synthesis and reporting agent | High |
| [ ] | Wk 10–11 | Agents | End-to-end integration and pipeline wiring | Medium |
| [ ] | Wk 11–13 | Evaluation | Component-level evaluation | Medium |
| [ ] | Wk 12–13 | Evaluation | End-to-end evaluation and LLM evaluator | Medium |

**Pitch workshop** — Evaluation results compiled, demo stable, narrative prepared.

| Status | Weeks | Phase | Task | Difficulty |
| :---: |-------|-------|------|------------|
| [ ] | Wk 14–15 | Evaluation | Bug fixes, iteration, and documentation | Low |
| [ ] | Wk 15–16 | Pitch prep | Pitch preparation and final demo | Low |

**October ReliaQuest pitch** — Live demo, evaluation results, and future development roadmap presented.

Task descriptions and rationale: [`docs/goals.md`](docs/goals.md)

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/purpose.md`](docs/purpose.md) | Problem, architecture, data sources, team |
| [`docs/goals.md`](docs/goals.md) | Full roadmap, evaluation criteria, deliverables |
| [`docs/structure.md`](docs/structure.md) | Repository navigation map |
| [`docs/changelog.jsonl`](docs/changelog.jsonl) | Project change log |
| [`docs/structure.md`](docs/structure.md) | Repository navigation map |
| [`docs/skills/global-project-rules/SKILL.md`](docs/skills/global-project-rules/SKILL.md) | Agent workflow rules (read first) |

## Quick Start

```bash
# Python setup & download datasets
uv sync
cp .env.example .env                      # central config (edit values as needed)
uv run main.py --download
uv run read-skills

# Build portable graph artifacts (ATT&CK and CAPEC)
uv run main.py --build attack --dry-run   # preview ATT&CK canonical and export paths
uv run main.py --build attack             # ATT&CK canonical truth + backend exports
uv run main.py --build capec              # CAPEC canonical truth + backend exports
uv run main.py --build all                # build ATT&CK and CAPEC artifacts

# Graph database infrastructure (Docker)
uv run main.py --docker start             # pull, start Neo4j + Gremlin, wait until ready
uv run main.py --docker status            # show container status
uv run main.py --docker stop              # stop containers

# Runtime graph loading (requires built artifacts; does not download or rebuild)
uv run main.py --graph health             # check Neo4j/Gremlin endpoint reachability
uv run main.py --dataset attack --graph verify   # no-load dataset/runtime verification
uv run main.py --dataset attack --graph neo4j    # load ATT&CK into Neo4j
uv run main.py --dataset attack --graph gremlin  # load ATT&CK into Gremlin
uv run main.py --dataset attack --graph all      # load ATT&CK into both backends
uv run main.py --dataset capec --graph gremlin   # load CAPEC into Gremlin (primary CAPEC backend)
uv run main.py --dataset capec --graph verify    # no-load CAPEC artifact/runtime verification

# Run KG builder tests
uv run python -m pytest utils/kg_builder/tests/
uv run python -m pytest utils/graph_loader/tests/

# Web demo UI
cd web && npm install
cd web && npm run dev
cd web && npm run build   # required after webfront changes
```

## Configuration

All tunable settings live in a single, git-ignored `.env` at the repository
root. Copy the documented template and edit it:

```bash
cp .env.example .env
```

[`.env.example`](.env.example) groups every setting into labeled sections —
dataset versions, data directory, Docker image versions, host ports, Neo4j
credentials, graph connection URIs, and runtime tuning — and each comment says
what the value controls and where it is read. Every value is the project
default, so an unedited `.env` (or no `.env` at all) keeps current behavior.

How it flows:

- **Python** — `main.py` calls `utils.config.load_env()` at startup to load
  `.env` into the environment; the downloader, KG builder, and graph loader read
  their values from there with the documented fallbacks.
- **Docker** — `docker/docker-compose.yml` reads the same variable names with
  `${VAR:-default}` fallbacks. `utils/infrastructure` layers the root `.env` on
  top of the committed `docker/.env` base, so root values win.

Real shell/CI environment variables always take precedence over `.env`.

## Repository Layout

```text
docker/   Neo4j and Gremlin Compose stack (pinned image versions)
docs/     purpose, goals, skills, changelog, plans, structure.md
utils/    Python utilities (download, kg_builder, graph_loader, infrastructure)
web/      Analyst-facing demo UI (React/Vite)
```

Agent pointer folders (`.claude/`, `.agents/`, `.cursor/`) route to canonical instructions under `docs/skills/`.

## ATT&CK Graph Artifacts

`uv run main.py --build attack` converts the pinned Enterprise STIX bundle into a **canonical graph interchange layer** plus generated backend exports. Canonical JSONL, schema, and manifest files under `data/graphs/attack/canonical/` are the source of truth; Neo4j and Gremlin outputs under `data/graphs/attack/exports/` are reproducible projections.

**Runtime loading** (`uv run main.py --dataset attack --graph neo4j|gremlin|all`) reads only from built canonical artifacts and exports. It does not download raw data or rebuild the graph. Semantic validation runs before any database write. After a successful load, runtime manifests are written under `data/graphs/attack/runtime/`.

| Output | Description |
|--------|-------------|
| `data/processed/pairs/enterprise-attack.json` | Preprocessing checkpoint (metadata, nodes, relationships, counts) |
| `data/graphs/attack/canonical/nodes.jsonl` | Canonical node records with `label` and `labels` (one JSON object per line) |
| `data/graphs/attack/canonical/relationships.jsonl` | Canonical edge records |
| `data/graphs/attack/canonical/schema.json` | Node-label and relationship-type allowlists (includes reserved `DataSource`) |
| `data/graphs/attack/canonical/manifest.json` | Counts, source metadata, canonical paths, export provenance, and SHA-256 hashes |
| `data/graphs/attack/exports/neo4j/nodes.csv` | Neo4j CSV node import (nested properties JSON-encoded) |
| `data/graphs/attack/exports/neo4j/relationships.csv` | Neo4j CSV relationship import |
| `data/graphs/attack/exports/neo4j/schema.cypher` | Neo4j-compatible schema description |
| `data/graphs/attack/exports/neo4j/constraints.cypher` | Uniqueness constraints per node label |
| `data/graphs/attack/exports/gremlin/nodes.jsonl` | Gremlin-ready vertex records (nested properties JSON-encoded) |
| `data/graphs/attack/exports/gremlin/relationships.jsonl` | Gremlin-ready edge records |
| `data/source_cards/attack.json` | Source registry card for planner and specialist agent routing |
| `data/graphs/attack/runtime/neo4j/load-manifest.json` | Runtime Neo4j load record (written after successful load + verification) |
| `data/graphs/attack/runtime/gremlin/load-manifest.json` | Runtime Gremlin load record (written after successful load + verification) |

## CAPEC Graph Artifacts

`uv run main.py --build capec` parses the pinned CAPEC v3.9 XML catalog into the same canonical/export/runtime layout as ATT&CK. The full catalog is built for source completeness; CAPEC-to-ATT&CK correlation uses normalized taxonomy mappings (`MAPS_TO` edges to `TaxonomyEntry` nodes with ATT&CK entry IDs).

| Output | Description |
|--------|-------------|
| `data/processed/discovery/capec-inventory.json` | Namespace-aware XML path inventory for schema-drift tolerance |
| `data/processed/pairs/capec.json` | Normalized intermediate entity checkpoint |
| `data/graphs/capec/canonical/nodes.jsonl` | Canonical CAPEC node records (`AttackPattern`, `Category`, `ExecutionStep`, etc.) |
| `data/graphs/capec/canonical/relationships.jsonl` | Canonical CAPEC edges (`ChildOf`, `MAPS_TO`, `HAS_EXECUTION_STEP`, …) |
| `data/graphs/capec/canonical/schema.json` | CAPEC node-label and relationship-type vocabulary |
| `data/graphs/capec/canonical/manifest.json` | Counts, metadata, export provenance, and SHA-256 hashes |
| `data/graphs/capec/exports/gremlin/nodes.jsonl` | Gremlin-ready vertex records (primary CAPEC runtime projection) |
| `data/graphs/capec/exports/gremlin/relationships.jsonl` | Gremlin-ready edge records |
| `data/graphs/capec/exports/neo4j/` | Optional Neo4j CSV/Cypher projection from the same canonical truth |
| `data/source_cards/capec.json` | Source registry card (Gremlin runtime backend) |
| `data/graphs/capec/runtime/gremlin/load-manifest.json` | Runtime Gremlin load record after successful load + verification |

## Runtime Graph Loading

Operator sequence:

```bash
uv run main.py --download
uv run main.py --build attack
uv run main.py --build capec
uv run main.py --docker start
uv run main.py --dataset attack --graph neo4j    # or gremlin | all
uv run main.py --dataset capec --graph gremlin
uv run main.py --graph health                    # infrastructure reachability only
uv run main.py --dataset attack --graph verify   # no-load artifact + live count checks
uv run main.py --dataset capec --graph verify
```

| Command | Role |
|---------|------|
| `--build attack\|capec\|all` | Generate canonical truth + backend exports (no database writes) |
| `--dataset attack --graph neo4j\|gremlin\|all` | Load ATT&CK built artifacts into live graph databases |
| `--dataset capec --graph gremlin` | Load CAPEC built artifacts into Gremlin (primary CAPEC backend) |
| `--graph health` | TCP reachability check for Neo4j Bolt and Gremlin WebSocket |
| `--dataset attack --graph verify` | Validate manifest hashes, semantic rules, runtime manifests, and live counts without loading |

Default endpoints: Neo4j `bolt://localhost:5456` (user `neo4j` / password `password`), Gremlin `ws://localhost:6455/gremlin`. Override with `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, and `GREMLIN_URI`.

Generated artifacts under `data/` are gitignored except `data/versions.json`. Rebuild with the same pinned input to reproduce identical counts and file hashes.

## Graph Database Infrastructure

`uv run main.py --docker start` manages the local Neo4j and Gremlin Server stack via Docker Compose. The CLI pulls pinned images, starts containers in the background, waits until both endpoints respond, prints connection details, and exits.

| Service | Host endpoint | Default credentials |
|---------|---------------|---------------------|
| Neo4j Browser | http://localhost:5455 | `neo4j` / `password` |
| Neo4j Bolt | bolt://localhost:5456 | `neo4j` / `password` |
| Gremlin Server | http://localhost:6455 | n/a |

Pinned image versions, host ports, and credentials are set in the central `.env` (see [Configuration](#configuration)); `docker/.env` is the committed fallback base. Image versions can also be overridden per-run with `--neo4j-version` and `--gremlin-version` on `--docker start`.

Neo4j data persists under `docker/neo4j/data/`. Use `uv run main.py --docker stop` to tear down containers without deleting volumes.

Docker Desktop may label the stack `docker` (from the `docker/` folder). Compose service names are `neo4j` and `gremlin`; the running containers are `ariadne-neo4j` and `ariadne-gremlin` as set in `docker-compose.yml`.
