# Frontend Refresh Plan — Neutral Palette, Compact Sidebar, Integrated Evidence, Background Queries

## 1. Introduction

This plan delivers four analyst-requested changes to the Ariadne web workbench (`web/`,
Next.js App Router + Tailwind v4, Woven Dusk). The goal is a cleaner, less-green
interface with a more usable conversation sidebar, evidence that reads as part of the
answer rather than a floating panel, and queries that keep running when the analyst
switches chats.

The approach neutralizes the base palette toward black/dark-gray while keeping oxidized
teal (and amber) as accents; redesigns the sidebar into compact pill rows with readable
AI-generated titles and no clutter metadata; restyles the "Show evidence & sources"
disclosure so it is a seamless downward extension of the reply container; and refactors
the client run machine so each conversation owns its own in-flight stream — a query no
longer cancels when the analyst navigates away, and busy chats show a spinning "swirl"
indicator. Work happens on the `worktree-frontend-refresh` worktree; each step ends with a
validated commit (no push, per project directive), and the branch merges to `main` only
after full green regression.

## 2. Gaps & Unanswered Questions

- **Depth of "less green"** (Requirement 1): Woven Dusk's canon is a green-undertoned
  charcoal (`#1B2122`). *Assumption*: shift the base surfaces to near-neutral dark
  gray/black (bg `#0E0F11`, surface `#17191B`, border neutral gray) and neutralize the
  sage muted-text tokens toward cool gray, while keeping `--color-primary` teal `#4E9E96`
  and `--color-secondary` amber `#C9924A` as accents. The `woven-dusk-design` skill
  palette table and `docs/changelog.jsonl` will be updated so the canonical docs stay
  truthful about the new base.
- **Title generation cost/latency** (Requirement 2): the backend already auto-titles via
  `naming.py`. *Assumption*: tighten the system prompt to 2–5 words and lower
  `max_tokens` so the first-turn title returns fast; keep the deterministic fallback.
- **Truncation cause** (Requirement 2): titles are cut by the CSS `truncate` class inside
  a narrow 212px rail, not a 15-char code cap. *Assumption*: fix by widening the rail
  slightly and allowing up to two lines (`line-clamp-2`) so 2–5 word titles show fully.
- **Background-query persistence scope** (Requirement 4): *Assumption*: persist in-flight
  streams in memory per conversation for the session only (no cross-reload resumption;
  the backend already persists completed turns). Switching chats keeps the stream folding
  events into that conversation's own run state; returning shows live progress.
- **Evidence integration** (Requirement 3): *Assumption*: "extension of the chat
  container" means the disclosure toggle and the expanded `AnswerCard` share the reply
  bubble's surface/shadow and connect with no gap (seamless rounded container), rather
  than sitting as a separate floating card beneath it.

No blocking gaps require human intervention; all assumptions above are low-risk and
reversible.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Neutralize the base palette (less green, teal/amber accents)
- **Locations**: `web/app/globals.css` (`@theme` tokens `--color-bg`, `--color-surface`,
  `--color-surface-deep`, `--color-console`, `--color-border`, `--color-text-muted`,
  `--color-text-faint`, `--color-text-dim`); hardcoded green rgba sweeps in
  `web/components/**` (e.g. `rgba(27,33,34,…)`, `rgba(78,158,150,0.05)` decorative
  fills in `AppShell.tsx`, `ConversationItem.tsx`, `ChatThread.tsx`); doc sync in
  `docs/skills/woven-dusk-design/SKILL.md` palette table.
- **Rationale**: the base tokens drive nearly every surface; neutralizing them plus the
  hardcoded charcoal-green rgba values removes the overall green cast in one coherent
  pass while leaving teal/amber accents intact. Doc sync keeps the design skill honest.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm run build && npm run lint`; visually inspect surfaces via preview/
  inspect). Once validated, commit stating: Frontend Refresh (1/6) Complete: Neutralized
  the base palette to black/dark-gray with teal/amber accents.

### Step 2: Short, fast AI-generated thread titles
- **Locations**: `utils/conversation/naming.py` (`_SYSTEM` prompt, `title_for`
  `max_tokens`); tests under `utils/conversation/tests/` covering `title_for` /
  `deterministic_title`.
- **Rationale**: the conversational stream already calls `title_for` on the first turn;
  tightening the instruction to 2–5 words and reducing `max_tokens` makes titles short
  and low-latency without touching the API/stream wiring or the deterministic fallback.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest utils/conversation/tests/`). Once validated, commit stating:
  Frontend Refresh (2/6) Complete: AI titles are now short (2–5 words) and fast.

### Step 3: Compact pill sidebar with readable titles, no clutter metadata
- **Locations**: `web/components/left/ConversationItem.tsx` (pill container, remove the
  `{turnCount} turns` Pill + `timeLabel` row, allow 2-line title via `line-clamp-2`),
  `web/components/left/ConversationsPanel.tsx` (tighter spacing, keep date-group
  headers or compact them), `web/components/shell/AppShell.tsx` (rail width bump for
  readability), and `web/lib/ui.ts` only if a helper becomes unused.
- **Rationale**: styling each row as a compact pill and dropping the turn-count/time
  metadata directly satisfies the "far more compact" and "remove metadata" asks; the
  2-line clamp plus a slightly wider rail fixes the ~15-char truncation.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm run build && npm run lint && npm test`; inspect the rail). Once
  validated, commit stating: Frontend Refresh (3/6) Complete: Compact pill sidebar with
  full-width titles and no clutter metadata.

### Step 4: Evidence disclosure as a seamless extension of the reply container
- **Locations**: `web/components/center/ReplyMessage.tsx` (bottom radius/shadow when
  expanded so it connects downward), `web/components/center/ChatThread.tsx` (`TurnBlock`
  wrapper so the reply bubble + expanded `AnswerCard` render as one continuous container
  — shared surface, connecting top radius removed on the card, no gap), and
  `web/components/center/AnswerCard.tsx` only for the connecting radius/shadow when
  docked beneath the reply.
- **Rationale**: the disclosure and `AnswerCard` currently render as separate stacked
  containers; unifying their surface/shadow and removing the gap makes evidence read as
  an extension of the answer, as requested, without changing the trust surface's content.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm run build && npm run lint && npm test`; inspect expanded/collapsed
  states). Once validated, commit stating: Frontend Refresh (4/6) Complete: Evidence &
  sources now extend the chat container instead of floating separately.

### Step 5: Background query execution + per-chat "swirl" indicator
- **Locations**: `web/lib/runMachine.ts` (the core change: key in-flight stream state —
  accumulator, abort controller, runs, liveStatus, streamingRunId — per conversation id
  so `selectConversation`/`newConversation` no longer `cancel()` a running stream;
  expose `runsByConversation` for the active view, a `busyConversationIds` set, and
  per-active `replaying`/`streamingRunId`), `web/components/workbench/WorkbenchContext.tsx`
  (surface `busyConversationIds`), `web/components/center/Composer.tsx` (disable keyed to
  the ACTIVE conversation streaming, not any), `web/components/left/ConversationsPanel.tsx`
  + `ConversationItem.tsx` (render a spinning swirl on busy rows), `web/components/ui/icons.tsx`
  (add a `SwirlIcon`/spinner), and `web/lib/__tests__/runMachine.test.ts` (new coverage:
  a stream on conversation A keeps folding after switching to B; busy set tracks it).
- **Rationale**: the run machine currently holds a single global in-flight stream and
  `cancel()`s it on every conversation switch, so a running query dies. Moving stream
  state into a per-conversation registry is the minimal architecture that lets queries
  continue in the background and lets the sidebar mark which chats are busy.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm run build && npm run lint && npm test`; live/manual: start a query,
  switch chats, confirm it keeps running with a swirl and completes). Once validated,
  commit stating: Frontend Refresh (5/6) Complete: Queries run in the background across
  chat switches with a per-chat swirl indicator.

### Step 6: Full regression, live E2E, docs, and merge to main
- **Locations**: whole `web/` gate (`npm run build && npm run lint && npm test`) + backend
  conversation suite (`uv run python -m pytest utils/conversation/ api/`); `docs/structure.md`
  / `docs/skills/*` touch-ups if any behavior changed; `docs/changelog.jsonl`; merge
  `worktree-frontend-refresh` → local `main`.
- **Rationale**: prove nothing regressed across all four changes together, capture any
  doc drift, and land on main per the worktree workflow only when 100% green.
- **Action**: Undergo the full verification/tests/validation process (all gates green;
  live E2E via `python app.py --prod` on alt ports + curl/preview if ports free). Once
  validated, commit stating: Frontend Refresh (6/6) Complete: Full regression green;
  merged the frontend refresh to main.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Neutral palette tokens | Black/dark-gray base with teal/amber accents | `web/app/globals.css` |
| Palette doc sync | Updated base-palette table | `docs/skills/woven-dusk-design/SKILL.md` |
| Short-title prompt | 2–5 word, low-latency titles + fallback | `utils/conversation/naming.py` |
| Title tests | Cover short-title + deterministic fallback | `utils/conversation/tests/` |
| Compact pill sidebar | Pill rows, 2-line titles, no metadata | `web/components/left/ConversationItem.tsx`, `ConversationsPanel.tsx` |
| Wider rail | Readable title width | `web/components/shell/AppShell.tsx` |
| Integrated evidence | Disclosure extends the reply container | `web/components/center/ReplyMessage.tsx`, `ChatThread.tsx`, `AnswerCard.tsx` |
| Per-conversation run machine | Background streams keyed by conversation | `web/lib/runMachine.ts` |
| Busy indicator wiring | `busyConversationIds` through context | `web/components/workbench/WorkbenchContext.tsx`, `Composer.tsx` |
| Swirl icon + busy rows | Spinner on active chats | `web/components/ui/icons.tsx`, `ConversationItem.tsx` |
| Background-query tests | Stream survives chat switch; busy set | `web/lib/__tests__/runMachine.test.ts` |
| Changelog entries | One per step | `docs/changelog.jsonl` |
