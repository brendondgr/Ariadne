# Workflow

## Environment

- **Python manager:** `uv`
- **Node:** required for `web/` (use LTS)

## Install

```bash
uv sync
cd web && npm install
```

## Run

```bash
# Python skill discovery
uv run read-skills

# Web development server
cd web && npm run dev
```

## Build

```bash
cd web && npm run build
```

Run `npm run build` after every webfront change before committing.

## Test

```bash
# Python tests (add as features grow)
uv run pytest

# Web lint
cd web && npm run lint
```

## Lint / Format

```bash
# Python (add ruff/black when configured)
# Web
cd web && npm run lint
```

## Changelog

Maintain `docs/changelog.jsonl` — one JSON object per line:

```json
{"timestamp":"ISO-8601","summary":"What changed (2-4 sentences max).","why":"Why the change was made."}
```

Append a new entry after each major step or meaningful change set.

## Git Workflow

1. After each major step and validations pass, commit.
2. On a feature branch or worktree, merge to `main` only when everything is 100% functional.
3. Do not force-push to `main`.

## Documentation Maintenance

Update these files when relevant:

| File | When |
|------|------|
| `docs/documentation.md` | Stack, architecture, or status changes |
| `docs/structure.md` | Repository tree changes |
| `docs/workflow.md` | Command or process changes |
| `docs/checklist.md` | Task completion or new follow-ups |
| `docs/changelog.jsonl` | Every major change |
| `docs/plans/` | New implementation or handoff plans |
| Web docs (`architecture.md`, `routes.md`, etc.) | Web structure or stack changes |

## Agent Handoff

Before starting work, read:

1. `docs/skills/global-project-rules/SKILL.md`
2. `docs/documentation.md`
3. `docs/structure.md`
4. `docs/workflow.md`
5. `docs/checklist.md`
6. `docs/changelog.jsonl`
7. Relevant skill under `docs/skills/`

## Supported Agents

- Claude Code → `.claude/skills/`
- OpenAI Codex → `.agents/skills/`
- Cursor → `.cursor/rules/`
