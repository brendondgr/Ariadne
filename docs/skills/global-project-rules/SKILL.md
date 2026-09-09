---
name: global-project-rules
description: Universal repository rules for all AI agents. Read before any work in this repository. Covers git workflow, changelog, build verification, commands, and project context.
---

# Global Project Rules

Every agent working in this repository must read this skill first, then the relevant domain skill under `docs/skills/`.

## Required Pre-Read

Before making changes, read:

1. This file
2. `docs/ARCHITECTURE.md`
3. `docs/goals.md`
4. `docs/changelog.jsonl`
5. The relevant skill under `docs/skills/`

## Project Context

Ariadne is a **federated agentic graph-database access prototype** for cybersecurity knowledge graphs — routing analyst questions across MITRE ATT&CK (Neo4j/Cypher) and CAPEC (Gremlin) via orchestrated planning, query, and synthesis agents.

| Layer | Location | Role |
|-------|----------|------|
| Project docs | `docs/ARCHITECTURE.md`, `docs/goals.md`, `docs/structure.md`, `docs/commands.md` | Pipeline stages and their configuration, timeline, repo map, commands |
| Research record | `docs/research/` | Every experiment, claim, decision, figure, and open question. The only place a research finding may live |
| Agent skills | `docs/skills/` | Canonical agent instructions |
| Python utilities | `utils/` | Domain-specific helpers (`download`, `kg_builder`, `graph_loader`, `infrastructure`, `planner`, `specialists`, `synthesis`, `evaluation`, `orchestration` — the LangGraph pipeline super-graph, `conversation` — the LangGraph conversational memory layer (persisted threads + router/validation/answer wrapping the pipeline), `launcher` — the app.py phases; `uv`, Python 3.13+) |
| Web API | `api/` | FastAPI service wrapping `utils/` for the UI (health, config, query SSE, admin SSE) |
| Webfront | `web/` | Analyst workbench UI (Next.js App Router + Tailwind v4 + Motion, Woven Dusk); proxies `/api/*` to `api/` |
| Launcher | `app.py` | Starts the FastAPI service + Next.js app together (`python app.py`) |
| Synthesis | `utils/synthesis/` | Claims-with-citations composer (always deterministic) + unconditional verifier; the LLM seam rewrites narrative prose only |
| Evaluation | `utils/evaluation/`, `utils/specialists/evalset/` | Component + end-to-end scorers, the 120-question golden catalogue, the golden-eval harness |

Supported agents: Claude Code (`.claude/skills/`), OpenAI Codex (`.agents/skills/`), Cursor (`.cursor/rules/`). Agent folders are pointers only — never duplicate instructions outside `docs/skills/`.

## Operational Rules

1. **ALWAYS commit at every step of the plan — this is mandatory, not optional.** After each step's changes are made and validations pass, immediately `git commit`. Do not batch multiple steps into one commit. **Do not `git push`** unless the operator explicitly asks for it in the current session; this repository is worked locally and pushing is the operator's call.
2. After all testing is complete for a set of changes, ensure they are committed (no uncommitted work should remain in the tree).
3. If working on a separate branch/worktree and EVERYTHING IS FUNCTIONAL 100%, then merge onto the main branch.
4. **Append-only records.** Never edit `docs/plans/` or `docs/research/audit-2026-08-03.md` in place — they are dated historical records; write a new file instead. Under `docs/research/`, the same rule binds **completed experiment folders**: once an experiment's `status` is `complete`, `failed`, or `superseded`, corrections go in a new experiment or an appended `AMENDMENTS` section, never a silent edit. It does **not** bind the living ledgers (`CLAIMS.md`, `DECISIONS.md`, `OPEN_QUESTIONS.md`, `RELATED_WORK.md`), generated files (`INDEX.md`, promoted figures and tables), or an in-progress experiment — those are meant to be updated. See `docs/research/DECISIONS.md` D-008.
5. **Always** append a new entry to `docs/changelog.jsonl` for every change — no matter how small or what type (code, docs, config, tests, skills). No change ships without a changelog entry. Each entry is simplistic jsonl recording when the change was made and a high-level overview of what was changed and why (preferably 2-4 sentences AT MAX).
6. If changes are made to the webfront, always ensure that `npm run build` are executed to ensure that everything compiles/runs correctly.
7. **Before quoting any result, read `docs/research/CURRENT.md`; run `make check-docs` before committing prose that quotes a number.** A figure that CURRENT.md lists as withdrawn may only be quoted alongside its replacement.

## Research record (mandatory)

- Any experiment, benchmark, baseline, ablation, or evaluation run MUST be
  recorded under `docs/research/experiments/` following
  [`docs/research/AGENT_INSTRUCTIONS.md`](../../research/AGENT_INSTRUCTIONS.md).
  Scaffold it with `make new-experiment SLUG=<slug>` — never by hand.
- Never report a metric in chat or a commit message without also writing it to
  the corresponding `manifest.yaml` and `RESULTS.md`. A number that exists only
  in a chat log does not exist.
- Never hand-edit a figure. Never hardcode a number in a plotting script —
  figures read from `data/metrics.json`.
- Failed and abandoned runs are recorded, not deleted. Set `status: failed` or
  `superseded` and use `docs/research/templates/negative_result.md`.
- Do not fabricate manifest fields. `unknown` is a valid value and a guess is
  not; three known fields beat ten invented ones.
- Every claim in `docs/research/CLAIMS.md` that an experiment supports must be
  referenced from that experiment's `supports_claims`. The validator enforces it.
- If asked to "just quickly check" a number, still create the experiment folder.
- Run `make validate-research` before committing anything under `docs/research/`.

## Commands

The complete, verified command reference is [`docs/commands.md`](../../commands.md).
The subset below is what most changes need.

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
python3 setup.py              # one-shot setup wizard: env -> .env -> data -> web -> launch
python app.py                 # web workbench: FastAPI api/ + Next.js web/ (--prod for production)
cd web && npm run dev         # web app alone (expects the API on :16501)

# Golden-eval harness (decoupled run -> judge -> report over the golden set)
uv run main.py --golden-eval --agentic --llm                # THE single command: run every question
                                                            # through the real LLM agentic pipeline
                                                            # (16-way concurrent), then LLM-grade each
uv run main.py --golden-eval --stage run --set attack --limit 3   # one stage at a time (artifacts persist)
uv run main.py --golden-eval --stage judge --llm --concurrency 16 # re-grade persisted answers only

# Build (required after webfront changes)
cd web && npm run build

# Test
uv run python -m pytest utils/kg_builder/tests/
uv run python -m pytest utils/graph_loader/tests/
uv run python -m pytest api/tests/    # FastAPI service contract tests
cd web && npm test            # webfront fixture/adapter contract tests (Vitest)

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
| Portfolio README | `docs/skills/portfolio-readme/SKILL.md` |

Implementation plans go in `docs/plans/` when needed.

Every skill listed above has exactly one pointer in each of `.claude/skills/`,
`.agents/skills/`, and `.cursor/rules/`, and the pointers contain no
instructions of their own. Parity is enforced by
`utils/specialists/tests/test_docs_contracts.py`.
