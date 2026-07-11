# Intent Classification — Implementation Plan

## Introduction

The proposal commits the federated planning agent to **"read the source cards,
classify the analyst's intent, identify required entities and relationships, and
emit a machine-readable plan."** Every clause of that sentence is implemented in
code today **except intent classification**, which is only implicit. Routing is
keyword/identifier matching in `utils/planner/drafter.py` (`_match_card`), and the
only explicit intent signal is a binary `is_definitional_intent` regex borrowed
from `utils/specialists/resolve.py` and used as a dead-end rescue path. There is
no intent taxonomy, no `intent` field on the `Plan`, and no intent metric in the
planner evaluation.

This plan makes intent classification a **first-class, evaluated, and
fully-visible** step of the planner. Two design rules govern it:

1. **Every intent label must change something concrete** — source selection,
   whether a join is expected, decomposition count, or which specialist path
   fires. An intent that changes nothing is decoration, not classification.
2. **The gate stays the sole authority.** Intent *biases* the draft; it can
   never ship a schema-invalid plan. This preserves the existing
   draft → gate → revise/degrade safety contract.

The classifier follows the exact dual-path pattern the drafter already uses
(`DeterministicDrafter` default + `OpenAICompatibleDrafter` hybrid with clean
fallback): a deterministic classifier is always available, an optional LLM
classifier refines it and degrades to deterministic on any failure.

The second half of the plan is the **front-end transparency requirement**:
whatever the backend decides, the analyst must see *what* it decided, *how* it
acted on that decision, and *why* — step by step. Intent classification becomes
a visible planner sub-step, and the plan's reasoning (intent, cues, rationale,
routing consequence, drafter used, gate iterations) is elevated from today's
scattered/hidden fields into one reasoning surface.

## Intent taxonomy (assumption — adjustable)

A closed set; each label maps to a real routing consequence and to specialist
templates that already exist (`capec_maps_to`, `dossier`, `reverse_maps`,
`hierarchy_chain`, Cypher intent templates):

| Intent | Consequence in the plan | Example |
|---|---|---|
| `definitional` | name-not-id → dossier/name-lookup path; single source | "What is Phishing?" |
| `lookup` | one source, entity by id, no join | "Show T1555's properties" |
| `enumeration` | one source, broad filtered scan | "List techniques using valid accounts" |
| `correlation` | two sources **+ expected join** on a canonical key | CAPEC credential-theft → ATT&CK → mitigations |
| `remediation` | ATT&CK side, `mitigates` edges | "What mitigations apply to T1555?" |
| `traversal` | neighbours / hierarchy / chain on one source | "What is the parent of CAPEC-560?" |
| `unsupported` | nothing routable → honest partial | out-of-scope request |

## Gaps & unanswered questions

- **[Assumption]** The 7-label taxonomy above. Sensible default; the maintainer
  may prune/rename before Phase 1. Everything downstream keys on these strings.
- **[Assumption]** Intent is **bias-only** — it never overrides the gate and
  never forces a source the cards don't support.
- **[Assumption — flagged consequence]** Adding `intent` to `Plan.to_dict`
  changes plan JSON, so the planner expected-plan fixtures, the event-order
  goldens (orchestration/specialists/api), and any committed plan snapshots must
  be **regenerated intentionally** (mirrors the `SubQuestion.hop` precedent,
  where `to_dict` omits the field when absent to protect byte-identity). To
  minimise churn, `to_dict` omits `intent` when `None`; it is populated whenever
  the classifier runs.
- **[Assumption]** LLM classifier reuses the existing `PlannerConfig` LLM knobs
  (`PLANNER_LLM_*`) gated behind a new `PLANNER_INTENT_LLM_ENABLED`, defaulting
  **off** so the LLM-off build stays reproducible.
- **[Open — low risk]** Whether to keep `is_definitional_intent` as the
  deterministic classifier's `definitional` rule (reuse) or inline a superset.
  Plan assumes **reuse** to avoid divergence.
- **[Standing directive]** Per the maintainer's standing instruction, each phase
  ends with a **commit + changelog entry but no push** (this overrides global
  rule #1's push mandate). Merging/pushing is the maintainer's call.

## Phases

### Phase 1 (1/8) — Intent taxonomy + deterministic classifier
- **Where:** new `utils/planner/intent.py` — `Intent` (closed string constants),
  `IntentClassification` (frozen: `label`, `confidence`, `rationale`, `cues:
  list[str]`, `source: "deterministic"|"llm"|"fallback"`, `to_dict`/`from_dict`),
  `IntentClassifier` Protocol, `DeterministicIntentClassifier` (cue rules:
  `map to`/`related to`/`across` → correlation; `mitigat*`/`remediat*` →
  remediation; `list`/`which`/`all` → enumeration; reuse `is_definitional_intent`
  → definitional; id-only → lookup; neighbour/parent/child/chain → traversal;
  else best-effort with low confidence).
- **Tests:** `utils/planner/tests/test_intent.py` (one case per label + tie-break).
- **Validation:** `uv run python -m pytest utils/planner/tests/test_intent.py`.
- **Wrap-up:** commit + changelog (no push).

### Phase 2 (2/8) — Plan carries intent; classifier wired into the subgraph
- **Where:** `utils/planner/schema.py` (`Plan.intent: IntentClassification | None`,
  `to_dict` omits when `None`, `from_dict` tolerant); `utils/orchestration/state.py`
  (`PlanningState` gains `intent`); `utils/orchestration/agents/planner/nodes.py` +
  `graph.py` (new `classify` node before `draft`; `finalize` copies intent onto the
  plan); `utils/planner/agent.py` unchanged public contract.
- **Tests:** extend planner subgraph tests; regenerate affected plan fixtures.
- **Validation:** `uv run python -m pytest utils/planner/ utils/orchestration/`.
- **Wrap-up:** commit + changelog (no push).

### Phase 3 (3/8) — LLM classifier (hybrid path) + factory
- **Where:** `LLMIntentClassifier` (in `intent.py` or `intent_llm.py`) reusing the
  `PlannerConfig` LLM settings; `select_intent_classifier(config)` mirroring
  `utils/planner/drafter_factory.py`; any failure → `DeterministicIntentClassifier`
  with `source="fallback"` recorded. Config knob `PLANNER_INTENT_LLM_ENABLED`
  in `utils/planner/config.py` (default off).
- **Tests:** stubbed-endpoint success + forced-fallback cases (no live HTTP).
- **Validation:** `uv run python -m pytest utils/planner/tests/`.
- **Wrap-up:** commit + changelog (no push).

### Phase 4 (4/8) — Drafters consume intent (the routing consequence)
- **Where:** `utils/planner/drafter.py` — `definitional` fires the name-lookup
  path directly (not only as a dead-end rescue); `correlation` proactively
  prefers two-source selection + join declaration when candidates exist; intent
  noted in `rationale`. `utils/planner/llm_drafter.py` — pass the classified
  intent into the prompt context.
- **Tests:** drafter cases asserting intent changes routing (correlation declares
  the join; definitional routes name lookup).
- **Validation:** `uv run python -m pytest utils/planner/`.
- **Wrap-up:** commit + changelog (no push).

### Phase 5 (5/8) — Evaluate intent
- **Where:** `utils/planner/evaluation/corpus.py` (`ExpectedCase.expected_intent`),
  `scorer.py` (`intent_correct` flag + `intent_accuracy_rate` in `aggregate`,
  surfaced in `CaseScore.to_dict`), `build_corpus.py` (emit `expected_intent`),
  fill `expected_intent` across `expected_plans/*.json` + `generated/`.
  `utils/evaluation/component_report.py` includes the new metric.
- **Tests:** `utils/planner/tests/test_evaluation.py` updated; regenerate corpus.
- **Validation:** `uv run python -m pytest utils/planner/ utils/evaluation/`.
- **Wrap-up:** commit + changelog (no push).

### Phase 6 (6/8) — Stream intent as a visible step
- **Where:** `utils/orchestration/main.py` — emit a `status(classifying)` phase
  and ensure the `plan` event carries `plan.to_dict()` intent (already flows via
  `api/services/query.py:render_pipeline_event`). Update the event-order docstring
  + goldens.
- **Tests:** `api/tests` + `utils/orchestration/tests` event-order goldens
  regenerated; `utils/specialists` parity goldens if touched.
- **Validation:** `uv run python -m pytest api/ utils/orchestration/ utils/specialists/`.
- **Wrap-up:** commit + changelog (no push).

### Phase 7 (7/8) — Front end: show what / how / why, step by step
- **Where:**
  - `web/lib/types.ts` — `IntentClassification` type + `Plan.intent`.
  - `web/lib/runMachine.ts` — add `stage-classify` to `PLANNER_STAGE_IDS`; handle
    the `classifying` status phase; intent rides on the existing `plan` event.
  - `web/components/center/MiniStepper.tsx` — render the new **Classify** step
    (so the *step* is visible in the progress meter).
  - **New** `web/components/center/IntentCard.tsx` (+ surface in the inspector) —
    the reasoning panel: **what** (intent label badge), **why** (confidence,
    matched cues, rationale, drafter/classifier source), **how** (routing
    consequence — sources chosen, join declared, iterations/gate trace). This
    also *elevates* `plan.rationale`, `plan.assumptions`, and `plan.trace`, which
    exist today but are barely surfaced.
  - `web/lib/adapt.ts` / `buildRun` — thread intent through the run model.
- **Tests:** Vitest cases for the folded intent + IntentCard rendering.
- **Validation:** `cd web && npm run lint && npm test && npm run build` (build is
  mandatory after webfront changes).
- **Wrap-up:** commit + changelog (no push).

### Phase 8 (8/8) — Docs + full regression
- **Where:** new `docs/intent-classification.md`; update `docs/structure.md`
  (classify node + `status(classifying)` + `Plan.intent`), `docs/planner_agent.md`
  (intent step + taxonomy), `docs/goals.md` if it tracks the four-component
  contract.
- **Validation:** full regression — `uv run python -m pytest` (utils + api),
  `cd web && npm test && npm run build`. Confirm the eval baselines were
  regenerated **intentionally** and the diff is explained in the changelog.
- **Wrap-up:** commit + changelog (no push).

## Deliverables

| # | Deliverable | Primary locations | Validation |
|---|---|---|---|
| 1 | Intent taxonomy + deterministic classifier | `utils/planner/intent.py`, `tests/test_intent.py` | pytest |
| 2 | `Plan.intent` + classify node in subgraph | `schema.py`, `orchestration/agents/planner/`, `state.py` | pytest (planner+orch) |
| 3 | LLM classifier + factory + fallback | `intent.py`/`intent_llm.py`, `drafter_factory` sibling, `config.py` | pytest (stubbed) |
| 4 | Drafters act on intent (routing changes) | `drafter.py`, `llm_drafter.py` | pytest |
| 5 | Intent scored in planner eval | `evaluation/{corpus,scorer,build_corpus}.py`, `expected_plans/`, `component_report.py` | pytest |
| 6 | Intent streamed as a visible step | `orchestration/main.py`, event-order goldens | pytest (api+orch) |
| 7 | Front-end what/how/why surface | `types.ts`, `runMachine.ts`, `MiniStepper.tsx`, new `IntentCard.tsx`, `adapt.ts` | lint + vitest + build |
| 8 | Docs + full green regression | `docs/intent-classification.md`, `structure.md`, `planner_agent.md` | full pytest + web build |

## Success criteria

- The planner emits a named intent on every plan; the intent measurably changes
  routing (correlation declares the join; definitional routes the name lookup).
- Intent accuracy is a reported number in the planner component report.
- The analyst sees a **Classify** step and a reasoning panel giving intent (what),
  cues + rationale + classifier source (why), and routing consequence + gate
  iterations (how) for every query.
- Full regression green; eval-baseline changes are intentional and changelogged.
- The LLM-off build remains deterministic and reproducible.
