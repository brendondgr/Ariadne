# Measurement and Retrieval Repair — the defect behind EXP-2026-09-002's weak tiers

*Written 2026-09-03. Supersedes Step 1 of `2026-09-03-publication-plan.md`, which
described this work as a single defect. It is four, and one of them is in the
instrument rather than the system.*

---

## 1. Introduction

EXP-2026-09-002 reported that "in 63 of 63 cases the system builds a database
query correctly and the query comes back empty", and the publication plan made
repairing that the gate on every quotable number. Direct inspection of the run's
own 572 answer artifacts shows the sentence is wrong in both halves: the query is
frequently *not* correct, and it usually does *not* come back empty — 455 of 572
results carry records. The "63 of 63" and "68 of 68" figures are an artifact of
`scripts/anomaly_triage.py:53`, which reads `row_count` off the result object
while the field only ever exists inside `traces[].detail`; the sum is therefore
always zero and `classify()` has exactly one reachable branch.

Re-derived from the artifacts, the 131 failures are four separate things: **53**
property reads where the system answered correctly and the scorer cannot see it
(recall lands on exactly `1/(gold_width+1)` in all 53, the signature of the
anchor being the only creditable item while sitting in the denominator); **62**
where the Gremlin `describe` compiler hardcodes `hasLabel("AttackPattern")` for
View and Category anchors; **8** where the Cypher ladder routes a Group or Tactic
property read to a neighbour-expansion template and answers a different question;
and roughly **8** still unexplained. This plan repairs the instrument first, then
the two real retrieval defects, then settles the budget-confounded `llm_query`
arm — three workstreams that run concurrently against disjoint code paths and
converge on a **single** 16-way re-run recorded as EXP-2026-09-003.

---

## 2. Gaps & Unanswered Questions

- **Fix the scorer or fix the bank?** The bank hash matches the run's preflight,
  so the 572 questions are comparable across every arm already measured.
  *Assumption*: **fix the scorer, never the bank.** Regenerating questions would
  forfeit that comparability and force a re-run of arms that are not defective.
- **What counts as "the description was surfaced"?** *Assumption*: normalised
  containment — casefold, collapse whitespace, strip citation markers — with a
  stated token-overlap floor for long values, applied to the composed answer
  narrative only, never to the database. The threshold is pre-registered before
  re-scoring, not tuned afterwards.
- **Does re-scoring require re-running?** *Assumption*: no. Steps 1 and 2 are
  applied to the 572 saved answers on disk, which is why they return an answer in
  hours rather than overnight.
- **The ~8 residual cases.** Cause unknown until the instrument is repaired.
  *Assumption*: they are triaged in Step 2 and recorded as `undetermined` if the
  artifacts cannot distinguish a cause, per the existing triage discipline.
- **The scorer fix moves numbers upward.** That is the direction that invites
  suspicion. *Assumption*: the new rule is written down and committed **before**
  any re-scored number is computed, and both figures are reported side by side
  permanently. **Human intervention is advisable on the framing**, not on the fix.
- **`llm_query`: re-run at an adequate budget, or cut the arm?** A working budget
  was 8,269 completion tokens against the arm's 4,096, and one probe at the
  larger budget died on a relay 502. Re-running 284 questions at 32,768 may not
  be affordable or may not complete. **Human intervention is needed to answer
  this question** — Step 6 produces the cost evidence, but the call is the
  operator's.
- **Does the holdout move?** *Assumption*: **no.** The 288 held-back questions
  stay sealed through every step here. Spending them belongs to Step 7 of the
  publication plan, after this plan closes.
- **Push policy.** `planner.md`'s template says "push to GitHub". Global rule 1
  and the operator's standing directive say commit locally and never push. **The
  commit wording below deliberately omits the push.**

---

## 3. Hierarchical Step-by-Step Instructions

### Concurrency map

Step 1 is blocking. Steps 2–4 and Step 6 then run **concurrently** — they touch
disjoint files and none imports another. Step 5 gates Step 7. Step 7 is the only
serialised long pole.

```
Step 1  (blocking, ~30 min)
   |
   +-- Workstream A: Step 2  (scorer + re-score)        \
   +-- Workstream B: Step 3, Step 4  (retrieval fixes)   >-- Step 5 -- Step 7 -- Step 8 -- Step 9
   +-- Workstream C: Step 6  (llm_query budget)         /
```

---

#### Step 1: Repair the anomaly triage classifier

- **Locations**: `scripts/anomaly_triage.py`, `classify()` (line 53). Cross-check
  against `utils/specialists/base.py:94`, which is where `row_count` actually
  lives.
- **Rationale**: `r.get("row_count") or 0` reads a field that exists on no result
  object in any of the 572 artifacts, so the sum is always 0 and
  `query_built_returned_no_rows` is the only reachable verdict. The three
  branches below it are dead code. Until this is fixed every number the script
  produces is the same number, and the published claim it fed is false. Read row
  counts from `len(result["records"])` — present and populated — and add a
  regression test that a result carrying records is never classified as empty.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Measurement and Retrieval Repair (1/9)
  Complete: anomaly triage read row_count from a level where it never exists, so
  every case classified as an empty query; fixed and covered by a test.*

---

#### Step 2 — Workstream A: Separate text-valued property gold from enumerable gold

- **Locations**: `utils/evaluation/score_e2e.py`, `score_answer_coverage()` (line
  162), `_COVERAGE_ASSERTION_KEYS` (line 137), `_surfaced_ids()` (line 140). Read
  `ex_gold.kind` as carried by `utils/specialists/evalset/spec_bank.py:182` and
  set by `utils/specialists/evalset/composition.py:465-476`. New matcher in
  `utils/evaluation/` alongside the existing scorer.
- **Rationale**: `score_answer_coverage` already documents that it returns `None`
  for "negatives, boundary, **property-only**" entries. The expansion bank
  re-enabled it accidentally by placing a property's literal value into
  `must_include_related`, which is a coverage key, so a multi-paragraph
  description is compared against `_surfaced_ids()` — a set built from citation
  primary ids and an id regex over the narrative. A paragraph is never an id, so
  22 text-gold questions can never score above the anchor, for any arm, on any
  run. The generator already distinguishes the two cases (`gold_kind="text"` vs
  `"set"`, 22 and 41 respectively); the scorer must branch on it. Set-valued gold
  (`aliases`, `x_mitre_platforms`) keeps the existing exact-id path unchanged.
  Write the matching rule and threshold into the module docstring **before**
  computing any re-scored figure.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Measurement and Retrieval Repair (2/9)
  Complete: text-valued property gold is scored by containment in the composed
  answer rather than against the entity-id pool, with the rule pre-registered.*

---

#### Step 3 — Workstream B: Bind the CAPEC anchor label instead of hardcoding it

- **Locations**: `utils/specialists/gremlin/builder.py`, `_describe()` (line 425
  for the seeded path, line 442 for the name path, and the sibling anchors at
  462, 468, 502). Label resolution enters via `ResolvedTask`.
- **Rationale**: the seeded `describe` anchor is literally
  `g.V().hasLabel("AttackPattern").has("id", within(ids))`, so a question about
  View CAPEC-284 asks the graph for an AttackPattern with that id and correctly
  gets nothing. This is the single largest real defect in the run: **62 cases** —
  2 View property reads plus 60 of the 68 containment failures, which are the
  same bug and not a separate weak area. Of those 60, 45 returned nothing and 15
  returned the wrong entities. Take the label from the resolved task's anchor
  label, falling back to `AttackPattern` only when nothing is resolved, and cover
  View, Category and Matrix anchors with tests.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Measurement and Retrieval Repair (3/9)
  Complete: the Gremlin describe compiler binds the resolved anchor label, fixing
  62 View/Category cases that asked for an AttackPattern by a View's id.*

---

#### Step 4 — Workstream B: Stop the unconditional Group and Tactic branches capturing property reads

- **Locations**: `utils/specialists/cypher/builder.py`, the dispatch ladder —
  branch 3 `if has_group: return self._group_techniques(resolved)` (line 438),
  branch 4 `if has_tactic: return self._tactic_techniques(resolved)` (line 472),
  and the `describe` fallthrough at line 480. Templates `_group_techniques()`
  (550) and `_tactic_techniques()` (699).
- **Rationale**: "What does the threat group APT38 (G0082) describe?" emits
  `MATCH (g:Group)-[:USES]->(t:Technique)` and returns 22 techniques — a correct
  query to a question nobody asked. Technique, Campaign and Software reach
  `describe` and score normally; Group and Tactic do not, which is the whole
  content of the "Group/Tactic/View score exactly zero" observation. This is a
  known bug class in this file: the comment at line 425 records that a
  Group+Software task "was captured by the unconditional Group branch below and
  answered with the group's techniques", fixed narrowly for Software and not for
  property reads. Gate both branches on an actual technique-edge intent rather
  than on the anchor label alone, and assert in tests that the existing
  actor→technique routes are byte-identical.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Measurement and Retrieval Repair (4/9)
  Complete: Group and Tactic property reads reach describe instead of being
  captured by the unconditional neighbour-expansion branches.*

---

#### Step 5: Recorded-answer regression guard over both committed banks

- **Locations**: `utils/specialists/evalset/` golden catalogue (120 questions)
  and `docs/evaluation/composition/bank/bank.json` (572). Diff harness under
  `utils/evaluation/`; run via `uv run main.py --golden-eval --stage run`.
- **Rationale**: Steps 3 and 4 change query construction, which is exactly the
  change class that has silently moved the golden catalogue before. Re-run the
  deterministic arm over **both** banks and diff every recorded answer excluding
  clock keys. Any movement in the 120-question golden set must be explained
  before the re-run, not discovered inside it. This step is the gate: Step 7 does
  not start until the diff is clean or every difference is accounted for.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Measurement and Retrieval Repair (5/9)
  Complete: deterministic answers re-run over both banks and diffed; movement
  confined to the repaired shapes.*

---

#### Step 6 — Workstream C: Establish what an honest `llm_query` arm costs

- **Locations**: `scripts/builder_budget_probe.py`,
  `utils/specialists/experiment_untruncated.py` (never calls `load_env()`, so the
  arm ran on `DEFAULT_MAX_TOKENS` while `.env` declared 2,048 for a different
  endpoint entirely), and the relay identity probe `scripts/model_identity.py`.
- **Rationale**: two independent defects produce one blank. The arm ran at 4,096
  when a working query needed 8,269 completion tokens, and the `.env` value it
  was supposed to read was both ignored and smaller. 153 of 284 questions
  returned nothing and were recorded exactly like wrong answers, so 0.3712 is not
  a baseline. Make the arm read the environment, then probe a bounded sample —
  20 real failing cases at 8,192 / 16,384 / 32,768 — and record wall-clock,
  completion tokens and relay timeout rate per budget. **Also probe and record
  the builder model's identity**, which ISSUES I-2 flags as an inference rather
  than a record. The output of this step is a cost table, not a decision.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Measurement and Retrieval Repair (6/9)
  Complete: llm_query reads its configured budget, the builder model is
  identified, and a per-budget cost table exists for the run/cut decision.*

---

#### Step 7: One re-run of all three arms, 16-way concurrent

- **Locations**: `scripts/expansion_overnight.py` (phase list and
  `overnight-state.json` resume), `uv run main.py --golden-eval --agentic --llm`
  with `--concurrency 16`, judging via `--stage judge --llm --concurrency 16`.
  Bank: `bank-dev.json`, **284 questions, dev half only**.
- **Rationale**: every prior step changes something that the headline depends on,
  and running them separately would cost three overnight runs and make
  attribution impossible. One run, all three arms, grading order counterbalanced
  as before so the ~0.01 position effect stays subtractable. The `llm_query` arm
  runs at whichever budget the Step 6 decision selects, or is excluded outright
  and said to be excluded. **The holdout half is not touched.** Write
  EXP-2026-09-003's `PROTOCOL.md` *before* this step starts — an unrecorded
  changed headline is precisely the failure EXP-2026-09-002 was filed to correct.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Measurement and Retrieval Repair (7/9)
  Complete: all three arms re-run and double-graded over the dev half under one
  protocol; holdout untouched.*

---

#### Step 8: File EXP-2026-09-003 and amend the claims it moves

- **Locations**: `make new-experiment SLUG=post-repair-arm-comparison`, then
  `manifest.yaml`, `RESULTS.md`, `ISSUES.md`, `data/POINTERS.md` with a SHA-256
  per artifact. Ledgers: `docs/research/CLAIMS.md` (C-012, C-023),
  `docs/research/DECISIONS.md`, `docs/research/OPEN_QUESTIONS.md`.
- **Rationale**: the -0.1642 gap in EXP-2026-09-002 was measured with two live
  retrieval defects in the deterministic arm and a scorer that could not credit
  22 text-gold questions for anybody. Whether the gap survives, narrows or widens
  is the finding, and the exit criterion is that it is **re-measured**, not that
  it holds. Report the pre-repair and post-repair figures side by side
  permanently, and record in `ISSUES.md` that the scorer change raises absolute
  numbers for all three arms and therefore cannot be read as an improvement to
  any of them. Run `make validate-research` before committing.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Measurement and Retrieval Repair (8/9)
  Complete: EXP-2026-09-003 filed with pre- and post-repair figures side by side;
  C-012 and C-023 amended.*

---

#### Step 9: Close out, and confirm the holdout is still sealed

- **Locations**: `docs/research/INDEX.md`, `docs/changelog.jsonl`, and a hash
  check that `bank.json`'s holdout half is byte-identical to its preflight value.
- **Rationale**: the 288 held-back questions are worth something only while
  untouched, and this plan repaired the system they will eventually test. Prove
  by hash that nothing here consumed them, then hand off to Step 7 of the
  publication plan, which spends them once.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, commit stating: *Measurement and Retrieval Repair (9/9)
  Complete: record closed and the 288-question holdout verified sealed by hash.*

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Triage classifier fix | Read row counts from the level where they exist; restore the unreachable branches. | `scripts/anomaly_triage.py` |
| Triage regression test | A result carrying records is never classified as an empty query. | `scripts/tests/test_anomaly_triage.py` |
| Text-gold matcher | Normalised containment scorer for text-valued property gold, threshold pre-registered in the docstring. | `utils/evaluation/property_gold.py` |
| Scorer branch | `score_answer_coverage` dispatches on `ex_gold.kind`; set-valued gold unchanged. | `utils/evaluation/score_e2e.py` |
| Scorer tests | Small fixture set: one text gold, one set gold, one negative — asserts set-gold scoring is byte-identical to before. | `utils/evaluation/tests/test_property_gold.py` |
| Re-scored artifact | The 572 saved answers re-scored under the new rule, old and new columns side by side. | `docs/evaluation/composition/bank/score-rescored.json` |
| Gremlin anchor binding | `_describe` binds the resolved anchor label instead of hardcoding `AttackPattern`. | `utils/specialists/gremlin/builder.py` |
| Gremlin label tests | View, Category and Matrix anchors produce their own label; AttackPattern path unchanged. | `utils/specialists/tests/test_gremlin_specialist.py` |
| Cypher dispatch fix | Group and Tactic branches gated on technique-edge intent, not anchor label alone. | `utils/specialists/cypher/builder.py` |
| Cypher routing tests | Property reads on Group/Tactic reach `describe`; existing actor→technique routes byte-identical. | `utils/specialists/tests/test_cypher_builder.py` |
| Regression diff harness | Re-runs the deterministic arm over both banks and diffs recorded answers excluding clock keys. | `utils/evaluation/recorded_answer_diff.py` |
| Budget cost table | Wall-clock, completion tokens and timeout rate at 8k/16k/32k over 20 real failing cases, plus the builder model's probed identity. | `docs/evaluation/composition/bank/budget-cost.json` |
| Env-reading fix | The `llm_query` arm calls `load_env()` and honours the configured budget. | `utils/specialists/experiment_untruncated.py` |
| Re-run protocol | Written before the run, not after. | `docs/research/experiments/EXP-2026-09-003-post-repair-arm-comparison/PROTOCOL.md` |
| Experiment record | Manifest, results, issues, hashed pointers; pre- and post-repair figures side by side. | `docs/research/experiments/EXP-2026-09-003-post-repair-arm-comparison/` |
| Holdout seal check | Hash proof that the 288 held-back questions were not consumed. | `docs/research/experiments/EXP-2026-09-003-post-repair-arm-comparison/ISSUES.md` |
