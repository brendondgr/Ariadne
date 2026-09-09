# Command Reference

Every command Ariadne exposes, verified against `setup.py`, `app.py`, and
`main.py`'s argument parser. For what the artifacts contain and where they land,
see [`structure.md`](structure.md).

All settings come from a single git-ignored `.env` (`cp .env.example .env`);
every value defaults to current behavior.

## Setup

| Command | What it does |
|---|---|
| `python3 setup.py` | Interactive five-step wizard: prerequisites → `.env` → inference endpoint → data pipeline → web deps, then launches the workbench |
| `python3 setup.py --yes` | Same, non-interactive, accepting every default |
| `python3 setup.py --no-launch` | Set everything up, print the commands, don't launch |
| `python3 setup.py --fresh` | Re-run steps already marked done |
| `python3 setup.py --skip-sync\|--skip-env\|--skip-inference\|--skip-data\|--skip-web` | Skip an individual step |
| `python3 setup.py --no-browser` | Launch without opening a browser tab |
| `python3 setup.py --prod` | Launch the workbench in production mode (`app.py --prod`) |

Manual equivalent:

```bash
uv sync
cp .env.example .env
cd web && npm install
```

## Data pipeline

| Command | What it does |
|---|---|
| `uv run main.py --download` | Download MITRE ATT&CK Enterprise STIX and CAPEC XML |
| `uv run main.py --download --force` | Re-download even if the files are present |
| `uv run main.py --pin` | Record sha256 checksums of the raw files already on disk (no re-download) |
| `uv run main.py --build attack\|capec\|all` | Build canonical artifacts + backend exports; no database writes |
| `uv run main.py --build all --dry-run` | Preview the build without writing files |

## Graph databases

| Command | What it does |
|---|---|
| `uv run main.py --docker start` | Start the pinned local Neo4j + Gremlin stack |
| `uv run main.py --docker stop\|status` | Stop the stack / show what is running |
| `uv run main.py --docker start --neo4j-version X --gremlin-version Y` | Override the pinned image versions |
| `uv run main.py --graph health` | Ping both backends; no `--dataset` needed |
| `uv run main.py --dataset attack --graph neo4j\|gremlin\|all` | Load ATT&CK into a backend |
| `uv run main.py --dataset capec --graph gremlin` | Load CAPEC into Gremlin (its primary runtime backend) |
| `uv run main.py --dataset attack --graph verify` | Validate already-loaded data |
| `uv run main.py --dataset attack --graph fixture-qa` | Reconcile raw == manifest == live, plus referential integrity |
| `uv run main.py --graph-stop neo4j\|gremlin\|all` | Stop a backend container without removing it |
| `uv run main.py --neo4j-login` | Write Neo4j credentials into `.env` (`--neo4j-uri/-user/-password` skip the prompts) |

## Everything at once

```bash
uv run main.py --yolo-all
```

Download → build → credential check → Docker → load ATT&CK into Neo4j and CAPEC
into Gremlin → verify. Steps already done are skipped; failures are classified as
stale-state (backup + rebuild), transient (retry with backoff), or needs-human
(surfaced in the summary table rather than crashed on).

## Asking questions

| Command | What it does |
|---|---|
| `uv run main.py --plan "…"` | Probe the live sources and emit the routing plan only |
| `uv run main.py --plan "…" --plan-llm` | Same, using the opt-in LLM drafter instead of the deterministic one |
| `uv run main.py --query "…"` | Plan, then run the specialists over the live graphs and print normalized evidence |
| `uv run main.py --query "…" --query-llm` | Same, with the LLM drafter for the planning stage |

Without `--plan-llm` / `--query-llm`, and with `ARIADNE_LLM_ENABLED` unset, the
whole path is deterministic. The specialists compile card-validated templates
and schema-derived primitives; the only way a model writes a query is the
`SPECIALIST_LLM_QUERY_BUILDER` baseline switch, off by default (see
[`ARCHITECTURE.md`](ARCHITECTURE.md) §5).

## Workbench

| Command | What it does |
|---|---|
| `uv run app.py` | Preflight → FastAPI on `:16501` + Next.js on `:16500` → status board → startup smoke query |
| `uv run app.py --prod` | Production build instead of dev with hot reload |
| `uv run app.py --smoke full` / `--no-smoke` | Run a whole federated query at startup / skip the smoke query |
| `uv run app.py --port N --api-port N --host 0.0.0.0` | Override ports and bind address |
| `uv run app.py --verbose` / `--open` | Show raw child logs / open a browser when ready |
| `uv run app.py --install` / `--skip-install` | Force `npm install` even if `web/node_modules` exists / never run it |
| `cd web && npm run dev` | The web app alone (expects the API on `:16501`) |

## Evaluation

| Command | What it does |
|---|---|
| `uv run main.py --component-eval` | Planner ×4 and specialist ×4 scorers → `docs/evaluation/component-evaluation.{md,json}` |
| `uv run main.py --e2e-eval` | The four end-to-end metrics over the 120-question catalogue → `docs/evaluation/e2e-evaluation.{md,json}` |
| `uv run main.py --e2e-eval --judge` | Same, with the opt-in LLM judge instead of the deterministic proxy |
| `uv run main.py --e2e-eval --no-live` | Skip the scorers that need a live stack |
| `uv run main.py --e2e-generate --e2e-workers 4` | Generate and save answers only; judging is a separate step |
| `uv run main.py --golden-eval --agentic --llm` | The decoupled run → judge → report harness, 16-way concurrent |
| `uv run main.py --golden-eval --stage run --set attack --limit 3` | One stage at a time; artifacts persist between stages |
| `uv run main.py --golden-eval --stage judge --llm --concurrency 16` | Re-grade persisted answers without re-running the pipeline |

The controlled arm experiment behind the standing evaluation record:

```bash
uv run python -m utils.evaluation.experiment_untruncated \
  --arm deterministic --root docs/evaluation/experiments/<name> --workers 4
uv run python -m utils.evaluation.failure_terminus --root <root> --arms <arm>
uv run python -m utils.evaluation.summarize_untruncated --root <root>
```

See [`evaluation/README.md`](evaluation/README.md) for which report is current.

## Research record (Makefile)

The Makefile exists for the research record only; application commands stay on
`main.py` / `app.py`.

| Command | What it does |
|---|---|
| `make new-experiment SLUG=<slug>` | Scaffold an experiment folder with the next ID and the current commit |
| `make validate-research` | Validate every experiment: schema, linkage, figures, pointers |
| `make index` | Regenerate `docs/research/INDEX.md` and `CURRENT.md` from the manifests |
| `make figures` | Regenerate every promoted figure and table |
| `make test-research` | The research-record test suite |
| `make verify-paper-numbers` | Review list: every number in the paper, traced / untraced / stale |
| `make check-docs` | Gate: no prose document quotes a withdrawn or superseded figure |
| `make check-record` | The full gate: validator, index freshness, stale-quote scan, docs contracts |

## Tests and builds

```bash
uv run python -m pytest utils/kg_builder/tests/
uv run python -m pytest utils/graph_loader/tests/
uv run python -m pytest utils/specialists/tests/
uv run python -m pytest api/tests/          # FastAPI contract tests
cd web && npm test                          # Vitest adapter/fixture contracts
cd web && npm run build                     # required after any webfront change
cd web && npm run lint
```

Live suites are marked `live`/`integration` and skip themselves when the Docker
stack is unreachable.
