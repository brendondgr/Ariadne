# Repository Structure

A map of the Ariadne repository: one line per directory or notable file. How
the pipeline works is in [`ARCHITECTURE.md`](ARCHITECTURE.md); every command is
in [`commands.md`](commands.md); what each number means is in
[`research/CURRENT.md`](research/CURRENT.md).

## Start here

| Need | Location |
|---|---|
| Project overview and quick start | [`README.md`](../README.md) |
| How the pipeline works, stage by stage | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| Every CLI command | [`docs/commands.md`](commands.md) |
| Roadmap and evaluation criteria | [`docs/goals.md`](goals.md) |
| Current figures and the claims ledger | [`docs/research/CURRENT.md`](research/CURRENT.md), [`docs/research/CLAIMS.md`](research/CLAIMS.md) |
| Change history | [`docs/changelog.jsonl`](changelog.jsonl) (how to read it: [`CHANGELOG.md`](CHANGELOG.md)) |
| Agent rules (read before coding) | [`docs/skills/global-project-rules/SKILL.md`](skills/global-project-rules/SKILL.md) |

## Root

| Path | What it is |
|---|---|
| `README.md`, `CONTRIBUTING.md`, `LICENSE`, `NOTICE` | Overview; contributor workflow; licence; MITRE attribution and pinned dataset versions |
| `main.py` | CLI: `--download`, `--build`, `--docker`, `--dataset`/`--graph`, `--plan`/`--query`, the evaluation entry points |
| `app.py` | Workbench launcher: preflight → FastAPI + Next.js → status board → smoke query |
| `setup.py` | One-command setup wizard (thin shim over `utils/setup_wizard/`) |
| `Makefile` | Research-record targets only (`validate-research`, `index`, `figures`, `check-docs`, `check-record`) |
| `.env.example` | The single configuration template; copy to a git-ignored `.env` |
| `langgraph.json` | LangGraph Studio entry (`langgraph dev` → `utils/orchestration/studio.py`) |
| `pyproject.toml`, `uv.lock`, `.python-version` | Python 3.13 project, managed with `uv` |
| `api/` | FastAPI service wrapping `utils/` for the web UI |
| `data/` | Raw downloads, canonical artifacts, exports, source cards (mostly gitignored); `data-identity/`, `data-merged/`, `data-tri/` are experiment fixtures |
| `docker/` | Neo4j + Gremlin Compose stack, plus the `neo4j-merged` and `neo4j-identity` experiment profiles |
| `docs/` | Documentation, research record, skills, plans, prompts, pitch material |
| `images/` | Logos used by the README |
| `logs/` | Sequential job logs written by `main.py` (gitignored) |
| `scripts/` | 83 one-off research scripts (`*.py`, `*.sh`): experiment drivers, overnight sweeps, report generators, `verify_paper_numbers.py`, `validate_research.py`, `new_experiment.py` |
| `utils/` | All Python code, by domain (below) |
| `web/` | Analyst workbench UI (Next.js App Router) |
| `.claude/`, `.agents/`, `.cursor/` | Agent tool folders — **pointers only**; canonical instructions live under `docs/skills/` |

## `docs/`

| Path | Contents |
|---|---|
| `ARCHITECTURE.md` | The pipeline stage by stage, with the env vars each stage actually reads |
| `goals.md` | Roadmap, evaluation criteria, deliverables |
| `commands.md` | Every command on `setup.py`, `app.py`, `main.py` and the Makefile |
| `source_cards.md` | Source-card format: three-layer lifecycle, field reference, authoring checklist |
| `agent-interfaces.md` | The four integration-frozen seams as public contracts |
| `query-safety.md` | The safety model by enforcement point, and the adversarial audit |
| `migration-guide.md` | Adding a new query-language specialist (openCypher/GQL) |
| `structure.md` | This file |
| `CHANGELOG.md`, `changelog.jsonl` | How to read the log; the log itself (one JSON line per change) |
| `research/` | **The live research record**: `CURRENT.md`, `CLAIMS.md`, `DECISIONS.md`, `OPEN_QUESTIONS.md`, `RELATED_WORK.md`, `INDEX.md`, `experiments/EXP-*/` (manifest, protocol, results per experiment), `paper/`, `figures/`, `tables/`, `reports/`, dated audits |
| `evaluation/` | Raw evaluation artifacts (answers, banks, per-arm runs); [`evaluation/README.md`](evaluation/README.md) says which are current and which are superseded |
| `plans/` | Dated implementation plans, kept as a historical record; `plans/robustness/` is the parallel-brief set |
| `prompts/` | Saved prompts for positioning and venue-selection sweeps |
| `pitch/` | October pitch plan, deck, script and preview |
| `proposal/` | The funded grant proposal |
| `assets/` | `architecture.svg` |
| `skills/` | Canonical agent instructions (global rules, planner, UI, design, accessibility) |

## `utils/`

| Package | Role |
|---|---|
| `config.py`, `llm/`, `llm_sampling.py` | `.env` loading and helpers; the single `ARIADNE_LLM_*` group with per-stage overrides; sampling params |
| `download/` | ATT&CK and CAPEC downloader with sha256 snapshot pinning |
| `kg_builder/` | STIX/XML → canonical graph artifacts → Neo4j/Gremlin exports; source-card generation (`registry.py`) |
| `graph_loader/` | Runtime load, verify, health; `fixture_qa/` reconciles raw == manifest == live |
| `infrastructure/` | Docker Compose lifecycle |
| `planner/` | Cards, discovery, intent, canonicalize (`canonical.py`, `rewrite_llm.py`), drafters, gate, agent, join keys, `card_enrichment.py`, planner evaluation |
| `specialists/` | Shared scaffold + Cypher and Gremlin swap points, `primitives/` (`describe`, `expand`; the other generic identifiers — `generic_walk`, `generic_chain`, `generic_bridge`, `generic_neighbors` — are emitted by the builders), `schema/` registry, `llm_builder.py` baseline, federation, `evalset/` banks and scorers, `pipeline.py` shim |
| `synthesis/` | Deterministic composer, verifier, reconciler, narrator, hybrid composer |
| `orchestration/` | The LangGraph pipeline graph (`main.py`), state, planner/specialists/assess/synthesis subgraphs, `studio.py` |
| `conversation/` | The conversational graph wrapping the pipeline (router, extraction, validation, answer, naming, SQLite persistence) |
| `evaluation/` | Component and end-to-end scorers, LLM judge, golden-eval harness, external benchmarks, arm experiment runners |
| `research_record/` | Manifest schema, validator, index generator and hashing behind the Makefile targets |
| `launcher/`, `setup_wizard/` | `app.py` phases (preflight, supervise, display, smoke); the setup wizard steps |
| `recovery.py`, `yolo.py`, `neo4j_login.py` | Backup/retry primitives; the `--yolo-all` runner; the `--neo4j-login` helper |

Tests live beside each package (`utils/<pkg>/tests/`); live suites are marked
`live`/`integration` and skip when the Docker stack is unreachable. The golden
banks and their verification report are under `utils/specialists/tests/golden/`.

## `api/` and `web/`

| Path | Contents |
|---|---|
| `api/main.py`, `api/models.py` | FastAPI app and Pydantic models |
| `api/services/` | `health`, `config`, `llm_models`, `query` (SSE over `iter_pipeline`), `conversations`, `graph`, `evaluation`, `infra`, `heartbeat` |
| `api/tests/` | Service contract tests |
| `web/app/` | Next.js App Router entry (`layout.tsx`, `page.tsx`, `globals.css`) |
| `web/components/` | `workbench`, `shell`, `header`, `left`, `center`, `inspector`, `graph`, `evaluation`, `settings`, `ui` |
| `web/lib/` | API client, SSE run machine, adapters, fixtures, types; `__tests__/` (Vitest) |

## Generated artifacts (gitignored)

| Path | Produced by |
|---|---|
| `data/raw/`, `data/versions.json` | `main.py --download` / `--pin` |
| `data/processed/`, `data/graphs/<dataset>/{canonical,exports,runtime}/` | `main.py --build` and the graph loader |
| `data/source_cards/` | `main.py --build` |
| `data/conversations.sqlite3` | The conversation layer |
| `docs/evaluation/golden/` | `main.py --golden-eval` |
| `logs/` | Every `main.py` job |
