# Step 3 — CAPEC anchor resolution: the id had the label baked into it

*Written 2026-09-03. Expands Step 3 of `2026-09-03-measurement-and-retrieval-repair.md`,
which described this as "the Gremlin describe compiler hardcodes
`hasLabel("AttackPattern")`". That is the visible half. The other half is worse
and removing only the visible one would fix nothing.*

---

## 1. Introduction

47 questions in the expansion bank fail because a CAPEC question about a View or
a Category is answered by asking the graph for an AttackPattern. The obvious
culprit is the anchor in `utils/specialists/gremlin/builder.py`, which reads
`g.V().hasLabel("AttackPattern").has("id", within(ids))` in five places. It is
not the whole story: `_capec_gremlin_id` converts `CAPEC-284` to
`capec:attack-pattern:284`, and the graph stores that vertex as
`capec:view:284`. The label is baked into the identifier, so deleting the
`hasLabel` filter would leave the lookup missing exactly as before.

CAPEC's own numbering does not distinguish the three kinds — CAPEC-98 is an
attack pattern, CAPEC-118 a category, CAPEC-284 a view — so no rule can infer
the label from the id, which is presumably why it was pinned to the commonest
case. The fix is to stop inferring: ids are unique across the whole CAPEC store
(6,374 nodes, 6,374 distinct ids), so a question about `CAPEC-284` can ask for
all three namespaces at once and let the graph decide. At most one can match,
the label filter becomes redundant, and no guess is made anywhere.

---

## 2. Gaps & Unanswered Questions

- **Does widening the id also widen what a question can reach?** *Assumption*:
  no, and this is the sharp edge. `cwe:284` exists alongside `capec:view:284`,
  so a numeric-suffix match would silently answer a CAPEC question with a CWE.
  The candidate list is the **three explicit CAPEC namespaces only** —
  `capec:attack-pattern:`, `capec:view:`, `capec:category:` — never a suffix
  match, and never `cwe:`. A test pins this.
- **Is the label filter still worth keeping?** *Assumption*: no, on the seeded
  paths. Identity is the id; the label can only ever exclude the right answer.
  It stays in `meta` for provenance and stays on the *name*-anchored path, where
  there is no id and the label is the only scope.
- **The name-anchored describe.** `_describe`'s no-seed branch scans
  `hasLabel("AttackPattern")` by name regex. *Assumption*: widen it to the three
  CAPEC vertex kinds so "what is Detailed Abstractions?" can resolve, keeping
  the label list explicit rather than dropping the filter (an unlabelled name
  regex over 6,374 vertices is a different and worse query).
- **Nine failures will survive this fix.** 8 `describe` and 1 `capec_neighbors`
  case are already anchored on AttackPattern *correctly*; their cause is
  something else. *Assumption*: they are re-triaged after this lands, not
  bundled into it.
- **Six `capec_maps_to` failures anchor on Technique**, which is not a CAPEC
  label at all — a reverse-direction question reaching the forward template
  while `_capec_reverse_maps` exists. That is a **routing** defect, not a label
  one. *Assumption*: out of scope here, recorded as a follow-up.
- **Does the safety gate accept an anchor with no `hasLabel`?** *Assumption*:
  yes — it is still id-bound and limited — but this is verified against the live
  gate in Step 4 rather than assumed, because the gate is the component with the
  most expensive failure mode.

---

## 3. Hierarchical Step-by-Step Instructions

#### Step 1: Make CAPEC id resolution namespace-complete

- **Locations**: `utils/specialists/gremlin/builder.py`, `_capec_gremlin_id`
  (line 73) and `_CAPEC_NUM_RE`. New `_capec_candidate_ids` returning every
  namespace a bare `CAPEC-<n>` could name.
- **Rationale**: this is the half of the defect that the label filter hides.
  `CAPEC-284` becomes `capec:attack-pattern:284`, which no vertex has; the view
  is `capec:view:284`. Returning all three candidates and letting `within(ids)`
  decide is correct because ids are unique store-wide — the graph disambiguates
  instead of the code guessing. The single-id function stays for callers that
  genuinely mean an attack pattern. **`cwe:` is never a candidate**, or a CAPEC
  question would be answerable by a CWE that shares its number.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *CAPEC Anchor Resolution (1/5) Complete: a
  bare CAPEC id resolves to all three CAPEC namespaces instead of assuming
  attack-pattern.*

#### Step 2: Anchor the seeded CAPEC templates on identity, not on a guessed label

- **Locations**: `utils/specialists/gremlin/builder.py` — `_describe` (line 425),
  `_capec_neighbors` (462, 468), `_capec_facets` (502), `_capec_maps_to` (519).
  `_cwe_chain` and `_capec_reverse_maps` are **not** touched: they anchor on
  `Weakness` and `TaxonomyEntry` deliberately.
- **Rationale**: with candidate ids in hand the `hasLabel` filter has no work
  left to do and can only remove the right vertex. Anchoring on
  `has("id", within(ids))` answers a View question about a View. The label moves
  to `meta` so a draft still records what it believed it was anchoring on.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *CAPEC Anchor Resolution (2/5) Complete: the
  seeded CAPEC templates anchor on the id, so a View question stops asking for
  an AttackPattern.*

#### Step 3: Widen the name-anchored describe to the CAPEC vertex kinds

- **Locations**: `utils/specialists/gremlin/builder.py`, `_describe`'s no-seed
  branch (line 442).
- **Rationale**: with no id there is no identity to anchor on, so the label is
  the only scope and dropping it would turn a name regex loose over 6,374
  vertices. Widening to an explicit `AttackPattern | View | Category` list keeps
  the query bounded while letting "what is Detailed Abstractions?" resolve.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *CAPEC Anchor Resolution (3/5) Complete: the
  name-anchored describe scopes to the three CAPEC vertex kinds.*

#### Step 4: Validate against the live store and the safety gate

- **Locations**: `utils/specialists/tests/test_gremlin_specialist.py`,
  `utils/specialists/tests/test_score_safety.py`, and the live CAPEC store
  (6,374 / 8,582 as reloaded 2026-09-03).
- **Rationale**: a query that is right on paper and refused by the gate is worth
  nothing, and the gate is the component whose failure is most expensive — 15
  genuine bypasses were found in EXP-2026-08-016. Assert the new anchors are
  accepted, that CAPEC-284 returns the View and CAPEC-98 the AttackPattern, and
  that neither returns the CWE sharing its number.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *CAPEC Anchor Resolution (4/5) Complete: new
  anchors verified against the live store and accepted by the safety gate.*

#### Step 5: Re-measure the affected questions and record what did not move

- **Locations**: `scripts/score_bank.py`, `scripts/anomaly_triage.py`; results
  under `docs/evaluation/composition/bank/`.
- **Rationale**: the claim is 47 cases (2 View property reads, 33 `describe`
  containment, 7 `capec_neighbors`, 5 `capec_maps_to`), and a claim of that
  shape is worth only what a re-run says. The 9 correctly-anchored failures and
  the 6 mis-routed `capec_maps_to` cases are **expected to survive** and must be
  reported as surviving rather than quietly folded into the total.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *CAPEC Anchor Resolution (5/5) Complete:
  affected questions re-measured, with the cases the fix does not address named.*

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Candidate id resolver | A bare `CAPEC-<n>` maps to all three CAPEC namespaces; never to `cwe:`. | `utils/specialists/gremlin/builder.py` |
| Id resolution tests | CAPEC-284 -> view, CAPEC-98 -> attack-pattern, CAPEC-118 -> category, and no `cwe:` candidate ever. | `utils/specialists/tests/test_gremlin_specialist.py` |
| Identity-anchored templates | `describe`, `capec_neighbors`, `capec_facets`, `capec_maps_to` anchor on the id. | `utils/specialists/gremlin/builder.py` |
| Template anchor tests | A View seed produces a query that can match a View; `_cwe_chain` and `_capec_reverse_maps` are byte-identical to before. | `utils/specialists/tests/test_gremlin_specialist.py` |
| Name-path scope | Name-anchored describe scoped to AttackPattern, View and Category. | `utils/specialists/gremlin/builder.py` |
| Gate acceptance test | The new anchors are accepted by the safety gate. | `utils/specialists/tests/test_score_safety.py` |
| Live smoke test | Against the reloaded CAPEC store: CAPEC-284 returns Detailed Abstractions, not CWE-284. | `utils/specialists/tests/test_gremlin_specialist.py` (live-marked) |
| Re-measured figures | Affected questions re-scored, with survivors named. | `docs/evaluation/composition/bank/` |
