# Step 9 — Live Pipeline Animation Plan

## 1. Introduction

The workbench already streams the real pipeline over SSE, but the *experience* of a live
run undersells what is happening: records pop into a lane all at once with no sense of
arrival order or timing, lanes sit visually inert while their specialist is actually
executing a query, the current phase is signalled only by small breathing dots, and the
event stream itself is visible only after the fact in the Raw JSON tab. The analyst asked
for the opposite: to *watch* the pipeline work — probing, planning, each specialist
starting, records arriving in order, the answer being verified — live and animated, so it
is always evident the system is genuinely working.

The approach adds one small honest signal to the backend (a `specialist-start` SSE event
emitted by the single `iter_pipeline` orchestrator, so the UI can show "now querying
attack, seeded with 18 ids" the moment it is true rather than inferring it), then builds
the visible experience entirely in the web layer: client-side arrival stamping of every
SSE event, a live activity ticker in the chat column narrating each event with elapsed
time, staggered per-record reveal with arrival-order badges in the specialist lanes, a
querying shimmer on lanes that are running but not yet returned, and an explicit animated
phase caption with a ticking elapsed counter. All motion follows the Woven Dusk rule —
animation that *explains* (arrival, order, progress), never decoration — and every live
behavior is gated on the existing `statusOf`/`replaying` machinery so past turns render
statically exactly as today.

## 2. Gaps & Unanswered Questions

- **True per-record arrival times.** The backend returns each specialist's records as one
  batch, so per-record arrival is a presentation choice, not a data fact. *Assumption:*
  stagger the reveal client-side (~40 ms/record, capped) and badge records with their
  **within-result order** (`#1…#N`) plus the result's real arrival time — honest (order
  within a result is the normalizer's real emission order) without inventing timestamps.
- **Lane "running" truth before the first specialist event.** Which lane is executing is
  known client-side only once its event arrives. *Resolution:* the new `specialist-start`
  event makes this exact — emitted by `iter_pipeline` right before each specialist runs,
  carrying sub-question id, source, index, and (for sequenced consumers) seed count.
- **Ticker persistence.** *Assumption:* the ticker streams below the answer skeleton
  during the run and remains afterwards as a collapsed "activity log (N events · X.Xs)"
  disclosure, so the record of what happened stays a click away without cluttering the
  finished answer.
- **Reduced motion.** *Assumption:* respect `prefers-reduced-motion` via Motion's global
  `useReducedMotion` where new continuous animation (ticker pulse, shimmer) is added.
- **Seeded demo turns.** *Assumption:* demo replay keeps working through the same
  status-map mechanism; the new surfaces simply stay empty for demo turns (no fake
  events), matching the existing `events: []` convention.

## 3. Hierarchical Step-by-Step Instructions

> Session directive: commit only, never push. Each step ends with a changelog entry +
> `git commit` on the worktree branch.

### Step 1: `specialist-start` event from the one orchestrator
- **Locations:** `utils/specialists/pipeline.py` (`iter_pipeline` — yield
  `("specialist-start", {sub_question, source, index, total, seed_count, producer})`
  immediately before `specialist.run(...)`, including the dependency-skip path so skips
  are also announced), `api/services/query.py` (map to an SSE frame),
  `api/tests/test_query.py` (event-order contract), `utils/specialists/tests/test_pipeline.py`
  (event-order test), `web/lib/types.ts` (`QueryEvent` union member).
- **Rationale:** The UI can only animate "now querying X" truthfully if the pipeline says
  so when it happens. The orchestrator is the single place to add it, so CLI/API cannot
  diverge; the CLI simply ignores the event. Additive to the SSE contract — the run
  machine ignores unknown events today, so this is backward-compatible.
- **Action:** Undergo the verification/tests/validation process for this phase (backend
  hermetic suites + api contract tests + tsc). Once validated, commit stating: *Live
  Animation (1/5) Complete: pipeline announces each specialist start (with seeding info)
  as an SSE event.*

### Step 2: Arrival stamping + live lane states in the run machine
- **Locations:** `web/lib/runMachine.ts` (stamp every captured event with elapsed-ms at
  arrival; handle `specialist-start` → `lane-<backend>: "running"` + store per-lane
  arrival meta; mark routed lanes "queued" when the plan arrives), `web/lib/types.ts`
  (`StampedQueryEvent` or `receivedMs` on stored events; `LaneArrival` view fields),
  `web/lib/adapt.ts` (thread arrival meta — order index per record, lane arrival elapsed,
  seed info — into `SpecialistLane`/`LaneRecord`), vitest in `web/lib/__tests__/`.
- **Rationale:** Everything the new surfaces render (ticker times, lane arrival captions,
  record order badges) derives from one honest stamping point: the moment the browser
  received each event. Keeping the projection in `adapt.ts` keeps components dumb and the
  logic unit-testable in node.
- **Action:** Undergo the verification/tests/validation process for this phase (vitest +
  tsc + eslint). Once validated, commit stating: *Live Animation (2/5) Complete: run
  machine stamps event arrival and exposes per-lane running/queued states and record
  order.*

### Step 3: Live activity ticker in the chat column
- **Locations:** new `web/lib/ticker.ts` (`describeEvent(event, elapsedMs) → TickerLine`
  — pure, unit-tested: one compact line per event type with accent + mono time),
  new `web/components/center/LiveTicker.tsx` (AnimatePresence-appended lines, auto-scroll,
  breathing caret while streaming; collapses to an "activity log" disclosure after done),
  wire into `web/components/center/AnswerCard.tsx` (render above/with the skeleton while
  `cardReplaying`, collapsed strip once answered), vitest for `describeEvent`.
- **Rationale:** This is the centerpiece of "see what it's doing in real time": a
  terminal-style narration (Woven Dusk console colors, Geist Mono) that appends a line the
  instant each event arrives — probe results with node counts, plan routing, each
  specialist start (with seed counts for sequenced consumers), each result with record
  count and elapsed time, verification outcome. Reuses the arrival stamps from Step 2.
- **Action:** Undergo the verification/tests/validation process for this phase (vitest +
  tsc + eslint + production build). Once validated, commit stating: *Live Animation (3/5)
  Complete: live activity ticker narrates every pipeline event with elapsed times.*

### Step 4: Lane life — querying shimmer, staggered records, arrival badges
- **Locations:** `web/components/inspector/SpecialistLane.tsx` (running state: shimmer
  placeholder rows + "querying <backend>…" mono caption while `lane-*` is running/queued;
  staggered per-record reveal on live arrival via `staggerContainer`/`popIn`, static for
  past turns), `web/components/inspector/LaneRecordRow.tsx` (arrival-order badge `#k`,
  motion-wrapped row), lane header arrival caption ("14 records · +0.9s", seed note for
  sequenced consumers), `web/lib/motion.ts` (shimmer/stagger variants if missing),
  `web/app/globals.css` (shimmer keyframe if CSS-side).
- **Rationale:** The lanes are where "what records were returned, when, and in what
  order" lives. Stagger + order badges make arrival order legible; the shimmer makes the
  gap between "specialist started" and "records arrived" visibly alive instead of inert;
  the caption ties each result to real elapsed time from the arrival stamps.
- **Action:** Undergo the verification/tests/validation process for this phase (vitest +
  tsc + eslint + production build). Once validated, commit stating: *Live Animation (4/5)
  Complete: lanes shimmer while querying and records arrive staggered with order badges
  and arrival times.*

### Step 5: Phase caption + ticking elapsed, live smoke, docs, merge
- **Locations:** `web/components/center/MiniStepper.tsx` (animated phase caption
  crossfading from the `status` events' message during live runs) and/or
  `web/components/inspector/ProgressMeter.tsx` (live ticking elapsed counter via a
  rAF/interval while `replaying`); docs (`docs/structure.md` web section);
  full gates (`uv run pytest utils/ api/`, `cd web && npm test && npm run lint &&
  npm run build`); live verification through `python app.py` — stream the credential-theft
  query and confirm the new SSE event order, then load the page in a preview browser and
  visually confirm the ticker, shimmer, stagger, and phase caption animate during a real
  run; merge worktree into local `main` (no push).
- **Rationale:** An explicit phase caption plus a ticking timer answers "is it working?"
  at a glance even before any evidence arrives; the browser check is the only honest
  validation of *animation* (unit tests can't see motion); closing pattern per repo rules.
- **Action:** Undergo the verification/tests/validation process for this phase (full
  regression + build + live browser smoke). Once validated, commit stating: *Live
  Animation (5/5) Complete: phase caption + live elapsed, full regression green, verified
  animating in the browser, merged to main.*

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| `specialist-start` event | Orchestrator announces each specialist run (+seed info, skips) | `utils/specialists/pipeline.py`, `api/services/query.py` |
| Event contract tests | Updated hermetic order/shape tests incl. the new event | `api/tests/test_query.py`, `utils/specialists/tests/test_pipeline.py` |
| Arrival stamping | Elapsed-ms stamped on every captured SSE event; lane queued/running states | `web/lib/runMachine.ts`, `web/lib/types.ts` |
| Arrival projection | Record order index, lane arrival time, seed captions | `web/lib/adapt.ts` + `web/lib/__tests__/` |
| Ticker helper + tests | Pure `describeEvent` narration lines | `web/lib/ticker.ts`, `web/lib/__tests__/ticker.test.ts` |
| LiveTicker component | Streaming activity log with elapsed times, collapsible after run | `web/components/center/LiveTicker.tsx` |
| Lane liveness | Querying shimmer, staggered record reveal, `#k` arrival badges | `web/components/inspector/SpecialistLane.tsx`, `LaneRecordRow.tsx` |
| Phase caption + timer | Crossfading phase message + ticking elapsed while streaming | `web/components/center/MiniStepper.tsx`, `inspector/ProgressMeter.tsx` |
| Docs + merge | structure.md web section updated; full gates; merged to main | `docs/structure.md`, `docs/changelog.jsonl` |
