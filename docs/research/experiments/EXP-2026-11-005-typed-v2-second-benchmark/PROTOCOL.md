# PROTOCOL — EXP-2026-11-005 Typed request format v2, and every arm on a second benchmark

Written 2026-11-14, before any part-A or part-B generation. Format v2 (commit 811a4366) was
fixed before any second-benchmark question was read. The second benchmark's selection is
mechanical (`utils/killtests/t2c/gold.py`).

## Questions

- **Part A:** does format v2 remove the "either/or" failures of EXP-2026-11-004 without
  costing accuracy elsewhere? Same 200 CypherBench questions, same models.
- **Part B:** on a benchmark whose question shapes the format was **not** designed from, do
  typed requests still beat free Gremlin, stay close to free Cypher, and score the same on
  both backends?

## Format v2 (`utils/killtests/typed/request.py`)

v2 is a superset of v1: every v1 request means the same in v2. It adds:
1. **Either/or:** `any_of` branches may name edges written in `edges` by their `var`; edge
   vars may repeat across branches. This is the form Gemma wrote in EXP-2026-11-004.
2. **Key property:** each label's key property comes from the card instead of a fixed
   `name`.
3. **Several properties:** `names_with` takes `props: [...]`.
4. **Text matching:** `starts_with`, `ends_with`, `contains_text`.
5. **Aggregates elsewhere:** `aggregate` over another node variable or an edge variable.
6. **Datetime properties** (compiled to `datetime()` in Cypher, ISO strings in Gremlin).

**Verification before the run:**
- the terrorist_attack training gold is unchanged (Cypher 1.000, Gremlin 0.9986 of 1,439);
- 4,000 random requests on the synthetic graph, now with a `title`-keyed label, text filters,
  edge aggregates and edge references: Cypher and Gremlin agree on 1.000.

## Part B data: Text2Cypher (2024v1), test split

- **Source:** Neo4j's dataset (Apache-2.0). Its questions come with free-form gold Cypher
  written for Neo4j's demo databases.
- **Graphs:** rebuilt locally from Neo4j's published dumps (`neo4j-graph-examples`), each in
  its own Neo4j and mirrored into its own TinkerGraph:

  | Graph | Nodes | Relationships |
  |---|---|---|
  | `movies` | 171 | 253 |
  | `northwind` | 1,035 | 3,139 |
  | `fincen` | 7,524 | 40,835 |

  Parity is exact: labels, relationship counts, and 50 sampled nodes per graph.
  `recommendations` is excluded because its nodes carry several labels, which a single-label
  mirror cannot represent. The other demo graphs have no published dump.
- **Selection** (mechanical): every test row for these graphs, deduplicated, whose gold Cypher
  runs, returns at least one row, returns only scalars, and does not use LIMIT without
  ORDER BY.
  - **Result:** 390 questions — movies 146, northwind 157, fincen 87.
  - **By source:** 375 are model-written (Neo4j's synthetic sets) and 15 are crowdsourced
    (human-written).
  - **Excluded:** 40 empty, 51 non-scalar, 47 LIMIT without ORDER BY, 16 duplicates, 2 gold
    errors.
- **Card:** labels, properties and relationship patterns are read from each graph. The key
  property comes from the schema alone: `name`, `title`, `<label>Name`, `companyName`,
  `<label>ID`, then any `...Name`, then any `...ID`. Point properties are dropped.
- **The shared schema block:** every arm sees the same card-rendered schema (key properties
  marked). The free arms add the same per-store note as in T1, and the 3-shot arms the same
  three terrorist_attack examples.

## Arms and models

- **Models:** the two healthy relay aliases, identified by tokenizer token ids at start:
  Gemma 4 31B and Qwen 3.8 27B. Temperature 0, max tokens 8192, 64 concurrent per model.
- **Part A arms:**
  - `typed2-0shot`, `typed2-3shot` and `typed2-3shot-repair`;
  - the free arms and the v1 typed arms are read from EXP-2026-11-003 and EXP-2026-11-004.
- **Part B arms:**
  - `cypher-0shot`, `cypher-3shot`, `gremlin-0shot`, `gremlin-3shot`;
  - `typed2-0shot`, `typed2-3shot`, `typed2-3shot-repair`.
- **`typed2-3shot-repair` (secondary):** an unparseable or invalid `typed2-3shot` reply gets one
  more turn showing the validator's message. Valid replies carry over unchanged. The free arms
  get no repair turn, so this arm is **not** in any kill rule.
- **No change to the format or compilers** after this protocol is committed (tag
  `killtests-exp005-run`).

## Hypotheses and kill rule

**Part A** (expectations, not a kill test):
- **A1:** for each model, `typed2-3shot` ≥ `typed-3shot` (v1) − 0.02.
- **A2:** Gemma's union-category accuracy rises from 0.43.

**Part B** (the kill test), for each model, at 3-shot:
- **H1 (backend independence):** typed2 via Cypher and via Gremlin differ by ≤ 0.02.
- **H2:** typed2 via Gremlin ≥ free Gremlin + 0.10.
- **H3:** typed2 via Cypher ≥ free Cypher − 0.05.

**Kill:** H2 fails for any model, **or** H3 fails for every model. H1 failing is a compiler
defect, recorded in ISSUES.md.

The primary metric is `B_typed2_3shot_gremlin_minus_free_gremlin_3shot`, per model, with a
paired bootstrap 95% CI.

## Secondary, exploratory

- Results by graph and by source; the crowdsourced subset (n = 15) is descriptive only.
- **Repair-arm gains.**
- **A post-hoc taxonomy of typed misses where free Cypher was right.** Each is classified by
  features of the gold Cypher (e.g. variable-length paths, list functions, arithmetic in
  RETURN, several aggregates, WITH chains). This separates "the format cannot say it" from "the
  model filled it in wrong". It is labelled exploratory.

## Known limits, stated before the run

- The Text2Cypher gold is itself mostly model-written. Gold errors hit every arm equally.
- Some questions exceed the 8,192-token budget for some arms (seen in the smoke run). The budget
  is the same as T1's, for every arm.
- The format is expected to lack some shapes this benchmark uses. That is what part B measures.

## Procedure

```bash
uv run python -m utils.killtests.t2c.load                       # mirrors + cards (done)
uv run --with pyarrow python -m utils.killtests.t2c.gold        # selection (done)
KILLTESTS_CONCURRENCY=64 uv run --with pyarrow python -m utils.killtests.t2c.run A B
```
