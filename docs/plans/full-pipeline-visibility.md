# Plan: Full Evidence-Backed Pipeline Visibility + Multi-Turn Chat

## 1. Introduction

The analyst workbench is already wired to the live backend: `POST /api/query` streams the
real federated pipeline as Server-Sent Events, and the FastAPI layer already emits the
**complete** pipeline payloads — the `plan` event carries `Plan.to_dict()` (including the
planner's iteration `trace`), each `specialist` event carries `SpecialistResult.to_dict()`
(raw Cypher/Gremlin query, every normalized `EvidenceRecord` with `properties`/`related`/
`provenance`, and the 6-step evaluator `traces`), and the `evidence` event carries the full
`FederatedEvidence.to_dict()` (join index + cross-source values). The inspector already has
Trace / Evidence / Join Index / Raw JSON tabs. The problem is **not** the backend or missing
data — it is that the **front end discards most of this richness**: it truncates records
(6 per lane, 200 total), collapses `properties`/`related`/`provenance.query`/timestamps into
a one-line blob, drops the planner iteration history and per-step `reasons`/`detail`, never
shows `skipped`/`unsupported.reason`/`assumptions`, the Raw JSON tab shows only the federated
bundle (not the plan, probe, answer, or the literal event stream), and the chat is **single-run**
(the left rail is a static mock — there is no multi-turn conversation).

This plan makes the workbench a faithful, exhaustive window onto the pipeline `main.py`
exposes: a **multi-turn chat** (each question becomes a retained, re-selectable turn), a
**full trace** (planner iterations + every specialist evaluator step with its reasons and
detail + task metadata + skipped/unsupported), **full evidence** (uncapped records with
expandable complete `properties`/`related` and per-record provenance/query/timestamp), and a
**full raw-JSON surface** (plan, probe, federated evidence, answer, and the literal ordered
SSE event log — the pipeline start-to-finish). It also closes the remaining `main.py`
admin gap (`--graph-stop`, `--yolo-all`). The data already arrives over the wire; this work
is overwhelmingly in `web/` (adapter, view-model types, run/conversation state, inspector +
chat components) plus one small, isolated backend phase for admin completeness.

## 2. Gaps & Unanswered Questions

- **Backend already emits everything needed for visibility.** Confirmed by audit: `plan.to_dict()`,
  `result.to_dict()` (with `query`, `records[]`, `traces[]`), and `evidence.to_dict()` are all on
  the SSE stream. *Assumption*: no query-pipeline backend changes are required for the visibility
  goal — this is a front-end exposure task. Reversible if a missing field surfaces during work.
- **Raw DB responses are not captured anywhere — by design.** The CLI normalizes rows to
  `EvidenceRecord`s and never retains the raw driver response. *Assumption*: "raw JSON" means the
  exact backend `to_dict()` payloads + the literal SSE event log, matching what `main.py` prints
  (`json.dumps(plan.to_dict())`, `json.dumps(evidence.to_dict())`). We do **not** add raw-driver-
  response capture (out of scope, not in the CLI). Marked here so it is a conscious boundary.
- **Evaluator step count.** The CLI audit of `contracts.py` shows 6 real `EvaluatorTrace` steps
  (intake, resolve, gate, execute, assess, normalize); the current UI invents ~8 micro-steps
  including placeholders. *Assumption*: the lane view is re-grounded to the **real** steps actually
  present in `result.traces[]` (whatever the loop emits, including any `handoff`), each rendered
  with its `ok`/`reasons`/`detail` — no invented steps. Implementer reads the live `traces` to fix
  the exact set in Phase 2.
- **Conversation persistence.** *Assumption*: multi-turn history is **client-side, in-memory** for
  the session (an array of `WorkbenchRun` turns in React state). No backend conversation store or
  localStorage is introduced (not requested; the pipeline is stateless per question). Switching
  turns re-renders cached run data; a "New" action starts a fresh thread. A persistent store is a
  clean future extension and is explicitly out of scope.
- **Large evidence lists / performance.** Real queries return hundreds of records (399 in the live
  smoke test). *Assumption*: the Evidence tab renders the full set behind incremental reveal
  ("show more" / capped initial window with a count) and a text filter, rather than a hard 200 cap,
  so nothing is silently dropped while keeping the DOM responsive. Any retained cap is shown with an
  explicit "+N more" affordance — never a silent truncation.
- **`--neo4j-login` coverage.** The Neo4j connection (URI/user/password) is already editable in the
  Settings panel via `PUT /api/config`. *Assumption*: that satisfies the credential capability; we do
  not add a duplicate admin action. The only genuinely-missing `main.py` modes are `--graph-stop`
  and `--yolo-all`, added in Phase 5.
- **Commit/push policy.** The repo's global rule says "commit AND push." The **user has explicitly
  overridden this for this session: commit at every step, do NOT push.** Every step below ends with a
  *local commit only*; the final merge to `main` is also local (not pushed). Human confirmation
  already given — no further intervention needed.

## 3. Hierarchical Step-by-Step Instructions

> Work happens in the git worktree `.claude/worktrees/full-pipeline-visibility` (branch
> `full-pipeline-visibility`), branched from local `main` HEAD (`c220889`). `node_modules` is
> symlinked from the main checkout (identical `package.json`). Each phase appends a
> `docs/changelog.jsonl` entry and runs `npm run build` + `npm run lint` + `npm test` when web files
> change (and `uv run python -m pytest api/tests/` when `api/` changes). Orchestration: Opus (this
> agent) owns the architecture, the shared `types.ts`/`adapt.ts` seams, and verification; isolated
> implementation chunks are delegated to Sonnet sub-agents; the backend phase (5) is file-disjoint
> from the front-end phases and may run concurrently with one of them.

### Step 1: Multi-turn conversation state + raw event/payload capture (the foundation)
- **Locations**: `web/lib/types.ts` (extend `WorkbenchRun` with `events: QueryEvent[]`, `rawPlan`,
  `rawProbe`, `rawAnswer`, `skipped[]`; add a `Conversation`/turn-list shape), `web/lib/runMachine.ts`
  (accumulate the raw ordered `events` and raw payloads per turn; on `submit` create a **new** turn
  instead of replacing the single run), `web/components/workbench/WorkbenchContext.tsx` (hold
  `runs: WorkbenchRun[]` + `activeRunId` + `newConversation()`/`selectRun()` instead of one `run`),
  `web/components/workbench/Workbench.tsx` + `web/components/center/ChatThread.tsx` (render the list
  of turns, each a `UserMessage` + `AnswerCard`, scrollable, newest in view),
  `web/components/left/ConversationsPanel.tsx` + `ConversationItem.tsx` (drive the rail from the real
  turn list; "New" clears to a fresh thread; clicking selects a turn).
- **Rationale**: Everything else (deeper trace/evidence/raw views per turn) hangs off the run object,
  and "full chat interfaces" is the headline gap. Capturing the literal event stream + raw payloads
  here is what makes the Phase 4 "pipeline start-to-finish" view and per-turn raw JSON possible.
  Doing the state refactor first prevents reworking the view phases against a single-run model.
- **Action**: Undergo the verification/tests/validation process for this phase (`npm run build` +
  `npm run lint`; extend `web/lib/__tests__/adapt.test.ts` to assert the run carries `events`/raw
  payloads; with the app running, ask two questions and confirm both turns persist, the rail lists
  them, switching turns shows the right run, and "New" resets). Once validated, **commit locally (do
  NOT push)**: `Pipeline Visibility (1/6) Complete: multi-turn conversation state and raw event/payload capture.`

### Step 2: Full trace depth — planner iterations + real evaluator steps + task metadata
- **Locations**: `web/lib/adapt.ts` (`buildPlannerStages` to surface `Plan.trace` as an iteration
  history with per-iteration drafter/gate_ok/reasons/counts; `buildLane`/micro-step builder re-grounded
  to the **real** `result.traces[]` steps, each carrying `ok`/`reasons`/`detail`; map
  `task.{seed_ids,limits,rationale,entities}`, `evidence.skipped[]`, `plan.unsupported[].reason`,
  `plan.assumptions`), `web/lib/types.ts` (extend `PlannerStage`/`SpecialistLane`/`MicroStep` to carry
  iterations, reasons, detail, task), `web/components/inspector/TraceTab.tsx`, `TraceStage.tsx`,
  `SpecialistLane.tsx`, `MicroStepPill.tsx` (render the planner iteration list; per-step expandable
  reasons + `detail` JSON; a task-metadata block; a skipped/unsupported section).
- **Rationale**: "See the full trace" means the planner's loop history and every specialist evaluator
  checkpoint with *why* it passed/failed and its detail — the data is already in `plan.trace` and
  `result.traces[].{reasons,detail}` but is currently reduced to a single boolean/timing. Re-grounding
  to the real steps removes the invented placeholders so the UI matches the pipeline.
- **Action**: Undergo the verification/tests/validation process for this phase (`npm run build` +
  `npm run lint`; extend the adapter test to assert iteration history + per-step reasons/detail are
  mapped; preview the Trace tab against a live query and confirm iterations, per-step reasons/detail,
  task metadata, and skipped/unsupported all render). Once validated, **commit locally (do NOT push)**:
  `Pipeline Visibility (2/6) Complete: full planner-iteration and specialist-evaluator trace depth.`

### Step 3: Full evidence depth — uncapped records, complete properties/related, per-record provenance
- **Locations**: `web/lib/adapt.ts` (`buildEvidenceRows`/`buildLane` to stop truncating — carry the
  full `properties`, `related[]`, `join_values`, and complete `provenance` incl. `query`, `record_id`,
  `timestamp`; replace the hard 200/6 caps with full data + an explicit reveal count),
  `web/lib/types.ts` (extend `EvidenceRow`/`LaneRecord` with `properties`, `related`, `provenance`),
  `web/components/inspector/EvidenceTab.tsx`, `LaneRecordRow.tsx` (expandable full pretty-JSON per
  record; show provenance backend + the exact query that produced it + timestamp; a text filter and
  incremental "show more" so large result sets stay responsive without silent loss).
- **Rationale**: "Evidence ... from the output" requires the complete normalized record — its full
  properties, adjacency (`related`), and the provenance query/id/timestamp that makes it auditable —
  not a 6-row, one-line-blob preview. Uncapping (with explicit reveal) honors "see the full evidence."
- **Action**: Undergo the verification/tests/validation process for this phase (`npm run build` +
  `npm run lint`; adapter test asserts full properties/provenance are mapped and nothing is silently
  capped; preview the Evidence tab on a live ~399-record query and confirm full records expand, the
  per-record query/timestamp show, filtering works, and the full count is reachable). Once validated,
  **commit locally (do NOT push)**: `Pipeline Visibility (3/6) Complete: uncapped evidence with full properties and per-record provenance.`

### Step 4: Full raw-JSON surface — plan, probe, evidence, answer, and the literal event stream
- **Locations**: `web/components/inspector/RawJsonTab.tsx` (a payload selector switching among **Plan**
  (with `trace`), **Probe / live sources**, **Federated evidence**, **Answer**, and the **Event stream**
  — every SSE event in arrival order, mirroring the CLI start-to-finish; copy-to-clipboard per payload),
  `web/components/inspector/InspectorTabs.tsx` (label/affordance if needed), `web/lib/types.ts`
  (reuse the `events`/raw payloads added in Step 1), optionally `web/components/center/AnswerCard.tsx`
  (the existing "view full evidence JSON" affordance points at the richer tab).
- **Rationale**: "Raw JSON and other information ... the full evidence-backed pipeline from start to
  finish" = exactly what `main.py` prints, plus the ordered event log that shows the pipeline executing
  stage by stage. The event stream is the literal, replayable trace of the run.
- **Action**: Undergo the verification/tests/validation process for this phase (`npm run build` +
  `npm run lint`; preview the Raw JSON tab and confirm each payload (plan/probe/evidence/answer/event
  stream) renders valid JSON, the event stream lists every event in order, and copy works). Once
  validated, **commit locally (do NOT push)**: `Pipeline Visibility (4/6) Complete: multi-payload raw-JSON surface with the literal SSE event stream.`

### Step 5: Admin completeness — `--graph-stop` and `--yolo-all` (everything main.py can do)
- **Locations**: `api/models.py` (add `"graph-stop"`, `"yolo-all"` to `AdminAction`; add a `service`
  target for graph-stop), `api/services/infra.py` (`_dispatch`: `graph-stop` → `docker_stop_service`,
  `yolo-all` → `YoloRunner().run()` streaming logs like the others), `api/tests/test_infra.py` (stubbed
  tests for the two new actions: dispatch + validation + handler cleanup), `web/lib/types.ts`
  (`AdminAction` union + body field), `web/components/settings/InfraActions.tsx` (buttons + a
  neo4j/gremlin/all target selector for graph-stop; clear host-dependency / long-running notice for
  yolo-all).
- **Rationale**: Closes "incorporate every single thing main.py can do" — the only CLI modes not yet
  reachable from the app. File-disjoint from `web/` view phases, so it can run concurrently with an
  earlier front-end phase. Tests keep the SSE contract honest.
- **Action**: Undergo the verification/tests/validation process for this phase (`uv run python -m pytest
  api/tests/ -q` green incl. the new actions; `npm run build` + `npm run lint`; preview the new admin
  buttons stream logs and complete). Once validated, **commit locally (do NOT push)**:
  `Pipeline Visibility (5/6) Complete: graph-stop and yolo-all admin actions across api + UI.`

### Step 6: Docs, full regression, merge to main
- **Locations**: `docs/structure.md` (web section: multi-turn chat + full trace/evidence/raw-event
  surfaces; api section: new admin actions), `docs/skills/global-project-rules/SKILL.md` (only if a
  command changes), `docs/changelog.jsonl` (final entry), this plan referenced from the changelog.
- **Rationale**: Canonical docs must describe the now-complete visibility surface and admin coverage so
  future agents don't reintroduce the truncated/single-run assumptions.
- **Action**: Undergo the full regression for the whole feature (`uv run python -m pytest api/tests/`;
  `cd web && npm test && npm run lint && npm run build`; boot `python app.py` on free ports and confirm
  `/api/health` 200 + a live query streams end-to-end, multiple turns persist, the Trace/Evidence/Raw
  JSON tabs show full depth + the event stream, and an admin action runs). Once validated, **commit
  locally (do NOT push)**, then merge the worktree into `main` with `--no-ff` (resolving any conflicts,
  re-running the regression on `main`): `Pipeline Visibility (6/6) Complete: docs, full regression, merged to main.`

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Multi-turn conversation state | Run array + active turn + new/select actions; raw event & payload capture per turn | `web/components/workbench/WorkbenchContext.tsx`, `web/lib/runMachine.ts`, `web/lib/types.ts` |
| Multi-turn chat UI | Scrollable thread of turns; rail driven by real turns | `web/components/center/ChatThread.tsx`, `web/components/left/ConversationsPanel.tsx`, `ConversationItem.tsx`, `web/components/workbench/Workbench.tsx` |
| Full trace adapter + view | Planner iteration history; real evaluator steps with reasons/detail; task metadata; skipped/unsupported | `web/lib/adapt.ts`, `web/components/inspector/TraceTab.tsx`, `TraceStage.tsx`, `SpecialistLane.tsx`, `MicroStepPill.tsx` |
| Full evidence adapter + view | Uncapped records; complete properties/related; per-record provenance query/timestamp; filter + reveal | `web/lib/adapt.ts`, `web/components/inspector/EvidenceTab.tsx`, `LaneRecordRow.tsx`, `web/lib/types.ts` |
| Multi-payload raw-JSON view | Plan/Probe/Evidence/Answer + literal ordered SSE event stream; copy per payload | `web/components/inspector/RawJsonTab.tsx`, `InspectorTabs.tsx` |
| Admin completeness | `graph-stop` + `yolo-all` actions across api + UI | `api/models.py`, `api/services/infra.py`, `web/components/settings/InfraActions.tsx`, `web/lib/types.ts` |
| **Frontend tests** | Adapter test asserts multi-turn accumulation, planner iterations + per-step reasons/detail, full record properties/provenance, and raw event capture (subset of a real federated bundle) | `web/lib/__tests__/adapt.test.ts` |
| **Backend tests** | Stubbed dispatch/validation/cleanup tests for `graph-stop` + `yolo-all` | `api/tests/test_infra.py` |
| Docs + changelog | Updated structure/rules + one entry per phase | `docs/structure.md`, `docs/skills/global-project-rules/SKILL.md`, `docs/changelog.jsonl` |
