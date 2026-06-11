---
name: global-project-rules
description: Universal repository rules for all AI agents. Read before any work in this repository. Covers git workflow, changelog, build verification, documentation maintenance, and required pre-read files.
---

# Global Project Rules

Every agent working in this repository must read this skill first, then the relevant domain skill under `docs/skills/`.

## Required Pre-Read Files

Before making changes, read:

1. `docs/documentation.md`
2. `docs/structure.md`
3. `docs/workflow.md`
4. `docs/checklist.md`
5. `docs/changelog.jsonl`

## Operational Rules

1. After each major step and validations pass, ensure that git committing occurs.
2. If working on a separate branch/worktree and EVERYTHING IS FUNCTIONAL 100%, then merge onto the main branch.
3. Keep an active changelog inside of `docs/changelog.jsonl`. The changelog should be simplistic jsonl that records when changes were made, a high-level overview of what was changed and why (preferably 2-4 sentences AT MAX).
4. If changes are made to the webfront, always ensure that `npm run build` are executed to ensure that everything compiles/runs correctly.

## Environment

- **Python:** managed with `uv`. Install: `uv sync`. Run scripts: `uv run <script>`.
- **Web:** `cd web && npm install` then `npm run dev` / `npm run build`.

## Documentation Maintenance

Update canonical docs when making relevant changes:

| File | Trigger |
|------|---------|
| `docs/documentation.md` | Stack, architecture, status |
| `docs/structure.md` | Repository tree changes |
| `docs/workflow.md` | Commands or process changes |
| `docs/checklist.md` | Task status changes |
| `docs/changelog.jsonl` | Every major change |

## Selected Skills

All canonical skills live under `docs/skills/`:

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

## Supported Agent Tools

- **Claude Code** → `.claude/skills/`
- **OpenAI Codex** → `.agents/skills/`
- **Cursor** → `.cursor/rules/`

Agent-specific folders contain pointers only. Never duplicate instructions outside `docs/skills/`.

## Setup Incomplete Until Verified

Do not declare setup or a major milestone complete until the Definition of Done in `docs/checklist.md` has been verified.
