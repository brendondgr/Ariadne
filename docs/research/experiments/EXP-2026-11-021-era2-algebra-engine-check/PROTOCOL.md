# PROTOCOL — EXP-2026-11-021 Era 2 Step 9 Phases E–F: do the two compilers mean the same thing, and is nothing changed?

Written 2026-11-20, after Phase D was committed (cfe3e8dd) and before any compiled query of the
algebra had run on a server. Model-free.

## Question

Two questions:
- Do the Cypher and Gremlin compilers of the operator algebra return the same answer for every
  operator, and the answer `docs/era-2-expansion/operator-algebra.md` defines?
- Did moving today's typed-step compilation (Phase D) change any answer?

## Hypotheses (predictions)

- **H1 — semantics:** every rule test of the semantics document passes on both backends. These
  are the tests named in its § 8, plus the amendments' tests. They run on a fixture graph whose
  answers are worked out by hand from the document.
- **H2 — differential:** zero Cypher/Gremlin disagreements beyond a relative tolerance of 1e-9 on
  float sums and averages. It runs on ATT&CK and CAPEC, each loaded into both engines.
  - **Predicted:** the first run finds defects in the Gremlin constructs that have never run on a
    server (`barrier()`/`dedup` inside `repeat`, `path().from()` inside `by()`, string
    `min`/`max`). It ends at zero after fixes.
  - The bar applies to the final run, and every defect fixed on the way is listed.
- **H3 — today's operations:** on the shapes today's builders answer (`expand`, `count`, `scan`,
  `common`), the new compilers return the same node ids as the builder's own query. Each is run
  on the same store.
- **H4 — regression (Phase F):**
  - the typed plan replay through the full pipeline returns identical entity ids, tree to tree,
    on a HEAD worktree;
  - the R arm's reference capture is byte-identical;
  - the deterministic recorded answers are identical except clock keys.

## Setup

**The verification pair:**
- `docker/algebra-verify/compose.yml`: Neo4j 5.26 on bolt 5480, TinkerPop gremlin-server 3.8.0
  on 6480.
- `scripts/algebra_verify_stores.py load` puts ATT&CK and CAPEC into both engines. It reuses the
  loader's stores and records, but skips the preflight and never writes a runtime manifest.
- **Loaded 2026-11-20:** 10,743 nodes and 36,251 edges in each engine, equal to the build
  manifests (ATT&CK 4,369 + CAPEC 6,374 nodes).

**Card names and spellings:** the relationships are the card's names. Neo4j uses them as written;
Gremlin uses the loader's uppercase form (`gremlin_edge_label`).

**The fixture graph:**
- written from the semantics document alone, by a writer who has not read the compilers;
- under its own labels (`Fx*`), loaded into both engines of the same pair;
- holds every hard case: ties at the cut, empty groups, missing and failing properties, two
  paths to one node, equal-length shortest paths, a cycle, dated nodes and edges, non-ISO
  dates, `number_text`, a node with extra Neo4j labels.

**The generator** (`utils/specialists/algebra/differential.py`), seeded:
- every operator instance the card allows (each label × relationship × direction ×
  operator), with filter and aggregate parameters drawn from the property values actually
  stored;
- plus 3,000 random compositions.

## Metrics

- **Rule tests:** passed per backend.
- **Disagreements:** the count of instances whose finished results differ. Node sets are
  compared by stored id; values exactly, except float sums and averages within relative 1e-9.
- **Coverage:** the share of (operator, label) cells exercised.
- **H3 agreement:** the share of distinct recorded `expand`/`count`/`scan`/`common` steps whose
  id sets are equal. The builder's public ids are mapped to stored ids through the store.

## Checks (Step 9 plan, Phases E and F)

| Check | Bar | On fail |
|---|---|---|
| Semantic tests, both backends | all pass | fix the compiler, never the rule |
| Rule-to-test table: every named test exists | all | write the missing test |
| Cypher/Gremlin disagreements | 0 beyond relative 1e-9 | each is a defect to fix; the tolerance is never widened |
| Coverage | 100% of applicable (operator, label) cells | extend the generator |
| New compilers equal today's answers on today's shapes | 100% | fix, or record a difference the semantics document already states and ask the operator |
| Live stores untouched | runtime manifests unchanged: attack/neo4j `f8f4b8dc…`, capec/gremlin `02124042…` | stop; reload and investigate |
| H4 replay, R capture, deterministic answers | identical | fix before Phase G |

## Procedure

```bash
docker compose -f docker/algebra-verify/compose.yml --env-file .env up -d
uv run python scripts/algebra_verify_stores.py load
uv run python -m pytest -q utils/specialists/algebra/tests/test_semantics.py utils/specialists/algebra/tests/test_differential.py
uv run python -m utils.specialists.algebra.differential --seed 20261120 --random 3000 --out <run dir>
# Phase F: the replay and regressions (commands in RESULTS)
```

## What would falsify this

- **H2 falls** if any disagreement remains that cannot be fixed without changing a rule. The rule
  is then not implementable alike on both engines, and that goes to the operator.
- **H3 falls** if today's answers differ from the algebra's on a shape it claims to keep. The
  algebra is then not "today's operations, unchanged in meaning".
