# Deterministic Conversation Anchoring

## 1. Introduction

A follow-up question in the workbench chat loses the entity the thread is about.
"What is Creating a Rogue Certification Authority Certificate?" resolves to CAPEC-459
correctly, but the next turn — "Please explore the execution steps involved" — returns
all 794 `ExecutionStep` nodes because the planner never learns the follow-up is *about
CAPEC-459*. Investigation showed the chat already runs the stateful
`/api/conversation-query` path, but **all** conversational context reaches the planner
through a single, best-effort LLM "reference resolution" rewrite in the orchestration
node ([utils/conversation/agents/orchestration.py](../../utils/conversation/agents/orchestration.py)).
When that LLM call is unavailable (exactly what the transcript's "validation LLM
unavailable" proves) or produces a rewrite that omits the entity, the raw follow-up
flows to a planner that is structurally blind to history
([utils/orchestration/main.py](../../utils/orchestration/main.py) `iter_pipeline`,
[utils/planner/agent.py](../../utils/planner/agent.py) `PlanningAgent.plan(request: str)`
— both take only a single question string).

The approach is **deterministic anchoring**: compute, in pure Python, the entity the
thread is currently focused on (its id + name) from the stored turns, and fold that
anchor into the resolved question *whenever the question names no entity of its own* —
independent of any LLM. The drafter already injects `ANALYST REQUEST:\n{request}`
verbatim ([utils/planner/llm_drafter.py:133](../../utils/planner/llm_drafter.py)), so an
anchored request like "Please explore the execution steps involved. (Regarding CAPEC-459
— Creating a Rogue Certification Authority Certificate.)" reaches the planner with a
concrete entity to route on, LLM up or down. This reuses infrastructure that already
exists: `_recent_dossier_ids`, `dossiers_from_turns`, and `entity_ids_in` in
[utils/conversation/persistence.py](../../utils/conversation/persistence.py).

## 2. Gaps & Unanswered Questions

- **Topic-change follow-ups without an entity id.** A question like "list all tactics"
  names no entity, so deterministic anchoring would wrongly attach the prior entity.
  *Assumption*: in a focused analytic thread this is rare, and the LLM rewrite (when up)
  already handles genuine topic changes. *Mitigation shipped*: anchor only when the
  question also carries a **referential cue** (pronoun / "it" / "that" / "these" / "the
  <noun>" / imperative follow-up verbs like "explore/expand/show/list its") **or** is
  short and verb-led; a question with its own subject noun phrase and no cue is left
  unanchored. This keeps false anchoring low without needing an LLM. Documented as a
  known limitation with the cue list.
- **Which entity when several are held.** *Assumption*: anchor to the most-recently
  hydrated entity first (recency), matching the existing `_recent_dossier_ids` contract,
  then any entity the question names explicitly (those need no anchoring and are skipped).
- **First turn produced no dossier.** If turn 1 stored no `entity_dossiers`, fall back to
  the entity ids found in the recent turn *text* (`entity_ids_in` over the last user +
  assistant turns). *Assumption*: text-level ids (e.g. "CAPEC-459" printed in the answer)
  are a sufficient anchor source; no graph re-query is needed.
- **Deterministic drafter mode.** Embedding an id in the request text helps the LLM
  drafter most; the deterministic drafter benefits only where its heuristics read ids.
  *Assumption*: acceptable — the default composer drafter is `llm`, and the anchor never
  *hurts* the deterministic path. No planner-signature change is in scope.

## 3. Hierarchical Step-by-Step Instructions

### Step 0: Worktree prerequisite (no commit)
- **Locations**: worktree root; symlink `data/` and `.env` from the primary checkout
  `/home/bdgr/Agents/Ariadne` (per the established worktree-setup convention); confirm
  `git status` clean and branch `claude/rogue-ca-certificate-dd952c`.
- **Rationale**: The conversation unit tests are deterministic/stubbed, but env loading
  and any ad-hoc live check need the shared `data/.env`. This is setup only — no code
  change, no commit.

### Step 1: Deterministic anchor computation (pure function + tests)
- **Locations**: [utils/conversation/persistence.py](../../utils/conversation/persistence.py)
  — new `conversation_anchor(turns) -> list[tuple[str, str]]` returning ordered
  `(entity_id, name)` pairs, most-relevant-first, built from `dossiers_from_turns` /
  `_recent_dossier_ids` (names) with a text-level `entity_ids_in` fallback over the most
  recent turns; and a `referential_followup(question) -> bool` cue detector. Tests in
  [utils/conversation/tests/test_persistence.py](../../utils/conversation/tests/test_persistence.py).
- **Rationale**: Isolate the deterministic logic where the other memory helpers already
  live and unit-test it in isolation (held-entity recency, id-in-text fallback, cue vs
  no-cue, empty history) before wiring it into the graph.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest utils/conversation/tests/test_persistence.py`). Once
  validated, commit to git (no push) stating: Deterministic Conversation Anchoring (1/4)
  Complete: added `conversation_anchor`/`referential_followup` pure helpers with tests.

### Step 2: Thread the anchor through conversation state → orchestration
- **Locations**: [utils/conversation/state.py](../../utils/conversation/state.py) — add an
  `anchor: list[tuple[str, str]]` (or list of `{id,name}`) input field to
  `ConversationState`. [utils/conversation/main.py](../../utils/conversation/main.py)
  `iter_conversation` — accept `anchor=` and seed it into `init`.
  [utils/conversation/agents/orchestration.py](../../utils/conversation/agents/orchestration.py)
  — after `resolve_question`, if the resolved question names no entity
  (`entity_ids_in`) **and** `referential_followup` is true **and** an anchor exists,
  deterministically append the top anchor to `resolved_question`, and enrich the emitted
  `context` event (e.g. `anchored: true`, `anchor_id`) so the UI/trace can show it.
- **Rationale**: The orchestration node is the single seam every turn passes through and
  already owns `resolved_question`; folding the anchor here makes the fix apply on both
  the graph and quick routes with no change to `iter_pipeline`/`PlanningAgent` signatures.
- **Action**: Undergo the verification/tests/validation process for this phase
  (existing conversation graph/orchestration tests + new orchestration anchor tests).
  Once validated, commit to git (no push) stating: Deterministic Conversation Anchoring
  (2/4) Complete: threaded anchor through state/iter_conversation and folded it into the
  orchestration resolve step behind the no-entity + referential-cue gate.

### Step 3: Compute and pass the anchor from the API service
- **Locations**: [api/services/conversations.py](../../api/services/conversations.py)
  `stream_conversation_events` — compute `anchor = conversation_anchor(turns)` alongside
  the existing `history_from_turns` / `memory_injection` calls and pass `anchor=` into
  `iter_conversation`. Persistence of the resolved/anchored question already flows through
  `acc["resolved_question"]` via the `context` event — confirm the anchored form is what
  gets stored so the *next* turn's history carries it too.
- **Rationale**: The service is the only layer holding the raw `turns`; it is where the
  deterministic anchor must be derived and injected. Reusing the existing `turns` fetch
  keeps it a one-line addition with no extra store round-trip.
- **Action**: Undergo the verification/tests/validation process for this phase
  (`uv run python -m pytest api/tests/test_conversations.py`; add a case asserting an
  entity-free referential follow-up reaches extraction with the anchor embedded). Once
  validated, commit to git (no push) stating: Deterministic Conversation Anchoring (3/4)
  Complete: API service derives the anchor from stored turns and passes it into the turn.

### Step 4: End-to-end regression + reproduce-the-bug guard
- **Locations**: a focused end-to-end style test (LLM stubbed *off*, mirroring the
  transcript's LLM-unavailable condition) under
  [utils/conversation/tests/](../../utils/conversation/tests/) — two turns: turn 1 holds
  CAPEC-459; turn 2 "explore the execution steps involved" must reach the extraction
  runner with a request string containing `CAPEC-459` (asserted via an injected stub
  runner that captures the question). Run the full conversation + api conversation suites.
- **Rationale**: Locks in the exact failure the user reported — with the LLM *down* — so a
  future refactor of the rewrite seam cannot silently reintroduce statelessness.
- **Action**: Undergo the verification/tests/validation process for this phase (full
  `utils/conversation/tests/` + `api/tests/test_conversations.py`; no web build needed —
  no `web/` changes). Once validated, commit to git (no push) stating: Deterministic
  Conversation Anchoring (4/4) Complete: added the LLM-down two-turn regression proving
  the follow-up anchors to the held entity.

### Step 5: Merge to main (only if 100% green)
- **Locations**: worktree → `main`. Per the concurrent-sessions rule, rebase/merge local
  `main`, resolve any conflicts, re-run the conversation + api suites, then merge.
- **Rationale**: Standard project close-out; main may have moved.
- **Action**: Undergo the full validation process; merge to main only when everything is
  functional. Commit (no push) any merge resolution with a changelog entry.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Anchor helpers | `conversation_anchor` + `referential_followup` pure functions | utils/conversation/persistence.py |
| Anchor helper tests | Recency, id-in-text fallback, cue detection, empty history | utils/conversation/tests/test_persistence.py |
| State + entry threading | `anchor` field on `ConversationState`; `iter_conversation(anchor=)` | utils/conversation/state.py, utils/conversation/main.py |
| Orchestration folding | Deterministic anchor append behind no-entity + cue gate; enriched `context` event | utils/conversation/agents/orchestration.py |
| Orchestration tests | Anchored vs unanchored resolve; LLM-off path | utils/conversation/tests/test_orchestration.py (new) or test_graph.py |
| Service wiring | Derive anchor from `turns`; pass into `iter_conversation` | api/services/conversations.py |
| Service test | Entity-free follow-up reaches extraction with anchor embedded | api/tests/test_conversations.py |
| E2E regression | Two-turn, LLM-down proof the follow-up anchors to CAPEC-459 | utils/conversation/tests/test_anchor_e2e.py (new) |
| Changelog entries | One per step | docs/changelog.jsonl |
