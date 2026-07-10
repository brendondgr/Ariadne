# Name-Anchored Retrieval Plan

## 1. Introduction

When a question names an entity ("Phishing") instead of citing an id (`T1566`), the retrieval
pipeline has no way to anchor a query: seeds come exclusively from id-shaped tokens in the
sub-question text, so a name-only question falls through every intent template to a bare label
scan. The observed failure — "How do you detect phishing?" returning all 222 techniques and a
confabulated answer — was exactly this: the LLM drafter died mid-turn, the deterministic fallback
matched only the `DETECTS` relationship (a signal the Cypher builder then ignored, because intent
checks look at labels only), and the builder emitted `MATCH (n:Technique) RETURN …`. The
validation safety net was down the same turn, so 222 junk rows became "evidence". The sibling
mitigation turn had the identical first-pass failure and was only rescued because the validation
LLM happened to be alive and injected "T1566" into the retry.

This plan makes the *first pass* correct in all three regimes (LLM planner up, deterministic
fallback, validation down) by adding deterministic name→query anchoring: the shared resolver
extracts name terms from the task text, both builders gain name-anchored templates that scope
queries with a case-insensitive name filter plus the in-scope intent edge (`DETECTS` /
`MITIGATES`), the deterministic drafter bridges detection/mitigation keywords to the right
entity scope, and the conversation layer's rewrite step learns to append known ids from memory.
All new behavior is deterministic (LLM-off safe) and every step lands as its own validated,
committed unit — committed locally, never pushed.

## 2. Gaps & Unanswered Questions

- **Noise in token-derived name terms**: free-text tokens ("works", "information") could ride
  along with the real name term. *Assumption*: extract quoted phrases first (highest confidence);
  otherwise filter tokens through the existing stopword list, the card's schema-identifier
  tokens, a small scaffold-vocabulary list (identify, find, retrieve, relevant, associated, …),
  and id-shaped patterns; require length ≥ 4; cap at 3 terms. Residual noise in a disjunctive
  `CONTAINS` filter matches nothing or is bounded by the injected LIMIT — strictly better than a
  full label scan.
- **Generic words that appear in real node names** (e.g. "information" ⊂ "Phishing for
  Information"): *Assumption*: drop them anyway — the distinctive term ("phishing") still
  anchors, and precision beats recall here.
- **SubTechnique coverage in name templates**: *Assumption*: anchor on the
  `(t:Technique OR t:SubTechnique)` union — safe for the validator because name filters do not
  trigger the attack_id-without-label rejection.
- **New committed concepts in `concepts.py`**: not needed — `name_terms` is a general mechanism;
  the committed-concept vocabulary stays reserved for fuzzy concepts and gold derivation.
- **Token budgets for router/validation** (`max_tokens=200/300` hardcoded): with a local
  thinking-model, reasoning tokens can exhaust the budget and return empty content — the likely
  source of the intermittent "unavailable" failures. *Assumption*: route these through the
  existing `CONVERSATION_LLM_MAX_TOKENS` config (default 1024) instead of hardcoding.
- **Scope of derived-artifact regeneration**: builder templates and drafter routing change, so
  per the concurrent-sessions rule the golden banks and planner corpus must be regenerated and
  the live goldens re-run against fresh graph data (wipe+reload first if stale). *Assumption*:
  regenerate banks + corpus in this plan; the full eval report only if bank contents change.
- **Human intervention**: none identified — no requirement in this plan needs a human decision
  before implementation.

## 3. Hierarchical Step-by-Step Instructions

#### Step 1: Name-anchor extraction in the shared resolver
- **Locations**: `utils/specialists/resolve.py` (`ResolvedTask` dataclass — new `name_terms`
  field; new `_extract_name_terms` helper called from `resolve()`); `utils/specialists/tests/test_resolve.py`.
- **Rationale**: Both builders need a deterministic, card-grounded source of name anchors before
  any template can use them. Extraction order: quoted phrases in the task text first ('Phishing'
  — the shape LLM-drafted sub-questions produce), else filtered free-text tokens (stopwords,
  card label/relationship identifier tokens, scaffold vocabulary, and id-shaped tokens removed;
  lowercased, deduped, min length 4, capped at 3). This mirrors how `concept_terms` already
  flows through `ResolvedTask`, so no downstream signature changes.
- **Action**: Undergo the verification/tests/validation process for this phase (unit tests for
  quoted, unquoted, noisy, and id-only texts; full `uv run python -m pytest utils/specialists`).
  Once validated, commit changes (do **not** push) stating: Name-Anchored Retrieval (1/7)
  Complete: Shared resolver extracts deterministic name terms from task text. Append a
  `docs/changelog.jsonl` entry.

#### Step 2: Cypher builder — relationship-intent + name-anchored templates
- **Locations**: `utils/specialists/cypher/builder.py` (`CypherQueryBuilder.build` intent flags
  `has_detection`/`has_mitigation` — also honor `DETECTS`/`MITIGATES` in
  `resolved.relationships` and task entities; new template methods
  `_technique_detection_by_name`, `_technique_mitigations_by_name`, `_technique_name_lookup`;
  docstring template census 13 → 16); `utils/specialists/tests/test_cypher_specialist.py`.
- **Rationale**: This is the core fix. Branch order: seeds keep absolute priority (existing
  behavior unchanged); when an intent is in scope but there are no technique seeds and
  `name_terms` exist, emit a name-anchored intent query — e.g. detection:
  `(t)` name-filtered union anchor `← [:DETECTS] ← (d:DetectionStrategy)` with the optional
  `HAS_ANALYTIC` hop, parameterised via `$terms` (validator-safe: read-only, known labels/edges,
  LIMIT injected). When *no* intent matches but name terms exist, `_technique_name_lookup`
  replaces the catastrophic `_label_scan` (which remains only for genuinely term-less requests).
  "How do you detect phishing?" then produces the 2-hop query the graph can actually answer.
- **Action**: Undergo the verification/tests/validation process for this phase (template
  routing tests incl. the DETECTS-relationship-only plan shape from the real failure; validator
  round-trip through `CypherValidator.validate`; non-regression for all 13 existing templates).
  Once validated, commit changes (do **not** push) stating: Name-Anchored Retrieval (2/7)
  Complete: Cypher builder anchors detection/mitigation/name-lookup queries on name terms.
  Append a `docs/changelog.jsonl` entry.

#### Step 3: Gremlin builder parity for CAPEC
- **Locations**: `utils/specialists/gremlin/builder.py` (name-term scoping on the
  AttackPattern scan path, reusing the existing concept-term `TextP.containing` machinery;
  priority: capec ids → concept terms → name terms → unscoped scan);
  `utils/specialists/tests/test_gremlin_specialist.py`.
- **Rationale**: The mitigation turn's CAPEC sub-query degraded the same way
  (`g.V().hasLabel("AttackPattern").elementMap().limit(1000)` → 558 rows). Scoping by name
  terms turns that into a phishing-pattern query, so cross-source evidence stays relevant and
  the answer agent stops reporting "no CAPEC mitigation records" against a wall of noise.
- **Action**: Undergo the verification/tests/validation process for this phase (builder unit
  tests + `GremlinValidator` round-trip; non-regression for concept-term and id paths). Once
  validated, commit changes (do **not** push) stating: Name-Anchored Retrieval (3/7) Complete:
  Gremlin builder scopes AttackPattern scans by name terms. Append a `docs/changelog.jsonl` entry.

#### Step 4: Deterministic drafter intent bridge
- **Locations**: `utils/planner/drafter.py` (`DeterministicDrafter.draft` / a small
  `_INTENT_BRIDGES` token→entities table applied after `_match_card`, filtered by
  `card.has_entity`); `utils/planner/tests/test_deterministic_drafter.py`.
- **Rationale**: In the failing turn the fallback drafter matched only `DETECTS`, so the plan
  carried no label scope at all. Bridging "detect/detection" → {DETECTS, DetectionStrategy,
  Technique} and "mitigate/mitigation" → {MITIGATES, Mitigation, Technique} (only entities the
  card actually has, keeping plans gate-valid by construction) means the LLM-off plan carries
  the same scope an LLM plan would, and Step 2's templates fire on the first pass.
- **Action**: Undergo the verification/tests/validation process for this phase (drafter routing
  tests for detect/mitigate phrasings; `PlanGate` still passes; full planner suite). Once
  validated, commit changes (do **not** push) stating: Name-Anchored Retrieval (4/7) Complete:
  Deterministic drafter bridges detection/mitigation keywords to full entity scope. Append a
  `docs/changelog.jsonl` entry.

#### Step 5: Conversation-layer hardening (id injection + token budgets)
- **Locations**: `utils/conversation/agents/orchestration.py` (`resolve_question` system prompt:
  when the question references an entity whose id appears in remembered facts, append the id in
  parentheses); `utils/conversation/agents/router.py` and
  `utils/conversation/agents/validation.py` (replace hardcoded `max_tokens=200/300` with
  `config.llm.max_tokens`); `utils/conversation/tests/test_orchestration.py`,
  `test_router.py`, `test_validation.py`.
- **Rationale**: Two independent risk reducers for the LLM path. (a) If the rewrite emits
  "How do you detect Phishing (T1566)?", seed extraction anchors everything regardless of
  builder heuristics — memory already holds the id from turn 1. (b) The turn's dual failure
  ("model returned no content") is characteristic of a thinking-model exhausting a 200–300
  token budget on reasoning; using the configured 1024 default removes the tightest budgets in
  the stack. Deterministic fallbacks stay untouched.
- **Action**: Undergo the verification/tests/validation process for this phase (prompt-content
  assertions via stub LLM; token-budget plumb-through tests; full conversation suite). Once
  validated, commit changes (do **not** push) stating: Name-Anchored Retrieval (5/7) Complete:
  Conversation rewrite injects known ids; router/validation use configured token budgets.
  Append a `docs/changelog.jsonl` entry.

#### Step 6: Regenerate derived evalset artifacts
- **Locations**: `utils/specialists/evalset/compile_banks.py` (regenerates
  `utils/specialists/tests/golden/*_questions.json`), `utils/planner/evaluation/build_corpus.py`
  (planner corpus / `expected_plans`), `utils/specialists/tests/golden/VERIFICATION.md` pins;
  affected assertions in `utils/specialists/evalset/tests/` and `utils/planner/tests/`.
- **Rationale**: Builder templates and drafter routing feed the derived banks and expected
  plans; the concurrent-sessions rule requires regenerating them in the same change so main
  never holds stale derived artifacts. If live fixtures are stale from concurrent sessions,
  wipe+reload Neo4j/Gremlin before re-running live goldens.
- **Action**: Undergo the verification/tests/validation process for this phase (regeneration
  scripts; `uv run python -m pytest utils/specialists/evalset utils/planner`; live golden suite
  against fresh graphs). Once validated, commit changes (do **not** push) stating:
  Name-Anchored Retrieval (6/7) Complete: Regenerated golden banks, planner corpus, and pins.
  Append a `docs/changelog.jsonl` entry.

#### Step 7: Live end-to-end verification and merge
- **Locations**: live run via `utils/specialists/pipeline.py` (`iter_pipeline`) and
  `utils/conversation/main.py` (`iter_conversation`) against Docker Neo4j/Gremlin; temporary
  scripts in the session scratchpad only; final `--no-ff` merge to `main`.
- **Rationale**: Prove the reported failure is fixed at the seam the user saw. LLM-off:
  "How do you detect phishing?" must return Phishing ← DETECTS ← its DetectionStrategy rows
  (not 222 techniques) on the first pass. LLM-on: replay the full six-turn thread
  (CAPEC-98 → … → detect → mitigate) through the conversation layer and confirm both the detect
  and mitigate turns anchor on the first extraction, with validation retries idle. Then run the
  complete test suite (`uv run python -m pytest`, `cd web && npm test && npm run lint && npm run
  build` — web untouched, gates only) before merging.
- **Action**: Undergo the verification/tests/validation process for this phase (live E2E above +
  full suites). Once validated, commit changes (do **not** push) stating: Name-Anchored
  Retrieval (7/7) Complete: Live E2E verified; merged feature branch to main with --no-ff.
  Append a `docs/changelog.jsonl` entry.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Name-term extraction | Deterministic quoted-phrase/token name anchors on `ResolvedTask` | utils/specialists/resolve.py |
| Resolver tests | Unit tests: quoted, noisy, id-only, schema-token filtering | utils/specialists/tests/test_resolve.py |
| Cypher name templates | `technique_detection_by_name`, `technique_mitigations_by_name`, `technique_name_lookup` + relationship-intent flags | utils/specialists/cypher/builder.py |
| Cypher builder tests | Routing, validator round-trip, 13-template non-regression | utils/specialists/tests/test_cypher_specialist.py |
| Gremlin name scoping | Name-term `TextP.containing` scope on AttackPattern scans | utils/specialists/gremlin/builder.py |
| Gremlin builder tests | Scoping priority + validator round-trip tests | utils/specialists/tests/test_gremlin_specialist.py |
| Drafter intent bridge | detect/mitigate keyword → card-filtered entity scope | utils/planner/drafter.py |
| Drafter tests | LLM-off plan-shape tests for detect/mitigate phrasings | utils/planner/tests/test_deterministic_drafter.py |
| Conversation hardening | Id-injecting rewrite prompt; configured token budgets | utils/conversation/agents/{orchestration,router,validation}.py |
| Conversation tests | Prompt/budget assertions with stub LLMs | utils/conversation/tests/ |
| Regenerated artifacts | Golden banks, planner corpus, verification pins | utils/specialists/tests/golden/, utils/planner/evaluation/ |
| Live E2E evidence | First-pass detection/mitigation answers over live graphs | scratchpad scripts; results quoted in commit/changelog |
