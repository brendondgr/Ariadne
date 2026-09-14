# Workbench controls: fast by default, verification and thinking on demand

**Status:** plan. Supersedes nothing; extends
`docs/plans/2026-09-14-frontend-prototype-configuration.md` after its Step 7.
**Date:** 2026-09-14

---

## 1. Introduction

A deterministic turn through the workbench takes ~43 seconds, and 42 of them are
not the pipeline. Timed per SSE event, the graph answers at **1.09 s**; the chat
wrapper's `validation` agent lands at **29.68 s** and its `answer` agent at
**40.39 s**. Both are LLM calls at a **4,096-token thinking budget**, and no
control on screen turns them off: `ConversationConfig` inherits `enabled` from
`ARIADNE_LLM_ENABLED`, and `with_llm_enabled()` is one-way — it can turn the
conversation LLM on and never off. The composer reads "Drafter: deterministic"
while four model calls run.

This plan replaces the three composer controls (`Plan/Full answer`, `Drafter`,
`Plain prose`) with three that describe what a reader actually chooses: **extract
fast by default, verify with a model on demand, and say what the thinking budget
is.** It follows the shape the operator asked for — get as much information as
possible as quickly as possible, then verify as an explicit act.

The deterministic claim verifier is **not** in scope and is not exposed. It runs
unconditionally on every path, cuts uncited claims and turns honest empties into
abstentions carrying the executed query. "Verification" in this plan means the
chat layer's LLM sufficiency agent, which is a second opinion rather than a
guarantee.

---

## 2. Gaps & Unanswered Questions

- **Does `verify: off` disable the whole conversation LLM, or only `validation`?**
  *Assumption*: the whole layer — `router`, `orchestration`, `validation`,
  `answer`. Leaving `answer` on would keep ~11 s and produce a model-written
  reply while the UI claims a fast path. The pipeline's own narrative is what a
  reader sees instead, and `Readable prose` is the control for improving it.
- **Losing `Plan` mode.** The composer's plan-only toggle disappears.
  *Assumption*: acceptable — the inspector already renders the plan on every run,
  so plan-only is a debugging view rather than a capability.
- **Losing the `Drafter` toggle.** *Assumption*: acceptable and desirable. Its
  only appeal was prose, which now has its own control, and it scores **0.5000**
  against the template cascade's **0.9467** on the same unseen questions.
  Reachable by environment for experiments; off the analyst's surface.
- **Thinking budget range.** Operator-specified: from **128**, doubling —
  128, 256, 512, 1024, 2048, 4096, 8192, 16384.
  *Assumption*: 0 is not offered; a reasoning model given 0 can truncate to empty
  (`skynet` did), and 128 is the honest floor. The default stays whatever the
  environment resolves, so a deployment that never touches the control behaves as
  it does today.
- **Which seams the budget governs.** *Assumption*: whichever run for that
  request — the narrator when `Readable prose` is on, the conversation agents
  when `Verify` is on. It is one number because an analyst is choosing "how long
  am I willing to wait", not tuning two independent knobs.
- **Does a per-request budget need a judged re-measure?** ***Human intervention
  is needed to answer this question.*** Every recorded figure was produced at a
  fixed environment budget. Exposing it lets an analyst run a configuration no
  experiment covers. The plan ships it as a *visible* control precisely so the
  choice is recorded on screen, but no figure here describes non-default budgets.

---

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Make the conversation LLM switchable off, not only on

- **Locations**: `utils/conversation/config.py` (`ConversationConfig.with_llm_enabled`),
  `utils/conversation/agents/validation.py`, `agents/answer.py`, `agents/router.py`,
  `agents/orchestration.py` (all read `config.llm.enabled`, no change expected).
- **Rationale**: this is the defect underneath the whole complaint. A one-way
  switch means the UI cannot express "deterministic", only "deterministic unless
  the environment says otherwise". Until it is two-way, no control added above it
  can be honest. The method becomes symmetric and its docstring says what changed
  and why the old behaviour was wrong.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Workbench Controls (1/5)
  Complete: the conversation LLM can be turned off as well as on.

### Step 2: Carry `verify` and `thinking_budget` on the request

- **Locations**: `api/models.py` (`QueryRequest`, `ConversationQueryRequest`),
  `api/main.py` (both routes), `api/services/query.py` (`stream_query_events`),
  `api/services/conversations.py` (`stream_conversation_events`),
  `utils/conversation/main.py` (`iter_conversation`), `utils/conversation/state.py`.
- **Rationale**: the workbench streams `/api/conversation-query`, so a field added
  only to `/api/query` is a dead control — the mistake caught in Step 7 of the
  previous plan. Both surfaces carry both fields, and `verify` maps to
  `with_llm_enabled(verify)` now that the call is two-way.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Workbench Controls (2/5)
  Complete: verify and thinking_budget travel on both query surfaces.

### Step 3: Apply the budget to whichever seams run

- **Locations**: `utils/conversation/config.py` (`ConversationConfig`, a
  `with_thinking_budget`), `utils/synthesis/config.py` (`SynthesisConfig`,
  `llm_thinking_budget`), `utils/conversation/agents/graph_extraction.py` (where
  the explicit `SynthesisConfig` is already built for the narrator).
- **Rationale**: the budget is invisible today and is most of the latency. One
  number governs the seams that actually run for that request, because the
  analyst is choosing how long to wait rather than tuning two knobs. `None` means
  "leave the environment's value alone", so an untouched deployment is unchanged.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Workbench Controls (3/5)
  Complete: a per-request thinking budget reaches the seams that run.

### Step 4: Replace the three composer controls with three that mean something

- **Locations**: `web/components/center/Composer.tsx`, `web/lib/api.ts`
  (`QueryRequestBody`, `ConversationQueryBody`), `web/lib/runMachine.ts` (the
  request assembled in `startStream`), `web/lib/types.ts`.
- **Rationale**: `Plan/Full answer` and `Drafter` both describe implementation
  seams rather than choices; `Drafter` additionally selects a measurably worse
  path. `Verify`, `Readable prose` and `Thinking` describe what the analyst is
  trading. Defaults are off / off / environment, which is the ~1 s path.
- **Rationale, second half**: `runMachine.startStream` builds the conversation
  body field by field rather than spreading the request, so a new field that is
  not added there is silently dropped — the same shape as the dead-toggle defect.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Workbench Controls (4/5)
  Complete: the composer offers Verify, Readable prose and Thinking.

### Step 5: Verify end to end and record the latencies

- **Locations**: `app.py` (full stack), the Browser pane, a new amendment in
  `docs/research/experiments/EXP-2026-09-020-plan-source-crossed/RESULTS.md`.
- **Rationale**: the claim this plan makes is a latency claim, so it is only
  finished when the four corners are timed through the running stack: default,
  verify on, prose on, and a raised budget. Per-event SSE timings, not a
  stopwatch on the whole request, because the point is *which stage* costs what.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Workbench Controls (5/5)
  Complete: the four control corners timed end to end and recorded.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Two-way conversation LLM switch | `with_llm_enabled` turns the layer off as well as on. | `utils/conversation/config.py` |
| Request fields | `verify` and `thinking_budget` on both query surfaces. | `api/models.py`, `api/main.py`, `api/services/` |
| Per-request thinking budget | `with_thinking_budget` on the conversation and synthesis configs. | `utils/conversation/config.py`, `utils/synthesis/config.py` |
| Composer controls | Verify / Readable prose / Thinking, defaulting to the fast path. | `web/components/center/Composer.tsx` |
| Control-plumbing tests | Assert `verify=False` disables the layer, that the budget reaches the config, and that a field added to the body survives `startStream`. | `utils/conversation/tests/test_controls.py`, `api/tests/test_query_controls.py` |
| Latency amendment | Per-event timings for the four control corners. | `docs/research/experiments/EXP-2026-09-020-plan-source-crossed/RESULTS.md` |
