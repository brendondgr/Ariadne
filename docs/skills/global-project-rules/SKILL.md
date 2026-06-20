---
name: global-project-rules
description: Universal repository rules for all AI agents. Read before any work in this repository. Covers git workflow, changelog, build verification, commands, and project context.
---

# Global Project Rules

Every agent working in this repository must read this skill first, then the relevant domain skill under `docs/skills/`.

## Required Pre-Read

Before making changes, read:

1. This file
2. `docs/purpose.md`
3. `docs/goals.md`
4. `docs/changelog.jsonl`
5. The relevant skill under `docs/skills/`

## Project Context

Ariadne is a **federated agentic graph-database access prototype** for cybersecurity knowledge graphs — routing analyst questions across MITRE ATT&CK (Neo4j/Cypher) and CAPEC (Gremlin) via orchestrated planning, query, and synthesis agents.

| Layer | Location | Role |
|-------|----------|------|
| Project docs | `docs/purpose.md`, `docs/goals.md`, `docs/structure.md` | Mission, architecture, timeline, repo map |
| Agent skills | `docs/skills/` | Canonical agent instructions |
| Python utilities | `utils/` | Domain-specific helpers (`download`, `kg_builder`, `graph_loader`, `infrastructure`; `uv`, Python 3.13+) |
| Webfront | `web/` | Analyst-facing demo UI (React/Vite, Woven Dusk) |
| Future | TBD per `docs/skills/repository-structure/` | Agent orchestration, graph fixtures, evaluation |

Supported agents: Claude Code (`.claude/skills/`), OpenAI Codex (`.agents/skills/`), Cursor (`.cursor/rules/`). Agent folders are pointers only — never duplicate instructions outside `docs/skills/`.

## Operational Rules

1. **ALWAYS commit AND push to GitHub at every step of the plan — this is mandatory, not optional.** After each step's changes are made and validations pass, immediately `git commit` and `git push` to the GitHub remote. Do not batch multiple steps into one commit and do not leave work unpushed. Every completed step must end with a pushed commit on GitHub.
2. After all testing is complete for a set of changes, ensure they are committed and pushed to GitHub (no local-only work should remain).
3. If working on a separate branch/worktree and EVERYTHING IS FUNCTIONAL 100%, then merge onto the main branch.
4. **Always** append a new entry to `docs/changelog.jsonl` for every change — no matter how small or what type (code, docs, config, tests, skills). No change ships without a changelog entry. Each entry is simplistic jsonl recording when the change was made and a high-level overview of what was changed and why (preferably 2-4 sentences AT MAX).
5. If changes are made to the webfront, always ensure that `npm run build` are executed to ensure that everything compiles/runs correctly.

## Commands

```bash
# Install
uv sync
cd web && npm install

# Data pipeline
uv run main.py --download
uv run main.py --build attack          # canonical artifacts + backend exports (no DB writes)
uv run main.py --docker start          # local Neo4j + Gremlin stack

# Runtime graph loading (requires built artifacts; does not download or rebuild)
uv run main.py --graph health
uv run main.py --dataset attack --graph neo4j    # or gremlin | all | verify

# Run
uv run read-skills
cd web && npm run dev

# Build (required after webfront changes)
cd web && npm run build

# Test
uv run python -m pytest utils/kg_builder/tests/
uv run python -m pytest utils/graph_loader/tests/

# Lint
cd web && npm run lint
```

## Changelog Format

One JSON object per line in `docs/changelog.jsonl`:

```json
{"timestamp":"ISO-8601","summary":"What changed (2-4 sentences max).","why":"Why the change was made."}
```

## Selected Skills

| Skill | Path |
|-------|------|
| Global rules | `docs/skills/global-project-rules/SKILL.md` |
| Repository structure | `docs/skills/repository-structure/SKILL.md` |
| Website architecture | `docs/skills/website-architecture/SKILL.md` |
| UI frontend | `docs/skills/ui-frontend/SKILL.md` |
| Woven Dusk design | `docs/skills/woven-dusk-design/SKILL.md` |
| Planner | `docs/skills/planner/SKILL.md` |
| Accessibility mobile | `docs/skills/accessibility-mobile/SKILL.md` |
| ADA compliance | `docs/skills/ada-compliance/SKILL.md` |

Implementation plans go in `docs/plans/` when needed.
