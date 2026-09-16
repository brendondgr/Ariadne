# Open-question correctness on cards and graphs

*Created 2026-09-15. Append-only: corrections go in a new dated plan, never in place.*

## 1. Introduction

The workbench answers a gold question verbatim at 1.0000 and the same question
with the entity named instead of cited at 0.3267 (`EXP-2026-09-021`, T3 after
D-035). With the name paraphrased (T4) or only described (T5) it answers nothing
at all: 0.0000, with four in five questions abstaining. The operator's target is
a system an analyst can use **without knowing the catalogue's vocabulary**, and
one that carries to a new graph on its source card and records alone, with no
catalogue-specific templates.

Two independent proposals were written for this on 2026-09-15 and reviewed
against each other: this session's seven ideas and Codex's
`EXP-2026-09-022` design. They agree on the architecture — bind the anchor
separately from interpreting the task, execute a structured request against the
schema-derived primitives instead of re-parsing English, and fix the lookup
order behind Q59. The review also found that the tree's own name index
(`utils/specialists/schema/namesearch.py`) already beats the new discovery
prototype at every candidate budget of five or more on T4/T5, so this plan
builds on the shipped index and keeps only two things from the prototype: its
non-cyber contract-test pattern and its handling of nested exact names across
sources. Every step below is pre-registered with a prediction and a falsifier
before it runs, and every mechanism reads the card, the schema registry, or the
graph's own records — never a MITRE fact.

The order is chosen by evidence and cost. The three loss classes measured on the
shipped arm are: (a) **anchor right, traversal wrong** at T1/T2 — 54 of 172
misses bind no relation because the card carries one gloss sentence per
relation; (b) **name never looked up** at T3 — 36 abstentions, 37 variants
reaching no exact anchor because the router must pick a dataset before the name
index runs (Q59); (c) **anchor never accepted** at T4/T5 — the gold entity is in
the shipped index's top five for 0.62/0.83 of questions and nothing is allowed to
choose it. Deterministic, model-free steps that address (b) and the recall half
of (a) come first; the model-in-the-loop acceptance for (c) comes last, after a
sealed holdout exists to calibrate it on.

## 2. Gaps & Unanswered Questions

- **Which metric carries the bar.** `records_exact` penalises the supersets
  that Steps 5 and 9 will deliberately produce. *Assumption*: from Step 5
  onward the **primary** metric is `records_recall` with `wrong_entity` and
  `catalogue_dump` as hard guards, `records_exact` reported beside it at every
  tier, and one judged pass on the final tree. **Confirm before Step 5 runs;**
  if the bar stays on `records_exact`, Step 5 is measured but not shipped.
- **A model on the critical path.** Steps 6 and 9 consult the local model per
  question when the deterministic rungs leave a slot unbound. `EXP-2026-09-021`
  measured that call at 5.8 s mean at T3. *Human intervention is needed to answer
  this question*: whether the workbench may spend that latency on an analyst's
  question is a product decision. Every model-consulting step ships behind a
  flag that defaults off until it is answered.
- **The reranker weights.** `bge-large` beat `bge-small` in the August probe but
  only `bge-small` is loadable offline; fetching the large ONNX weights is a
  download the operator must approve. *Assumption*: Step 9 is measured with
  `bge-small` first, and the large model is an optional adapter with its own
  ablation row.
- **The blind-holdout isolation test.** Fixing the CAPEC bridge's inner-join
  defect in Step 7 breaks the byte-identical isolation test that freezes the
  2026-07-26 arm figures. *Human intervention is needed to answer this
  question*: whether those figures may become non-comparable. Step 7 fixes the
  three defects that do not touch the frozen path and records the fourth as a
  decision request.
- **Who authors the holdout.** Step 1 authors new variants with the same local
  model that Step 9 later consults. *Assumption*: acceptable for retrieval and
  binding decisions because the model never sees gold at authoring time and the
  variants are sealed by hash; the judged pass in Step 10 uses the cross-model
  judge from `EXP-2026-08-007` to break the tie.
- **Cross-source name collisions.** "Phishing" and "Brute Force" are complete
  names in both ATT&CK and CAPEC; 37 of 101 T3 questions collide once lookup
  runs before routing. *Assumption*: the router's own selection breaks the tie
  when it selects a source; when it selects none and the names collide, the form
  reports an ambiguity rather than choosing. Step 4 measures how often that
  leaves a question unanswered.
- **Threshold seen on the exposed bank.** The distinctiveness rule's 1 %
  document-frequency cut in Step 3 was read off the exposed bank during the
  review. *Assumption*: it is pre-registered as-is and confirmed on the sealed
  holdout; if it needs moving to pass, the step records that as a failure.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Seal a fresh holdout bank before any rule is set

- **Locations**: `scripts/author_variants.py`, `scripts/build_bank.py`,
  `scripts/split_variants.py`, `scripts/holdout_seal.py`;
  new directory `docs/evaluation/variants-holdout-2026-09/` (`variants.json`,
  `slot_gold.json`, `reference.json`, `SEAL.md` with the SHA-256 of each);
  `utils/specialists/evalset/` for the entity pool.
- **Rationale**: the 579-variant bank has been read by every rule and threshold
  in this plan's ancestry and by both proposals; Q28's frozen half is spent. Hold
  out **entities**, not paraphrases: forty gold-shaped questions over ATT&CK and
  CAPEC entities that appear in no existing variant, with T3–T6 variants authored
  under the same tier notes as `variants-2026-08-29`. Capture the reference
  twice on the shipped tree and require a byte-identical diff. The exposed bank
  stays the development and regression set; the sealed bank is opened once per
  step, for confirmation only, and never for choosing a value.
- **Validation**: `SEAL.md` hashes recorded; a test in
  `utils/planner/tests/test_holdout_bank.py` asserts zero entity-id overlap with
  `variants-2026-08-29` and that the two reference captures are identical.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit locally (no push unless the operator asks) stating:
  Open-Question Correctness (1/10) Complete: a fresh entity-held-out bank
  authored, captured twice and sealed by hash.

### Step 2: Pre-register the anchor-hygiene experiment and record the review probes

- **Locations**: `make new-experiment SLUG=anchor-hygiene-and-q59`; its
  `PROTOCOL.md`, `manifest.yaml`, `RESULTS.md`; a committed
  `data/shipped_vs_prototype.py` that re-derives the review's comparison from
  `EXP-2026-09-022`'s hash-pinned `predictions.jsonl` and the shipped index.
- **Rationale**: the review's numbers exist only in a scratchpad and a chat log,
  which under the research rules means they do not exist. Record them first:
  shipped index versus the prototype's pooled arm on identical gold groups, the
  exact-name distribution (T3 60 single-and-gold, 41 ambiguous of which 37
  cross-source; T4/T5 28/26 single-and-wrong; T6 9 binds), and the fact that
  27 of the 54 wrong binds are one node named "Credentials". Then write H1
  (Step 3) and H2 (Step 4) with thresholds before either runs. Primary metric:
  `records_exact` at T3 on the exposed bank; confirmation metric: the same on
  the sealed bank.
- **Validation**: `make validate-research`, `make check-docs`; the comparison
  script's output matches `RESULTS.md` to four decimals.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit locally stating: Open-Question Correctness (2/10)
  Complete: H1 and H2 pre-registered and the shipped-versus-prototype
  comparison entered into the record.

### Step 3: Exact-name hygiene — distinctiveness and cross-source nesting

- **Locations**: `utils/specialists/schema/namesearch.py` — `exact_name_matches`
  gains a corpus-frequency check computed from the index's own `_postings`
  (no list of words, no dataset name); new `exact_name_matches_all(cards, text)`
  that runs every live source and suppresses a name nested inside a longer
  match from **any** source (the shipped nesting filter is per-source, so
  "Remote Services" and "Credentials" both fire inside CAPEC's "Remote Services
  with Stolen Credentials"); `utils/planner/canonical.py` `deterministic_fill`
  calls the new helper; `utils/planner/config.py` flag
  `ARIADNE_EXACT_NAME_DISTINCT`; tests in
  `utils/specialists/schema/tests/test_namesearch_distinct.py` plus a
  non-cyber "library" card fixture in the style of
  `utils/planner/tests/test_discovery_candidates.py`.
- **Rationale**: a single-token name whose token appears in more than 1 % of
  the corpus's own documents is an ordinary word, not a lookup; the rule is a
  function of the graph and carries to any card. On the exposed bank it keeps
  60/60 T3 gold binds, removes 39 of 54 T4/T5 wrong binds and 7 of 9 T6 binds.
  **Pre-registered prediction** (sealed bank): T3 gold-bind loss ≤ 2 %; wrong
  single binds at T4/T5 reduced by ≥ 60 %; T6 binds ≤ 2. **Falsifier**: any T3
  loss above 2 %, or the 1 % value having to move to pass — then the rule is
  tuning and is recorded as failed, not adjusted.
- **Validation**: `uv run python -m pytest utils/specialists/schema/tests
  utils/planner/tests`; `scripts/variant_harness.py compare` on both banks with
  the flag on and off at 32 workers; `wrong_entity` and `abstained` per tier
  beside `records_exact`.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit locally stating: Open-Question Correctness (3/10)
  Complete: incidental exact names no longer bind, measured on the sealed bank.

### Step 4: Q59 — look the name up before routing the dataset, with a tie-break

- **Locations**: `utils/planner/canonical.py` `deterministic_fill` (the early
  return on `not datasets` and the anchor loop over `datasets`), a new
  `_anchor_first_datasets` that runs `exact_name_matches_all` before
  `_selected_datasets` and lets an unambiguous name choose the source;
  `utils/planner/drafter.py` `_select_sources` unchanged and used as the
  tie-break when names collide across sources; flag
  `ARIADNE_ANCHOR_BEFORE_ROUTING`; `utils/orchestration/agents/planner/nodes.py`
  records the new provenance `exact-name-routed`; tests in
  `utils/planner/tests/test_canonical_anchor_first.py`.
- **Rationale**: "Which countermeasures apply to Windows Management
  Instrumentation?" binds nothing because "countermeasures" routes nowhere and
  the name is never looked up, while "What mitigations …" binds T1047. An
  entity name implies its dataset. The exact path only: the ranked index stays
  refused. When exact hits span sources and the router selected one of them, the
  router wins; when it selected none, the form carries the ambiguity and the
  answer says so. **Pre-registered prediction** (exposed bank): T3
  `skipped_unresolved_anchor` 37 → ≤ 15, T3 `records_exact` 0.3267 → ≥ 0.45,
  T1/T2 unchanged, T6 `wrong_entity` ≤ 0.0667, T4/T5 `wrong_entity` not above
  the D-035 values because Step 3 runs first. **Falsifier**: T3 `wrong_entity`
  above 0.07 or any T6 rise.
- **Validation**: unit tests for the six probe questions from Q59 and the
  Phishing/Brute Force collisions; `variant_harness.py compare` on both banks;
  the amendment recorded in the Step 2 experiment.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit locally stating: Open-Question Correctness (4/10)
  Complete: a named entity is looked up before its dataset is chosen.

### Step 5: Expand instead of describe when the relation is unbound

- **Locations**: `make new-experiment SLUG=expand-on-unbound-relation`;
  `utils/planner/drafter.py` where an anchored, non-definitional request with
  no matched relation falls to the describe path (the `is_definitional_request`
  rescue near line 615 and the specialist's `_describe`); a new
  `utils/planner/expand_plan.py` that turns such a form into one `describe` plus
  bounded `expand` requests over every non-zero facet the registry declares for
  the anchor's label (`utils/specialists/primitives/expand.py` `ExpandRequest`,
  `paginate`; `utils/orchestration/agents/assess/policy.py` `expandable_facets`
  as the facet source); `utils/synthesis/composer.py` groups the enumeration
  claim by relation; flag `ARIADNE_EXPAND_UNBOUND`.
- **Rationale**: "How do I defend against T1047?" returns one record — the
  technique's own description — because "defend against" matches no relation;
  gold is five mitigations. The anchor is right and the traversal is unknown, so
  return everything one hop away, grouped, bounded by the card's row limit per
  facet, rather than one record. The registry supplies the facets, so nothing
  here names a catalogue. **Pre-registered prediction**: T1/T2
  `records_recall` 0.5470/0.5230 → ≥ 0.75; `records_exact` within ± 0.02;
  `catalogue_dump` ≤ baseline + 0.02. **Falsifier**: dump rate above that, or
  exact falling more than 0.02 — the bound is then wrong, not the idea, and the
  step stops rather than tunes.
- **Validation**: primitive tests in `utils/specialists/primitives/tests`;
  composer tests for grouped enumeration; both banks compared; the
  recorded-answer regression diff over both golden banks before shipping (per
  the recorded-answer rule).
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit locally stating: Open-Question Correctness (5/10)
  Complete: an anchored question with an unknown relation returns its
  neighbourhood, grouped, instead of one record.

### Step 6: Execute the form directly instead of re-parsing rendered English

- **Locations**: `make new-experiment SLUG=direct-form-execution`; new
  `utils/planner/form_plan.py` (`IntentForm` → `Plan`: `describe` for
  `MODE_DESCRIBE`, `expand` with `relation`/`direction`/`target_labels`
  otherwise, `utils/specialists/schema/paths.py` `relation_chain` for
  multi-hop forms, the count mode as an aggregate over the same request);
  `utils/orchestration/agents/planner/nodes.py` `canonicalize` returns the plan
  and keeps `canonical_question` for the record only; `scripts/variant_harness.py`
  gains a `form_execute` arm beside the rendered arms; flag
  `ARIADNE_FORM_EXECUTE`; then, under this flag only, lift the D-034
  identifier skip so the model may fill relation and target labels on an
  id-bearing question while `rewrite_require_resolved_anchor` keeps the anchor
  fixed; tests in `utils/planner/tests/test_form_plan.py` and a non-cyber card
  fixture proving the planner emits a valid request for a schema it has never
  seen.
- **Rationale**: the rewrite stage renders the form to English and the drafter
  parses it again; 13 of the 17 T1 breaks under the unguarded arm had the right
  id and the schema-resolved relation and lost them in the round trip. A form
  is graph-agnostic; rendered English is not. Once the form executes directly,
  the model may safely interpret "what stops T1047" because the anchor is
  immutable and the gate already checks relation and direction against the
  card. **Pre-registered prediction**: deterministic-rung breaks at T1/T2 → 0
  paired against baseline; with the identifier skip lifted, T1/T2
  `records_exact` + ≥ 0.10 on the 54 unbound-relation cases' tiers;
  `wrong_entity` flat. **Falsifier**: the not-worse-than-baseline rule at T1/T2
  fails — then the identifier skip stays and only the deterministic rung
  executes directly.
- **Validation**: 342 existing orchestration and planner tests plus the new
  ones; `variant_harness.py compare --rewrite form_execute` on both banks;
  paired per-variant fixed/broken counts recorded.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit locally stating: Open-Question Correctness (6/10)
  Complete: the intent form is executed as a plan, and the model may interpret
  the task on an id-bearing question without touching the anchor.

### Step 7: Generic-engine parity so the templates can be retired

- **Locations**: `make new-experiment SLUG=generic-engine-parity`;
  `utils/specialists/cypher/builder.py` `_generic_chain`, `_declared_paths`,
  `_generic_neighbors`, `_generic_intersect`; `utils/specialists/gremlin/builder.py`
  mirrors; dependent sub-question seed ordering in the orchestration planner
  (the "sub-question q2 produced no seed identifiers" abstention on the MAP
  cases); `utils/planner/join_keys.py` for the CAPEC→ATT&CK bridge; the paired
  per-case diff from `EXP-2026-09-021`'s `data/paired_engines.py` reused as the
  instrument; `.env` `SPECIALIST_GENERIC_ONLY`.
- **Rationale**: the schema-derived engine loses to the hand-written cascade by
  0.175 at T1 for three named reasons — reverse-direction asks (12 wrong),
  cross-source joins whose dependent hop runs before its seeds exist (9
  abstain), and the CWE chain (5 abstain) — the same capability class
  `EXP-2026-08-001` fixed on the authored-plan path and never on what the real
  planner emits. Closing them is the one change that makes a new graph
  answerable on its card alone. **Pre-registered prediction**: primitives within
  − 0.02 of templates at T1, T2 and T3, paired; no category where templates win
  by more than two cases. **Falsifier**: any such category — record it and do
  not flip the default. The bridge's inner-join defect is fixed only if the
  isolation-test decision in §2 is answered yes.
- **Validation**: `utils/specialists/tests`; live golden tests against the
  running Neo4j/Gremlin stack (reload fixtures first per the live-fixture rule);
  both banks compared under `SPECIALIST_GENERIC_ONLY=1`; if parity holds, the
  default flips in `.env`/`.env.example` with a D-entry.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit locally stating: Open-Question Correctness (7/10)
  Complete: the schema-derived engine reaches template parity on the three named
  defects.

### Step 8: A relation lexicon generated from the card's own glosses, offline

- **Locations**: `make new-experiment SLUG=relation-lexicon-from-glosses`;
  new `scripts/generate_relation_lexicon.py` (one local-model call per declared
  relation, input = the gloss and endpoint labels, output = a reviewable
  paraphrase list); new overlay key `relationship_paraphrases` in
  `data/source_cards/overlays/*.overlay.json`; `utils/planner/lexicon.py`
  `gloss_forms` extended to read it; `utils/planner/drafter.py`
  `_concept_indexes` consumes it; the tri-source identity bank from
  `EXP-2026-08-013` as the over-matching control; tests in
  `utils/planner/tests/test_lexicon_paraphrases.py` on the library fixture.
- **Rationale**: the T1/T2 ceiling is verb vocabulary and the card carries one
  gloss sentence per relation. Generating paraphrases once at card-build time
  keeps the query path deterministic and model-free and works for any card with
  glosses; the generated list is committed and reviewable. It runs after Step 6
  so gains are measured on direct execution, not the round trip.
  **Pre-registered prediction**: T1/T2 unbound-relation cases 54 → ≤ 20;
  `wrong_entity` flat; the identity bank's routing precision unchanged.
  **Falsifier**: the identity bank pulls in a catalogue it did not before — the
  lexicon over-matches and is narrowed to exact gloss forms only.
- **Validation**: planner tests; `variant_harness.py compare` on both banks;
  `EXP-2026-08-013`'s routing-precision figure re-run and compared.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit locally stating: Open-Question Correctness (8/10)
  Complete: relation vocabulary generated from glosses, reviewable and
  model-free at query time.

### Step 9: T4/T5 acceptance as a disclosed closed choice over the shipped index

- **Locations**: `make new-experiment SLUG=disclosed-anchor-acceptance`;
  `utils/planner/canonical.py` `candidate_lists` (the shipped `search_in` top
  five, then an optional reranker); new optional adapter
  `utils/specialists/schema/rerank.py` (FastEmbed, versioned, stands down when
  `exact_name_matches_all` fires — the guard the August probe showed T3 needs);
  `utils/planner/rewrite_llm.py` `build_prompt`/`choose` gain a "none of these"
  index; `utils/orchestration/agents/planner/nodes.py` relaxes
  `rewrite_require_resolved_anchor` to "the model may choose the anchor from the
  reranked list only, and the answer must disclose it"; `utils/synthesis/composer.py`
  emits a first claim "Resolved to <id> (<name>) from your description"; flag
  `ARIADNE_ANCHOR_DISCLOSED`; calibration on the sealed bank only.
- **Rationale**: D-034 proved this rung can answer T4/T5 (0.0962/0.1250) and
  bought it with `wrong_entity` near 0.30 because the model chose from raw BM25
  top five with no refusal option and no disclosure. The gold entity is in the
  shipped top five for 0.62/0.83 of questions; reranking under the guard raised
  T4 rank-1 from 0.35 to 0.52 with the small model. A disclosed resolution turns
  a silent wrong answer into a visible, correctable one, which is the right
  behaviour for an analyst who does not know the name. **Pre-registered
  prediction** (sealed bank): T4/T5 `records_exact` ≥ 0.30 with `wrong_entity`
  ≤ 0.15 and T6 acceptance ≤ 0.10. **Falsifier**: `wrong_entity` above 0.15 —
  then the rung ships as a clarification ("Did you mean X or Y?") and not as an
  answer.
- **Validation**: rewrite tests; both banks; T6 reported as the first row; the
  latency of the reranker and the model call recorded per question.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit locally stating: Open-Question Correctness (9/10)
  Complete: a described entity is resolved from a reranked closed list and the
  answer says which one it chose.

### Step 10: Ship through the workbench, prove portability, and state the position

- **Locations**: `.env`, `.env.example`, `README.md` "What Actually Runs";
  `docs/research/DECISIONS.md` (one D-entry per shipped flag),
  `docs/research/OPEN_QUESTIONS.md` (Q59 closed or amended, Q60 amended),
  `docs/research/CURRENT.md`; the running workbench via `python app.py` and the
  query SSE route in `api/`, checked in the browser on the Q59 probe questions
  and three T4/T5 questions; a new contract test
  `utils/specialists/tests/test_no_catalogue_literals.py` asserting that no
  module added by this plan contains a catalogue identifier pattern or entity
  name; the tri-source identity bank run once more as the portability check; one
  judged pass over the final tree's answers on the sealed bank with the
  cross-model judge.
- **Rationale**: the frontend is the deliverable. Every flag is switched on in
  the shipped `.env` only if its step passed its own falsifier, the browser
  check proves the SSE path carries the new answer shapes, and the literal-free
  test plus the identity bank are the evidence that nothing here is ATT&CK
  knowledge in disguise. The judged pass is the only measurement that answers
  "does the analyst get a correct answer", and it has never been run on this
  bank. If the webfront needs a change for the disclosed-anchor claim,
  `cd web && npm run build` is mandatory before the commit.
- **Validation**: `make validate-research`, `make check-docs`, the full test
  suites, `npm run build` if `web/` changed; the per-tier table for both banks
  recorded in `CURRENT.md`.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit locally stating: Open-Question Correctness (10/10)
  Complete: every passing mechanism shipped behind its flag, verified in the
  workbench, and the honest per-tier position recorded.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Sealed holdout bank | Forty entity-held-out questions with T3–T6 variants, gold, reference and hashes | `docs/evaluation/variants-holdout-2026-09/` |
| Holdout seal test | Asserts zero entity overlap with the exposed bank and a reproducible reference | `utils/planner/tests/test_holdout_bank.py` |
| Shipped-vs-prototype comparison | Re-derives the review's retrieval comparison from pinned predictions | `docs/research/experiments/EXP-…-anchor-hygiene-and-q59/data/shipped_vs_prototype.py` |
| Exact-name hygiene | Corpus-frequency distinctiveness and cross-source nested-name suppression | `utils/specialists/schema/namesearch.py` |
| Exact-name tests | Library-card fixture plus the Credentials/at/Phishing cases | `utils/specialists/schema/tests/test_namesearch_distinct.py` |
| Anchor-first routing | Name lookup before dataset selection with the router as tie-break | `utils/planner/canonical.py` |
| Anchor-first tests | Q59 probes and cross-source collisions | `utils/planner/tests/test_canonical_anchor_first.py` |
| Expand-on-unbound plan | Describe plus bounded facet expansion for an anchored request with no relation | `utils/planner/expand_plan.py` |
| Grouped enumeration | Composer claim grouped by relation | `utils/synthesis/composer.py` |
| Form-to-plan executor | `IntentForm` executed as describe/expand requests, no re-parse | `utils/planner/form_plan.py` |
| Form executor tests | Cyber and non-cyber fixtures, paired fixed/broken counts | `utils/planner/tests/test_form_plan.py` |
| Generic-engine fixes | Reverse direction, join seed ordering, CWE chain | `utils/specialists/cypher/builder.py`, `utils/specialists/gremlin/builder.py` |
| Relation lexicon generator | Offline paraphrases per declared relation from its gloss | `scripts/generate_relation_lexicon.py`, `data/source_cards/overlays/` |
| Lexicon tests | Paraphrase consumption on the library fixture | `utils/planner/tests/test_lexicon_paraphrases.py` |
| Reranker adapter | Optional, versioned, guarded by exact-name | `utils/specialists/schema/rerank.py` |
| Disclosed-anchor rung | Closed choice with refusal and a disclosure claim | `utils/planner/rewrite_llm.py`, `utils/orchestration/agents/planner/nodes.py` |
| Harness arms | `form_execute` and `disclosed` arms with every variable pinned | `scripts/variant_harness.py` |
| Portability contract test | No catalogue literal in any module this plan adds | `utils/specialists/tests/test_no_catalogue_literals.py` |
| Experiment records | One per measured step, pre-registered, with amendments | `docs/research/experiments/` |
| Decisions and questions | D-entries per shipped flag; Q59/Q60 amended | `docs/research/DECISIONS.md`, `docs/research/OPEN_QUESTIONS.md` |
| Shipped configuration | Flags on only where the step passed | `.env`, `.env.example`, `README.md` |
