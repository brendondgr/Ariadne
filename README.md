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
| [ ] | Wk 4–5 | Data layer | Build Gremlin CAPEC fixture | Medium |
| [ ] | Wk 5 | Data layer | Author source cards | Low |

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
| [`docs/changelog.jsonl`](docs/changelog.jsonl) | Project change log |
| [`docs/skills/global-project-rules/SKILL.md`](docs/skills/global-project-rules/SKILL.md) | Agent workflow rules (read first) |

## Quick Start

```bash
# Python setup & download datasets
uv sync
uv run main.py --download
uv run read-skills

# Build portable graph artifacts (ATT&CK)
uv run main.py --build attack --dry-run   # preview canonical and export paths
uv run main.py --build attack             # writes canonical truth + backend exports
uv run main.py --build capec              # future work (exits with notice)
uv run main.py --build all                # ATT&CK build; CAPEC deferred

# Graph database infrastructure (Docker)
uv run main.py --docker start             # pull, start Neo4j + Gremlin, wait until ready
uv run main.py --docker status            # show container status
uv run main.py --docker stop              # stop containers

# Run KG builder tests
uv run python -m pytest utils/kg_builder/tests/

# Web demo UI
cd web && npm install
cd web && npm run dev
cd web && npm run build   # required after webfront changes
```

## Repository Layout

```text
docker/   Neo4j and Gremlin Compose stack (pinned image versions)
docs/     purpose, goals, skills, changelog, plans
utils/    Python utilities (by domain)
web/      Analyst-facing demo UI (React/Vite)
```

Agent pointer folders (`.claude/`, `.agents/`, `.cursor/`) route to canonical instructions under `docs/skills/`.

## ATT&CK Graph Artifacts

`uv run main.py --build attack` converts the pinned Enterprise STIX bundle into a **canonical graph interchange layer** plus generated backend exports. Canonical JSONL, schema, and manifest files under `data/graphs/attack/canonical/` are the source of truth; Neo4j and Gremlin outputs under `data/graphs/attack/exports/` are reproducible projections. This phase **does not load Neo4j or Gremlin Server**; downstream loaders consume the generated files later.

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

Generated artifacts under `data/` are gitignored except `data/versions.json`. Rebuild with the same pinned input to reproduce identical counts and file hashes.

## Graph Database Infrastructure

`uv run main.py --docker start` manages the local Neo4j and Gremlin Server stack via Docker Compose. The CLI pulls pinned images, starts containers in the background, waits until both endpoints respond, prints connection details, and exits.

| Service | Host endpoint | Default credentials |
|---------|---------------|---------------------|
| Neo4j Browser | http://localhost:5455 | `neo4j` / `password` |
| Neo4j Bolt | bolt://localhost:5456 | `neo4j` / `password` |
| Gremlin Server | http://localhost:6455 | n/a |

Pinned image versions live in `docker/.env` (`NEO4J_VERSION=5.26`, `GREMLIN_VERSION=3.8.0`). Override at runtime with `--neo4j-version` and `--gremlin-version` on `--docker start`.

Neo4j data persists under `docker/neo4j/data/`. Use `uv run main.py --docker stop` to tear down containers without deleting volumes.

Docker Desktop may label the stack `docker` (from the `docker/` folder). Compose service names are `neo4j` and `gremlin`; the running containers are `ariadne-neo4j` and `ariadne-gremlin` as set in `docker-compose.yml`.
