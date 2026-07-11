# Intent Classification

Planner step one, made explicit. The proposal charges the planning agent with
four jobs — *read the source cards, **classify the analyst's intent**, identify
required entities/relationships, and emit a machine-readable plan*. This is the
second job as a real, evaluated, and visible step rather than an implicit side
effect of keyword routing.

Two rules govern it:

1. **Every intent label changes the plan.** Intent is a routing signal, not a
   decoration — a label that changes nothing is not carried.
2. **The gate stays the sole authority.** Intent *biases* the draft; it can never
   ship a schema-invalid plan. A mis-classification is safe by construction.

## Taxonomy

A closed set (`utils/planner/intent.py`, `Intent`), each label mapped to a
concrete plan consequence:

| Intent | Consequence | Example |
|---|---|---|
| `correlation` | two sources **+ declared join** on a canonical key | "Which CAPEC patterns map to ATT&CK techniques?" |
| `remediation` | the ATT&CK `mitigates` side | "What mitigations apply to T1555?" |
| `traversal` | a hierarchy / neighbour / chain walk | "What are the sub-techniques of T1021?" |
| `enumeration` | a bounded, filtered scan of a set | "List techniques that use valid accounts" |
| `lookup` | one entity fetched by id | "Look up CAPEC-555" |
| `definitional` | resolve a named entity by name (dossier path) | "What is Phishing?" |
| `unsupported` | no recognizable, in-scope intent | out-of-scope request |

## Classifier

Mirrors the drafter's dual-path design: a deterministic default and an optional
LLM refinement that degrades cleanly back to it.

* **`DeterministicIntentClassifier`** — priority cue rules over the request
  (`correlation` > `remediation` > `traversal` > `enumeration` > `lookup` >
  `definitional`), with a card-aware `lookup`-vs-`unsupported` fallback when no
  cue fires. Reuses the specialists' `is_definitional_intent`. Always available;
  no network.
* **`LLMIntentClassifier`** + **`HybridIntentClassifier`** (`intent_llm.py`) —
  posts to the same OpenAI-compatible endpoint the drafter uses, validates the
  label against the taxonomy, clamps confidence, and on any transport / HTTP /
  parse / out-of-taxonomy failure falls back to the deterministic label (tagged
  `source="fallback"`). Enabled by `PLANNER_INTENT_LLM_ENABLED` (default off);
  `select_intent_classifier(config)` is the factory.

## Where it runs and what it changes

* The planner subgraph runs a **`classify`** node before `draft`
  (`utils/orchestration/agents/planner/`); `finalize`/`degrade` copy the result
  onto the emitted plan as `Plan.intent` (`utils/planner/schema.py`, omitted from
  `to_dict` when absent so pre-intent plan JSON stays byte-identical).
* The drafters **consume** it (`utils/planner/drafter.py`): a `correlation`
  intent pulls in a live, card-valid join partner and declares the canonical
  join when keyword routing found only one side; the name/id-lookup rescue fires
  for a `definitional` question **or** any in-scope intent that names a concrete
  entity id (so bare lookups like "Look up CAPEC-555" route instead of dropping).
  The LLM drafter gets the classified intent as a prompt hint.

## Evaluation

Intent accuracy is a reported planner metric (`utils/planner/evaluation/`).
Ground truth is **independent** of the classifier: generated cases derive
`expected_intent` from the specialist question templates (`build_corpus.py`
`TEMPLATE_INTENT`); curated anchors set it by hand. The scorer emits
`intent_correct` per case and `intent_accuracy_rate` in `aggregate`
(corpus-wide **0.979** at time of writing — the lone miss is a tactic literally
named *Defense Impairment* tripping the remediation cue, exactly the proper-noun
edge case the LLM classifier is positioned to fix).

## On the wire and in the UI

* The super-graph plan node emits a **`classifying`** status phase before
  `planning`; the classified intent rides the existing `plan` event as
  `plan.intent` (`utils/orchestration/main.py`, `api/services/query.py`).
* The workbench shows a **Intent** step in the mini-stepper and an **IntentCard**
  reasoning panel — *what* (label + confidence + which classifier decided),
  *why* (rationale + the exact cues that fired), *how* (the sources routed and
  any declared join) — under the stepper in the Answer Card
  (`web/components/center/IntentCard.tsx`).

## Configuration

| Env var | Default | Effect |
|---|---|---|
| `PLANNER_INTENT_LLM_ENABLED` | off | Use the hybrid LLM classifier (else deterministic only) |
| `PLANNER_LLM_BASE_URL` / `PLANNER_LLM_MODEL` | local endpoint | Shared with the drafter's LLM path |

## Key files

* `utils/planner/intent.py` — taxonomy, `IntentClassification`, deterministic classifier
* `utils/planner/intent_llm.py` — LLM classifier, hybrid, factory
* `utils/planner/schema.py` — `Plan.intent`
* `utils/orchestration/agents/planner/` — the `classify` node
* `utils/planner/drafter.py` — intent-driven routing
* `utils/planner/evaluation/{corpus,scorer,build_corpus}.py` — intent scoring
* `web/components/center/IntentCard.tsx` — the what/why/how panel
