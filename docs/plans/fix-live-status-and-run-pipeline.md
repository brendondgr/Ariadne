# Plan: Fix False "Live" Source Status + Wire the Run Pipeline Button

## 1. Introduction

Two defects in the analyst workbench need fixing. First, the header source pills
("NEO4J", "GREMLIN") report **LIVE at all times** even when the graphs are not
actually loaded. The root cause is that `GET /api/health` uses a **pure TCP
reachability probe** (`api/services/health.py::live_sources`) — it only checks
that the port accepts a socket, not that the graph contains data. Empirically,
with both containers running right now, the TCP probe reports both *live*, while
the content-aware planner probe correctly reports both *down* (neo4j auth
failure, gremlin graph empty at 0 nodes). The fix is to make `/api/health`
content-aware so a backend counts as live only when its graph is genuinely
loaded — otherwise "Dead".

Second, the header **Run Pipeline** button (`web/components/header/RunPipelineButton.tsx`)
is a visual stub with no `onClick` — the backend (`POST /api/admin`, action
`yolo-all` → `YoloRunner().run()`) and client helper (`streamAdmin`) already
exist and work; only the wiring is missing. The fix is to wire the button to
`streamAdmin({ action: "yolo-all" })` behind a confirm guard, streaming progress
and surfacing the result, modeled on the existing `InfraActions` component.

The two fixes are independent and will each ship as their own validated,
committed step (commit-only — this repo's directive is **commit, never push**).

## 2. Gaps & Unanswered Questions

- **Pill wording ("Dead" vs "Down", "running" vs "Live").** The user asked for
  "Dead" when not loaded and "running" when up. *Assumption*: relabel the
  not-loaded state to **DEAD** (the actual bug) and keep the established **LIVE**
  label for the healthy state, since "LIVE" is used across the app, fixtures, and
  tests and reads equivalently to "running". Easy to rename further if desired.
- **What "loaded" means.** *Assumption*: reuse the planner's existing definition —
  reachable AND `node_count >= min_live_nodes` (default 1) AND expected labels
  present. This is the same verdict the real query pipeline trusts, so the header
  cannot disagree with query behavior.
- **Probe cost on a 5s poll.** *Assumption*: reuse one module-level cached planner
  probe so its 5s TTL cache absorbs the 5s frontend poll (≈one real probe per
  cycle), and always fall back to the fast TCP verdict if the content probe errors
  so `/api/health` never raises.
- **Where pipeline progress shows in the compact header.** *Assumption*: a small
  popover log panel anchored under the button (reusing the `InfraActions` console
  styling), plus a running/disabled state and a confirm guard.
- **Branch strategy.** *Assumption*: work on a local branch `fix-live-status-and-pipeline`
  in the main working tree (keeps the gitignored `data/`/`.env` in place), commit
  per step, then merge to `main` locally once fully verified. No push.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Make `/api/health` content-aware (fix the false "Live")

- **Locations**: `api/services/health.py` — rewrite `live_sources()` to fold in a
  content probe. Reuse `utils/planner/agent.py::PlanningAgent.live_sources()` /
  `utils/planner/discovery.py::LiveSourceProbe` (verdict already encodes empty /
  unauthorized / label-missing as not-live with a reason and a `node_count`). Keep
  the existing fast TCP + Docker check to distinguish `starting` (container up,
  port not yet accepting) from `down`, but when the port IS reachable, defer the
  live/down verdict to the content probe and populate `SourceHealth.nodes`.
  Add a module-level cached `PlanningAgent` (lazy singleton) so the probe's 5s TTL
  cache is reused. Map the planner's per-dataset view (attack→neo4j, capec→gremlin)
  onto the per-backend `SourceHealth`. Wrap the content probe so any failure falls
  back to the TCP verdict — the endpoint must never raise.
- **Locations (model)**: `api/services/health.py::SourceHealth` gains a `nodes:
  int | None` field; `api/main.py::get_health` passes `nodes` through to
  `LiveSourceModel` (which already has the field).
- **Rationale**: The header reads `/api/health`; making that endpoint reflect
  real graph-loaded state is the single change that flips the pills to DEAD when
  docker is down OR graphs are unloaded, and to LIVE (with node count) only when
  data is truly present.
- **Validation**: `uv run python -m pytest api/tests/test_health.py` — extend it
  with a case proving "port reachable but graph empty ⇒ down/dead" and that the
  endpoint still never raises. Manual: run the content probe against the live
  containers and confirm both report not-live while empty; if graphs are loaded,
  confirm live with node counts.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: Fix Live Status & Pipeline (1/3) Complete:
  /api/health now reports DEAD unless the graph is actually loaded.

### Step 2: Relabel the not-loaded pill to "DEAD"

- **Locations**: `web/components/header/InfraStatusPill.tsx` — change the `down`
  label in `STATE_LABEL` from "DOWN" to "DEAD" (keep "LIVE"/"STARTING…"). Confirm
  `InfraStatusBar.tsx` polling already flows the new statuses through (no change
  expected).
- **Rationale**: Matches the user's requested wording for the failure state; the
  functional flip was done in Step 1, this is the visible label.
- **Validation**: `cd web && npm run lint` and `cd web && npm test` stay green;
  `cd web && npm run build` compiles (required after any webfront change).
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: Fix Live Status & Pipeline (2/3) Complete:
  header pill reads DEAD when a backend is not loaded.

### Step 3: Wire the Run Pipeline button to the yolo-all pipeline

- **Locations**: `web/components/header/RunPipelineButton.tsx` — convert to a
  client component with `running` state, a confirm guard (mutating op), and an
  `onClick` that calls `streamAdmin({ action: "yolo-all" }, onEvent)` from
  `web/lib/api.ts`, disabling the button and showing progress while it streams;
  surface streamed `log`/`status` lines and the terminal `done` result in a small
  popover console (reuse `CONSOLE_BG`/`SHADOW` from `web/lib/ui.ts`, mirroring
  `web/components/settings/InfraActions.tsx`). No backend or `api.ts` change — the
  endpoint and helper already exist.
- **Rationale**: The only missing link is the frontend handler; wiring it makes
  the header button actually run the full download→build→docker→load→verify
  pipeline and show its progress.
- **Validation**: New `web/components/header/__tests__/RunPipelineButton.test.tsx`
  (Vitest) mocking `streamAdmin` — asserts a click (after confirm) invokes
  `streamAdmin` with `action: "yolo-all"` and renders streamed lines + result.
  `cd web && npm test`, `npm run lint`, `npm run build` all green.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: Fix Live Status & Pipeline (3/3) Complete:
  header Run Pipeline button triggers and streams the yolo-all pipeline.

### Step 4: End-to-end smoke, changelog, merge to main

- **Locations**: `docs/changelog.jsonl` (one entry per step already; add a final
  merge/smoke entry), then `git merge` the branch into `main` locally.
- **Rationale**: Global rules require a green production build and proof the two
  launcher processes compose; the changelog must record every change; the branch
  merges to main only when 100% functional.
- **Validation**: `python app.py` boots both processes; `GET /api/health` through
  the Next proxy reflects real state; clicking Run Pipeline streams logs. Full
  gate: `uv run python -m pytest api/tests/`, `cd web && npm test && npm run lint
  && npm run build`.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit + merge to main stating: Fix Live Status & Pipeline
  (merge) Complete: both fixes verified end-to-end and merged.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Content-aware health service | `live_sources()` reports DEAD unless graph loaded; `nodes` populated; never raises | `api/services/health.py` |
| Health model passthrough | `nodes` carried into the API response | `api/main.py`, `api/services/health.py` |
| Health contract test | Proves reachable-but-empty ⇒ down and no-raise invariant | `api/tests/test_health.py` |
| DEAD pill label | Not-loaded state reads "DEAD" | `web/components/header/InfraStatusPill.tsx` |
| Run Pipeline handler | Button streams `yolo-all` behind a confirm guard | `web/components/header/RunPipelineButton.tsx` |
| Run Pipeline test | Vitest: click ⇒ `streamAdmin({action:"yolo-all"})` + rendered output | `web/components/header/__tests__/RunPipelineButton.test.tsx` |
| Changelog entries | One per step + merge | `docs/changelog.jsonl` |
