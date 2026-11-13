# PROTOCOL — EXP-2026-11-003 Free query writing: model-written Cypher vs model-written Gremlin on the same graphs

Written 2026-11-13, before any code for this experiment ran. Kill test T1.

## Question

On property graphs the system has never seen, how often do off-the-shelf models write a query
that returns exactly the right records, in Cypher and in Gremlin, with no examples and with
three examples?

## Hypothesis

- **H1:** model-written Gremlin is materially worse than model-written Cypher. With 3 examples,
  Gremlin exact-records is at least 5 points below Cypher.
- **H2:** neither language reaches 80% exact-records with 3 examples.

## Setup

- **Graphs:** two CypherBench test graphs, loaded into a dedicated Neo4j (`killtests-neo4j`,
  bolt :5470). They are mirrored into a dedicated TinkerGraph Gremlin server
  (`killtests-gremlin`, :6470) by `utils/killtests/t1/mirror.py`. The shipped ATT&CK and
  CAPEC stores are untouched.
- **Mirror check:**
  - node, edge and per-label counts are equal;
  - 50 random nodes have equal properties;
  - 30 questions get hand-written Gremlin that returns the same records as the reference
    Cypher.
- **Arms:**
  - `cypher-0shot`;
  - `cypher-3shot`;
  - `gremlin-0shot`;
  - `gremlin-3shot`.
- **Prompt:** one schema block (labels, properties, relation patterns) rendered identically for
  both languages, then the question.
- **Examples:** the 3-shot examples are the same three training-split questions in both
  languages. Their Gremlin is hand-written and checked against the reference Cypher.
- **Models:** every healthy model on the `:9090` relay, with the served model read off each
  response. On 2026-11-13 this is `swift15-flashnext` only. A single-model result is reported
  as **provisional**, because the plan requires several sizes.
- **Decoding and execution:**
  - temperature 0, max tokens ≥ 4096;
  - the query is extracted from the first fenced block, else the whole reply;
  - each query is executed read-only with a 30 s timeout;
  - a parse error, a timeout or a write attempt counts as wrong.

## Data

About 200 test questions, 100 per graph. They are sampled with seed 20261113, stratified by
CypherBench's category field. The gold record sets come from executing CypherBench's
reference Cypher.

## Metrics

- **exact_records:** the returned rows, as a multiset of value tuples with columns compared
  order-insensitively by value, equal to the gold rows.
- Reported by arm × model × category, with a paired bootstrap 95% CI for Gremlin minus Cypher
  at each shot count.
- Also reported: the syntax-error rate and the timeout rate.

## Baselines

The two languages are each other's baseline: same questions, same schema text, same model,
same examples.

## Procedure

```bash
docker compose -f docker/killtests/compose.yml up -d
uv run python -m utils.killtests.t1.load      # CypherBench graphs -> killtests-neo4j
uv run python -m utils.killtests.t1.mirror    # killtests-neo4j -> killtests-gremlin, with parity checks
uv run python scripts/killtests_run.py --only t1
uv run python -m utils.killtests.analysis t1
```

## What would falsify this

**Kill rule,** for every model, on the 3-shot arms: the idea that typed requests have a gap to
win is dead if `exact_records(gremlin-3shot) ≥ exact_records(cypher-3shot) − 0.05` **and**
both are `≥ 0.80`. Free generation is then good enough in both languages.

## Pre-run amendments (2026-11-13, after the smoke run, before the full run)

1. **Graphs.** The test graphs are `flight_accident` and `nba`, the two smallest in CypherBench's
   test split (189 and 270 questions; both full graphs are under 7 MB). `terrorist_attack`, a
   training graph, is loaded beside them so that the 3-shot examples' Gremlin can be verified.
   The three graphs share no node label and no relationship type, so one Neo4j instance and one
   TinkerGraph hold all three.
2. **Gold.** The reference Cypher executed on `killtests-neo4j` matches CypherBench's own
   `answer_json` on 458 of 459 test questions. The one that disagrees (`c34ad241…`) is
   excluded before sampling.
3. **Mirror proof.**
   - Labels and relationship counts are equal in both stores.
   - 50 sampled nodes have equal properties.
   - All 3 shot examples and all 30 hand-written Gremlin translations (15 per graph, one per
     query shape) return the same normalised records as the reference Cypher. These are
     `utils/killtests/t1/{shots,handwritten}.py`, tested in `tests/test_t1.py`.
4. **Store facts in the prompt.** Each language's prompt states how its store represents
   `date` values (Neo4j dates; ISO strings in TinkerGraph) and `list[str]` properties (lists;
   multi-valued properties). The schema block is otherwise identical.
5. **Token budget 8,192.** One smoke generation hit the 4,096-token limit while still
   reasoning and returned no query.
6. **Normalisation.** Each row is the sorted tuple of its canonicalised values; a result is the
   multiset of its rows. Column order, column names and row order are ignored; duplicates
   count. CypherBench's `WITH DISTINCT n` semantics therefore apply: deduplicating names
   instead of nodes is a different result.
