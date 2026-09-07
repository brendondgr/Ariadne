# Plan — Stop the workbench SSE stream dying mid-run

## 1. Introduction

An analyst running a question with the **llm** drafter sees the activity ticker
reach `planning and routing the question…` and then stop, roughly half the time.
Nothing is wrong with the plan, the graphs, or the model: the pipeline is still
working. The problem is that the pipeline emits **no SSE traffic at all** while
any of its three LLM stages runs (`plan`, the specialist query builder, and
`synthesize`), and the browser's inactivity watchdog — `SSE_STALL_MS = 90_000`
in `web/lib/streamConfig.ts` — cancels any stream that has been silent for 90
seconds. Measured over 12 concurrent questions against `:9090/default-model`,
5/12 runs (42%) had a silent gap longer than 90 s; the longest was 429 s. The
gap almost always follows `status(planning)`, which is exactly the line the
analyst last sees.

A second, harder failure was captured live: a request that stalls inside
`build_specialist()` while holding the CPython import lock for
`utils.specialists.cypher.specialist` **permanently wedges the worker** — every
later request blocks forever at `_lock_unlock_module`, and eventually even
`/api/health` stops answering. This is the "it never recovers until I restart"
half of the report.

The approach is to make the stream prove it is alive (a heartbeat), remove the
request-time import that can wedge the worker, and make the documented
`PIPELINE_TIMEOUT_S` budget actually bound the stages that blow it.

---

## 2. Gaps & Unanswered Questions

- **Heartbeat wire format.** An SSE *comment* frame (`: ping\n\n`) resets the
  client's inactivity timer and is dropped by `parseSseFrame` (no `data:` line
  ⇒ `null`), so it needs no change to `web/lib/types.ts` or `runMachine.ts`.
  *Assumption*: use a comment frame, not a new named event, so the typed event
  union and every existing UI/vitest contract stay untouched.
- **Heartbeat interval.** *Assumption*: 10 s. Comfortably under the 90 s budget
  and under `SSE_SLOW_MS` (25 s), cheap, and it survives an interval being
  lowered by an operator.
- **Interrupting an in-flight LLM call.** `requests` cannot be cancelled from
  another thread, so a deadline check can only refuse to *start* the next stage,
  not abort a running one. *Assumption*: check the deadline at the node
  boundary, matching what the specialist loop already does at
  `utils/orchestration/agents/specialists/nodes.py:84`.
- **Why the worker wedged inside the import.** The captured `py-spy` stack shows
  the lock holder blocked in LangGraph's `BackgroundExecutor.__exit__`, but the
  spliced frames make the precise trigger unprovable from one dump. *Assumption*:
  do not chase the trigger; remove the hazard by never taking a module import
  lock on a request thread. Recorded as an open question rather than a claim.
- **`PIPELINE_TIMEOUT_S` semantics.** Today it is a *specialist-loop* budget
  advertised as a *total-pipeline* budget. Making it truly total changes when a
  slow run degrades. *Human intervention is needed to answer this question* if
  the 120 s default should also cap planning and synthesis outright; this plan
  only makes the deadline **visible** at those boundaries and degrades honestly
  once it has already passed, which cannot make a currently-succeeding run fail.

---

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Add the SSE heartbeat helper
- **Locations**: new `api/services/heartbeat.py` (function `with_heartbeat`);
  new tests in `api/tests/test_heartbeat.py`.
- **Rationale**: `stream_query_events` iterates a *blocking* generator, so no
  frame can be emitted while `next()` is inside an LLM call. The helper drains
  the pipeline iterator on a worker thread into a queue and yields either the
  next real item or a heartbeat sentinel when the queue is idle past the
  interval. Isolating it means both SSE endpoints get identical behaviour and
  the timing logic is unit-testable without HTTP or a model.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: SSE Stall Fix (1/4) Complete: Added the
  `with_heartbeat` iterator helper and its unit tests.

### Step 2: Emit the heartbeat from both SSE endpoints
- **Locations**: `api/services/query.py` (`stream_query_events`),
  `api/services/conversations.py` (`stream_conversation_events`);
  `api/tests/test_query.py`, `api/tests/test_conversations.py`.
- **Rationale**: These are the only two long-lived streams an analyst watches,
  and both have the same silent-LLM-stage shape. Emitting a comment frame keeps
  the typed event contract byte-identical, so `web/lib/types.ts`, `runMachine.ts`
  and the vitest fixtures need no change.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: SSE Stall Fix (2/4) Complete: Both query and
  conversation SSE streams now heartbeat while a stage is silent.

### Step 3: Remove the request-time specialist import
- **Locations**: `api/main.py` (startup warm-up), `utils/specialists/__init__.py`
  (`build_specialist` — docstring only); `api/tests/test_main.py`.
- **Rationale**: `build_specialist` imports its backend subpackage lazily on the
  request thread, so the import lock is taken under a LangGraph worker. A
  request that stalls mid-import wedges every later request in the process —
  observed, with `/api/health` also dead. The server needs both backends anyway,
  so importing them once at startup keeps the CLI's laziness and removes the
  whole failure class from the service.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: SSE Stall Fix (3/4) Complete: The API warms the
  specialist backends at startup so no request thread takes an import lock.

### Step 4: Honour the pipeline deadline at the plan and synthesis boundaries
- **Locations**: `utils/orchestration/main.py` (`plan_node`, `synthesize_node`);
  `utils/orchestration/tests/test_pipeline_graph.py`.
- **Rationale**: `PIPELINE_TIMEOUT_S` is documented as the total-pipeline
  deadline but is only read at `agents/specialists/nodes.py:84`. A run can
  therefore spend 4 × `ARIADNE_LLM_TIMEOUT_S` in the planner alone with the
  120 s budget already blown. Checking the deadline before starting each of the
  two remaining LLM stages makes the advertised budget mean something, and
  degrades to the deterministic path with a stated reason instead of silence.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: SSE Stall Fix (4/4) Complete: The plan and
  synthesis nodes now respect the total-pipeline deadline.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Heartbeat helper | Wraps a blocking event iterator, yielding keep-alives while a stage is silent. | `api/services/heartbeat.py` |
| Heartbeat unit tests | Fake slow iterator asserts keep-alives arrive on interval and real items are never reordered or dropped. | `api/tests/test_heartbeat.py` |
| Query stream heartbeat | `stream_query_events` emits comment frames during silent stages. | `api/services/query.py` |
| Conversation stream heartbeat | Same for the chat pane's stream. | `api/services/conversations.py` |
| Specialist import warm-up | Both backends imported at API startup; no import lock on a request thread. | `api/main.py` |
| Deadline checks | `plan_node` / `synthesize_node` respect the total-pipeline deadline. | `utils/orchestration/main.py` |
| Concurrency probe | Fires N parallel `/api/query` streams and reports the worst silent gap per run — the script that measured 5/12 over 90 s. | `utils/tests/sse_gap_probe.py` |

