# Plan: `--yolo-all` Single-Command Pipeline

## 1. Introduction

The project currently requires the user to run six or more separate commands to
go from a fresh checkout to a fully-loaded, verified graph stack. This plan adds
a single `--yolo-all` flag to `main.py` that orchestrates the entire pipeline
end-to-end in one invocation: download datasets → build canonical artifacts →
configure credentials (only if unconfigured) → start Docker infrastructure →
load ATT&CK into Neo4j and CAPEC into Gremlin → verify both graphs are live.

Each step runs sequentially and its outcome is captured in a `StepResult`. At
the end (and with a running prefix line as each step completes), a clean
box-drawing summary table is printed to stdout so the user can scan the entire
run at a glance. Failures are surfaced per-step; the runner does not abort on
non-critical failures so the table always shows the full picture.

---

## 2. Gaps & Unanswered Questions

- **Credential detection heuristic**: "configured already" means `NEO4J_PASSWORD`
  in the environment differs from the compiled-in default (`password`). If it
  matches the default the step is marked *Skipped (using defaults)* — no
  interactive prompt is shown, keeping `--yolo-all` fully non-interactive.
  *Assumption*: this is the correct signal; the user can always run
  `--neo4j-login` afterwards to change it.

- **Step failure policy**: Download, build, and Docker-start failures abort the
  remaining pipeline (nothing to load). Load/verify failures record the error
  but do not abort the other backend. *Assumption*: this is the right split.

- **Existing data / already-running stack**: The runner checks whether artifacts
  and containers already exist before running each phase, so re-running
  `--yolo-all` on a warm environment is fast (most steps report *Skipped*).

- **`rich` / colour libraries**: The project has no `rich` dependency. The
  summary table is rendered with plain Unicode box-drawing characters so no new
  dependency is required.

---

## 3. Hierarchical Step-by-Step Instructions

### Step 1 — Scaffold `utils/yolo.py` with data structures and table renderer

- **Locations**: `utils/yolo.py` (new file)
- **Rationale**: Keeping all orchestration logic out of `main.py` prevents that
  file from ballooning and lets the runner be unit-tested independently.
- **What to add**:
  - `StepStatus` literal type: `"ok"`, `"skipped"`, `"failed"`, `"running"`
  - `StepResult` dataclass: `name`, `status: StepStatus`, `detail: str`,
    `duration_s: float`
  - `print_step_line(result)` — prints one prefix line like
    `  ✓ Download Datasets (2.1s) — ATT&CK v19.0, CAPEC v3.9`
  - `print_summary_table(results)` — renders the full Unicode box-drawing table
    to stdout after all steps complete
  - `YoloRunner` class skeleton with a `run() -> list[StepResult]` entry point
    and one private method stub per pipeline step (7 total)

> *Action: Validate the file imports cleanly (`uv run python -c "from utils.yolo import YoloRunner"`), then push: Yolo-All (1/4) Complete: Scaffolded utils/yolo.py with StepResult, table renderer, and YoloRunner skeleton.*

---

### Step 2 — Implement the 7 orchestration methods in `YoloRunner`

- **Locations**: `utils/yolo.py` — seven private methods:
  1. `_step_download()` — Instantiates `DatasetDownloader` and calls
     `download_all()`. Detects already-downloaded files via the downloader's
     existing `force=False` idempotency; reports counts from downloaded datasets.
  2. `_step_build()` — Instantiates `KGBuildRunner` and calls `build_all()`.
     Detects already-built manifests by checking that
     `data/graphs/attack/canonical/manifest.json` and
     `data/graphs/capec/canonical/manifest.json` exist; skips if both present.
  3. `_step_credentials()` — Reads `NEO4J_PASSWORD` from the environment via
     `env_str`. If it equals `DEFAULT_NEO4J_PASSWORD` from
     `utils/graph_loader/config.py`, marks step *Skipped (using defaults)*.
     Otherwise marks *OK (already configured)*. Never prompts.
  4. `_step_docker_start()` — Calls `docker_start()`. Checks running status
     first via `docker_status()` output; skips if both containers are already up.
  5. `_step_load_attack()` — Calls `run_graph_command(dataset="attack",
     graph="neo4j")`. Extracts node/relationship counts from the runtime
     manifest written by the loader and includes them in the detail string.
  6. `_step_load_capec()` — Calls `run_graph_command(dataset="capec",
     graph="gremlin")`. Extracts vertex count from the runtime manifest.
  7. `_step_verify()` — Calls `run_graph_command(dataset="attack",
     graph="verify")` and `run_graph_command(dataset="capec", graph="verify")`
     in sequence. Records pass/fail for each and combines into one detail string.

- **Rationale**: Each method wraps exactly one existing public API call, captures
  timing via `time.monotonic()`, catches expected exceptions into `StepResult`
  with `status="failed"` and the exception message as `detail`, and returns the
  `StepResult`. The `run()` method calls them in order, prints a prefix line
  after each, and enforces the abort policy (steps 1–4 abort on failure; steps
  5–7 do not).

- **Runtime manifest path** (for count extraction):
  `data/graphs/{dataset}/runtime/{backend}/load_manifest.json`

> *Action: Run `uv run main.py --yolo-all` end-to-end in a clean environment and confirm all 7 steps complete or skip with correct statuses and the summary table renders without errors. Push: Yolo-All (2/4) Complete: Implemented all 7 YoloRunner orchestration methods.*

---

### Step 3 — Wire `--yolo-all` into `main.py`

- **Locations**: `main.py` — `main()` function: argument parser section and
  dispatch block
- **Rationale**: The flag needs to appear in the CLI help, set the `job_type`
  for logging, and dispatch to `YoloRunner().run()`.
- **What to add**:
  - In the argument parser, add a new group *Full Pipeline (--yolo-all)* with
    one flag `--yolo-all` (`action="store_true"`) and a one-line description.
  - In the `job_type` determination block, add `elif args.yolo_all: job_type =
    "yolo-all"`.
  - In the dispatch block, add the corresponding `elif args.yolo_all:` branch
    that instantiates `YoloRunner` and calls `run()`, then exits 0 if all
    non-skipped steps have `status="ok"`, or 1 if any step has
    `status="failed"`.
  - Update the `TYPICAL WORKFLOW` epilog to mention `--yolo-all` at the top as
    the single-command shortcut.

> *Action: Run `uv run main.py --help` and confirm `--yolo-all` appears with its description. Run `uv run main.py --yolo-all` and confirm the table prints. Push: Yolo-All (3/4) Complete: Wired --yolo-all into main.py CLI.*

---

### Step 4 — Tests and validation

- **Locations**: `utils/graph_loader/tests/` (existing test directory) — new
  file `test_yolo.py`
- **Rationale**: The runner touches many subsystems; unit tests that mock each
  step function ensure the table renderer, abort policy, and exit-code logic are
  correct without running the full pipeline.
- **What to test**:
  - `print_summary_table` renders without exceptions given a list of mixed-status
    `StepResult` objects.
  - `YoloRunner.run()` aborts after step 1 failure (download) and marks
    steps 2–7 as `"skipped"` in the returned list.
  - Credential detection: `_step_credentials()` returns `"skipped"` when
    `NEO4J_PASSWORD` equals the default, and `"ok"` when overridden.
  - Exit code is 1 when any step is `"failed"`, 0 otherwise.
- **Also validate**: `uv run python -m pytest utils/graph_loader/tests/test_yolo.py` passes.

> *Action: Run the test suite and confirm all new tests pass. Push: Yolo-All (4/4) Complete: Added unit tests for YoloRunner table, abort policy, and credential detection.*

---

## 4. Deliverables Table

| Deliverable | Description | Location |
|---|---|---|
| `utils/yolo.py` | YoloRunner orchestrator, StepResult, table renderer | `utils/yolo.py` |
| `--yolo-all` CLI flag | New argument group wired into main.py dispatch | `main.py` |
| Unit tests | Table renderer, abort policy, credential detection, exit-code logic | `utils/graph_loader/tests/test_yolo.py` |
| Changelog entry | Timestamped entry describing the new feature | `docs/changelog.jsonl` |

### Expected summary table output

```
╔══════════════════════════════════════╤══════════╤═════════════════════════════════════════╗
║ Step                                 │ Status   │ Detail                                  ║
╠══════════════════════════════════════╪══════════╪═════════════════════════════════════════╣
║ 1. Download Datasets                 │ ✓ OK     │ ATT&CK v19.0, CAPEC v3.9                ║
║ 2. Build Artifacts                   │ ✓ OK     │ attack + capec                          ║
║ 3. Configure Credentials             │ — Skipped│ Using defaults (run --neo4j-login)      ║
║ 4. Start Docker Infrastructure       │ ✓ OK     │ Neo4j + Gremlin running                 ║
║ 5. Load ATT&CK → Neo4j               │ ✓ OK     │ 1914 nodes, 21042 relationships (12.3s) ║
║ 6. Load CAPEC → Gremlin              │ ✓ OK     │ 4888 vertices (8.1s)                    ║
║ 7. Verify Graphs                     │ ✓ OK     │ ATT&CK ✓  CAPEC ✓                       ║
╚══════════════════════════════════════╧══════════╧═════════════════════════════════════════╝
  All steps completed successfully.
```
