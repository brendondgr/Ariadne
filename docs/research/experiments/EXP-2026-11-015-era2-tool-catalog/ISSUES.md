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
