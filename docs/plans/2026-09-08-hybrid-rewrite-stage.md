# Hybrid rewrite stage — turning any phrasing into the question the engine already answers

**Date:** 2026-09-08
**Mode:** B — no worktree, straight onto `main`.
**Commit at every step. Never push.** The planner skill's template says "push to
GitHub"; the operator's standing directive and `global-project-rules` rule 1
both override it. Every step also appends to `docs/changelog.jsonl`.

**Agent workflow, if used:** Opus plans (this file), Haiku searches, Sonnet
implements. Steps 1 and 3 are independent of each other and can run in
parallel; Step 2 needs Step 1's form schema; Step 4 needs Steps 1 and 3; Steps
5–8 are sequential.

---

## 1. Introduction

The deterministic engine is not the weak part of this system. On the 120 gold
questions as written it scores **1.0000** on every metric of the variant
harness (EXP-2026-08-020, T0). It is also the part every published claim rests
on: no model writes a query, retrieval is byte-identical across runs
(EXP-2026-09-010), and abstention is provable. What the same experiment showed
is that this correctness is a property of *phrasing*: keep the identifier and
change one verb and record identity falls to **0.50**; drop the identifier and
keep the exact name, **0.24** (Arm 6); paraphrase the name or describe the
entity, **exactly 0.0000 on 208 questions across every arm tried**. The
candidate index that could close that gap was measured at 68% precision on a
frozen half and correctly left switched off, because the accept decision —
"is the top candidate what the analyst meant?" — is the decision no threshold
on the available signals could make.

This plan builds the hybrid the operator asked for by putting one new stage in
front of the engine and changing nothing behind it. The stage rewrites the
analyst's question into a **canonical, tier-0 form in the source card's own
vocabulary**: a fixed intent form (anchors, labels, relation, direction, mode)
that a deterministic renderer turns into the sentence the engine already
answers perfectly. A deterministic pass fills as much of the form as stems,
exact names and the resolver ladder can bind; when slots remain unbound, the
existing name index produces **candidate lists**, and a language model fills
the remaining slots **by choosing from those lists only**. A gate rejects any
choice that is not in the card or not in a list, and the question abstains
rather than guesses. The model therefore renames and selects; it never plans
and never writes a query — the constraint Step 7 of the 2026-08-29 plan set and
never got to build. Model choices are cached by question hash so evaluation
re-runs are free and repeatable, and with the stage off the pipeline is
byte-identical to today, which every step below re-proves.

The measurement is the deliverable as much as the code. The stage is scored on
the frozen 579-variant bank per tier against the same reference Arms 0–6 used,
so arm-to-arm deltas carry no authoring variance; on the 572-question expansion
bank's dev and holdout halves; and, per the operator's directive, with **two
served models on `:9090` — `default-model` and `default-model-2` — three runs
each**, alongside a model-off arm that must be byte-identical to the shipped
Arm 6 reference. Each model's real identity is probed and recorded before any
run, because an alias is not a model (D-028).

---

## 2. Gaps & Unanswered Questions

**Resolved by assumption — proceeding.**

- **What the "form" is.** *Assumption:* the same five slots
  `docs/evaluation/variants-2026-08-29/slot_gold.json` already records for
  every gold question — `anchors`, `anchor_labels`, `target_labels`,
  `relation`, plus a `mode` (describe / enumerate / count) and `direction`
  derived from the card's declared edge endpoints. That file was built from
  question metadata and raw-source answers, never from system behaviour, which
  is exactly why it can serve as the understanding-gold for this stage without
  defining the incumbent as correct.
- **How the engine consumes the form.** *Assumption:* through a **rendered
  canonical sentence**, not a new plan type. A deterministic renderer emits
  the T0 wording for the form (one sentence template per relation, seeded from
  the card's `entity_descriptions` glosses), and the existing drafter receives
  that sentence as `request`. This keeps `utils/specialists/` untouched, keeps
  the byte-identical claim trivially true with the flag off, and makes the
  stage testable on its own: render(slot_gold) must round-trip to the gold
  question's records. Passing structured seeds directly to the drafter is a
  later optimisation, not a prerequisite.
- **Which split is reported.** The 2026-08-31 split's `report` half was spent
  once, on the name-index margin threshold, and EXP-2026-08-020 says any future
  threshold work needs a fresh split. This stage fits no threshold, but a
  prompt iterated against a bank is fitted to it all the same. *Assumption:*
  prompt and renderer development happen **only on the `tune` half**; the
  `report` half is run once at the end and disclosed as "seen once before, for
  a different mechanism"; and the expansion bank's `bank-holdout.json` — never
  seen by anything in this stage — is the second, clean report set.
- **Cache location.** *Assumption:* the model's picks are cached under the
  experiment's `data/` folder (committed, so the run is reproducible from the
  record), keyed by `sha256(prompt_version, served_model_identity, question)`.
  A workbench-time cache under `data/cache/` (git-ignored) is the same
  mechanism with a different root.
- **Concurrency and budget.** *Assumption:* 16 workers (32 raised fallbacks
  in EXP-2026-08-019), `max_tokens ≥ 2048` with `thinking_budget` under it
  (the served model is a reasoning model that truncates to empty otherwise),
  `sampling_params()` for greedy seeded decoding.
- **Where the conversation rewrite goes.** *Assumption:* the existing
  `resolve_question` node stays as the multi-turn front door and its output is
  this stage's input; the thread's held anchor becomes a pre-filled anchor
  slot. No behaviour of that node changes in this plan.
- **Negative controls are a gate, not a metric.** *Assumption:* an arm that
  raises T6 `wrong_entity` above Arm 6's 0.1000 or T6 `catalogue_dump` above
  0.0667 does not ship regardless of how much T4/T5 improve. Confident-and-
  wrong is the failure this project exists to avoid; the pre-registration in
  Step 7 says so before any number is seen.

**Human intervention is needed to answer these.**

- **Ship threshold.** What T4/T5 record identity, at what T6 cost, is enough
  to flip `ARIADNE_REWRITE` and `ARIADNE_REWRITE_MODEL` on by default? The
  plan pre-registers *"T4 and T5 `records_exact` both > 0.25 with every T6
  metric no worse than Arm 6"* as the ship rule and reports against it;
  confirm or replace that rule **before Step 7 runs**, not after.
- **Which `default-model-2` is meant.** On 2026-09-05 `default-model-2` on
  `:9090` served `gemma4-31B-mtp` one afternoon and failed to serve at all
  that night. Step 0 probes it; if it resolves to the same weights as
  `default-model` the comparison is a repeatability check, not a model
  comparison, and the operator should say whether to substitute
  `default-model-3` or wait.
- **Ambiguity surface.** When the model returns "ambiguous" the stage can
  abstain, or it can show the analyst the candidate list the way the resolver's
  `AmbiguousAnchor` already does. The plan wires the abstention; the
  "did you mean?" surface is a UI decision to confirm.

---

## 3. Hierarchical Step-by-Step Instructions

### Step 0 — Preconditions: live graphs, model identities, baseline reference

- **Locations:** `uv run main.py --graph verify` (both datasets — `health`
  is not a content probe, I-1); `scripts/model_identity.py --json --date
  2026-09-08` for `default-model` and `default-model-2` on `:9090`;
  `scripts/variant_harness.py capture` against
  `docs/evaluation/variants-2026-08-29/reference_arm6.json`.
- **Rationale:** every later number is read against a reference that must be
  byte-identical to the shipped Arm 6 capture, on graphs that are actually
  loaded, with model strings that name weights rather than aliases. If the
  reference does not match, nothing after this is interpretable; if
  `default-model-2` is down or identical to `default-model`, the operator
  decides now (see §2) rather than after a wasted overnight.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Hybrid Rewrite Stage
  (0/8) Complete: graphs verified, both model identities recorded, Arm 6
  reference re-captured byte-identical.

### Step 1 — The intent form and its deterministic renderer

- **Locations:** new `utils/planner/canonical.py` — `IntentForm` dataclass
  (`anchors`, `anchor_labels`, `target_labels`, `relation`, `direction`,
  `mode`, `datasets`, `unbound: list[str]`), `render(form, cards) -> str`,
  `form_from_slot_gold(record)`; templates for the sentence per relation read
  the card's `entity_descriptions` (`utils/planner/cards.py` `SourceCardView`)
  so nothing in the renderer names ATT&CK or CAPEC. Tests in
  `utils/planner/tests/test_canonical.py`. A round-trip script
  `scripts/rewrite_roundtrip.py` that renders every `slot_gold.json` record,
  runs it through the deterministic pipeline via `variant_harness`'s capture
  path, and diffs records against `reference_arm6.json`.
- **Rationale:** the whole design rests on one property — a correctly filled
  form renders to a question the engine answers exactly as it answers the
  gold question. That must be proved on the 120 gold forms before any model is
  involved, and every gold question whose rendered form does *not* round-trip
  is a finding about the renderer or about the gold (the 2026-08-30 plan's
  "disagreement is a finding" rule), listed in the experiment's `ISSUES.md`,
  never silently reconciled.
- **Validation:** unit tests for rendering each relation and each mode; the
  round-trip reports how many of 120 match `records_exact` (target: all
  scorable ones), with every miss explained.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Hybrid Rewrite Stage
  (1/8) Complete: intent form and deterministic renderer round-trip the gold
  forms to the Arm 6 records.

### Step 2 — Deterministic fill: bind every slot the existing machinery can

- **Locations:** `utils/planner/canonical.py` `deterministic_fill(question,
  cards, intent) -> IntentForm`, composed from what is already shipped:
  `utils/planner/lexicon.py` (`stem`, `within_one`, `gloss_forms`) through
  `drafter.py`'s `_concept_indexes` / `_match_card` for relation and label
  slots; `utils/specialists/schema/namesearch.py` `exact_name_matches` and
  the resolver ladder in `utils/specialists/resolve/resolver.py` for anchor
  slots; `utils/planner/intent.py` `DeterministicIntentClassifier` for
  `mode`; `utils/planner/schema.py` / `edge_correspondence.py` for
  `direction` from the card's declared endpoints. Flag `ARIADNE_REWRITE`
  (default **off**) in `utils/planner/config.py` `PlannerConfig`.
- **Rationale:** this is the "skip the model" path in the diagram. Everything
  that binds here is byte-reproducible and costs nothing, and T0/T1/T2
  questions should mostly bind completely so the model is never called for
  them. The function's contract is that it never guesses: an unbound slot is
  reported in `form.unbound`, not filled with the best available match — the
  ranked index is deliberately *not* consulted here (EXP-2026-08-020 Step 6).
- **Validation:** tests that T0 wording binds fully, that a synonym verb binds
  the relation through the lexicon, that an exact name binds the anchor, that
  a paraphrased name leaves the anchor unbound; with the flag off,
  `variant_harness.py capture` is byte-identical to Step 0's reference.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Hybrid Rewrite Stage
  (2/8) Complete: deterministic fill binds what the shipped machinery can and
  reports the rest as unbound; flag-off path byte-identical.

### Step 3 — Candidate lists for the unbound slots

- **Locations:** `utils/planner/canonical.py` `candidate_lists(question,
  form, cards) -> CandidateLists`; entity candidates from
  `namesearch.search_in(...)` top-k (k = 5) restricted to the labels already in
  scope, carrying id, name and the first sentence of the description;
  relation candidates = the card's `relationship_types` with their
  `entity_descriptions` gloss; label candidates = `node_labels`. Tests in
  `utils/planner/tests/test_canonical.py` plus a measurement script
  `scripts/rewrite_candidates.py` that reports **recall@k of the gold anchor**
  per tier on the `tune` half only.
- **Rationale:** the name index "works as a component and fails as a router"
  — the right entity is usually in the top one or two. This step uses it only
  as a list producer, with no accept decision and no threshold, so nothing
  here can be over-fitted. Recall@k is the ceiling on what Step 4's model can
  achieve and must be known before the model is blamed or credited.
- **Validation:** unit tests on a fixture index; recall@5 per tier recorded
  in the experiment folder.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Hybrid Rewrite Stage
  (3/8) Complete: candidate lists built from the existing index, recall@k
  ceiling measured per tier.

### Step 4 — The model fills the form from the lists, and the gate checks it

- **Locations:** new `utils/planner/rewrite_llm.py` — prompt builder
  (question + candidate lists with indices + relation glosses + the fixed
  JSON schema), transport through `utils/llm` `chat` with
  `utils/llm_sampling.sampling_params` and the `ARIADNE_LLM_*` group
  (`utils/llm/config.py`), JSON parsing via `llm_drafter.extract_json_object`,
  a `RewriteUnavailable` exception mirroring `DrafterUnavailable`; a cache
  (`utils/planner/rewrite_cache.py`) keyed by
  `sha256(PROMPT_VERSION, served_model, question)` with a root configurable
  by `ARIADNE_REWRITE_CACHE_DIR`. `gate_form(form, lists, cards)` in
  `canonical.py`: every anchor must be an index into the list, every label in
  `node_labels`, every relation in `relationship_types`, direction consistent
  with the card's endpoints, else the form is marked abstain with a reason.
  Flag `ARIADNE_REWRITE_MODEL` (default **off**). Tests in
  `utils/planner/tests/test_rewrite_llm.py` with a fake client.
- **Rationale:** this is the one purple box that is new. It differs from the
  LLM drafter (−0.1185) and the free-form query arm (0.50) in kind, not
  degree: it cannot name a source, choose a hop, or emit an identifier that
  is not on the list it was handed. The gate is what makes "closed choice"
  true rather than asserted; the cache is what makes a model seam
  re-runnable for free and lets Step 7 separate model variance from pipeline
  variance.
- **Validation:** gate tests that an invented label, an invented id, an
  out-of-range index and a reversed direction are each rejected; a fake-client
  test that a returned "ambiguous" abstains; a cache hit test; with the
  model flag off the pipeline is byte-identical to Step 2.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Hybrid Rewrite Stage
  (4/8) Complete: gated, cached model fill that can only choose from the
  candidate lists.

### Step 5 — Wire the stage into the planner graph and the record

- **Locations:** `utils/orchestration/agents/planner/nodes.py` `build_nodes`
  — new `canonicalize` node between `classify` and `draft`, so `draft`
  receives the rendered canonical sentence as `request` when the stage
  binds, and the original request otherwise; `graph.py` edges
  `classify → canonicalize → draft`; `utils/orchestration/state.py`
  `PlanningState` gains `canonical_question`, `intent_form`, `rewrite_trace`
  (`rung ∈ {off, deterministic, model, abstain}`, served model, cache hit,
  unbound slots); the trace is copied into `run_meta.rewrite` on the answer
  (where `run_meta.synthesis` already lives) and emitted as a `context` SSE
  event next to the conversation node's `resolved_question`
  (`utils/conversation/agents/orchestration.py`). The thread's held anchor
  pre-fills the anchor slot.
- **Rationale:** the answer record has to say which rung answered, because
  the paper's sentence is "the model was consulted on X% of questions and
  those scored Y". Placing the node after `classify` keeps intent available
  to the deterministic fill; placing it before `draft` keeps the drafter,
  gate, specialists and composer untouched.
- **Validation:** `uv run python -m pytest utils/orchestration/tests
  utils/planner/tests api/tests` with `ORCH_MAX_HOPS=5` and the LLM flags
  explicitly off in the environment (the API's import-time `load_env()` will
  otherwise send "LLM-off" tests to the live model); flag-off 120-question
  capture byte-identical to Step 0; one manual workbench run showing the
  `context` event. No webfront change in this plan, so no `npm run build`.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Hybrid Rewrite Stage
  (5/8) Complete: canonicalize node wired before draft with rung provenance
  on every answer; flag-off pipeline byte-identical.

### Step 6 — Harness: score the stage per tier, per slot, per model

- **Locations:** `scripts/variant_harness.py` — `compare` gains
  `--rewrite {off,det,model}`, `--llm-model`, `--repeat N`,
  `--cache-dir`, and writes the served-model identity into every scored
  record; scoring gains **slot accuracy** against `slot_gold.json` (per slot
  and `form_exact`) and `rung`, `model_consulted`, `cache_hit`, `latency_s`
  beside the existing `records_exact`, `records_recall`, `queries_exact`,
  `abstained`, `wrong_entity`, `catalogue_dump`. `scripts/score_bank.py`
  gains `--rewrite` so the 572-question expansion bank is scored with the
  stage on and off, dev and holdout apart. A metrics aggregator writes
  `data/metrics.json` for the experiment. Tests in
  `utils/specialists/evalset/tests/test_variant_scoring.py` on a three-case
  fixture.
- **Rationale:** slot accuracy is the metric that isolates *understanding*
  from *retrieval*: a form that is right but renders to a sentence the engine
  mishandles is a renderer defect, and a wrong form that still retrieves the
  gold by dumping is the I-11 failure class. Both are invisible in
  `records_exact` alone. Per-model, per-repeat fields are what let Step 7
  report mean and spread rather than one draw.
- **Validation:** fixture tests for every new metric; a dry `--limit 5` run
  per mode producing the expected fields; the `report` half physically
  filtered out unless `--split report` is passed.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Hybrid Rewrite Stage
  (6/8) Complete: variant and bank harnesses score the stage per tier, per
  slot, per model and per repeat.

### Step 7 — The experiment: two models, three runs each, pre-registered

- **Locations:** `make new-experiment SLUG=hybrid-rewrite-stage` →
  `docs/research/experiments/EXP-2026-09-014-hybrid-rewrite-stage/`;
  `PROTOCOL.md` written and committed **before** any model run, carrying the
  hypotheses, the ship rule from §2, and the arms; `manifest.yaml` with one
  `model:` entry per arm in the `relay/<served-model>@<date>` shape from
  Step 0; runs into `data/`; `ISSUES.md` for every anomaly.
  Arms, all on the `tune` half first and the `report` half plus
  `bank-holdout.json` once at the end:
  - **R0** rewrite off — must be byte-identical to Arm 6's reference.
  - **R1** deterministic fill only (`ARIADNE_REWRITE=1`, model off).
  - **R2** model fill, `default-model` on `:9090`, **3 runs**, cache cleared
    between runs so model variance is measured, then a 4th run from cache to
    prove the cache reproduces run 3.
  - **R3** model fill, `default-model-2` on `:9090`, **3 runs**, same protocol.
  - **R4** the 572-question expansion bank, dev and holdout, rewrite off /
    det / model with whichever model R2–R3 ranked first, one run.
  Also recorded per arm: model-consulted rate, cache hit rate, mean latency,
  token cost, and the recall@k ceiling from Step 3 for comparison.
- **Rationale:** the operator's directive is a model comparison on `:9090`,
  and Q2's unfinished half is that no LLM-in-the-loop arm has ever been run
  twice. Three seeded runs per model, with a cleared cache, give the first
  mean-and-spread on a model seam in this pipeline; the cached fourth run
  shows what the cache buys. Pre-registering the ship rule and the T6 gate is
  what stops this from becoming a tuning exercise on the bank.
- **Validation:** R0 diff empty; every run's manifest names weights not an
  alias; `report` half and `bank-holdout.json` each read exactly once and
  the run logs show it; the spread across the three runs per model reported
  as sd, not as a single number.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Hybrid Rewrite Stage
  (7/8) Complete: EXP-2026-09-014 run — rewrite off / deterministic /
  default-model ×3 / default-model-2 ×3 on the variant bank, plus the
  expansion bank dev and holdout.

### Step 8 — Write-up, decisions, defaults

- **Locations:** `EXP-2026-09-014/RESULTS.md` with every figure read from
  `data/metrics.json`; `docs/research/OPEN_QUESTIONS.md` (Q2's LLM-arm
  variance half, Q28's threshold question, the T4/T5 zero); `CLAIMS.md` —
  a new claim only if the ship rule is met, scoped to the tiers and the
  model it was measured on; `DECISIONS.md` — one entry recording the
  rewrite-stage placement and the "selects, never plans" rule, and one
  recording the default-flag decision either way; `utils/planner/config.py`
  flag defaults changed **only** if the pre-registered rule holds and the
  operator confirms; `docs/changelog.jsonl`.
- **Rationale:** a number that exists only in a chat log does not exist. The
  default-on decision is the operator's, made against the rule written in
  Step 7's protocol, and the record must show the rule preceded the result.
- **Validation:** `make validate-research` and `make index` pass; every
  metric quoted in RESULTS.md resolves to a key in `metrics.json`; flag
  defaults match the DECISIONS entry.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Hybrid Rewrite Stage
  (8/8) Complete: results, decisions and defaults recorded; research record
  validates.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Model identity probes | Served-weights strings for `default-model` and `default-model-2` on `:9090`, dated | `EXP-2026-09-014/manifest.yaml` (via `scripts/model_identity.py --json`) |
| Intent form + renderer | `IntentForm`, `render()`, `form_from_slot_gold()`; card-driven sentence templates | `utils/planner/canonical.py` |
| Round-trip proof | Renders all 120 gold forms and diffs records against Arm 6; misses listed | `scripts/rewrite_roundtrip.py`, `EXP-2026-09-014/ISSUES.md` |
| Deterministic fill | Binds slots from lexicon, exact names, resolver ladder, intent, card endpoints; never guesses | `utils/planner/canonical.py` `deterministic_fill()` |
| Candidate lists + recall@k | Top-k entities from the name index, relations and labels from the card; ceiling per tier | `utils/planner/canonical.py` `candidate_lists()`, `scripts/rewrite_candidates.py` |
| Gated model fill | Prompt, transport, JSON parse, `RewriteUnavailable`; gate rejects anything off-list or off-card | `utils/planner/rewrite_llm.py`, `utils/planner/canonical.py` `gate_form()` |
| Rewrite cache | Keyed by prompt version, served model, question; committed under the experiment for runs | `utils/planner/rewrite_cache.py`, `EXP-2026-09-014/data/cache/` |
| Planner wiring + provenance | `canonicalize` node, state fields, `run_meta.rewrite`, `context` SSE event | `utils/orchestration/agents/planner/{nodes,graph}.py`, `utils/orchestration/state.py`, `utils/conversation/agents/orchestration.py` |
| Flags | `ARIADNE_REWRITE`, `ARIADNE_REWRITE_MODEL`, `ARIADNE_REWRITE_CACHE_DIR`, all default off | `utils/planner/config.py`, `.env.example` |
| Harness extensions | `--rewrite`, `--llm-model`, `--repeat`, slot accuracy, rung and model fields; bank scoring with the stage on/off | `scripts/variant_harness.py`, `scripts/score_bank.py` |
| Unit tests: form and renderer | Each relation and mode renders; slot_gold forms load | `utils/planner/tests/test_canonical.py` |
| Unit tests: deterministic fill | T0 binds fully; synonym verb binds relation; exact name binds anchor; paraphrase leaves it unbound | `utils/planner/tests/test_canonical.py` |
| Unit tests: gate and model fill | Invented label / id / index / direction rejected; "ambiguous" abstains; cache hit; flag-off byte-identical | `utils/planner/tests/test_rewrite_llm.py` |
| Unit tests: scoring | Every new metric on a three-case fixture; `report` half filtered unless requested | `utils/specialists/evalset/tests/test_variant_scoring.py` |
| Pipeline tests | Node ordering, state fields, provenance on the answer, flag-off identity | `utils/orchestration/tests/test_planner_canonicalize.py` |
| Experiment record | PROTOCOL (pre-registered), manifest, per-arm runs, metrics.json, RESULTS, ISSUES | `docs/research/experiments/EXP-2026-09-014-hybrid-rewrite-stage/` |
| Ledger updates | Open questions, claims (conditional), two decisions, changelog entries per step | `docs/research/{OPEN_QUESTIONS,CLAIMS,DECISIONS}.md`, `docs/changelog.jsonl` |
