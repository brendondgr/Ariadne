# Step 5 Golden Evalset — Specialist Question Banks with Snapshot-Derived Gold Answers

## 1. Introduction

This plan builds the golden test set that proves each query specialist works in isolation (roadmap Step 5) and lays the measurement foundation for Steps 6–7 (synthesis verification, abstention, and coverage-hole plugging). The evaluation-suite design document (compass artifact, 2026-07-03) supplies the question catalog and scoring philosophy; this plan turns its single-source subset into machine-checkable artifacts: a **gold bank** materialized from the pinned raw snapshot (ATT&CK v19.0 STIX bundle, CAPEC v3.9 XML — never hand-keyed, per the Step 7 discipline), **compiled question banks** whose entries are `SpecialistTask` payloads with ID-set assertions, an **AI-assisted verification pass** where independent agents re-derive every gold answer from the raw snapshot and adversarially compare, and **parameterized live tests** that run each question through the real specialists against the live Docker graph stack.

Two properties make the suite trustworthy. First, gold answers are derived from the *raw* snapshot while the specialists answer from the *loaded graph* — the two only agree if the KG build was faithful, so the suite doubles as an end-to-end ingestion check. Second, every question is filtered to the intent templates the deterministic builders actually support (Cypher: `technique_mitigations`, `group_techniques`, `tactic_techniques`, `node_lookup`, `label_scan`; Gremlin: `capec_maps_to`, `capec_neighbors`, `capec_lookup`, `capec_scan`), with unsupported archetypes tagged for the future LLM drafter rather than silently failing. Federated and narrative-rubric questions from the design document are out of scope here — they are the Step 6 system eval.

## 2. Gaps & Unanswered Questions

- **Gold derivation must mirror the load policy.** Raw-derived answers must apply the same filters the ingest applies (ATT&CK: exclude `revoked`/`x_mitre_deprecated` objects and relationships, exclude-at-load; CAPEC: load-and-tag deprecated). *Assumption*: reuse the policy documented in the source-card identity block and validate against the canonical JSONL where ambiguous.
- **Question count.** The design document targets 100–130 across the whole system. *Assumption*: the Step 5 single-source slice is ~45 questions (~25 ATT&CK, ~20 CAPEC) covering every supported archetype ≥3×, Campaign coverage (Step 7 gap), and negatives (T9999, CAPEC-116 no-mapping, deprecated CAPEC-557). Extension to the full catalog happens when the LLM drafter and Step 6 land.
- **Commit/push discipline.** Session directive: commit at every step but **do not push**; global-rules push language is overridden for this session. Merge to main at the end once everything is green. *Assumption applied throughout.*
- **AI verification scope.** Verifier agents re-derive **all** bank questions (not a sample) since ~45 is affordable; each works only from `data/raw/` + its own code, never the gold script's functions. *Assumption*: 2 independent verifiers per question is sufficient (agreement of both = verified; any disagreement = human-visible flag in the report and a fix before merge).

## 3. Hierarchical Step-by-Step Instructions

#### Step 1: Gold-bank materialization script
- **Locations**: new package `utils/specialists/evalset/` (`__init__.py`, `gold_bank.py`, `cli.py`); output artifact `utils/specialists/tests/golden/gold_bank.json` (committed); unit tests `utils/specialists/evalset/tests/test_gold_bank.py`.
- **Rationale**: Everything downstream keys off snapshot-derived gold. `gold_bank.py` parses `data/raw/attack/v19.0/enterprise-attack.json` (STIX: `mitigates`, `uses`, `subtechnique-of`, kill-chain phases, object lookups incl. Campaigns) and `data/raw/capec/v3.9/capec_latest.xml` (per-pattern fields, ChildOf/ParentOf/CanPrecede, Related_Weaknesses, ATT&CK taxonomy mappings, Status), applying the documented load policy. Unit tests pin the design document's verified anchors (CAPEC-555 → {T1021, T1114.002, T1133}; CAPEC-116 → no mapping; CAPEC-98 parent CAPEC-151 and children 163/164/656; T1021.001 = Remote Desktop Protocol) — if the script disagrees with a verified anchor, the script is wrong.
- **Action**: Undergo the verification/tests/validation process for this phase (unit tests green, gold bank regenerates deterministically, changelog entry). Once validated, commit stating: Step 5 Golden Evalset (1/5) Complete: gold-bank materialization from the pinned v19/3.9 snapshot.

#### Step 2: Question-bank compiler + committed banks
- **Locations**: `utils/specialists/evalset/questions.py` (authored archetype definitions), `utils/specialists/evalset/compile_banks.py`; outputs `utils/specialists/tests/golden/attack_questions.json`, `capec_questions.json` (committed); unit tests `utils/specialists/evalset/tests/test_banks.py`.
- **Rationale**: Each bank entry carries: `id`, `tier`, `question` (prose), `task` (full `SpecialistTask` payload: source, text, entities, seed_ids, join_key, limits), `expected_template` (which builder intent must fire), and `assertions` (`min_records`, `must_include_ids`, `must_include_related`, `forbid_ids`, `id_scheme`, `expect_empty`). Gold IDs come from the gold bank at compile time — no hand-keyed sets. The routing unit test runs every entry through `resolve()` + the real builder (no DB) and asserts the drafted template equals `expected_template`, so a bank/builder drift fails fast and cheap. Includes Campaign `node_lookup` questions (Step 7 gap) and the negative battery (Step 7 abstention groundwork: T9999 → `expect_empty`; CAPEC-116 `capec_maps_to` → `expect_empty`; CAPEC-557 lookup → status Deprecated).
- **Action**: Undergo the verification/tests/validation process for this phase (compiler deterministic, routing tests green, changelog entry). Once validated, commit stating: Step 5 Golden Evalset (2/5) Complete: compiled machine-checkable question banks.

#### Step 3: AI-assisted gold verification
- **Locations**: Workflow run (no repo code); report `utils/specialists/tests/golden/VERIFICATION.md` (committed); any gold fixes land in `gold_bank.py`/`questions.py`.
- **Rationale**: The user cannot hand-verify security-domain gold answers; independent re-derivation substitutes for domain review. Each verifier agent receives one question + its gold assertion, and must re-derive the answer from `data/raw/` using its own ad-hoc parsing (jq/python), then adversarially report agree/disagree with evidence. Two verifiers per question; disagreements are re-examined, root-caused (script bug vs. verifier error), fixed, and re-verified. The report records per-question verdicts and the final agreement rate — this is the artifact that says "the gold is trustworthy."
- **Action**: Undergo the verification/tests/validation process for this phase (100% agreement or documented resolutions, changelog entry). Once validated, commit stating: Step 5 Golden Evalset (3/5) Complete: AI-verified gold bank with verification report.

#### Step 4: Golden live tests
- **Locations**: `utils/specialists/tests/test_golden_attack.py`, `utils/specialists/tests/test_golden_capec.py`; shared runner helper `utils/specialists/tests/golden/_runner.py` if needed.
- **Rationale**: One parameterized test per bank entry (pytest `parametrize` over the JSON), marked `live`, skipping when Neo4j/Gremlin unreachable (reusing the existing `_neo4j_reachable`/`_gremlin_reachable` guards). Each run asserts: `result.ok`, all assertion clauses (ID-set containment, `expect_empty`, `forbid_ids`), every `EvaluatorTrace` step ok, and `check_contract()` clean — i.e., the specialist answered the question *correctly*, not merely without error (the 97% problem, measured). Start the Docker stack, ensure both graphs loaded, run the golden suites plus the full specialist/loader/builder regression.
- **Action**: Undergo the verification/tests/validation process for this phase (golden suites green live, full regression green, changelog entry). Once validated, commit stating: Step 5 Golden Evalset (4/5) Complete: live golden tests green against the loaded graphs.

#### Step 5: Docs, regression, merge
- **Locations**: `docs/structure.md` (evalset layer), `docs/plans/specialist-agents-plan.md` (Step 5 checkoff note), `docs/changelog.jsonl`; merge `worktree-step5-golden-evalset` → `main`.
- **Rationale**: Canonical docs must describe the evalset package, the golden artifacts, the regeneration CLI, and the verification report before the feature lands. Merge only after the full suite is green from the worktree.
- **Action**: Undergo the verification/tests/validation process for this phase (full regression green post-merge on main, changelog entry). Once validated, commit stating: Step 5 Golden Evalset (5/5) Complete: docs updated and branch merged to main.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Gold-bank script | Parses pinned raw ATT&CK STIX + CAPEC XML into gold answers under the load policy. | utils/specialists/evalset/gold_bank.py |
| Gold bank artifact | Committed snapshot-derived gold answers (regenerable via CLI). | utils/specialists/tests/golden/gold_bank.json |
| Bank compiler + archetypes | Authored question archetypes compiled with gold IDs into bank JSON. | utils/specialists/evalset/questions.py, compile_banks.py |
| Question banks | ~45 machine-checkable single-source questions (tasks + assertions + expected routing). | utils/specialists/tests/golden/attack_questions.json, capec_questions.json |
| Gold-bank unit tests | Anchor regression tests (CAPEC-555, CAPEC-116, CAPEC-98, T1021.001, load-policy filters). | utils/specialists/evalset/tests/test_gold_bank.py |
| Routing unit tests | Every bank entry resolves + routes to its expected builder template, no DB. | utils/specialists/evalset/tests/test_banks.py |
| Verification report | Per-question AI re-derivation verdicts + agreement rate. | utils/specialists/tests/golden/VERIFICATION.md |
| Golden live tests | Parameterized live runs of every bank entry through the real specialists. | utils/specialists/tests/test_golden_attack.py, test_golden_capec.py |
| Docs updates | Evalset layer documented; plan cross-referenced. | docs/structure.md, docs/plans/specialist-agents-plan.md |
