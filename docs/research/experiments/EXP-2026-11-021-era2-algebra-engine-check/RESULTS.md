# RESULTS — EXP-2026-11-021 Era 2 Step 9 Phases E–F: do the two compilers mean the same thing, and is nothing changed?

## 1. Headline

**The engine gate is met.** On ATT&CK and CAPEC loaded into both engines, Cypher and Gremlin agree
on all 9,391 operator instances (0 disagreements), covering 424 of 424 applicable (operator, label)
cells. Every semantic rule test passes on both engines (46 each). The new compilers return today's
answers on 853 of 864 recorded steps; the other 11 are differences the operator ruled on.

Moving today's typed-step compilation changed nothing, tree to tree:
- **Phase D:** 1,121 distinct recorded steps compile to byte-identical query text.
- **Phase F:**
  - R reference: 120 of 120 byte-identical;
  - deterministic answers: 344 of 344 byte-identical;
  - typed replay: 2,049 of 2,049 answers with the same entity ids.

It took eight compiler defects and four rulings by the operator (amendment 4) to get there.
H1, H2 (final run), H3 (with the rulings) and H4 hold.

## 2. Results table

From `data/metrics.json` and the run outputs in `data/POINTERS.md`. One system run per check
(`n_runs: 1`). The checks are deterministic, so no intervals are given.

**Checks (protocol)**

| Check | Bar | Result | Pass |
|---|---|---|---|
| Semantic tests, both backends | all pass | 46/46 Cypher, 46/46 Gremlin | yes |
| Rule-to-test table: every named test exists | all | yes (12 rules; parsed by a test) | yes |
| Cypher/Gremlin disagreements | 0 beyond relative 1e-9 | 0 of 9,391 | yes |
| Coverage | 100% of applicable cells | 424/424, including 13 edge-property cells | yes |
| New compilers equal today's answers | 100% | 853/864 equal, 11 documented (§ 4), 0 unexplained | yes, with the operator's rulings |
| Live stores untouched by Phases E–F | manifests unchanged | the verification runs never touched them; they were reloaded on purpose for the store fix (§ 4) | yes |
| H4: replay, R capture, deterministic answers (Phase F) | identical | all identical, bytes included (R, deterministic) | yes |

**The differential, run by run**

| Run | Instances | Disagreements | Errors | Coverage |
|---|---|---|---|---|
| Part 1, first | 8,583 | 482 | 57 | 410/411 |
| Part 1, final | 8,611 | 479 (433 list encoding, 46 edge reuse) | 0 | 411/411 |
| After amendment 4, first | 9,226 | 14 | 1 | 424/424 |
| **After amendment 4, final** | **9,391** | **0** | **0** | **424/424** |

## 3. Figures

None.

## 4. Interpretation

**What the differential found** (each fixed in the compiler, never in a rule):
1. **Repeated-hop `expand`** returned route nodes unfiltered.
2. **`describe`** leaked the loader's `properties_json`.
3. **`having`** on a text value crashed `finish`. It is now refused.
4. **`common`** anchors lost all but one label.
5. **Gremlin:** a walk's start label was invisible inside child traversals.
6. **Gremlin:** `simplePath` made a reach time out. Fixed-hop walks now use an explicit pairwise
   check.
7. **The card typed `external_references` as a list.** It is a list of objects (§ 6).
8. **Gremlin `shortest`** timed out. It now bounds the forward search with a backward one: from
   49 s to 3 s, and all 24 shortest-path instances agree.

**Four rulings by the operator (2026-11-20, amendment 4).** The first two removed the 479
part-1 disagreements, which no compiler fix could:
- **Lists:** the stores were fixed rather than the rules.
  - String lists are list values in both engines;
  - empty lists are not stored;
  - lists of objects are JSON text in both.
  - Relationship properties, including the "how" `description`, are now written in both
    loaders.
- **Walks never visit a node twice:** stricter than either engine's default; both enforce it.
- **Anchors must be of their stated label:** 8 of today's steps differ, because placeholder
  seeds of another label stand in for run-time anchors.
- **A filter on a property the store does not hold matches nothing:** today's builder drops it
  silently (1 step). Fixed in Phase G.

The other 2 documented differences are card-invalid steps the builder ran (S3; known from Phase C).

**The store fix's own regression** (`store-fix/README.md`). It compares today's answers before and
after the storage change, on reloaded stores.
- **Entity ids identical:**
  - R reference 120/120;
  - dev 284/284;
  - bank-2026-08-20 30/30;
  - all 2,049 replayed typed answers.
- **Two id changes,** both in bank-2026-08-19. They are capped answers that show a different
  correct subset of the same set (8 of 29, and 4 of 12, CWE patterns), because the wipe and reload
  changed insertion order.
- **Byte changes** are CAPEC answers printing lists as lists.

**What this means for Step 9.** The engine is ready for Phase G. The operators mean one thing on
both engines, the document says what that is, and the shipped answers are unchanged. No claim
moves; this is engineering.

## 5. Threats to validity

- **The differential compares the engines with each other.** Agreement shows that both
  compilers implement the same reading, not that the reading is right. The semantic tests carry
  correctness: 46 hand-computed answers per engine, from a writer who had not read the
  compilers. A wrong rule in the document would pass both.
- **The data limits what real data can test:**
  - ATT&CK and CAPEC have no numeric properties, so S11's float tolerance was exercised on the
    fixture only;
  - before the store fix, edge filters were fixture-only too;
  - edge-property cells now come from properties the card does not declare, added to the
    differential's own card copy.
- **H3's anchor differences come from placeholder seeds.** The snapshot gives anchor-less steps
  a fixed seed (T1047, a Technique), so the "wrong label" cases are partly the harness's. The
  rule they test, typed anchors, is the operator's, and real mixed-label seeds will hit it.
- **The capped-answer subset depends on store insertion order** (§ 4). That predates this work, but
  any comparison across a reload must compare full sets, not capped samples.
- **The part-1 runs were on the old storage rule.** Their counts are kept for the record and are
  superseded by the after-amendment-4 runs.

## 6. What surprised us

- **The engines stored the same data differently,** and nothing had noticed:
  - Gremlin held every list as JSON text, `"[]"` included;
  - Neo4j dropped empty lists and lists of objects;
  - both dropped every relationship property.

  Each builder had worked around its own engine's encoding (the Gremlin builder refuses list
  filters). Only a differential over the same data in both engines could show it.
- **The card's typing was wrong for `external_references`.** "array" in the card, but an array of
  objects. Fixed in `utils/agent/catalog.py`: an array whose example holds non-strings is typed
  `string`. **This changes the planner's catalog** for that property in every consumer, and its
  effect is measured in Phase H's off arms.
- **The protocol's predicted Gremlin defects** (`barrier`/`dedup` in `repeat`, `path().from()`,
  string `min`/`max`) did not appear. The real ones were label scoping and path tracking.

## 7. Follow-ups

- **Phase G:**
  - expose the operators behind the two switches;
  - map public ids to stored ids for the new compilers;
  - fix the builder's silently dropped filter;
  - re-label Step 6's out-of-coverage items that become answerable.
- **The off-arm reference for Phase G's "switches off" check** is the commit that ends Phase F,
  not an earlier HEAD, since the catalog typing fix belongs to it.

## 8. Reproduction

```bash
docker compose -f docker/algebra-verify/compose.yml --env-file .env up -d
uv run python scripts/algebra_verify_stores.py load
uv run python -m pytest -q utils/specialists/algebra/tests            # semantics + small differential (live)
uv run python -m utils.specialists.algebra.differential --seed 20261120 --random 3000 --out <dir>
uv run python scripts/algebra_h3_check.py ...                          # see its --help
uv run python scripts/algebra_typed_snapshot.py compare docs/evaluation/algebra-2026-11/typed-query-snapshot.jsonl
# store fix and Phase F: docs/evaluation/algebra-2026-11/store-fix/ and phase-f/ (scripts and diffs)
```
