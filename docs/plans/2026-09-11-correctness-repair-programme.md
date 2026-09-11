# Correctness repair programme — the six defects behind 0.6569, fixed and measured against a concurrent control

**Date:** 2026-09-11
**Mode:** B — no worktree, straight onto `main`.
**Commit at every step. Never push.** The planner skill's template says "push to
GitHub"; the operator's standing directive and `global-project-rules` rule 1
both override it. Every step also appends to `docs/changelog.jsonl`.

**Server boundary.** Steps 0–4 need no language model and no judge; they are
code, tests, the model-free regression and record work. Step 5 onward needs
the LLM server (`:9090`) for judging, generation and question authoring, and
each of those steps says how many hours it will hold it.

**Agent workflow, if used:** Steps 1, 2 and 4 are independent of one another
and can run in parallel after Step 0; Step 3 should follow Step 1 because the
chained walk anchors on the same identifier resolution; Step 5 needs Step 4;
Steps 6–8 are sequential.

---

## 1. Introduction

Two diagnostics of the same 284 development answers were written on
2026-09-11, independently. [`EXP-2026-09-017`](../research/experiments/EXP-2026-09-017-correctness-improvement-diagnostic/)
re-aggregates the original paired qwen judgments by question tier, prices the
headroom per tier (two-hop questions carry **+0.1116** of a possible +0.3431),
and proposes four research-backed directions: repair the CAPEC gate (Q45),
compile an *answer contract* that renders the requested field before any
prose, represent multi-hop requests as a typed chain with execution feedback
(after Guo et al., EMNLP 2023, *Parse-Execute-Refine*), and rank ambiguous
entity candidates jointly. It also prescribes the measurement that would make
any of those claimable: a concurrent paired control, unchanged answers as a
grader-drift control, counterbalanced grading, paired intervals, latency at
the shipped budget, scoring corrections reported apart from capability gains,
and a **freshly sealed** evaluation set for the final read because the
288-question holdout is spent.

The second diagnostic (the session's loss map, published as an artifact and
recorded in Step 0 as `EXP-2026-09-017` amendment A-2) joined the same
judgments to the bank's anchor, predicate chain and filter fields and to each
answer's retrieval outcome, and assigned every question to the first *mechanism*
that applies. Its per-case scores are byte-identical to EXP-017's CSV. It
found that the tier headroom is mostly five ordinary defects, each with a code
location, plus one dead model seam:

| Mechanism | n | generic mean | share of the 97.5 points lost | where |
|---|---:|---:|---:|---|
| Two-hop chain collapsed to the shortest schema path | 56 | 0.463 | 30.9% | `cypher/builder.py` `_generic_chain`, `gremlin/builder.py` walk |
| Five CAPEC edges declared but not allowlisted (Q45) | 34 | 0.429 | 19.9% | `kg_builder/schema/capec.py`, `gremlin/validator.py` |
| Narrator timed out, no other defect | 49 | 0.696 | 15.3% | `SYNTHESIS_LLM_TIMEOUT_S` default 120 s |
| D5 property filter never reaches the query or the composer | 39 | 0.670 | 13.2% | plan carries no filter; builders and composer ignore the text |
| Category / View seed mapped to the attack-pattern namespace | 23 | 0.467 | 12.6% | `gremlin/builder.py` `_gremlin_vertex_id` at two walk call sites |
| Composer never states an empty requested set | 16 | 0.641 | 5.9% | `synthesis/composer.py` `compose` |
| No known defect, narrator ran | 67 | **0.968** | 2.2% | — |

The two agree on every number and disagree on nothing; they differ in
resolution. EXP-017's "answer contract" is the general form of two of the
mechanisms above (the D1 property questions it exhibits are all narrator
time-outs where the deterministic composer had dropped the *list-valued*
requested property, `x_mitre_platforms`, because `_attribute_pairs` skips
lists), and its "typed chain" is the general form of the shortest-path
collapse. This plan therefore takes EXP-017's measurement protocol and
research framing as the contract, and the loss map's mechanisms as the work
list, in the order the prize sizes dictate. The same four builder defects sit
in the spent holdout in similar proportion (95 two-hop, 58 filtered, 30
Category or View anchors, 22 touching the five edges), so what is repaired on
the development half transfers to the figure the pitch quotes.

The bound on the prize, if every affected question rose only to the single-hop
ATT&CK mean of 0.797, is about **+0.20** on the development mean. The plan
does not promise it. It pre-registers what each repair must show, in Step 0,
before any number is seen.

---

## 2. Gaps & Unanswered Questions

**Resolved by assumption — proceeding.**

- **The gold-plan protocol stays.** `EXP-2026-09-005` injects the bank's
  authored plan (`_gold_plan` in `utils/evaluation/experiment_untruncated.py`)
  so that retrieval starts from a known-correct plan. That plan carries the
  ordered graph vocabulary (`entities`, in path order, repeats dropped), the
  seed ids and the limits, and **nothing else**: no filter, no requested
  property, only the first relationship token of a chain. *Assumption:* the
  plan is not extended. Requested property, filter and chain are derived at run
  time from what the system already receives — the ordered `entities` list and
  the sub-question text against the card's declared vocabulary — so the shipped
  path, which gets an LLM-drafted plan of the same shape, benefits identically.
  Extending the plan schema is the alternative and is a protocol change to
  disclose; it is listed under human decisions.
- **Which arm is repaired.** `generic` (schema-derived primitives, LLM planner
  replan, LLM specialist seam, LLM narrator, facet loop) is the arm that carries
  `C-023` and the pitch's 0.6546, so it is the primary arm. `generic_composed`
  (same primitives, deterministic composition, no model) is its model-free
  twin and is run beside it in every measurement, because it is byte-
  reproducible and because EXP-017's answer contract must hold *without* a
  narrator to be a construction property. The `deterministic` template arm is
  run as the regression control and must stay byte-identical throughout.
- **Narrator budget.** `scripts/generic_identity_rerun.py` (EXP-2026-09-010)
  already found the narrator's failures to be read time-outs at the 120 s
  default and raised `SYNTHESIS_LLM_TIMEOUT_S` to 600 with a `degraded()`
  health check. *Assumption:* every generic run in this plan uses that budget
  and that check, and a run whose fallback rate exceeds the healthy reference
  of 0.14 (`EXP-2026-09-016` I-4) is discarded and re-run, never reported.
- **Judge.** `qwen38-27B-v2` on `:9090`, two counterbalanced positions per
  answer, `max_tokens 32768`, 16 workers per instance across two instances, as
  in `EXP-2026-09-016` A-5. `gemma4-31B` grades a second pass for *ordering*
  only; its scores are never averaged with qwen's (EXP-2026-09-009). Q48's
  boilerplate artefact is left in place for comparability and reported
  separately, per EXP-017.
- **Concurrency for generation.** 24 workers, `ORCH_MAX_HOPS=5`,
  `SPECIALIST_LLM_TIMEOUT_S=4096`, matching `scripts/holdout_run.py` and
  `EXP-2026-09-016` A-1, so cost figures are comparable to the cost table.
- **Chain realisation.** A chain is realised as one query per source with the
  intermediate retained as a row (the `generic_neighbors` contract already
  carries intermediates); the star walk stays as the fallback when the chain
  returns nothing, so a chained question can only gain records. Cross-source
  chains (D6) go through the existing join machinery unchanged in this plan;
  only the single-source legs are chained.
- **Disclosure.** `EXP-2026-09-005` repaired the *template* arm before
  comparing. Everything here repairs the *generic* arm and widens a gap
  `C-023` already reports in its favour. RESULTS says so in its first
  paragraph, and `C-023`'s evidence column is amended, not replaced.

**Human intervention is needed to answer these.**

- **Slot source for the requested property and the D5 filter.** The plan
  derives both from the sub-question text against the card (Step 4). The
  alternative is to extend the bank task and the plan schema with
  `requested_property` and `filters`, which the bank's `spec` already holds.
  That is cleaner and more general, but it changes what every arm receives and
  must be run for all three arms and disclosed as a protocol change. **Confirm
  text-derived (recommended) or schema-extended before Step 4 starts.**
- **Ship rule for the chained walk.** The plan pre-registers *"D4 + D6 generic
  mean rises by at least 0.10 on the development half, the deterministic arm is
  byte-identical, `fabricated_mapping` stays at 0 and the wrong-entity rate on
  the variant bank's T6 does not rise"* as the rule for making the chain the
  default. Confirm or replace it **before Step 6 runs**.
- **The fresh sealed set.** EXP-017 is right that the holdout is spent. Minting
  a new 288-question set requires the author model on `:9090` for question
  phrasing (`spec_bank.to_bank(seed=…)`, `author_path: subagent`) and then a
  judged run of three arms: roughly the cost of `EXP-2026-09-007` again, a
  night of the server. **Approve the spend, and choose the seed, before Step 7.**
- **Q45's mechanism.** Derive the five patterns from the canonical snapshot into
  `CAPEC_ALLOWED_EDGE_PATTERNS` (authorable, reviewable, fail-closed), or give
  the validator a registry fallback so a lagging card cannot forbid a real edge
  again (general, but it moves policy from the card to the data). The plan does
  the first and adds the second as a *warning*, not a permission, so the card
  stays the policy. Confirm that the card remains the sole permission source.

---

## 3. Hierarchical Step-by-Step Instructions

### Step 0 — Record the mechanisms, repair the record, pre-register the experiment

- **Locations:** `docs/research/experiments/EXP-2026-09-017-…/RESULTS.md`
  (append **AMENDMENT A-2**: the mechanism table above, its first-match
  assignment rule, and the retrieval-outcome and narrator splits), with
  `data/mechanisms.csv` (per case: mechanism, records, coverage, fallback
  reason, anchor label, predicate chain, filter) and `data/mechanisms.py` (the
  join, reading only the committed `cases.csv` plus the bank and the saved
  answers, never regrading); `docs/research/OPEN_QUESTIONS.md` — add the
  missing `Q49` index row; **amend `Q47`**: the audit in
  `EXP-2026-09-016/data/generic_fallback_audit.json` divided by the answer
  directory's *file* count (3,407; 1,440; 852), of which only 284, 288 and 284
  are answers, so the true narrator-fallback rates are **0.43** (dev), **0.30**
  (holdout) and **0.07** (expansion) against a healthy reference of 0.14 — file
  as an appended amendment to `EXP-2026-09-016` (`A-7`), re-issue the JSON with
  answer denominators, and re-state Q47 as *partly answered in the wrong
  direction*; file `Q50` (Category/View namespace), `Q51` (chain collapse),
  `Q52` (filter never applied), `Q53` (composer drops list-valued requested
  properties and never states an empty set). Then
  `make new-experiment SLUG=correctness-repair` →
  `EXP-2026-09-018-correctness-repair`; write `PROTOCOL.md` with the six
  hypotheses and kill gates below **before** any code changes; run
  `scripts/holdout_seal.py` to assert the holdout is still unspent by any
  repaired arm; capture the model-free references for both banks
  (`deterministic` and `generic_composed` over `bank-dev.json` and
  `bank-holdout.json` at the current commit) under
  `EXP-2026-09-018/data/reference/` so every later diff has a baseline.
- **Pre-registered hypotheses (development half, paired, same session):**
  **H1** chained walk: D4 + D6 generic mean +0.10 or more; **H2** namespace:
  zero-record rate on non-D0 Category/View anchors falls from 25 of 25 to 0;
  **H3** Q45: the 34-question slice's judged mean rises from 0.429 to 0.60 or
  more; **H4** answer contract: on the frozen-evidence re-composition, the
  requested property value appears in the claims on 100% of D1 property
  questions whose evidence carries it, and the judged mean on those questions
  rises; **H5** filter: on D5, records outside the filter are absent from the
  claims and the judged mean rises; **H6** no regression: `deterministic` is
  byte-identical on both banks, `fabricated_mapping` stays 0 on every arm,
  the variant bank's T6 wrong-entity and catalogue-dump rates do not rise, and
  generic single-user latency at the shipped budget does not exceed 2x its
  Step 0 reference. **Kill gate:** any rise in `fabricated_mapping` or T6
  wrong-entity means the change does not ship regardless of the mean.
- **Rationale:** the numbers in this plan exist only in a chat log and an
  artifact until A-2 is written, and the record's rule is that such numbers do
  not exist. Q47's audit is arithmetically wrong in a committed file that says
  "no published figure is affected"; it must be corrected before the pitch
  cites it, and before this plan's narrator budget is justified by it. The
  protocol is written now because EXP-017's own falsification clause says an
  intervention selected on this data needs a concurrent control and a fresh
  set, and a hypothesis written after the run is not one.
- **Validation:** `make validate-research`, `make index`, `make check-docs`
  all green; A-2's script reproduces the 0.6569 and 0.4946 means from
  `cases.csv` exactly; the re-issued audit JSON's denominators equal the
  answer counts.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  (0/8) Complete: mechanisms recorded, Q47 audit corrected, Q49–Q53 filed,
  EXP-2026-09-018 pre-registered with references captured.

### Step 1 — Category and View seeds resolve in their own namespace

- **Locations:** `utils/specialists/gremlin/builder.py` — the two walk call
  sites that build `ids` with `_gremlin_vertex_id` (the generic walk near the
  `union` assembly, and the join-owner traversal) switch to
  `_capec_candidate_ids`, whose docstring already describes this exact
  failure; the anchor stays identifier-only (no `hasLabel` on the seed).
  Tests in `utils/specialists/tests/test_generic_primitives.py`: a
  `Category`-seeded and a `View`-seeded walk bind all three namespaces;
  `test_generic_only_isolation.py` still proves the template path untouched.
- **Rationale:** all 21 Category anchors and 18 of 20 View anchors in the
  development run returned zero records because `CAPEC-687` became
  `capec:attack-pattern:687`, which no vertex has. The template path fixed
  this in July and the walk never adopted it. It is the cheapest repair in the
  plan and it unblocks Step 3, whose chains often start at a Category.
- **Validation:** unit tests; `scripts/catalogue_regression.py` over the
  variant reference (no template answer moves); `generic_composed` re-run over
  `bank-dev.json` diffed against the Step 0 reference: only Category/View-
  anchored questions change, and every change is a gain in gold coverage.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  (1/8) Complete: Category and View seeds resolve in the generic walk; 25
  zero-record anchors now retrieve.

### Step 2 — The five declared CAPEC edges are allowlisted, derived from the snapshot

- **Locations:** `utils/kg_builder/schema/capec.py` `CAPEC_ALLOWED_EDGE_PATTERNS`
  gains `HAS_ALTERNATE_TERM`, `HAS_EXAMPLE`, `HAS_INDICATOR`,
  `HAS_PREREQUISITE`, `REQUIRES_RESOURCE`, each `AttackPattern → <target>`,
  with a test that asserts every entry of `CAPEC_RELATIONSHIP_TYPES` has a
  pattern and that each pattern's endpoint pair is exactly the one observed in
  the canonical snapshot (`utils/kg_builder/tests/`); the card is regenerated
  through `utils/planner/card_enrichment.py` so `data/source_cards/capec.json`
  carries 21 of 21; `utils/specialists/gremlin/validator.py` keeps rejecting an
  edge with no pattern, and additionally emits a *warning* trace when the
  registry's `facet_exists` says the edge is real (so a lagging card is visible
  in the trace, but never permitted by data alone); tests in
  `utils/specialists/tests/test_gremlin_validator.py`.
- **Rationale:** Q45. The validator treats a relationship missing from a
  non-empty allowlist as forbidden and rejects the draft before it runs, and
  ATT&CK's empty allowlist is unconstrained, so the more complete card is the
  one punished. Deriving the patterns from the snapshot makes them reviewable;
  keeping the validator fail-closed keeps the safety property. The 240-probe
  audit (`EXP-2026-08-016`) is re-run because a gate changed.
- **Validation:** unit tests; the 240 adversarial probes still block at 1.000;
  `generic_composed` re-run over both banks: only questions touching the five
  edges change, all gains; the template arm is byte-identical.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  (2/8) Complete: CAPEC card allowlists all 21 declared edges from the
  snapshot; the gate stays fail-closed and the probe audit holds.

### Step 3 — Two-hop questions are answered as a chain, with the star as fallback

- **Locations:** `utils/specialists/schema/paths.py` — new `chain_paths(registry,
  dataset, labels_in_order, *, max_hops)` returning, for each consecutive label
  pair in the plan's ordered `entities`, the shortest declared hop sequence
  between *that pair*, so `Campaign → Software → Technique` becomes
  `[USES]` then `[USES]` rather than the direct `Campaign –USES→ Technique`;
  `utils/specialists/cypher/builder.py` `_generic_chain` — when the resolved
  labels give an ordered chain of two or more legs, emit one `OPTIONAL MATCH`
  per leg *from the previous leg's variable* (`(n)-[:USES]->(m0)`, then
  `(m0)-[:USES]->(m1)`), collect per leg so intermediates land in the related
  set, and keep the existing per-label star as the fallback branch;
  `utils/specialists/gremlin/builder.py` — the walk adds a chained branch
  (`out(e1).out(e2)`) under the same guard and budget rules, with the
  intermediate emitted via `path()` or a second `select`; both builders name
  `chain` in `QueryDraft.template` and record `dropped` branches in meta as
  today. Tests in `utils/specialists/tests/test_generic_primitives.py` for a
  two-leg Cypher chain, a two-leg Gremlin chain, a Category-rooted chain, and
  the fallback when the chain is empty.
- **Rationale:** this is the largest prize (30.9% of the loss) and the
  mechanism is exact: both builders compute the shortest path from the anchor
  to each wanted label independently and union the results around the seed,
  which answers "which techniques do C0023's tools use" with the campaign's own
  four techniques. The plan's `entities` list is already in path order, so no
  new input is needed. This is EXP-017's "typed chain" at its minimum: the
  chain is typed by the schema, intermediates are kept, and a failed leg is
  visible in the trace; the execution-feedback replanning Guo et al. describe
  is left to the existing bounded loop and named as future work.
- **Validation:** unit tests; `generic_composed` over both banks diffed against
  the Step 0 reference: D4 gold coverage rises, no single-hop question loses a
  record; template arm byte-identical; the pre-run gate still accepts every
  chained draft under `max_traversal_depth`.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  (3/8) Complete: generic builders chain consecutive labels and keep the star
  as fallback; two-hop coverage rises on both banks.

### Step 4 — The answer contract: requested property, filter and empty set, model-free

- **Locations:** `utils/planner/canonical.py` — a small `RequestedSlots`
  (`property: str | None`, `filter: tuple[label, property, value] | None`,
  `relation: str | None`) and `requested_slots(text, entities, card, registry)`
  that binds the property from the card's declared property names and glosses
  (`label_properties`, the card's property descriptions such as
  `x_mitre_platforms`), the filter from a property name plus a value the
  registry has observed on that label (`value_verdict`; the bank's 105 filters
  use six properties on four labels, all `eq`), and the relation from the
  ordered `entities`; nothing is guessed, and an unbound slot stays `None`.
  `utils/synthesis/composer.py` — `_attribute_claim` projects the *requested*
  property even when its value is a list (joined, capped), while the generic
  attribute listing keeps skipping lists; `_enumeration_claims` applies a bound
  filter to the records before claims are built and says so in the claim
  ("… rated Medium likelihood"); a new `_absence_claim` states "X has no
  <requested relation>" when the anchor resolved and the requested relation
  returned no rows, carrying the executed query as its evidence exactly as an
  `Abstention` does, with `kind="absence"`; `utils/synthesis/verifier.py`
  admits an absence claim only when its query ran clean and returned nothing
  for that relation; `utils/synthesis/narrator.py` gets a test that the rendered
  prose keeps every requested value the claims carry. The builders may also
  push a bound `eq` filter into the query (`WHERE m.prop = $v` / `has(prop,
  v)`) — do this in the same step so retrieval and composition agree. Tests in
  `utils/planner/tests/test_canonical.py`, `utils/synthesis/tests/test_composer.py`
  and `test_abstention.py`.
- **Rationale:** EXP-017's second direction and the loss map's fifth and sixth
  mechanisms are one thing: the deterministic composer does not know what was
  asked. The two D1 examples EXP-017 exhibits (platforms of T1027.006,
  contributors of T1530) are answers whose evidence carried the value and whose
  claims dropped it because `_attribute_pairs` skips list values, and whose
  narrator, which would have said it, had timed out; the D5 filter is never
  applied anywhere; the D0-with-records case lists a parent and never says the
  requested set is empty. Making the requested slot a verified claim removes the
  dependence on the narrator entirely, which is what turns "the narrator
  usually says it" into a construction property `C-017` can rest on.
- **Validation:** unit tests; `generic_composed` over both banks diffed
  against the Step 0 reference: every D1 property question whose evidence
  carries the property now has it in a claim; D5 claims contain no
  out-of-filter record; template arm byte-identical (the composer changes are
  gated on a bound slot, and the template path binds none unless the text
  names one — assert this explicitly in `test_generic_only_isolation.py`).
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  (4/8) Complete: composer states the requested property, applies the bound
  filter and asserts empty sets with proof; no model involved.

### Step 5 — Frozen-evidence composition comparison (first server step, ~2 h)

- **Locations:** `scripts/recompose_frozen.py` — loads every saved
  `EXP-2026-09-005` generic answer, rebuilds `FederatedEvidence` from its
  `logic_flow.results`, runs the Step 4 composer and verifier over that
  identical evidence, and writes a parallel answer set under
  `EXP-2026-09-018/data/frozen/`; a deterministic check per case that every
  requested value present in evidence is present in the claims; then the judge
  over the old and new answer sets **blinded and position-counterbalanced**, 16
  workers per instance, with unchanged answers (those whose claims did not
  change) as the grader-drift control.
- **Rationale:** this is the experiment EXP-017 asked for by name. It isolates
  composition from retrieval: the same records, two composers, one judge. If
  the judged mean does not move on D1 and D5 here, Step 4 is wrong and Step 6
  should not carry it.
- **Validation:** the drift control's paired difference is within the
  grader-repeatability SD (0.0066 median, `EXP-2026-09-012`); H4 and H5 read
  off the changed cases; results into `EXP-2026-09-018/data/metrics.json`.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  (5/8) Complete: frozen-evidence comparison judged; composition gain isolated
  from retrieval.

### Step 6 — Concurrent paired control on the development half (server, one night)

- **Locations:** `scripts/repair_control_run.py` (after
  `scripts/generic_identity_rerun.py`) — in one session, on the same live
  graphs, run `generic` and `generic_composed` at the repaired commit **and**
  at the Step 0 reference commit (via a checked-out worktree of that commit),
  and `deterministic` at both, over `bank-dev.json`; env as in the assumptions
  (`SYNTHESIS_LLM_TIMEOUT_S=600`, `SPECIALIST_LLM_TIMEOUT_S=4096`,
  `ORCH_MAX_HOPS=5`, 24 workers); `degraded()` after each arm, re-run any arm
  above 0.14 fallback; judge every arm two positions; the single-user latency
  sample (20 questions, one worker) for the repaired `generic` at the shipped
  120 s budget and at 600 s; `scripts/model_identity.py --json` before the
  first run. Scoring: paired bootstrap per tier and per mechanism slice
  against the pre-registered H1–H3, H6; the T6 wrong-entity and catalogue-dump
  rates from `scripts/variant_harness.py` on the repaired build.
- **Rationale:** EXP-017's protocol, exactly: a concurrent control removes the
  session effect Q46 documented (a 0.0503 move between sessions with zero
  within-session spread), the reference-commit arm is the only honest baseline
  for a changed builder, and the latency reading at the shipped budget is what
  Q37 says any future LLM-arm figure must carry.
- **Validation:** every arm's fallback rate below 0.14; `deterministic`
  byte-identical to its reference on all 284; `fabricated_mapping` 0 on all
  arms; H1–H3 and H6 read and recorded whichever way they fall; the
  narrator-timed-out and narrator-ran splits reported for both generic arms.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  (6/8) Complete: repaired and reference arms judged in one session; H1–H3
  and H6 recorded.

### Step 7 — A freshly sealed evaluation set, run once (server, one night plus authoring)

- **Locations:** `utils/specialists/evalset/composition.py` +
  `spec_bank.to_bank(seed=<new>)` with the author model, following
  `docs/plans/2026-09-01-bank-expansion.md`'s generation and gate steps;
  the new bank written to `docs/evaluation/composition/bank/bank-fresh-<date>.json`,
  SHA-256 sealed in `EXP-2026-09-018/data/POINTERS.md` **before** any arm
  sees it, with the same tier mix as the holdout and its generation seed
  recorded; then one run of `generic`, `generic_composed` and `deterministic`
  at the configuration Step 6 selected, judged two positions, gemma pass for
  ordering only; the spent holdout re-run as a regression set and reported as
  such, never as new evidence.
- **Rationale:** EXP-017's closing condition. The development half selected
  the configuration and the holdout has been judged, so neither is unseen; the
  only figure that can replace 0.6546 on a slide is one from a set nothing here
  has touched.
- **Validation:** `scripts/holdout_seal.py`-style assertion that the fresh bank
  has no saved answers before the run; the fresh-set figure and its paired
  intervals into `metrics.json`; the holdout regression diffed against
  `EXP-2026-09-007`.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  (7/8) Complete: fresh sealed set generated, sealed and judged once; holdout
  re-run as regression only.

### Step 8 — Write-up, ledgers, defaults, pitch numbers

- **Locations:** `EXP-2026-09-018/RESULTS.md` (headline, per-mechanism table
  before/after, the frozen-evidence result, the fresh-set figure, the
  disclosure paragraph, threats to validity), `manifest.yaml` with every
  figure; `docs/research/CLAIMS.md` — `C-023` evidence amended with the
  fresh-set figure and the repaired dev figure, `C-017` gains the absence
  claim; `docs/research/DECISIONS.md` — one decision on making the chained walk
  and the answer contract default (if the ship rule held), one on the fresh-set
  discipline (a spent holdout is a regression set); `OPEN_QUESTIONS.md` —
  close Q45, Q50–Q53 and record what remains; `docs/pitch/` — **only if** the
  fresh-set figure is in hand, a fourth numbers audit updating slide 5 and B1
  with the fresh figure labelled as such and the old 0.6546 kept as the
  holdout figure; `make index`, `make validate-research`, `make check-docs`.
- **Rationale:** the record is the deliverable. A repaired arm without an
  amended claim and an updated pitch is a number in a chat log again.
- **Validation:** all three gates green; every figure in the write-up traces to
  `metrics.json`; the pitch audit's verification log extended.
- **Action:** Undergo the verification/tests/validation process for this
  phase. Once validated, commit (do not push) stating: Correctness Repair
  (8/8) Complete: results, claims, decisions and pitch figures recorded.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Mechanism amendment | A-2: per-case mechanism assignment, retrieval outcome, narrator split; reproduces 0.6569 / 0.4946 | `docs/research/experiments/EXP-2026-09-017-…/RESULTS.md`, `data/mechanisms.{csv,py}` |
| Audit correction | Q47 fallback audit re-issued with answer denominators; EXP-016 amendment A-7 | `docs/research/experiments/EXP-2026-09-016-…/{RESULTS.md,data/generic_fallback_audit.json}`, `OPEN_QUESTIONS.md` |
| Open questions | Q49 indexed; Q50–Q53 filed | `docs/research/OPEN_QUESTIONS.md` |
| Pre-registered protocol | H1–H6, kill gate, arms, budgets, judge, seeds | `docs/research/experiments/EXP-2026-09-018-correctness-repair/PROTOCOL.md` |
| Reference captures | Model-free answers for `deterministic` and `generic_composed` on both banks at the pre-repair commit | `EXP-2026-09-018/data/reference/` |
| Namespace fix | Walk call sites use `_capec_candidate_ids` | `utils/specialists/gremlin/builder.py` |
| Allowlist completion | Five patterns derived from the snapshot; card regenerated; validator warning trace | `utils/kg_builder/schema/capec.py`, `data/source_cards/capec.json`, `utils/specialists/gremlin/validator.py` |
| Chained walk | `chain_paths()`; chained `OPTIONAL MATCH` legs and Gremlin chain branch; star fallback | `utils/specialists/schema/paths.py`, `utils/specialists/cypher/builder.py`, `utils/specialists/gremlin/builder.py` |
| Requested slots | `RequestedSlots`, `requested_slots()` bound from card vocabulary and observed values | `utils/planner/canonical.py` |
| Answer contract | Requested-property projection, bound-filter enumeration, absence claim with proof, verifier rule | `utils/synthesis/composer.py`, `utils/synthesis/verifier.py`, `utils/synthesis/narrator.py` |
| Unit tests: builders | Namespace binding; chain legs (Cypher, Gremlin, Category-rooted); empty-chain fallback; template path untouched | `utils/specialists/tests/test_generic_primitives.py`, `test_generic_only_isolation.py` |
| Unit tests: gate | 21/21 patterns; endpoint pairs match snapshot; unknown edge still rejected; warning trace | `utils/kg_builder/tests/`, `utils/specialists/tests/test_gremlin_validator.py` |
| Unit tests: contract | List-valued requested property projected; filter applied; absence claim verified; narrator keeps values | `utils/synthesis/tests/test_composer.py`, `test_abstention.py`, `utils/planner/tests/test_canonical.py` |
| Frozen-evidence tool | Re-composes saved evidence; deterministic requested-value check; blinded paired judging | `scripts/recompose_frozen.py`, `EXP-2026-09-018/data/frozen/` |
| Control runner | Repaired and reference commits in one session; `degraded()` guard; latency at two budgets | `scripts/repair_control_run.py` |
| Fresh sealed set | New-seed bank, SHA-256 sealed before use; one judged run; holdout as regression | `docs/evaluation/composition/bank/bank-fresh-<date>.json`, `EXP-2026-09-018/data/POINTERS.md` |
| Experiment record | manifest, PROTOCOL, RESULTS, ISSUES, metrics.json, figures | `docs/research/experiments/EXP-2026-09-018-correctness-repair/` |
| Ledger and pitch updates | C-023 / C-017 amended, two decisions, questions closed, fourth pitch numbers audit | `docs/research/{CLAIMS,DECISIONS,OPEN_QUESTIONS}.md`, `docs/pitch/`, `docs/changelog.jsonl` |
