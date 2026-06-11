# Ariadne

Ariadne is a federated agentic graph-database system that threads together cybersecurity knowledge graphs to guide analysts through the labyrinth of interconnected adversary techniques, patterns, and mitigations. Named after Ariadne who guided Theseus through a maze to escape the Minotaur.

This repository implements a proof-of-concept for **ReliaQuest Innovation Challenge Fund — Challenge Three: Knowledge Graph Integration**. The prototype federates queries across MITRE ATT&CK Enterprise STIX (Neo4j/Cypher) and MITRE CAPEC attack patterns (Gremlin Server, Neptune-style), using an orchestrator and source-specific agents to plan, query, and synthesize analyst-facing answers with full provenance.

## Grant

| Field | Value |
|-------|-------|
| PI | Olmo S. Zavala Romero, FSU Department of Scientific Computing |
| Technical lead | Brendon DGR (graduate research assistant) |
| Period | June 8, 2026 – October 23, 2026 |
| Amount | $29,298 |

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/purpose.md`](docs/purpose.md) | Problem, architecture, data sources, team |
| [`docs/goals.md`](docs/goals.md) | Deliverables, timeline, evaluation criteria |
| [`docs/changelog.jsonl`](docs/changelog.jsonl) | Project change log |
| [`docs/skills/global-project-rules/SKILL.md`](docs/skills/global-project-rules/SKILL.md) | Agent workflow rules (read first) |

## Quick Start

```bash
# Python
uv sync
uv run read-skills

# Web demo UI
cd web && npm install
cd web && npm run dev
cd web && npm run build   # required after webfront changes
```

## Repository Layout

```text
docs/     purpose, goals, skills, changelog, plans
utils/    Python utilities (by domain)
web/      Analyst-facing demo UI (React/Vite)
```

Agent pointer folders (`.claude/`, `.agents/`, `.cursor/`) route to canonical instructions under `docs/skills/`.
