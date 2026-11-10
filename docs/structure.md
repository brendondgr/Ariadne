# Repository Structure

A map of the Ariadne repository: one line per directory or notable file. How
the pipeline works is in [`ARCHITECTURE.md`](ARCHITECTURE.md); every command is
in [`commands.md`](commands.md); what each number means is in
[`research/CURRENT.md`](research/CURRENT.md).

The documentation is split into two eras at the October 2026 pitch: **era 1**,
the Innovation Challenge (June 8 to October 19, 2026, finished), and **era 2**,
the expansion (from 2026-10-20). The front door is [`README.md`](README.md).

## Start here

| Need | Location |
|---|---|
| Project overview and quick start | [`README.md`](../README.md) |
| The two eras: what we started with, where we're going | [`docs/README.md`](README.md) → [`era-1-challenge/`](era-1-challenge/README.md), [`era-2-expansion/`](era-2-expansion/README.md) |
| How the pipeline works, stage by stage | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| Every CLI command | [`docs/commands.md`](commands.md) |
| Year-one roadmap and evaluation criteria (era 1, complete) | [`docs/goals.md`](goals.md) |
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
| `data/` | Raw downloads, canonical artifacts, exports, source cards (mostly gitignored); `data/identity/` holds the identity-graph experiment (EXP-2026-08-011, which cites its pre-2026-10-15 path `data-identity/`); `data-merged/` and `data-tri/` are local, regenerable experiment fixtures |
| `docker/` | Neo4j + Gremlin Compose stack, plus the `neo4j-merged` and `neo4j-identity` experiment profiles |
| `docs/` | Documentation: era 1 (`era-1-challenge/`), era 2 (`era-2-expansion/`), the reference set both use, the research record, skills (below) |
| `images/` | Logos, the README banner, and the workbench screenshot |
| `logs/` | Sequential job logs written by `main.py` (gitignored) |
| `scripts/` | 83 one-off research scripts (`*.py`, `*.sh`): experiment drivers, overnight sweeps, report generators, `verify_paper_numbers.py`, `validate_research.py`, `new_experiment.py`; `scripts/judging/` holds the model-judge workflow scripts (formerly a top-level `scratchpad/`) |
| `utils/` | All Python code, by domain (below) |
| `web/` | Analyst workbench UI (Next.js App Router) |
| `.claude/`, `.agents/` | Agent tool folders — **pointers only**; canonical instructions live under `docs/skills/` |

## `docs/`

The front door is [`README.md`](README.md). Every entry below is marked by era.

**Reference for both eras** (timeless)

| Path | Contents |
|---|---|
| `README.md` | The front door: the two eras side by side, then this reference set |
| `ARCHITECTURE.md` | The pipeline stage by stage, with the env vars each stage actually reads |
| `commands.md` | Every command on `setup.py`, `app.py`, `main.py` and the Makefile |
| `source_cards.md` | Source-card format: three-layer lifecycle, field reference, authoring checklist |
| `agent-interfaces.md` | The four integration-frozen seams as public contracts |
| `query-safety.md` | The safety model by enforcement point, and the adversarial audit |
| `migration-guide.md` | Adding a new query-language specialist (openCypher/GQL) |
| `structure.md` | This file |
| `CHANGELOG.md`, `changelog.jsonl` | How to read the log; the log itself (one JSON line per change, both eras) |
| `assets/` | `architecture.svg` |
| `skills/` | Canonical agent instructions (global rules, planner, UI, design, accessibility) |

**Era 1 — the Innovation Challenge, finished** (June 8 to October 19, 2026)

| Path | Contents |
|---|---|
| `era-1-challenge/` | Its README lists everything from era 1 that is kept in this repository |
| `goals.md` | The year-one roadmap, evaluation criteria and deliverables; every row done |
| `RESULTS.md` | What was measured, its limits, and how to reproduce it — the research detail moved out of the README |
| `plans/` | Dated implementation plans, 2026-08-05 to 2026-09-16, closed; `plans/robustness/` is the parallel-brief set. Stays here because experiments, scripts and code cite it |
| `evaluation/` | Raw evaluation artifacts (answers, banks, per-arm runs), hash-pinned by the experiments; [`evaluation/README.md`](evaluation/README.md) says which are current and which are superseded |

**Era 2 — the expansion, current** (from 2026-10-20)

| Path | Contents |
|---|---|
| `era-2-expansion/` | The goal, the figures it starts from and the operator's requirements (`README.md`) |

**Shared by both eras**

| Path | Contents |
|---|---|
| `research/` | **The live research record**: `CURRENT.md`, `CLAIMS.md`, `DECISIONS.md`, `OPEN_QUESTIONS.md`, `RELATED_WORK.md`, `INDEX.md`, `experiments/EXP-*/` (manifest, protocol, results per experiment), `figures/`, `tables/`, `reports/`, dated audits. Its README says which parts are era 1 (experiments to `EXP-2026-09-029`, reports to 2026-09-14) and which era 2 |

### Moved paths

Dated records (plans, experiments, audits, the changelog) keep citing the paths that existed
when they were written. These are the moves since then:

| Moved on | From | To |
|---|---|---|
| 2026-11-10 | docs/era-1-challenge/pitch/, showcase/, proposal.md; docs/era-2-expansion/proposals/, decision-model-tests.md; docs/prompts/; docs/research/paper/; docs/research/top-tier-programme-2026-09.md; docs/REORGANIZATION-2026-10.md; the publication and era-2 plans; the novelty-audit and agentic-loop reports | Out of this repository, to private storage (see `AGENTS.md`) |
| 2026-11-10 | docs/research/reports/2026-10-26-agentic-loop/probe/ | `docs/research/reports/2026-10-26-latency-probe/` |
| 2026-10-26 | docs/expansion/ | `docs/era-2-expansion/` |
| 2026-10-15 | scratchpad/ | `scripts/judging/` |
| 2026-10-15 | data-identity/ | `data/identity/` |

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
