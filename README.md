# Ariadne

Ariadne is a federated agentic graph-database system that threads together cybersecurity knowledge graphs to guide analysts through the labyrinth of interconnected adversary techniques, patterns, and mitigations. Named after Ariadne who guided Theseus through a maze to escape the Minotaur.

This repository implements a proof-of-concept for **ReliaQuest Innovation Challenge Fund — Challenge Three: Knowledge Graph Integration**. The prototype federates queries across MITRE ATT&CK Enterprise STIX (Neo4j/Cypher) and MITRE CAPEC attack patterns (Gremlin Server, Neptune-style), using an orchestrator and source-specific agents to plan, query, and synthesize analyst-facing answers with full provenance.

**Award period:** June 8, 2026 – October 23, 2026

## Timeline

| Phase | Focus | Milestone |
|-------|-------|-----------|
| 1 | Data and schema layer — STIX/CAPEC fixtures, source cards, Neo4j + Gremlin graph schemas | Foundation before agents |
| 2 | Federated planning agent — intent classification, sub-questions, source routing | ITS check-in |
| 3 | Source query agents — Cypher (Neo4j) and Gremlin specialists with validation and safety | Midpoint review |
| 4 | Synthesis agent — cross-source joins on ATT&CK/CAPEC IDs, provenance-linked answers | Pitch workshop prep |
| 5 | End-to-end evaluation and October demonstration | ReliaQuest pitch (Oct 2026) |

By October 2026 the team delivers a working demo that queries ATT&CK and CAPEC as distinct sources, correlates patterns with techniques and mitigations, and evaluates routing, grounding, and provenance. See [`docs/goals.md`](docs/goals.md) for evaluation criteria and risk notes.

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/purpose.md`](docs/purpose.md) | Problem, architecture, data sources, team |
| [`docs/goals.md`](docs/goals.md) | Deliverables, evaluation criteria, risk notes |
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
