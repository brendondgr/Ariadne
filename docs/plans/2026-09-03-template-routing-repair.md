# Step 4 — Template routing: the ladder answers a different question

*Written 2026-09-03. Widens Step 4 of `2026-09-03-measurement-and-retrieval-repair.md`,
which scoped this at 8 Cypher cases. EXP-2026-09-003 showed the same defect on
the CAPEC side, where it was hidden behind the anchor bug until that was fixed.*

---

## 1. Introduction

The deterministic arm chooses a query by walking a ladder of conditions over the
labels a question mentions. Twice, the ladder selects a template that answers a
different question from the one asked. On the ATT&CK side, `if has_group:` fires
unconditionally, so *"What does the threat group APT38 describe?"* returns
APT38's 22 techniques. On the CAPEC side, `_resolve_neighbor_rels` recognises
only the seven relationships that leave an **AttackPattern**, so a question about
what a Category *contains* finds no neighbour relationship at all, falls through
to `describe`, and reports the category's status. Both queries are valid, both
execute cleanly, both return the right entity, and neither answers the question.

EXP-2026-09-003 measured the CAPEC half after the anchor fix: the system now
retrieves `capec:category:156` where it used to retrieve nothing, and still
answers *"has Status: Stable"* to a question whose gold is six member ids.
Retrieving the right vertex was a precondition, not an answer. 63 membership
questions in the bank depend on this — 43 forward, 20 reverse — plus the 8
ATT&CK property reads, which is the whole of what Step 4 now covers.

---

## 2. Gaps & Unanswered Questions

- **The general fix is the one we must not make.** A ladder that read its
  neighbour vocabulary from the schema registry would fix this and every future
  instance — and it is precisely what `_generic_walk` already does, under
  `SPECIALIST_GENERIC_ONLY`. Adopting it in the template path would make the
  deterministic arm *into* the generic arm and destroy the comparison C-023
  rests on. *Decision*: extend the hand-written vocabulary by hand. If a
  hand-written library needs a hand edit for every shape the schema already
  declares, **that is the finding**, and re-measuring after the edit is the fair
  version of the test.
- **Direction.** 20 of the 63 membership questions ask from the member's end
  ("which views is CAPEC-66 collected under?"). `.both()` would answer both
  directions and over-return, since a Category has members *and* containers.
  *Assumption*: resolve direction from the resolved labels — outward when the
  anchor is the container, inward when it is the member — and treat a case where
  neither is determinable as out of scope rather than guessing.
- **The planner names the edge `MEMBER_OF`; the graph's edge is `HAS_MEMBER`.**
  *Assumption*: normalise the planner's name to the graph's, the same category of
  handling as `_AP_LABEL_TO_REL`. The spec's own step records
  `predicate: HAS_MEMBER, reverse: false`, so the graph name is authoritative.
- **`_REL_TARGET_LABEL["MEMBER_OF"]` is `Category`, and that is wrong for the
  common case** — `View -[HAS_MEMBER]->` reaches AttackPatterns *and*
  Categories. *Assumption*: leave the target label unset for the membership
  edge, which `_capec_neighbors` already handles by emitting an unlabelled
  `.out()`. A wrong `hasLabel` would reintroduce the defect Step 3 removed.
- **The behaviour lock will fire again.** *Assumption*: only if a *fixture* case
  changes template or string. Verified during implementation; if it does, a
  generation 5 is hand-authored under the generation-4 protocol, not regenerated.
- **Does gating the Group branch break the actor→technique routes?** *Assumption*:
  no, and it is asserted rather than assumed — the frozen `group_techniques`
  case must still route to `group_techniques` byte-identically.

---

## 3. Hierarchical Step-by-Step Instructions

#### Step 1: Gate the ATT&CK Group and Tactic branches on technique intent

- **Locations**: `utils/specialists/cypher/builder.py` — the dispatch ladder's
  branch 3 (`if has_group:` -> `_group_techniques`) and branch 4
  (`if has_tactic:` -> `_tactic_techniques`), and the `describe` fallthrough
  below them.
- **Rationale**: the branches fire on the presence of a label, so any question
  naming a Group is answered with that group's techniques — including a question
  about the group itself. Technique, Campaign and Software reach `describe` and
  score normally; Group and Tactic are the two that do not, which is the whole
  content of EXP-2026-09-002's "Group and Tactic score exactly zero". This is a
  known bug class in this file: the comment above branch 3 records a Group+Software
  task being captured the same way and fixed narrowly for Software. Gate both on
  an actual technique-edge intent.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Template Routing Repair (1/5) Complete: Group
  and Tactic property reads reach describe instead of being answered with the
  anchor's techniques.*

#### Step 2: Teach the CAPEC neighbour vocabulary the membership edge

- **Locations**: `utils/specialists/gremlin/builder.py` — `_AP_NEIGHBOR_RELS`,
  `_resolve_neighbor_rels`, `_REL_TARGET_LABEL`, and `_capec_neighbors`.
- **Rationale**: `_AP_NEIGHBOR_RELS` is seven edges that leave an AttackPattern,
  so a Category's or a View's own containment edge is invisible and the question
  falls through to `describe`. The vocabulary's name says what it assumes. Add
  the membership edge, normalising the planner's `MEMBER_OF` to the graph's
  `HAS_MEMBER`, and leave its target label unset so the traversal stays
  unlabelled — `View -[HAS_MEMBER]->` legitimately reaches two kinds.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Template Routing Repair (2/5) Complete: a
  containment question routes to a membership traversal instead of describe.*

#### Step 3: Resolve traversal direction rather than assuming outward

- **Locations**: `utils/specialists/gremlin/builder.py` — `_capec_neighbors`
  gains a direction, derived from the resolved labels.
- **Rationale**: 20 of the 63 membership questions ask from the member's end.
  `_capec_neighbors` emits `.out()` unconditionally, which answers the forward
  43 and silently returns nothing for the other 20 — trading one wrong answer
  for another. `.both()` would over-return, because a Category has both members
  and containers. Direction is derivable: outward when the anchor label is the
  container, inward when it is the member.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Template Routing Repair (3/5) Complete:
  membership traversals resolve their direction from the anchor's role.*

#### Step 4: Hold the behaviour lock and validate live

- **Locations**: `utils/specialists/tests/test_generic_only_isolation.py`,
  `utils/specialists/tests/test_cypher_builder.py`,
  `utils/specialists/tests/test_gremlin_specialist.py`, and both live stores.
- **Rationale**: Step 1 changes routing on a path the frozen fixture covers
  (`group_techniques`), and a routing change that moved a fixture case would
  mean an actor→technique question had been rerouted — a real regression, not a
  bookkeeping event. Assert the fixture is untouched; if any case legitimately
  moves, hand-author generation 5 under the same protocol. Then confirm live
  that CAPEC-156 returns its members and G0082 returns its description.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Template Routing Repair (4/5) Complete:
  behaviour lock held and both fixes verified against the live stores.*

#### Step 5: Re-measure, and record what still does not move

- **Locations**: `utils/evaluation/experiment_untruncated` over the affected
  dev-half ids; a new experiment folder via `make new-experiment`.
- **Rationale**: EXP-2026-09-003 predicted 47 and delivered 2, so a scope claim
  in this family is worth exactly what a re-run says. Predict before running —
  8 ATT&CK property reads and the dev-half share of the 63 membership questions
  — and report the shortfall as prominently as the gain. **The holdout stays
  sealed.**
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Template Routing Repair (5/5) Complete:
  re-measured against a prediction recorded in advance.*

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Gated Group/Tactic branches | Both fire on technique-edge intent, not on a label's presence. | `utils/specialists/cypher/builder.py` |
| Cypher routing tests | Group and Tactic property reads reach `describe`; actor→technique routes byte-identical. | `utils/specialists/tests/test_cypher_builder.py` |
| Membership vocabulary | `MEMBER_OF`/`HAS_MEMBER` recognised, target label deliberately unset. | `utils/specialists/gremlin/builder.py` |
| Direction resolution | Outward from a container, inward from a member; undeterminable is out of scope. | `utils/specialists/gremlin/builder.py` |
| Gremlin routing tests | Forward and reverse containment produce the right traversal; a Category's members are reachable. | `utils/specialists/tests/test_gremlin_specialist.py` |
| Behaviour-lock check | The frozen fixture is unmoved, or generation 5 is hand-authored under protocol. | `utils/specialists/tests/test_generic_only_isolation.py` |
| Live verification | CAPEC-156 returns its members; G0082 returns its description. | run against both stores |
| Experiment record | Prediction recorded before the run; shortfall reported as prominently as the gain. | `docs/research/experiments/` |
