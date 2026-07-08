# Conversational Threads & Orchestration Layer — Implementation Plan

## 1. Introduction

Ariadne today is a **single-shot analyst tool**: the analyst types one question, the
LangGraph pipeline (`planner → specialists → synthesis`) answers it, and the left rail
lists each *turn* as a throwaway "conversation" held only in browser memory. Clicking
**New** discards everything, and there is no backend persistence, no cross-turn memory,
and no way to return to an earlier conversation.

This plan converts Ariadne into a **modern, memory-inclusive, multi-threaded chat**
(ChatGPT/Claude-style) and — per the analyst's direction — wraps the existing agents in a
new **conversational orchestration layer**. Every user turn now enters an
**Orchestration Agent**, is classified by a **Redirect/Router Agent** into either a fast
**memory-grounded Answer** or a full **Graph Extraction** run (the *existing*
planner→specialist→synthesis pipeline, unchanged internally). Graph runs pass through a
**Validation Agent** that decides whether the evidence is sufficient — looping back into
extraction with new parameters and a reason when it is not, up to a bounded cap — before
the **Answer Agent** composes the final, conversation-aware reply. Threads are persisted
in **SQLite**, auto-named by an LLM, and are listable / selectable / renamable / deletable
from a real backend-driven sidebar. The existing `POST /api/query` contract and its
byte-identical golden tests are preserved untouched; all new behavior rides on a new
conversation-aware path.

The work is decomposed so each phase is independently committable and testable: the
storage layer first, then the new agents bottom-up, then the assembled conversation
super-graph, then the API surface, then the frontend client / state / UI, then end-to-end
validation and the merge to `main`.

---

## 2. Gaps & Unanswered Questions

Resolved with the analyst (recorded here so implementers do not re-litigate):

- **Memory model** — A conversational orchestration layer wrapping the existing pipeline
  as a "Graph Extraction Agent." *Resolved.*
- **Storage backend** — SQLite via the stdlib `sqlite3`, DB file under `data/`
  (gitignored), path configurable by env. *Resolved.*
- **Thread actions (v1)** — Delete, Rename, and LLM auto-title all included. *Resolved.*
- **Quick-answer grounding** — Memory-grounded only: the quick path may use *only* facts
  already established in the thread (prior verified synthesis/evidence) or ask for
  clarification; anything needing new graph facts is routed to graph extraction. *Resolved.*
- **Endpoint coexistence** — Keep `POST /api/query` byte-identical (all current
  golden/contract tests untouched); conversational turns use a new conversation-aware
  path that reuses the existing pipeline internally as a subgraph. *Resolved.*

Assumptions taken for simple gaps (proceeding without blocking):

- **DB location / name** — `data/conversations.sqlite3`, overridable via
  `ARIADNE_CONVERSATION_DB`. *Assumption.*
- **Router / Validation / Answer are LLM-driven with deterministic fallbacks** — mirroring
  the repo's "LLM-off build stays byte-reproducible" ethos: router defaults to `graph`
  (never silently skips grounding), validation defaults to `pass`, the answer agent falls
  back to the synthesis narrative, and auto-title falls back to a truncated first question.
  *Assumption.*
- **Validation retry cap** — default 2 re-extraction attempts (env
  `ARIADNE_CONVERSATION_MAX_VALIDATION_ITERS`), matching the bounded-ReAct idiom already in
  the planner. *Assumption.*
- **Persistence timing** — turns are persisted server-side on stream completion (`done`),
  so a client disconnect cannot lose a completed turn; the thread rehydrates from stored
  payloads without re-running the pipeline. *Assumption.*

Complex gaps needing human input **later** (do not block the build; flag at the relevant
phase):

- **Long-thread context budgeting** — how much prior history to feed the router/answer
  agents once threads grow beyond the LLM context window (summarize? last-N turns?).
  *Human intervention may be needed once threads get long; v1 uses last-N turns + stored
  verified facts.*

---

## 3. Hierarchical Step-by-Step Instructions

> Workflow note: per the project's standing directive for this repo, **commit + append a
> `docs/changelog.jsonl` entry at every step, but do NOT push**. If everything is 100%
> functional at the end, merge `feat/conversational-threads` → `main`. Each step ends with
> the validation/commit action below.

### Step 1: SQLite persistence store

- **Locations**: new `utils/conversation/__init__.py`, `utils/conversation/store.py`
  (`ConversationStore` class: `create_conversation`, `list_conversations`,
  `get_conversation`, `rename_conversation`, `delete_conversation`, `append_turn`,
  `list_turns`), `utils/conversation/config.py` (DB path resolution via
  `ARIADNE_CONVERSATION_DB`), `utils/conversation/tests/test_store.py`. Document the env
  var in `.env.example`.
- **Schema**: `conversations(id, title, created_at, updated_at)` and
  `turns(id, conversation_id, seq, role, question, payload_json, mode, drafter, route,
  created_at)` with a foreign key + ordering index on `(conversation_id, seq)`.
- **Rationale**: Everything else (agents, API, UI) reads/writes threads through this store;
  it must exist and be proven with hermetic temp-DB tests before any consumer depends on
  it. No new dependency — stdlib `sqlite3` only.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest utils/conversation/tests/`). Once validated, commit (do NOT
  push) stating: Conversational Threads (1/11) Complete: Added the stdlib-SQLite
  ConversationStore with hermetic CRUD tests and configurable DB path.

### Step 2: Conversation graph state & config scaffolding

- **Locations**: `utils/conversation/state.py` (`ConversationState` TypedDict — thread
  history, user message, resolved/standalone question, route decision + reason, extraction
  result [reuses `SynthesizedAnswer`/`FederatedEvidence`], validation verdict + missing
  params, retry counter, final answer), `utils/conversation/config.py`
  (`ConversationConfig.from_env` — router/answer/validation LLM groups reusing the existing
  OpenAI-compatible knobs, `max_validation_iters`, quick-answer enable flag),
  `utils/conversation/tests/test_state.py`.
- **Rationale**: State is the LangGraph seam every new agent node builds on; it must wrap
  the existing frozen contracts (`Plan`, `SynthesizedAnswer`, `FederatedEvidence`) rather
  than redefine them, exactly as the prior LangGraph migration did.
- **Action**: Undergo the verification/tests/validation process for this phase. Once
  validated, commit (do NOT push) stating: Conversational Threads (2/11) Complete: Added
  ConversationState schema and env-backed ConversationConfig wrapping existing contracts.

### Step 3: Router (redirect) agent + memory-grounded Answer agent

- **Locations**: `utils/conversation/agents/router.py` (`route()` node — LLM classifies
  quick vs graph from history + user message; deterministic fallback = `graph`),
  `utils/conversation/agents/answer.py` (`answer()` node — composes the final
  conversation-aware reply; for the quick path, strictly memory-grounded using prior
  verified synthesis/evidence or a clarification request; deterministic fallback = pass
  through the synthesis narrative), shared prompt/util module, tests under
  `utils/conversation/tests/`.
- **Rationale**: These two LLM nodes are the conversational brain; building and unit-testing
  them in isolation (stub LLM + LLM-off fallbacks) de-risks the graph assembly in Step 5.
  The memory-grounded constraint preserves the project's no-hallucination guarantee.
- **Action**: Undergo the verification/tests/validation process for this phase. Once
  validated, commit (do NOT push) stating: Conversational Threads (3/11) Complete: Added the
  router and memory-grounded answer agents with stubbed-LLM and deterministic-fallback tests.

### Step 4: Graph Extraction wrapper + Validation agent (bounded retry)

- **Locations**: `utils/conversation/agents/graph_extraction.py` (wraps
  `utils/orchestration` — drives the existing pipeline on the resolved question, forwards
  its events, returns evidence + synthesis), `utils/conversation/agents/validation.py`
  (`validate()` node — sufficiency gate; on `insufficient` returns new search parameters +
  a reason and increments the retry counter; bounded by `max_validation_iters`;
  deterministic fallback = `pass`), tests under `utils/conversation/tests/`.
- **Rationale**: The extraction wrapper must reuse the existing super-graph verbatim (no
  reinterpretation of the golden-pinned pipeline), and the validation loop is the analyst's
  explicitly requested "not enough info → search again with new parameters" mechanism, which
  needs a hard cap to stay bounded.
- **Action**: Undergo the verification/tests/validation process for this phase. Once
  validated, commit (do NOT push) stating: Conversational Threads (4/11) Complete: Wrapped the
  existing pipeline as the Graph Extraction agent and added the bounded validation retry gate.

### Step 5: Assemble the conversation super-graph

- **Locations**: `utils/conversation/graph.py` (compiles the StateGraph:
  Orchestration/context-resolve → Router → conditional {quick→Answer→END |
  graph→GraphExtraction→Validation→(loop back to GraphExtraction | Answer→END)}),
  `utils/conversation/main.py` (`iter_conversation(question, *, conversation_id, history,
  mode, use_llm, ...)` generator emitting, via `get_stream_writer`, the additive event
  vocabulary `route`/`context`/`validation`/`final` plus the forwarded existing pipeline
  events; keeps the existing `answer` event as the grounded synthesis payload),
  golden event-order tests for quick / graph / retry paths (hermetic stubs).
- **Rationale**: This is where the layered architecture becomes real; the emitted stream is
  a load-bearing contract for the UI, so parity and ordering are pinned by dedicated
  goldens rather than assumed (the same discipline used in the LangGraph migration).
- **Action**: Undergo the verification/tests/validation process for this phase. Once
  validated, commit (do NOT push) stating: Conversational Threads (5/11) Complete: Compiled the
  Orchestration→Router→Extraction→Validation→Answer super-graph with golden event-order tests.

### Step 6: Auto-title + persistence integration

- **Locations**: `utils/conversation/naming.py` (`title_for()` — LLM title from the first
  user message, deterministic fallback = truncated question), integration in
  `utils/conversation/main.py` to persist the user turn + assistant turn to
  `ConversationStore` on completion and auto-title on the first turn, tests under
  `utils/conversation/tests/`.
- **Rationale**: Naming and persistence are the "savable threads" requirement; wiring them
  at the graph boundary (on `done`) guarantees a completed turn is never lost and the
  thread is fully rehydratable from stored payloads.
- **Action**: Undergo the verification/tests/validation process for this phase. Once
  validated, commit (do NOT push) stating: Conversational Threads (6/11) Complete: Added
  LLM auto-titling with deterministic fallback and wired server-side turn persistence.

### Step 7: API endpoints

- **Locations**: `api/models.py` (Conversation/Turn response models, `ConversationQueryRequest`
  with optional `conversation_id`, rename request), `api/services/conversations.py`
  (thin service over `ConversationStore` + `iter_conversation`), `api/main.py`
  (`GET/POST /api/conversations`, `GET/DELETE/PATCH /api/conversations/{id}`, and the SSE
  `POST /api/conversation-query` streaming `iter_conversation` with persistence),
  `api/tests/test_conversations.py`. **`POST /api/query` and `api/tests/test_query.py`
  remain untouched.**
- **Rationale**: Exposes threads + the conversational stream to the web app while leaving
  the existing stateless contract and its golden tests byte-identical, per the resolved
  endpoint-coexistence decision.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest api/tests/` — new suite green, `test_query.py` green unmodified).
  Once validated, commit (do NOT push) stating: Conversational Threads (7/11) Complete: Added
  the conversations CRUD + conversation-query SSE endpoints; existing /api/query untouched.

### Step 8: Frontend API client, types & rehydration adapter

- **Locations**: `web/lib/conversations.ts` (list/create/get/delete/rename +
  `streamConversation()`), `web/lib/types.ts` (thread/turn types, new SSE event variants
  `route`/`validation`/`final`/`context`/`conversation`, `conversation_id` on the request),
  `web/lib/adapt.ts` (map a stored turn payload → `WorkbenchRun` via the existing
  `buildRun`, plus a lightweight bubble for quick-path turns), Vitest specs under
  `web/lib/__tests__/` (or the existing test location).
- **Rationale**: A typed client + rehydration adapter isolates all backend-shape knowledge
  in `lib/`, keeping the presentation layer a pure function of view-models exactly as it is
  today.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm test`). Once validated, commit (do NOT push) stating: Conversational Threads
  (8/11) Complete: Added the conversations API client, new SSE event types, and the turn→run
  rehydration adapter with Vitest coverage.

### Step 9: Frontend run machine & context wiring

- **Locations**: `web/lib/runMachine.ts` (add `conversationId`, `loadConversation(id)`,
  make `newConversation()` create/select a thread, route `submit()` through the
  conversation endpoint with `conversation_id`, handle `route`/`validation`/`final`/`context`
  events, refresh the thread list + title on `done`, add `deleteConversation`/`renameConversation`),
  `web/components/workbench/WorkbenchContext.tsx` (expose conversation list + actions).
- **Rationale**: The run machine is the single source of truth for turn state; extending it
  (rather than the components) keeps the memory/threading logic in one tested place.
- **Action**: Undergo the verification/tests/validation process for this phase. Once
  validated, commit (do NOT push) stating: Conversational Threads (9/11) Complete: Extended the
  run machine with thread load/create/delete/rename and conversational event handling.

### Step 10: Frontend UI — sidebar & chat rendering

- **Locations**: `web/components/left/ConversationsPanel.tsx` +
  `web/components/left/ConversationItem.tsx` (backend-driven thread list, real date grouping
  Today/Yesterday/This week/Older, active/select, inline rename, delete with confirm,
  empty + loading states), `web/components/center/ChatThread.tsx` +
  `web/components/center/AnswerCard.tsx` (render the conversational `final` reply as the
  message bubble with the grounded synthesis card collapsible beneath; show router/validation
  indicators). Follow Woven Dusk tokens; keep mobile drawer behavior.
- **Rationale**: Delivers the actual ChatGPT-style experience the analyst asked for;
  isolating it as the last frontend step lets it consume the already-tested client + state.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`cd web && npm run lint && npm run build`, plus preview verification). Once validated,
  commit (do NOT push) stating: Conversational Threads (10/11) Complete: Reworked the sidebar
  into persisted threads and rendered conversational replies over collapsible grounded cards.

### Step 11: End-to-end validation, docs & merge

- **Locations**: full backend regression (`uv run python -m pytest utils/ api/`), web
  (`cd web && npm test && npm run lint && npm run build`), live launcher smoke
  (`python app.py`) exercising: (a) a graph turn ("Which ATT&CK techniques does CAPEC-98
  map to?"), (b) a memory follow-up ("tell me more about T1598") that resolves the
  reference and answers, (c) a memory-grounded quick meta-question ("what did we just
  discuss?"), and (d) a validation-retry case. Update `docs/structure.md`
  (`utils/conversation/` row, new endpoints, new SSE events), `README` tech-stack/feature
  bullets, and `docs/changelog.jsonl`.
- **Rationale**: Proves the layered conversational architecture works end-to-end with real
  memory across turns, confirms the old pipeline is still byte-identical, and leaves the
  docs accurate before landing on `main`.
- **Action**: Undergo the verification/tests/validation process for this phase. Once
  validated and 100% functional, commit (do NOT push) and **merge
  `feat/conversational-threads` → `main`**, stating: Conversational Threads (11/11) Complete:
  End-to-end memory validated across turns, docs updated, feature merged to main.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Conversation store | Stdlib-SQLite CRUD for threads + turns | `utils/conversation/store.py` |
| Store config | DB path resolution / env knob | `utils/conversation/config.py` |
| Conversation state | LangGraph `ConversationState` wrapping existing contracts | `utils/conversation/state.py` |
| Router agent | Quick-vs-graph redirect (LLM + deterministic fallback) | `utils/conversation/agents/router.py` |
| Answer agent | Memory-grounded / final conversational reply | `utils/conversation/agents/answer.py` |
| Graph Extraction wrapper | Reuses existing pipeline as a subgraph | `utils/conversation/agents/graph_extraction.py` |
| Validation agent | Bounded sufficiency-retry gate | `utils/conversation/agents/validation.py` |
| Conversation super-graph | Compiled orchestration graph + `iter_conversation` | `utils/conversation/graph.py`, `utils/conversation/main.py` |
| Auto-titling | LLM thread naming + deterministic fallback | `utils/conversation/naming.py` |
| API endpoints | Conversations CRUD + conversation-query SSE | `api/services/conversations.py`, `api/main.py`, `api/models.py` |
| Frontend client | Typed conversations client + rehydration adapter | `web/lib/conversations.ts`, `web/lib/adapt.ts`, `web/lib/types.ts` |
| Run machine wiring | Thread load/create/delete/rename + event handling | `web/lib/runMachine.ts`, `web/components/workbench/WorkbenchContext.tsx` |
| Sidebar + chat UI | Persisted-thread sidebar + conversational rendering | `web/components/left/*`, `web/components/center/*` |
| **Store tests** | Hermetic temp-DB CRUD + ordering | `utils/conversation/tests/test_store.py` |
| **Agent tests** | Router/answer/validation stub-LLM + fallback tests | `utils/conversation/tests/` |
| **Graph tests** | Golden event-order for quick/graph/retry paths | `utils/conversation/tests/` |
| **API tests** | Conversations CRUD + conversation-query contract | `api/tests/test_conversations.py` |
| **Frontend tests** | Client + rehydration adapter Vitest specs | `web/lib/__tests__/` |
| Docs | structure.md rows, README bullets, changelog | `docs/structure.md`, `README*`, `docs/changelog.jsonl` |
