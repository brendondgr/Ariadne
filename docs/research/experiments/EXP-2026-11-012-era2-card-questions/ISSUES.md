# ISSUES — EXP-2026-11-012

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

<!-- Entry template — newest first:

## YYYY-MM-DD — <one-line summary>
**Impact:** what this changes about the reported numbers (e.g. "seed 3 excluded; n=4 not 5 for this cell").
**Cause:** the mechanism, if known.
**Resolution:** what was done. "Not resolved" is a valid answer.
**Paper implication:** what must be stated in the paper because of this.

-->

## 2026-11-16 — Sonnet round 1 superseded: schema labels copied verbatim
**Impact:** none on the recorded banks. Round 1 (805 of 805 passed the checks on the first try) is kept in `data/sonnet/v1/` and not used.
- 98% of its non-schema questions named the asked-for kind by its exact label ("Which TaxonomyEntry entries does CAPEC-440 map to?").
- Round 2 has 0 such questions. Qwen's run has 237 of 805.

**Cause:** the shared rule said "name the asked-for kind directly", and the direction sentence says "the {target} entries". Sonnet read both literally; Qwen did so less often. The checks did not define the case.

**Resolution:** PROTOCOL amendment 6.
- Plain-wording rule in every tier.
- `schema_label_copied` is a checked problem.
- The joined-label stem is added to the schema-tier leak list.
- Fixture tests cover all three.

All 805 jobs were rewritten in round 2.

**Paper implication:** a question generator's leak checks need a style check too. Label-literal phrasing is easier for any agent, not only the writer's own model.

## 2026-11-16 — The plain-wording rule clashed with the synonym tier's forbidden words in 10 jobs
**Impact:** 10 of round 2's synonym-tier questions failed their first check, then passed on the one retry. No question was dropped.
**Cause:** amendment 6 told the writer it "may name the asked-for kind as 'detection strategy'". For 10 jobs, that kind's name shares a word with the relation's forbidden list ("detection", "techniques", "execution steps", "alternate terms", "references").
**Resolution:** the retry named the clash. The rule now says to describe the kind in other words when its name uses a forbidden word. This change came after the run, so the job files record what the writers actually saw. A fixture test covers it.
**Paper implication:** none.

## 2026-11-16 — An earlier test leaks Neo4j credentials into the live exact tests
**Impact:** none on the recorded numbers. Run in one batch with `utils/specialists/evalset`, the kill-test live tests in `utils/agent/tests/test_exact_live.py` skip with "Unauthorized". Run alone, all 21 pass.
**Cause:** an earlier test in the batch changes the Neo4j credentials in the process environment. This predates Step 6 and was not traced further.
**Resolution:** not resolved. Run the live suites on their own, as `scripts/era2_exact_check.py` already does.
**Paper implication:** none.

## 2026-11-16 — The writer is not seeded: reruns differ slightly
**Impact:** from run to run, survivor counts move by one or two questions at the same anchors. For example, CAPEC's synonym tier kept 37, 35 and 36 in runs 2, 3 and 4.
**Cause:** the question writer samples at temperature 0.7 through the relay, which takes no seed. The anchors, the gold and the splits are seeded (20261116) and do not move.
**Resolution:** the fourth run is the record. Its questions and hashes are fixed by POINTERS.
**Paper implication:** report yields as one run's yields, not as a property of the method.

## 2026-11-16 — The run's tree was dirty relative to the pre-registration commit
**Impact:** none. The manifest's commit is f7daaf85, the pre-registration. The recorded run used that tree plus exactly the changes that the Step 6 commit adds:
- the edge-label map;
- the absent-slot guard;
- the ambiguity budget;
- the id-format rule;
- their tests.
**Resolution:** recorded here, with `dirty: true` in the manifest.
**Paper implication:** none.

## 2026-11-16 — Run 3 superseded: id-format hints leaked into the schema tier
**Impact:** run 3 had 837 questions; 14 of its 75 ATT&CK schema-tier questions copied id-format hints from the label's description ("T-ID.NNN", "DET-IDs", "v19"). These name the target label by its id scheme. The blind proxy reader rejected one of them as garbled; the leak audit had not defined the case.
**Cause:** the schema-tier prompt quotes the label's description, and that description carries its id format.
**Resolution:** PROTOCOL amendment 3. `format_hints` is now forbidden in the prompt, leak-checked with one retry, and part of G3's audit. Run 4 keeps 75 of 75 ATT&CK schema questions, with 0 hints.
**Paper implication:** a leak check that only forbids the label's own words is not enough, because a description can name the label in other ways.

## 2026-11-16 — Two recorded runs voided: a card/store relation-name mismatch, and the ambiguity budget
**Impact:**
- **Run 1 (void):** 703 questions.
  - Every CAPEC AttackPattern-to-AttackPattern question (9) was labelled "insufficient" with empty gold, when the sets were not empty.
  - G1 passed anyway, because both fetch paths used the same wrong relation name.
  - CAPEC got 0 ambiguous questions, ATT&CK 8.
- **Run 2 (superseded):** 476 ATT&CK and 349 CAPEC questions, with 8 and 1 ambiguous.
**Cause:**
- **The name mismatch.** The CAPEC card names five relations in CamelCase (`ChildOf`). Ariadne's loader stores `CHILD_OF`. Step 5's `GremlinBackend` queried the card name, so the sets were silently empty.
  - Step 5's own results are unaffected: they ran on the kill-test stores, which keep source names.
- **The ambiguity budget.** It was split in fixed halves, with one relation-ambiguity question per label pair. ATT&CK's card has no eligible pair, and CAPEC has one.
**Resolution:** see PROTOCOL amendments 1 and 2.
- `GremlinBackend(edge_label=...)` now maps card names to stored labels.
- A guard reports any card slot with no edge anywhere in the store; after the fix there are none.
- A live CAPEC test pins the mapping.
- The ambiguity budget is rebalanced, with fixture tests.
**Paper implication:** a gold answer that "re-executes identically" does not protect against a vocabulary mismatch shared by both paths. Era 2's agent must use the same edge-label map, or it will report CAPEC hierarchy questions as having no answer.
