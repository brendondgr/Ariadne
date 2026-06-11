# Checklist

## Initialization Definition of Done

### Intake Complete

- [x] Project goal, runtime, deliverables, target users, supported tools, and validation workflow documented.
- [x] Website architecture decided: React/Vite SPA under `web/`.
- [x] Supported agents: Claude Code, Cursor, OpenAI Codex.

### Canonical Docs Complete

- [x] `docs/` exists.
- [x] `docs/documentation.md` reflects project direction.
- [x] `docs/structure.md` exists (blank — user to fill).
- [x] `docs/workflow.md` includes install, run, test, lint, build, changelog, and git rules.
- [x] `docs/checklist.md` exists.
- [x] `docs/plans/` exists.
- [x] `docs/skills/` exists.
- [x] `docs/skills/global-project-rules/SKILL.md` exists.
- [x] All 8 selected skills exist under `docs/skills/`.
- [x] Supporting skill files preserved.

### Agent Pointers Complete

- [x] Claude Code pointers verified.
- [x] Codex pointers verified.
- [x] Cursor pointers verified.

### Project Structure Complete

- [x] `web/`, `utils/`, `docs/` exist.
- [x] `npm run build` passes in `web/`.
- [x] `uv run read-skills` works.

### Cleanup Complete

- [x] Starter skill directories removed.
- [x] Root `read-yaml.py` removed.
- [x] `initialize.md` retained until user confirms completion.

### Verification Complete

- [x] Final tree inspected.
- [x] Pointer targets verified.
- [x] Validation commands run (`uv run read-skills`, `npm run build`).

## Follow-Up Work

- [ ] Fill in `goals.md` and `purpose.md`.
- [ ] Fill in `docs/structure.md` with canonical repository tree.
- [ ] Add Python tests under `tests/` as features grow.
- [ ] Expand web routes beyond landing page.
- [ ] User confirms initialization complete — then optionally remove `initialize.md`.
