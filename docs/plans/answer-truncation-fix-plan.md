# Answer Truncation Fix Plan

## 1. Introduction

Analysts report that the conversational answer is being cut off mid-sentence
(`"Unfortunately, the"`, `"…Disk Content Wipe (T1561."`), and that raising the
LLM's max-token budget does nothing. The displayed reply is produced by the
conversation **answer agent** (`utils/conversation/agents/answer.py`) via
`client.complete(messages, max_tokens=config.llm.max_tokens)` — a different seam
from the synthesis narrator/claims composer. Three compounding causes were
confirmed by reading the code and probing the live LLM relay:

1. **The raised knob never reaches the answer agent.** `config.llm.max_tokens`
   resolves from `CONVERSATION_LLM_MAX_TOKENS` (default `1024`) and, unlike
   `base_url`/`model`/`timeout`, does **not** fall back to
   `SYNTHESIS_LLM_MAX_TOKENS`. The operator raised the synthesis knob; the answer
   agent stayed at 1024.
2. **No `finish_reason` handling anywhere.** Every LLM seam ignores
   `choices[0].finish_reason`. On a `length` stop the partial content is shown
   verbatim (mid-word), and when the relay returns `content: null` on a length
   stop, the `if not content` guard silently degrades to the deterministic path.
   A live probe confirmed the relay returns `finish_reason: "length"` plus a
   `usage` block on truncation — signals currently discarded.
3. **Input pressure hides the real ceiling.** The answer prompt bundles up to 12
   history turns plus an evidence brief of up to 10 records × 600-char
   descriptions; against a bounded model context window the completion is capped
   at `n_ctx − prompt_tokens`, so heavy turns truncate earlier and no client
   `max_tokens` value can recover the space.

The approach: wire the operator's max-token knob through to the answer agent,
make truncation observable and gracefully rendered instead of a silent mid-word
chop, bound the evidence-brief input so output always has headroom, and document
the model-context-window ceiling. All changes are deterministic and LLM-off safe;
each phase lands as its own validated, locally-committed unit (commit, never push).

## 2. Gaps & Unanswered Questions

- **Which endpoint/model synthesis+conversation should use.** The `.env`
  "Synthesis" block is mislabeled (`PLANNER_LLM_BASE_URL/MODEL` where
  `SYNTHESIS_LLM_BASE_URL/MODEL` belong), so both default to the dead
  `:9090`. *Resolved by operator*: point them at `http://localhost:4000/v1`
  model `skynet` (now healthy on the relay).
- **Answer output budget.** *Resolved by operator*: `CONVERSATION_LLM_MAX_TOKENS`
  should inherit `SYNTHESIS_LLM_MAX_TOKENS` (24000) when unset.
- **Truncation rendering when the model still hits its ceiling.** *Assumption*:
  keep the partial answer, trimmed back to the last complete sentence, and append
  a single explicit truncation note naming the knob — this preserves the useful
  content the analyst asked for while being honest, and the verified claim table
  remains the trust surface beneath it. Fall back to the deterministic narrative
  only when nothing usable remains.
- **Real context-window size of `skynet`.** Unknown from the client side and not
  repo-controllable. *Assumption*: surface `usage.prompt_tokens` /
  `completion_tokens` / `finish_reason` in logs so the operator can see when the
  window (not `max_tokens`) is the binding constraint; raising the server's
  context length is an operator action, documented in `.env.example`.
  *(2026-08-04: still unknown, and this is the reading the repository has
  settled on. `skynet` is Gemma 4 31B; the served window and the quantisation
  are recorded as open in [`../evaluation/README.md`](../evaluation/README.md).)*

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Plan (this document)
- **Locations**: `docs/plans/answer-truncation-fix-plan.md`.
- **Rationale**: Capture the confirmed diagnosis and the staged fix before code
  changes, so each phase is independently validatable and reviewable.
- **Action**: Commit (do not push) with a `docs/changelog.jsonl` entry —
  `Answer Truncation Fix (1/6) Complete: authored the diagnosis + staged plan`.

### Step 2: Route the max-token knob to the answer agent
- **Locations**: `utils/conversation/config.py`
  (`ConversationLLMConfig.from_env`); `utils/conversation/tests/test_config.py`.
- **Rationale**: The answer agent's cap must honor the operator's configured
  budget. Make `max_tokens` inherit `SYNTHESIS_LLM_MAX_TOKENS` when
  `CONVERSATION_LLM_MAX_TOKENS` is unset (mirroring the existing base_url/model/
  timeout inheritance), so the value the operator raised actually applies.
- **Action**: Validate `uv run python -m pytest utils/conversation/tests/test_config.py`;
  commit (do not push) + changelog — `Answer Truncation Fix (2/6)`.

### Step 3: Detect and surface truncation in the shared client
- **Locations**: `utils/conversation/llm.py` (`ConversationLLM`): add a
  `CompletionResult` (content, finish_reason, usage) and a
  `complete_verbose()`; keep `complete()` as a thin wrapper; log a WARNING with
  prompt/completion token counts on a `length` finish; treat `content is None`
  on a `length` finish as an explicit truncation rather than a bare "no content".
  Tests in `utils/conversation/tests/`.
- **Rationale**: `finish_reason`/`usage` are the only client-side signals that
  reveal the context-window ceiling; capturing them makes truncation observable
  and lets the answer agent react without breaking the other callers (router,
  validation, orchestration, naming) that keep using `complete()`.
- **Action**: Validate the conversation LLM tests; commit (do not push) +
  changelog — `Answer Truncation Fix (3/6)`.

### Step 4: Render truncation gracefully in the answer agent
- **Locations**: `utils/conversation/agents/answer.py` (`_compose_graph`,
  `_compose_quick`, `compose_answer`); tests in `utils/conversation/tests/`.
- **Rationale**: A mid-word chop must never reach the analyst. On a `length`
  finish, trim the reply to the last complete sentence and append one explicit
  truncation note naming the knob; fall back to the deterministic verified
  narrative only when nothing usable remains.
- **Action**: Validate the answer-agent tests; commit (do not push) + changelog —
  `Answer Truncation Fix (4/6)`.

### Step 5: Bound evidence-brief input pressure
- **Locations**: `utils/conversation/agents/answer.py` (`evidence_brief` and its
  `_MAX_*` bounds); tests in `utils/conversation/tests/`.
- **Rationale**: Record-heavy turns are exactly where the prompt crowds out the
  output budget. Add a total-size (character) budget for the brief so the answer
  prompt stays bounded regardless of how many records a turn returned, leaving
  headroom for the completion within a bounded context window.
- **Action**: Validate the answer-agent tests; commit (do not push) + changelog —
  `Answer Truncation Fix (5/6)`.

### Step 6: Docs, `.env`, regression, and merge
- **Locations**: `.env.example` (document `CONVERSATION_LLM_MAX_TOKENS`
  inheritance + the `n_ctx` ceiling note); operator `.env`
  (`SYNTHESIS_LLM_BASE_URL=http://localhost:4000/v1`,
  `SYNTHESIS_LLM_MODEL=skynet`); full test run across
  `utils/conversation/tests utils/synthesis/tests api/tests`.
- **Rationale**: The env fix is the operational half of the bug (dead default
  endpoint); the docs prevent recurrence; the full suite guards against
  regressions in the shared conversation/synthesis/api surface before merge.
- **Action**: Validate the full suites; commit (do not push) + changelog; merge
  `answer-truncation-fix` → `main` — `Answer Truncation Fix (6/6) Complete`.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Plan | This diagnosis + staged plan | `docs/plans/answer-truncation-fix-plan.md` |
| Max-token inheritance | Answer agent honors `SYNTHESIS_LLM_MAX_TOKENS` fallback | `utils/conversation/config.py` |
| Truncation detection | `finish_reason`/`usage` capture, verbose completion, logging | `utils/conversation/llm.py` |
| Graceful truncation UX | Sentence-trim + explicit note on `length` finish | `utils/conversation/agents/answer.py` |
| Input budget | Total-size cap on the evidence brief | `utils/conversation/agents/answer.py` |
| Config docs | `CONVERSATION_LLM_MAX_TOKENS` + `n_ctx` guidance; endpoint fix | `.env.example`, operator `.env` |
| Unit tests | Config inheritance, finish_reason/verbose completion, truncation render, brief budget | `utils/conversation/tests/test_config.py`, `utils/conversation/tests/test_llm.py`, `utils/conversation/tests/test_answer.py` |

Per phase: validate, then **commit (do not push)** with a `docs/changelog.jsonl`
entry. Merge to `main` only when everything is green.
