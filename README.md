# Ariadne

Ariadne is a federated agentic graph-database system that threads together cybersecurity knowledge graphs to guide analysts through the labyrinth of interconnected adversary techniques, patterns, and mitigations. Named after Ariadne who guided Theseus through a maze to escape the Minotaur.

This repository implements a proof-of-concept for **ReliaQuest Innovation Challenge Fund — Challenge Three: Knowledge Graph Integration**. The prototype federates queries across MITRE ATT&CK Enterprise STIX (Neo4j/Cypher) and MITRE CAPEC attack patterns (Gremlin Server, Neptune-style), using an orchestrator and source-specific agents to plan, query, and synthesize analyst-facing answers with full provenance.

**Award period:** June 8, 2026 – October 23, 2026

## Roadmap

| Weeks | Phase | Task | Difficulty |
|-------|-------|------|------------|
| Wk 1–2 | Setup | Environment and tooling setup | Low |
| Wk 2–3 | Setup | Download and validate public data sources | Low |
| Wk 3–4 | Data layer | Build Neo4j ATT&CK fixture | Medium |
| Wk 4–5 | Data layer | Build Gremlin CAPEC fixture | Medium |
| Wk 5 | Data layer | Author source cards | Low |

**ITS check-in** — Both graph fixtures live, source cards complete, environment reproducible.

| Weeks | Phase | Task | Difficulty |
|-------|-------|------|------------|
| Wk 6–7 | Agents | Federated planning agent | High |
| Wk 7–8 | Agents | Cypher specialist agent | High |
| Wk 8–9 | Agents | Gremlin specialist agent | High |

**Midpoint review** — All three agents functional end-to-end on the credential-theft example query flow.

| Weeks | Phase | Task | Difficulty |
|-------|-------|------|------------|
| Wk 10 | Agents | Synthesis and reporting agent | High |
| Wk 10–11 | Agents | End-to-end integration and pipeline wiring | Medium |
| Wk 11–13 | Evaluation | Component-level evaluation | Medium |
| Wk 12–13 | Evaluation | End-to-end evaluation and LLM evaluator | Medium |

**Pitch workshop** — Evaluation results compiled, demo stable, narrative prepared.

| Weeks | Phase | Task | Difficulty |
|-------|-------|------|------------|
| Wk 14–15 | Evaluation | Bug fixes, iteration, and documentation | Low |
| Wk 15–16 | Pitch prep | Pitch preparation and final demo | Low |

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
