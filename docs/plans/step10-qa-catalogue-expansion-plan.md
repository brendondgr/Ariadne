# Step 10 — Q&A Catalogue Expansion to 120 (Federated + Hard Tiers)

## 1. Introduction

This plan implements the Q&A catalogue expansion committed in the external planning
document (*7.qa-catalogue-expansion-plan.md*): grow the machine-checkable evaluation
catalogue to **120 questions total**, weighted so the federated cross-source scenarios the
proposal exists to demonstrate — CAPEC↔ATT&CK joins with snapshot-derived gold — become
the single largest new slice. Every new gold answer is computed from the pinned ATT&CK
v19 STIX bundle and CAPEC 3.9 XML at build time (the established `gold_bank.py` /
`compile_banks.py` discipline), re-derived by two independent AI verifiers, and wired
into the live golden suites so the join is asserted against the real Neo4j + Gremlin
stack.

The approach follows the source plan's six build steps: extend the gold bank with the
join maps and the new single-source maps, add the small set of deterministic builder
templates the new question shapes require, author the three slices (federated,
ATT&CK-only, CAPEC-only) as compiled banks, run the two-verifier re-derivation, wire the
live parameterized suites, and close with docs + count reconciliation + full regression.
Work happens in the worktree `worktree-step10-qa-catalogue`; per the session directive,
every step ends in a **commit (never a push)** plus a `docs/changelog.jsonl` entry, and
the branch merges to local `main` only when everything is green.

## 2. Gaps & Unanswered Questions

- **Count reconciliation (53, not 45).** The source plan was authored against 45 bank
  questions; Step 7 has since grown the banks to 53 (32 ATT&CK + 21 CAPEC). The plan's
  hard validation gate is "catalogue loads to exactly **120**", and its federated slice
  (40, ≈1/3 share) is the proposal-critical number. *Assumption*: keep Slice A at the
  full 40 and trim Slices B+C from 35 to 27 (B 18→14, C 17→13) — the trims fall on
  sub-types Step 7 already partially covered (extra negatives, extra CWE-edge coverage).
  Net-new = 67; 53 + 67 = 120 exactly; federated share = 40/120 = 33%.
- **Tier distribution deviation.** The target matrix (~30 Easy / ~48 Medium / ~26 Hard /
  ~16 Adversarial) cannot be hit exactly from the current 53 (21 E / 24 M / 0 H / 8 A)
  when the 67 new questions land mostly Medium/Hard/Adversarial as the plan requires.
  *Assumption*: land near ~21 E / ~53 M / ~24 H / ~22 A, document the actual split, and
  pin exact counts in a catalogue-census test. Easy stays under-target because Easy
  single-source is already saturated — the same rationale the source plan gives.
- **How federated bank entries execute live.** The NL planner is not the unit under test
  here; the source plan's data model gives every federated entry explicit per-source
  `tasks` with a `seed_from` dependency. *Assumption*: the federated golden runner
  builds a `Plan` from those tasks and drives the committed federation + synthesis path
  (`federation.execution_order` → specialists → `bundle_evidence` → `synthesize`),
  asserting `must_correlate` against the live join index. The NL-question path stays
  covered by the existing `test_acceptance_federated.py`.
- **Cross-source partials live.** A "source down" cannot be staged against the shared
  live stack. *Assumption*: 2 of the 4 partials are unsupported-side partials runnable
  live (one side hits a schema boundary, e.g. ICS-only Asset); 2 are one-specialist-absent
  partials staged by injecting a single live specialist into the runner — honest, live,
  and deterministic.
- **CAPEC prerequisites are vertex properties, not nodes.** The C-slice
  "consequences / skills / prerequisites" sub-type uses `HAS_CONSEQUENCE` /
  `REQUIRES_SKILL` edges (both loaded); prerequisites are asserted only if cleanly
  reachable via lookup properties, otherwise that count shifts to consequences/skills.
  *Assumption*: no ingest change in this step.

## 3. Hierarchical Step-by-Step Instructions

#### Step 1: Gold maps — join maps + new single-source maps in the gold bank
- **Locations**: `utils/specialists/evalset/gold_bank.py` (`parse_attack_bundle`,
  `parse_capec_xml`), regenerated `utils/specialists/tests/golden/gold_bank.json`,
  anchor tests in `utils/specialists/evalset/tests/test_gold_bank.py`.
- **Work**: ATT&CK side — add `technique_tactics` (T-ID → tactic IDs, from kill-chain
  phases), `software_techniques` (S-ID → T-IDs from `uses`), detection maps
  (`technique_detections` T-ID → DetectionStrategy IDs via `detects`,
  `detection_analytics` DS-ID → Analytic IDs via `x_mitre_analytic_refs`,
  `datacomponent_analytics` DC-ID → Analytic IDs via log-source refs), and an
  `excluded_ids` list (revoked/deprecated ATT&CK IDs, for honest-empty negatives).
  CAPEC side — add `execution_steps` (ordered), `consequences`, `skills`,
  `cwe_to_capec` (inverse of `related_weaknesses`). Verify the CAPEC-555 →
  T1021/T1114.002/T1133 anchor still holds and add anchors for each new map.
- **Rationale**: every downstream slice resolves its gold from these maps at compile
  time; they must exist and be pinned before any question can be authored.
- **Action**: Undergo the verification/tests/validation process for this phase
  (evalset tests green, regeneration deterministic). Once validated, commit to GitHub
  (no push) stating: QA Catalogue Expansion (1/7) Complete: gold bank extended with
  federated join maps and detection/software/CAPEC-substructure maps, all anchored.

#### Step 2: Builder templates — the deterministic query shapes the new slices need
- **Locations**: `utils/specialists/cypher/builder.py` + `normalizer.py` (+ routing
  cascade), `utils/specialists/gremlin/builder.py` + `normalizer.py`, hermetic tests
  `utils/specialists/tests/test_cypher_specialist.py`, `test_gremlin_specialist.py`,
  routing expectations in `utils/specialists/evalset/tests/test_banks.py`.
- **Work**: Cypher — `software_techniques` (S→USES→T), `technique_detection`
  (T←DETECTS−DS−HAS_ANALYTIC→A), `subtechnique_parent` (T−HAS_SUBTECHNIQUE→ST, seeded
  from either end), `technique_tactics` (TA−HAS_TECHNIQUE→T seeded by T),
  `tactic_technique_mitigations` (2-predicate: tactic AND mitigation),
  `datacomponent_analytics` (A−MONITORS→DC seeded by DC). Gremlin —
  `capec_reverse_maps` (T-seeded TaxonomyEntry → in(MAPS_TO) → patterns),
  `cwe_chain` (CWE-seeded Weakness → in(EXPLOITS_WEAKNESS) → patterns → out(MAPS_TO),
  join-key emitting), `capec_hierarchy_chain` (2-hop ChildOf). Each template gets a
  deterministic routing branch keyed on entities/seed-ID patterns, normalizer support
  emitting primary + related + join values, and hermetic builder/routing tests.
  Validators stay untouched (all labels/edges exist on the cards; depth ≤ 3).
- **Rationale**: the catalogue can only contain questions the deterministic builders can
  express; these nine shapes are exactly the gap between the source plan's sub-types and
  today's seven Cypher + four Gremlin templates.
- **Action**: Undergo the verification/tests/validation process for this phase (hermetic
  specialist suites + live smoke of each new template). Once validated, commit to GitHub
  (no push) stating: QA Catalogue Expansion (2/7) Complete: nine new deterministic
  builder templates with routing, normalization, and tests.

#### Step 3: Author Slices B + C — 27 single-source questions
- **Locations**: `utils/specialists/evalset/questions.py` (new anchors + builders),
  regenerated `utils/specialists/tests/golden/attack_questions.json` /
  `capec_questions.json`, count/routing updates in
  `utils/specialists/evalset/tests/test_banks.py`.
- **Work**: Slice B (ATT&CK, 14): 3 technique→detection-strategy→analytic, 3
  software→techniques, 2 sub-technique↔parent, 3 multi-constraint
  (tactic ∧ mitigation, Hard), 1 data-component→analytics, 2 deprecated/revoked
  honest-empty negatives. Slice C (CAPEC, 13): 3 pattern→execution-steps, 3
  consequences/skills, 3 abstraction-hierarchy 2-hop (Hard), 2 pattern→CWE, 2
  deprecated-pattern negatives. All gold values resolved from Step 1 maps; anchors
  chosen for stable, non-trivial gold sets.
- **Rationale**: fills the Hard tier and the v19-detection / CAPEC-substructure coverage
  gaps while staying inside the just-landed template vocabulary.
- **Action**: Undergo the verification/tests/validation process for this phase (bank
  compile deterministic, routing tests, live golden attack/capec suites green at 46/34).
  Once validated, commit to GitHub (no push) stating: QA Catalogue Expansion (3/7)
  Complete: 27 single-source questions authored with snapshot-resolved gold.

#### Step 4: Author Slice A — 40 federated questions with computed `must_correlate`
- **Locations**: new `utils/specialists/evalset/federated_questions.py`, compile hook in
  `utils/specialists/evalset/compile_banks.py`, new committed bank
  `utils/specialists/tests/golden/federated_questions.json`, invariants in
  `utils/specialists/evalset/tests/test_banks.py` (or a sibling test module).
- **Work**: implement the source plan's entry shape (`sources`, `hops`, `tasks` with
  `seed_from`, `assertions.must_correlate` + per-side assertions, `gold_provenance`).
  Sub-slices: 10 CAPEC→techniques→mitigations (Hard), 6 CAPEC→technique→tactic
  (Medium), 6 reverse ATT&CK→CAPEC (Medium), 5 CWE→CAPEC→ATT&CK (Hard), 6 no-mapping
  negatives (Adversarial), 4 partials (Adversarial), 3 multi-pattern fan-in (Hard).
  Every `must_correlate` set is the compile-time intersection of the CAPEC-side map and
  ATT&CK-side existence; per-side `must_include_related` sets come from the Step 1 maps;
  negatives assert the producer's honest empty and the consumer's dependency abstention.
- **Rationale**: this is the catalogue's reason to exist — the questions that measure
  cross-source answer accuracy and mapping recall; gold must be a computed join, never
  eyeballed.
- **Action**: Undergo the verification/tests/validation process for this phase (bank
  loads, 40 entries, intersection discipline pinned by tests, regeneration
  deterministic). Once validated, commit to GitHub (no push) stating: QA Catalogue
  Expansion (4/7) Complete: 40 federated questions with computed must_correlate gold.

#### Step 5: Two-verifier AI re-derivation of every new gold answer
- **Locations**: `utils/specialists/tests/golden/VERIFICATION.md`; verifier work
  products under the session scratchpad (not committed).
- **Work**: two independent agents re-derive every new gold claim **from `data/raw/`
  only** (Verifier A: jq/grep/sed toolchain; Verifier B: independently written Python),
  both forbidden from reading `utils/specialists/`. Claims cover the new single-source
  gold sets, every federated `must_correlate` intersection, and the negatives'
  emptiness. Any disagreement blocks the entry. Record protocol + verdict census in
  VERIFICATION.md.
- **Rationale**: the established substitute for hand domain-review; keeps the
  zero-hand-keyed-gold guarantee auditable.
- **Action**: Undergo the verification/tests/validation process for this phase (all
  verdicts agree; discrepancies resolved by fixing gold, never by relaxing assertions).
  Once validated, commit to GitHub (no push) stating: QA Catalogue Expansion (5/7)
  Complete: two-verifier re-derivation recorded, N/N claims agree.

#### Step 6: Live parameterized suites — the join asserted against the running stack
- **Locations**: new `utils/specialists/tests/test_golden_federated.py`; existing
  `test_golden_attack.py` / `test_golden_capec.py` /
  `utils/synthesis/tests/test_golden_synthesis.py` pick the new entries up from the
  banks automatically.
- **Work**: the federated runner loads `federated_questions.json`, builds a `Plan` from
  each entry's tasks, drives `federation` sequencing + specialists + `bundle_evidence` +
  `synthesize` (LLM off), then asserts: `must_correlate` ⊆ live cross-source join
  values, per-side assertion blocks via the shared `golden_runner` vocabulary,
  sequencing audit rows (producer/consumer/seed counts), honest double-abstention for
  negatives, and correct-partial shape for partials (answerable side intact). Skips
  cleanly when the stack is down. Single-source suites re-run live at the new counts.
- **Rationale**: the catalogue is only a ruler if the live system can actually be held
  against it; this is the layer that measures the join, not just the sides.
- **Action**: Undergo the verification/tests/validation process for this phase (all
  golden suites green live, first run, zero failures). Once validated, commit to GitHub
  (no push) stating: QA Catalogue Expansion (6/7) Complete: 120-question catalogue green
  through the live specialist, federated, and synthesis suites.

#### Step 7: Docs, count reconciliation, full regression, merge
- **Locations**: `docs/structure.md`, `utils/specialists/tests/golden/VERIFICATION.md`,
  `docs/goals.md` / `README.md` roadmap rows if touched, catalogue-census test
  (three banks total exactly 120 with the recorded tier/source/federated split),
  `docs/changelog.jsonl`, merge of `worktree-step10-qa-catalogue` into local `main`.
- **Work**: document the expanded catalogue (counts, tiers, federated data model,
  verification census); add the 120-census test; run the full backend regression
  (`uv run python -m pytest utils/ api/`) including all live suites; merge to `main`
  (commit-only, no push).
- **Rationale**: the source plan's definition of done — totals reconciled, docs honest,
  everything green before the branch lands.
- **Action**: Undergo the verification/tests/validation process for this phase (full
  regression green; census test pins 120). Once validated, commit to GitHub (no push)
  stating: QA Catalogue Expansion (7/7) Complete: docs + census + full regression green,
  merged to main.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Extended gold bank | Join maps + detection/software/CAPEC-substructure maps, snapshot-derived | `utils/specialists/evalset/gold_bank.py`, `utils/specialists/tests/golden/gold_bank.json` |
| New builder templates | 6 Cypher + 3 Gremlin deterministic shapes with routing + normalizers | `utils/specialists/cypher/builder.py`, `utils/specialists/gremlin/builder.py` |
| Slice B+C questions | 27 single-source entries (Hard tier + coverage gaps) | `utils/specialists/evalset/questions.py`, `utils/specialists/tests/golden/{attack,capec}_questions.json` |
| Slice A federated bank | 40 federated entries with computed `must_correlate` | `utils/specialists/evalset/federated_questions.py`, `utils/specialists/tests/golden/federated_questions.json` |
| Two-verifier record | Independent re-derivation census for all new gold | `utils/specialists/tests/golden/VERIFICATION.md` |
| Federated golden runner | Live suite driving federation + synthesis per entry | `utils/specialists/tests/test_golden_federated.py` |
| Template unit tests | Hermetic builder/routing/normalizer tests for the nine new shapes | `utils/specialists/tests/test_cypher_specialist.py`, `test_gremlin_specialist.py` |
| Catalogue census test | Pins 120 total + tier/source/federated split | `utils/specialists/evalset/tests/test_banks.py` |
| Docs | Expanded-catalogue documentation + changelog entries per step | `docs/structure.md`, `docs/changelog.jsonl` |
