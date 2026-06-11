# Ariadne Documentation

## Overview

Ariadne is a project repository with a Python utility layer (`utils/`), a React/Vite webfront (`web/`), and canonical agent instructions under `docs/skills/`. Project goals and purpose are defined in root `goals.md` and `purpose.md` (to be filled in).

## Tech Stack

| Layer | Technology |
|-------|------------|
| Python | 3.13+, managed with `uv` |
| Web | React + Vite + TypeScript + Tailwind CSS |
| Fonts | Geist Sans, Geist Mono |
| Design | Woven Dusk palette (see `docs/design-system.md`) |

## Supported Agent Tools

- Claude Code (`.claude/skills/`)
- OpenAI Codex (`.agents/skills/`)
- Cursor (`.cursor/rules/`)

All agents read canonical instructions from `docs/skills/` — agent-specific folders contain pointers only.

## Architecture

- **Web app mode:** React/Vite SPA under `web/`
- **Documentation:** All project docs under `docs/`
- **Skills:** Canonical skill definitions under `docs/skills/`
- **Utilities:** Python helpers under `utils/`, organized by domain

## Key Decisions

- `docs/` is the single source of truth for instructions and documentation.
- Woven Dusk dark theme replaces the starter Vercel light palette.
- Geist typography and shadow-as-border depth system retained from the Vercel design reference.
- WCAG 2.2 AA accessibility enforced via `accessibility-mobile` and `ada-compliance` skills.

## Current Status

Repository initialization complete. See `docs/checklist.md` for remaining follow-up work.
