# Plan — One-Command Setup Hardening + README Restructure

## 1. Introduction

Ariadne already ships a two-stage `setup.py` wizard (stage 1 bootstraps `uv`; stage 2,
`utils/setup_wizard/`, runs prerequisites → `.env` → data pipeline → web deps → launch).
This plan closes the gap between that wizard and the user's requested "single command that
sets up the entire system": it promotes **local-inference-server setup** to a first-class,
*verified* wizard step (today the LLM endpoint is only a buried sub-prompt inside `.env`
customization, and nothing probes whether the endpoint is actually reachable), and it makes
the wizard finish by **printing a copy-paste command cheat-sheet** — start the inference
server + Docker containers, trigger a query through `main.py`, or launch the web workbench —
rather than silently exec-ing `app.py`.

The second half restructures `README.md`: a **Quick Start** block moves to the very top,
the standalone **Overview** section is merged into the opening introduction, and the body is
made scannable with tables (a command cheat-sheet mirroring the wizard, a prerequisites
table). The approach reuses existing machinery throughout — `_tcp_up` for liveness,
`set_env_values`/`env_str` for `.env` writes, the `describe → detect → run` step contract —
so the wizard orchestrates and never reimplements. All work happens in an isolated worktree,
is validated with the hermetic wizard test suite, committed per step (no push), then merged
to local `main`.

## 2. Gaps & Unanswered Questions

- **What is "the server for local inference sync"?** Resolved from the code: it is the
  external, user-provided **OpenAI-compatible LLM endpoint** (default `http://localhost:9090/v1`,
  model `default-model`) consumed by the five `*_LLM_*` groups (planner, specialist, synthesis,
  conversation, eval). No repo component *launches* it; the pipeline degrades to deterministic
  drafters when it is absent. *Assumption:* setup.py's job is to **configure** the endpoint in
  `.env` and **probe/verify** ("sync") its reachability — not to install or serve a model. The
  cheat-sheet reminds the user to start their own server.
- **Should the wizard still auto-launch the workbench?** The user wants copy-paste commands as
  the deliverable, but the current one-command-to-running-workbench flow is valuable. *Assumption:*
  do both — always print the cheat-sheet on success, then keep the existing launch hand-off
  (default launches; `--no-launch` prints and stops). No regression to the advertised flow.
- **Is an unreachable inference endpoint a setup failure?** *Assumption:* no. The step is
  `required = False` and a down/unconfigured endpoint is a warning with remediation, never a
  hard stop — matching the pipeline's graceful degradation.
- **README audience.** *Assumption:* keep it a project/portfolio README (funded research
  context, PI/team, roadmap all retained); only restructure and add tables, do not cut content.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Local Inference Sync Server step
- **Locations**: `utils/setup_wizard/steps.py` — new `InferenceServerStep(WizardStep)` plus a
  module-level `probe_inference(base_url) -> tuple[bool, str]` helper (parse host/port via
  `urllib.parse.urlsplit`, reuse `utils.yolo._tcp_up` for liveness, then stdlib `urllib.request`
  GET `<base_url>/models` for a model count). Factor the LLM enable/config block **out of**
  `customize_env` into this step so it owns endpoint config end-to-end. `utils/setup_wizard/__init__.py`
  — insert the step into the `steps` list after `EnvStep`, before `DataStep`.
- **Rationale**: the user names inference-server setup as a distinct phase; it must be its own
  describe/detect/run step and, crucially, *verify* the endpoint (the "sync") instead of writing
  a URL blindly. Placing it after `.env` (needs the file to exist) and before data matches the
  user's stated order (env → inference → data).
- **Action**: Undergo the verification/tests/validation process for this phase (new hermetic
  tests for `probe_inference` with a monkeypatched `_tcp_up`/urlopen, and for the step's
  detect/run enabling path). Once validated, commit to GitHub — no push — stating: Setup
  One-Command (1/3) Complete: Added a verified local-inference-server wizard step (configure the
  OpenAI-compatible endpoint across all five LLM groups, then probe reachability + model list).

### Step 2: Copy-paste command cheat-sheet
- **Locations**: `utils/setup_wizard/__init__.py` — new `print_next_commands(ui, *, llm_enabled,
  web_port, api_port)` printing a grouped panel (start inference server [only if `llm_enabled`] →
  `uv run main.py --docker start` → `uv run main.py --query "…"` [`--query-llm` when LLM on] →
  `uv run app.py`). Call it from `main()` on all-green, before `_launch`; simplify `_launch` so
  `--no-launch` just returns (cheat-sheet already printed). Derive `llm_enabled` from
  `env_str("PLANNER_LLM_ENABLED")`.
- **Rationale**: the user's core ask — "give the commands to copy and paste to start the server
  and docker containers … trigger a query through the main python file or load up the web
  server." Printing it unconditionally on success makes the deliverable explicit whether or not
  the user opts to auto-launch.
- **Action**: Undergo the verification/tests/validation process for this phase (test that the
  cheat-sheet lists docker/query/web commands and gates the inference-server line on
  `llm_enabled`; re-run full wizard suite). Once validated, commit to GitHub — no push —
  stating: Setup One-Command (2/3) Complete: Wizard now ends by printing a copy-paste command
  cheat-sheet (inference server, Docker, `main.py --query`, web workbench).

### Step 3: README restructure
- **Locations**: `README.md` — add a top **Quick Start** section (the one command + a
  prerequisites table + a command cheat-sheet table mirroring Step 2); merge the standalone
  **Overview** section into the opening intro (title tagline + funding + overview become one
  cohesive lead); keep Architecture / Tech Stack / Key Features / Challenges / Status /
  Documentation / Team / Repository Layout / Roadmap, tightening to tables where it improves
  scannability. Update `docs/structure.md` only if it references the removed section anchor.
- **Rationale**: the user wants setup steps at the top, the intro and overview combined, and a
  more structured, table-driven document.
- **Action**: Undergo the verification/tests/validation process for this phase (Markdown link
  check — every relative link resolves; visual read for structure). Once validated, commit to
  GitHub — no push — stating: Setup One-Command (3/3) Complete: README restructured — top Quick
  Start with prerequisites + command tables, Overview merged into the intro, table-driven body.

### Step 4: Merge to main
- **Locations**: the worktree branch `worktree-setup-onecommand-readme` → local `main`.
- **Rationale**: task step 5 — land the isolated work on `main` once everything is green; never
  `git add -A` (symlink noise), only explicit files; no push (user pushes manually).
- **Action**: Full hermetic regression (`uv run python -m pytest utils/setup_wizard/`), confirm
  main has not moved incompatibly, fast-forward/merge, re-run tests on `main`.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Inference-server step | `InferenceServerStep` + `probe_inference` helper; LLM config moved out of `customize_env` | `utils/setup_wizard/steps.py` |
| Step wiring | Insert inference step after `.env`, before data | `utils/setup_wizard/__init__.py` |
| Command cheat-sheet | `print_next_commands` + `main()`/`_launch` wiring | `utils/setup_wizard/__init__.py` |
| Wizard unit tests | Probe (up/down/model-count), step detect/run, cheat-sheet contents + LLM gating | `utils/setup_wizard/tests/test_steps.py` |
| README | Top Quick Start (prereqs + command tables), Overview merged into intro, table-driven body | `README.md` |
| Changelog entries | One entry per step | `docs/changelog.jsonl` |
| Plan | This document | `docs/plans/setup-onecommand-and-readme-plan.md` |
