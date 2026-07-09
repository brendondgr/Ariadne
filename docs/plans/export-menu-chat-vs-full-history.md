# Export Menu: "Chat Only" vs "Full History"

## 1. Introduction

The thread title strip currently has a single **Export chat** action
([ThreadHeader.tsx](../../web/components/center/ThreadHeader.tsx)) that copies the
whole conversation to the clipboard as Markdown via
`buildChatExport()` ([export.ts](../../web/lib/export.ts)). The analyst wants
this turned into an **Export** control that offers two choices:

- **Chat Only** — the existing behavior (question + assistant reply per turn).
- **Full History** — a step-by-step transcript of *what the pipeline did, in
  what order*, for each turn: routing decision, planner stages, each specialist
  query and how many records it returned, sequencing, validation verdict, and
  per-stage timings, followed by the assistant reply.

All the data Full History needs is already on the client. Every turn is a
`WorkbenchRun` ([types.ts:424](../../web/lib/types.ts)) that carries the derived,
UI-ready projections we render elsewhere:

- `route` (`"quick" | "graph"`) and `validation` (`ValidationResult`),
- `plannerStages: PlannerStage[]` — ordered planning stages (`index`, `title`,
  `status`, `summary`),
- `lanes: SpecialistLane[]` — each specialist run (`backend`, `title`, `rows`,
  `ms`, `query`, `records`, `arrival.order`, `task.rationale`),
- `answer.sequencingNotes` and `answer.timings`,
- `reply` — the conversational answer already used by Chat Only.

This means Full History is a pure serializer over data we already hold — no new
API calls, no backend changes. The work is entirely in `web/`.

## 2. Gaps and Unanswered Questions

Resolved with sensible defaults (no human input needed):

- **Output channel** — keep the existing clipboard-copy behavior for both
  options (consistent with today's Export chat; no file-download plumbing
  exists). Assumption accepted.
- **Format** — Markdown for both, matching `buildChatExport`. Full History uses
  nested Markdown (numbered turns, then a "Pipeline" subsection with an ordered
  list). Assumption accepted.
- **Quick turns** — turns routed `quick` (answered from memory) have no
  planner/lane activity; Full History renders "Answered from memory (no graph
  queried)" plus the reply. Assumption accepted.
- **Ordering signal** — planner stages in array order, then specialist lanes
  sorted by `arrival.order` (falling back to array order when arrival is null,
  e.g. demo/legacy turns). Assumption accepted.

No blocking unknowns.

## 3. Implementation Steps

### Phase 1 — `buildFullHistoryExport` serializer (lib, test-first)

**Where:** [web/lib/export.ts](../../web/lib/export.ts),
[web/lib/__tests__/export.test.ts](../../web/lib/__tests__/export.test.ts)

1. Keep `buildChatExport` byte-identical (Chat Only must not change).
2. Add `buildFullHistoryExport(title, runs): string`:
   - Reuse `routeLabel` / `assistantText` helpers.
   - Per turn: `## N. You` + question; a **Pipeline** block:
     - Route line ("Queried the graphs" / "Answered from memory").
     - For graph turns: an ordered list — each planner stage as
       `index. title — status` (+ summary when present), then each specialist
       lane as `backend · title — N records (M ms)` with the query fenced, in
       `arrival.order`.
     - Sequencing notes (if any), validation verdict (`pass`/`insufficient` +
       reason), timings line (if any).
     - For quick turns: a single "Answered from memory (no graph queried)" line.
   - Then `**Assistant** _(route label)_:` + reply text (same as Chat Only).
   - Turns separated by `---`.
3. Add Vitest cases: a graph turn with planner stages + two lanes renders the
   ordered pipeline and record counts; a quick turn renders the memory line and
   no pipeline list; empty-thread and default-title cases mirror the existing
   ones.

**Validate:** `cd web && npm test -- export` (new + existing export specs green).

### Phase 2 — Export dropdown in the thread header

**Where:** [web/components/center/ThreadHeader.tsx](../../web/components/center/ThreadHeader.tsx)

1. Relabel the button **Export** with a caret; on click toggle a small popover
   (reuse the click-away-backdrop + `absolute … z-30` pattern from
   [GraphSearchBar.tsx:235](../../web/components/graph/GraphSearchBar.tsx)).
2. Two menu items: **Chat Only** → `buildChatExport`, **Full History** →
   `buildFullHistoryExport`. Both copy to clipboard and show a transient
   "Copied" confirmation (retain the 1600ms reset), then close the menu.
3. Preserve current a11y/disabled behavior: disabled when `runs.length === 0`,
   `aria-haspopup`/`aria-expanded`, keyboard `Escape` closes, Woven Dusk styling
   consistent with the existing button and the graph dropdown.

**Validate:** `cd web && npm run lint`; `npx tsc --noEmit` shows no *new* errors
(two pre-existing test-file errors are known/allowed per changelog).

### Phase 3 — Build, live check, commit

1. `cd web && npm test` (full Vitest suite green), `npm run lint`, `npm run build`
   (required after any webfront change — Turbopack production build must pass).
2. Live check: launch the workbench on fallback ports
   (`python app.py --port 16600 --api-port 16601`) if the defaults are held by a
   concurrent session; open the UI, run a graph turn + a memory follow-up, open
   **Export → Full History**, paste, and confirm the transcript shows the
   planner stages, specialist queries with record counts, and the reply in order.
   If ports/preview are unavailable, fall back to the component + serializer
   tests as the behavioral proof and note it.
3. Append a `docs/changelog.jsonl` entry (what changed + why).
4. `git add` the explicit changed files and `git commit` (**do not push** — per
   the standing project directive; commit only).

### Phase 4 — Merge to main (if on a worktree)

1. Only when Phases 1–3 are 100% green, merge the worktree branch into `main`.
2. Re-run `cd web && npm test` + `npm run build` post-merge; resolve any conflicts.

## 4. Deliverables

| # | Deliverable | Location | Validation |
|---|-------------|----------|------------|
| 1 | `buildFullHistoryExport` serializer + `buildChatExport` unchanged | `web/lib/export.ts` | `npm test -- export` |
| 2 | Export serializer tests (graph, quick, empty, default title) | `web/lib/__tests__/export.test.ts` | `npm test -- export` |
| 3 | Export dropdown (Chat Only / Full History) | `web/components/center/ThreadHeader.tsx` | `npm run lint`, `tsc --noEmit` |
| 4 | Full webfront gates green | `web/` | `npm test`, `npm run lint`, `npm run build` |
| 5 | Live spot-check of Full History output | running workbench | manual paste check (or test fallback, noted) |
| 6 | Changelog entry | `docs/changelog.jsonl` | present, 2–4 sentences |
| 7 | Committed (not pushed); merged to main if on worktree | git | `git log`, post-merge build green |
