# Plan: Ariadne Analyst Workbench Front End (Next.js + Motion)

## 1. Introduction

This plan replaces the entire Ariadne webfront with the three-region **analyst workbench** shown in the provided mockup (`Ariadne Workbench.dc.html`): a header with live infra status pills, a left Conversations rail, a center chat thread with structured Answer Cards, and a right Inspector that renders the agent pipeline step-by-step (Trace / Evidence / Join Index / Raw JSON). The mockup is the visual source of truth; the longer written spec is supporting context for behavior and data shapes.

The approach has two deliberate halves, matching the request. **First**, reproduce the mockup as a fully *compartmentalized* component tree — each region and sub-block is its own reusable React container — so the layout is faithful and reproducible. **Second**, layer **event-based animations** on top using the Motion library, driven by an explicit run-state machine, so that every part animates in response to state events. This makes the UI "animation-ready" for when a live, streaming workflow backend is wired in later: a stage flipping `pending → running → pass` (or a trace stage arriving) is an event the UI already knows how to animate.

Per the confirmed stack decision, `web/` is migrated from React/Vite to **Next.js (App Router) + TypeScript + Tailwind v4 + Motion**, preserving the existing Woven Dusk design tokens and Geist fonts. All work happens in the `worktree-nextjs-workbench-ui` worktree and is merged to `main` only when 100% functional.

## 2. Gaps & Unanswered Questions

- **Framework (resolved):** Next.js App Router was chosen by the user over keeping React/Vite. *Decision recorded; proceeding with Next.js.*
- **Animation library (resolved):** Motion (Framer Motion successor) chosen over CSS-only. *Proceeding with `motion`.*
- **Infra/Data-Sources panel (Pillar A):** The written spec describes a 6-stage infra pipeline panel in the left rail, but the mockup's left rail contains **only Conversations**. *Assumption: reproduce the mockup faithfully (Conversations only). The header's two infra status pills and the "Run Pipeline" button ARE in the mockup and will be built. The full infra-stage panel is flagged as an optional future extension, out of scope for matching the mockup.*
- **Backend / live data:** No streaming API exists yet and the request defers it ("when we eventually start bringing in and implementing a workflow"). *Assumption: this phase is frontend-only. The UI renders typed mock fixtures (the WMI→CAPEC sample from the mockup) and is structured as a pure renderer of trace objects so a real SSE/WebSocket source can replace the fixture later.*
- **Exact trace-object field names:** Mirrored from `docs/planner_agent.md`, `docs/specialist_agents.md`, and `utils/specialists` + `utils/planner` (extracted via a research sub-agent) so TypeScript types match the backend `to_dict()` shapes. *Where a field is ambiguous, the mockup's displayed JSON wins for now and the type is marked accordingly.*
- **Commit/push policy:** The user explicitly instructed **commit but do NOT push**. *This overrides the global rule's "always push" wording. Every phase ends with a local commit; no `git push`. Merge to `main` locally at the end.*
- **Geist fonts:** Next.js ships first-party `Geist` and `Geist_Mono` via `next/font/google`. *Assumption: use `next/font` instead of `@fontsource-variable/geist` for cleaner Next integration; the Woven Dusk token values are unchanged.*

## 3. Hierarchical Step-by-Step Instructions

> Commit wording note: per the user's override, each phase ends by **committing locally (no push)**, not pushing.

### Step 1: Scaffold the Next.js app in `web/` (replace the Vite setup)
- **Locations:** `web/package.json` (scripts → `next dev` / `next build` / `next lint`, deps: `next`, `react`, `react-dom`, `motion`, `tailwindcss`, `@tailwindcss/postcss`), `web/next.config.ts`, `web/tsconfig.json`, `web/postcss.config.mjs`, `web/app/layout.tsx`, `web/app/page.tsx` (temporary empty shell), `web/app/globals.css` (port `index.css` + `tokens.css`), delete `web/vite.config.ts`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, `web/eslint.config.js` (replace with Next ESLint). Keep `web/src/assets/` only if reused.
- **Rationale:** Everything downstream renders inside this app shell. The Woven Dusk tokens, Geist fonts (`next/font`), Tailwind v4 `@theme`, and `shadow-border`/`shadow-card` utilities must be wired into the App Router layout before any component is built, or each component would re-invent styling.
- **Action:** Run `npm install` then `npm run build` and a `npm run dev` smoke test; confirm a blank dark (`#1B2122`) page renders with Geist loaded and no TS/lint errors. Once validated, commit locally (no push): `Workbench UI (1/8) Complete: Migrated web/ to Next.js App Router + Tailwind v4 + Motion with Woven Dusk tokens and Geist fonts.`

### Step 2: Define trace types and the sample fixture
- **Locations:** `web/lib/types.ts` (interfaces: `LiveSource`, `PlanTrace`, `EvaluatorTrace`, `Plan`, `MicroStep`, `SpecialistResult`, `EvidenceRecord`, `JoinCandidate`, `FederatedEvidence`, plus UI enums `StageStatus`, `RunStatus`), `web/lib/fixtures.ts` (the WMI→CAPEC run from the mockup: two specialist lanes, four evidence records, two join candidates, exit 0), `web/lib/conversations.ts` (the sidebar list fixture).
- **Rationale:** The Inspector and Answer Card must be pure functions of trace data so a live backend can later replace the fixture with zero component changes. Types mirroring the backend `to_dict()` keys keep that swap honest.
- **Action:** `npm run build` (type-check passes). Once validated, commit locally (no push): `Workbench UI (2/8) Complete: Added TypeScript trace types mirroring the planner/specialist objects and the WMI→CAPEC sample fixture.`

### Step 3: Build the shell, header, and shared UI primitives (static)
- **Locations:** `web/components/shell/AppShell.tsx` (full-height three-region flex/grid), `web/components/header/HeaderBar.tsx`, `web/components/header/InfraStatusPill.tsx`, `web/components/header/RunPipelineButton.tsx`, `web/components/ui/Pill.tsx`, `web/components/ui/StatusDot.tsx`, `web/components/ui/ThreadGlyph.tsx` (the Ariadne logo SVG), `web/components/ui/CodeBlock.tsx` (mono syntax-tinted block), `web/components/ui/icons.tsx`; wired into `web/app/page.tsx`.
- **Rationale:** The shell fixes the non-scrolling full-height frame and the three internally-scrolling regions; the header and primitives are reused by every later region. Building them first prevents layout churn.
- **Action:** `npm run build`; visually verify via the Preview tool (header pills, wordmark, layout regions) against the mockup. Once validated, commit locally (no push): `Workbench UI (3/8) Complete: Built the app shell, header bar with infra pills, and shared Woven Dusk UI primitives.`

### Step 4: Build the left rail and center chat thread (static)
- **Locations:** `web/components/left/ConversationsPanel.tsx`, `web/components/left/ConversationItem.tsx` (active vs. idle, Plan/Query glyph, time-group headers); `web/components/center/ChatThread.tsx`, `web/components/center/ThreadHeader.tsx`, `web/components/center/UserMessage.tsx`, `web/components/center/AnswerCard.tsx`, `web/components/center/MiniStepper.tsx`, `web/components/center/ProvenanceChip.tsx`, `web/components/center/JoinChip.tsx`, `web/components/center/Composer.tsx` (mode toggle, drafter toggle, send).
- **Rationale:** These are the analyst's primary read/write surfaces. The Answer Card's mini-stepper and provenance chips share state with the Inspector (selected turn / jump-to-stage), so they are built before wiring that cross-panel interaction.
- **Action:** `npm run build`; visual verification via Preview against the mockup. Once validated, commit locally (no push): `Workbench UI (4/8) Complete: Built the Conversations rail and the center chat thread, Answer Card, and composer.`

### Step 5: Build the right Inspector (static)
- **Locations:** `web/components/inspector/InspectorPanel.tsx`, `web/components/inspector/InspectorTabs.tsx`, `web/components/inspector/ProgressMeter.tsx`, `web/components/inspector/TraceTab.tsx`, `web/components/inspector/TraceStage.tsx` (probe/draft/gate/emit with the vertical thread connector + shield emphasis on gate), `web/components/inspector/SpecialistLane.tsx`, `web/components/inspector/MicroStepRow.tsx` (the 8 checkpoints), `web/components/inspector/EvidenceRecordRow.tsx`, `web/components/inspector/EvidenceTab.tsx`, `web/components/inspector/JoinIndexTab.tsx`, `web/components/inspector/RawJsonTab.tsx`.
- **Rationale:** The Inspector is the product's signature ("see exactly what is going on step-by-step"). It is the densest component and renders the validated-query and evidence-record blocks that justify the whole UI. Tab switching and stage expand/collapse use React state here.
- **Action:** `npm run build`; visual verification of all four tabs via Preview against the mockup. Once validated, commit locally (no push): `Workbench UI (5/8) Complete: Built the Inspector with Trace/Evidence/Join/Raw tabs, specialist lanes, and validated-query + evidence renderers.`

### Step 6: Add event-based Motion animations across every part
- **Locations:** `web/lib/motion.ts` (shared variants: stage-enter, dot pulse/ring, stepper-fill, card-reveal, tab-crossfade, lane-expand), `web/lib/runMachine.ts` (`useRunState` hook — an event-reducer that advances `pending → running → pass/partial/fail` per stage and emits a timed sequence), `web/components/inspector/RunController.tsx` (a "Replay run" control to demonstrate the event-driven sequence); animation wiring edits in `StatusDot`, `InfraStatusPill`, `MiniStepper`, `AnswerCard`, `TraceStage`, `SpecialistLane`, `MicroStepRow`, `InspectorTabs`, `ProgressMeter`.
- **Rationale:** The request is explicit: animations must be an "animated event-based approach" so a future live workflow drives them. Centralizing the run-state machine and Motion variants means each component animates off a `status` prop / event, not ad-hoc timers — exactly the seam a real SSE stream will plug into. `AnimatePresence` handles stages/records streaming in and out. Respect `prefers-reduced-motion`.
- **Action:** `npm run build`; verify via Preview that triggering a replay animates dots, stepper, trace stages, and progress meter in ordered sequence. Once validated, commit locally (no push): `Workbench UI (6/8) Complete: Added the event-driven run-state machine and Motion animations across the shell, stepper, inspector stages, and status dots.`

### Step 7: Responsive behavior, accessibility, and real states
- **Locations:** `web/components/shell/AppShell.tsx` (≥1024px three columns; <1024px Inspector becomes a slide-over drawer; <768px left rail becomes a hamburger drawer + single-column chat), `web/components/shell/MobileDrawer.tsx`, plus `aria` labels / focus rings / `role` attributes across interactive primitives, and empty/loading/partial/error state variants in `ChatThread`, `AnswerCard`, `InspectorPanel`, `Composer` (e.g. "No sources — Build" message, partial-exit amber chip, failed-stage auto-expand).
- **Rationale:** Woven Dusk + ADA rules require color-plus-icon status, teal focus rings, and intentionally-designed mobile (not just stacked). The spec enumerates states that must exist (empty, loading, partial exit 1, failure, no-sources exit 2); designing them now prevents a "happy-path only" UI.
- **Action:** `npm run build` and `npm run lint`; verify desktop/tablet/mobile via Preview at multiple widths and confirm keyboard focus + reduced-motion. Once validated, commit locally (no push): `Workbench UI (7/8) Complete: Added responsive drawers, accessibility (focus/ARIA/reduced-motion), and empty/loading/partial/error states.`

### Step 8: Documentation, changelog, regression, and merge to main
- **Locations:** `docs/changelog.jsonl` (append entries per phase as they land), `docs/skills/global-project-rules/SKILL.md` + `docs/structure.md` (update webfront stack note: React/Vite → Next.js, and the commands), `web/README` notes if present; final regression `cd web && npm run build && npm run lint`; then `git merge` the worktree branch into `main` locally.
- **Rationale:** Global rules require a changelog entry for every change and that webfront changes compile (`npm run build`). The worktree merges to `main` only when everything is 100% functional, per the user's instruction and global rule 3.
- **Action:** Run the full `npm run build` + `npm run lint` regression; confirm green. Once validated, commit locally (no push), then merge the worktree into `main` (no push): `Workbench UI (8/8) Complete: Updated docs/changelog and stack notes, passed the build/lint regression, and merged the Next.js workbench to main.`

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Next.js app scaffold | App Router + Tailwind v4 + Motion + Geist, Woven Dusk tokens | `web/app/layout.tsx`, `web/app/globals.css`, `web/next.config.ts`, `web/package.json` |
| Trace types | TypeScript interfaces mirroring planner/specialist `to_dict()` objects | `web/lib/types.ts` |
| Sample fixtures | WMI→CAPEC run + conversations list (pure render input) | `web/lib/fixtures.ts`, `web/lib/conversations.ts` |
| App shell + header | Three-region full-height frame, header pills, run/login | `web/components/shell/*`, `web/components/header/*` |
| Conversations rail | Grouped chat list with active/Plan/Query states | `web/components/left/*` |
| Chat thread | User messages, Answer Card, mini-stepper, provenance chips, composer | `web/components/center/*` |
| Inspector | Trace/Evidence/Join/Raw tabs, lanes, query + evidence renderers | `web/components/inspector/*` |
| Run-state machine | Event reducer that drives status transitions | `web/lib/runMachine.ts` |
| Motion variants | Centralized event-based animation definitions | `web/lib/motion.ts` |
| Shared UI primitives | Pill, StatusDot, ThreadGlyph, CodeBlock, icons | `web/components/ui/*` |
| **Render smoke test** | Lightweight test asserting the fixture renders the expected stages/records (small subset of data) | `web/lib/__tests__/fixtures.test.ts` (or a typed assertion script under `web/lib/`) |
| Docs + changelog | Stack-change note + per-phase changelog entries | `docs/changelog.jsonl`, `docs/skills/global-project-rules/SKILL.md`, `docs/structure.md` |
