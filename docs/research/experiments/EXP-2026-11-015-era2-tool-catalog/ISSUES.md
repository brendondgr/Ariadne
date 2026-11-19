# ISSUES — EXP-2026-11-015

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

## 2026-11-18 — G3's bar of 0.98 was out of reach for any language-model planner
**Impact:** G3 fails at 0.5167, but the English control scores only 0.6667 on the same 120
questions.
- **What the reference is.** It is the rules pipeline's own capture, so a 1.0 on T0 holds by
  construction only for the rules pipeline.
- **What G3 measured.** For a model planner, T0 measures how closely it reproduces the rules
  plan.
- **The relative reading still fails.** T-lazy minus E is −0.15, interval [−0.25, −0.06].

**Cause:** the protocol carried over "T0 = 1.0000 by construction" from the rules-only harness.
It named the threat, but it did not set the bar relative to the control.
**Resolution:** the verdict stands as pre-registered. RESULTS §7 proposes re-gating against E
or judged gold in a new protocol.
**Paper implication:** a T0 figure from the variant harness for a model-planned arm must be
reported beside E's, never against 1.0.

## 2026-11-18 — The anchorless scan: the typed path's main confidently-wrong defect
**Impact:** 11 of T-lazy's 12 dev confidently-wrong answers, and 16 of its 61 on variants
T0–T5, are a `scan` step with no anchor ids. Each returns a whole label. G4 was judged on the
counts as they are.
**Cause:** an anchor that does not resolve. There are two cases:
- the id does not exist (the NEG/EXC questions);
- the id belongs to another graph (an ATT&CK id asked of CAPEC, stored there as a
  `TaxonomyEntry` id).

There are two routes to the scan:
- **The repair turn (9 of 18).** The anchor refusal's `fix` names "scan" as an alternative
  (`utils/planner/typed.py:483`).
- **The first emission (9 of 18).** The typed plan had no "not found" outcome.

**Resolution:** not fixed in this experiment. RESULTS §7 lists the changes for the plan
revision.
**Paper implication:** a teaching error message is part of the planner's prompt. Its
suggestions must be checked as carefully as the prompt.

## 2026-11-18 — R re-anchors the synonym tier at 0.3917; CLAIMS C-014 still quotes 0.4667
**Impact:**
- **Today's figure matches September.** Today's rules-only T1 is 0.3917, identical to the
  2026-09-15 baseline capture, and both reference captures are identical on 120 of 120
  questions.
- **0.4667 is older.** It is EXP-2026-08-020's August figure. The change happened between
  August and mid-September, not in this step.
- **C-014's row still quotes 1.0000 → 0.4667 → …** from August.

**Resolution:** C-014 is not edited here; its evidence cites EXP-2026-08-020 by date. Whether to
add today's figure to C-014 is the operator's call.
**Paper implication:** quote the synonym tier as 0.3917 on the current tree, with 0.4667 as
the August figure.

## 2026-11-18 — Run outputs moved out of the experiment folder; scorer changes after the run
**Impact:** none on any figure.
- **The move.** Phase 2 wrote about 70 MB under `data/`, which was moved to
  `docs/evaluation/experiments/tool-catalog-2026-11-18/` (POINTERS).
- **`--runs`.** `scripts/era2_catalog_score.py` gained `--runs`, so it can read from the new
  location.
- **The G4 cell.** The variants row of G4 in the scoreboard had printed no pass value. Each
  part now shows its own, and the both-parts row is added.
- **The diagnosis.** A reported-only section was added. It covers outcome classes,
  anchor-insensitive records_exact, and confidently-wrong answers by cause.

All of these were added after the results were seen. None of them changes a gate's inputs or
rule, and the gate figures are byte-for-byte the same before and after.
**Paper implication:** the diagnosis figures are post hoc and must be labelled so.

## 2026-11-18 — The text boundary moves the English reads; it does not yet replace the words with meaning
**Impact:** E1 passes (120 of 120 identical with nonsense text), but on the rules path the
specialists still read word lists taken from the question.
- **What the lists are.** `TaskSignals` carries `name_candidates`, `name_tokens`,
  `question_words` and `mentioned_values`.
- **When they are made.** They are computed once, when the task is made.
- **What the builders read.** Only those lists, never `task.text`. But they are extracted
  strings, not typed meaning.

The typed arms replace them with typed steps (anchor ids, relation, direction, target).

**Reads left in place, outside the boundary:**
- `utils/specialists/llm_builder.py:208` reads the question. It runs only when
  `SPECIALIST_LLM_QUERY_BUILDER=true`, never in this experiment's arms.
- `utils/specialists/federation.py:122,432` reads the planner sub-question during routing.
- `utils/synthesis/composer.py:143,271` reads it for the answer's wording.

**Resolution:** reported as built. The protocol's item 5 names only the builders and the
resolver.
**Paper implication:** describe the boundary as "the question is read once, upstream". The
claim "the specialists take typed meaning" holds only on the typed path.

## 2026-11-18 — Six benchmark cards were not generated, because their stores are not loaded
**Impact:** E2 covers 13 cards: ATT&CK, CAPEC and the 11 CypherBench schemas. Six were
skipped, because their cards are built by introspecting a live store and those stores were
unreachable:
- the Text2Cypher graphs movies, northwind and fincen (bolt 5501–5503);
- the Mind the Query graphs wwc, healthcare and er (5511–5513).

A supplementary test generates catalogs from the six cards saved by the kill tests
(`logs/killtests-2026-11/*/cards-v3/`). Those are not counted as loaded.
**Resolution:** as the protocol allows, the skips are recorded with their reason.
**Paper implication:** none.

## 2026-11-18 — `jsonschema` is not a project dependency
**Impact:** none on E2's result. The Draft 2020-12 meta-schema check imports `jsonschema`
when it is installed. Otherwise it runs the same check through
`uv run --offline --no-project --with jsonschema`, from uv's cache. 364 parameter schemas,
0 failures.
**Resolution:** not added to the lockfile in this step.
**Paper implication:** none.

## 2026-11-18 — E2's no-graph-names check first found three mentions written before Step 8
**Impact:** none. Three files predating Step 8 named things that the new check catches:
- `utils/agent/exact.py` had two docstring examples, `ChildOf` and `playsFor`;
- `utils/agent/view.py` had one message word, "leads", which is a relation name in a
  CypherBench card.

The build agent first pinned these as allowed. They were reworded the same day, and the pin
was removed, so E2 now passes with no exceptions.
**Paper implication:** none.

## 2026-11-18 — The graph stores were stale on entry and were reloaded
**Impact:** none on any figure.
- **What was wrong.** Neo4j reported a canonical-hash mismatch, and Gremlin was empty after a
  restart.
- **What was done.** Both were reloaded (`main.py --dataset attack --graph neo4j`,
  `--dataset capec --graph gremlin`), and both verify passes came back clean before any
  check ran.

**Paper implication:** none.
