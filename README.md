# Ariadne

Ariadne is a project repository with a Python utility layer, a React/Vite webfront, and canonical agent instructions.

## Quick Start

```bash
# Python
uv sync
uv run read-skills

# Web
cd web && npm install && npm run dev
cd web && npm run build
```

## Documentation

All project documentation lives under [`docs/`](docs/):

| File | Purpose |
|------|---------|
| [`docs/documentation.md`](docs/documentation.md) | Project overview, stack, status |
| [`docs/structure.md`](docs/structure.md) | Repository tree (to be filled in) |
| [`docs/workflow.md`](docs/workflow.md) | Commands, git, changelog rules |
| [`docs/checklist.md`](docs/checklist.md) | Active checklist |
| [`docs/changelog.jsonl`](docs/changelog.jsonl) | Change log |
| [`docs/design-system.md`](docs/design-system.md) | Woven Dusk design tokens |

Root [`goals.md`](goals.md) and [`purpose.md`](purpose.md) define project intent (to be filled in).

## Agent Skills

Canonical skill definitions: [`docs/skills/`](docs/skills/)

Every agent must read [`docs/skills/global-project-rules/SKILL.md`](docs/skills/global-project-rules/SKILL.md) first.

Agent pointer folders (instructions only — not source of truth):

| Tool | Path |
|------|------|
| Claude Code | `.claude/skills/` |
| OpenAI Codex | `.agents/skills/` |
| Cursor | `.cursor/rules/` |

## Project Layout

```text
Ariadne/
├── docs/           # Documentation and canonical skills
├── web/            # React/Vite webfront
├── utils/          # Python utilities by domain
├── goals.md        # Project goals (blank)
└── purpose.md      # Project purpose (blank)
```

## Design

Woven Dusk dark theme with Geist typography. See [`docs/skills/woven-dusk-design/SKILL.md`](docs/skills/woven-dusk-design/SKILL.md).
