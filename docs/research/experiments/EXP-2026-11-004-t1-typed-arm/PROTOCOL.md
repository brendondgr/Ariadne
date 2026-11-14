# PROTOCOL — EXP-2026-11-004 Typed requests compiled to Cypher and Gremlin (the T1 typed arm)

Written 2026-11-14, after the compilers were verified on training data and before any typed
request was generated or executed for a test question.

## Question

On the same 200 unseen-graph questions as EXP-2026-11-003, with the same models, does a model
that fills in a **typed request**, compiled by code into Cypher and into Gremlin, return the
exact records more often than the same model writing Gremlin itself? Is it as good as the model
writing Cypher itself? And is its accuracy the same on both backends?

## Hypotheses

For each model, with 3 examples:

- **H1 (backend independence):** typed-via-Cypher and typed-via-Gremlin exact-records differ by
  at most 0.02.
- **H2 (beats free Gremlin):** typed-via-Gremlin exact-records is at least 0.10 above free
  Gremlin.
- **H3 (not worse than free Cypher):** typed-via-Cypher exact-records is no more than 0.05 below
  free Cypher.

## What would falsify this

**Kill rule.** The typed arm is killed if **either**:
- H2 fails for any model: typed requests do not clearly beat free Gremlin; **or**
- H3 fails for every model: typed requests are clearly worse than free Cypher on all models,
  so the form costs more than it saves.

**H1 is not part of the kill rule.** If H1 fails, it is a compiler defect to be recorded in
ISSUES.md, not evidence about typed requests.

The primary metric is `typed_3shot_gremlin_minus_free_gremlin_3shot`, per model, with a paired
bootstrap 95% CI.

## Setup

- **Questions and gold:** the recorded `t1/gold` stage of EXP-2026-11-003: 200 CypherBench test
  questions, 100 each from `flight_accident` and `nba`, seed 20261113. These are the same
  questions, gold records, stores (`killtests-neo4j` :5470, `killtests-gremlin` :6470) and
  normaliser as the free arms.
- **Models:** the relay's two healthy aliases on 2026-11-14:
  - `default-model`, which serves Gemma 4 31B;
  - `default-model-2`, which serves Qwen 3.8 27B.

  Each is identified at start by tokenizer from returned token ids, as in EXP-2026-11-003.
  `swift15-flashnext` is no longer served, so it gets no typed arm.
- **Free-arm comparison:** each model's own free-arm run in EXP-2026-11-003, made on
  2026-11-13 with the same weights. The typed arm is paired with it question by question.
- **Arms:**
  - `typed-0shot` and `typed-3shot`;
  - each is scored on both backends (`-cypher` and `-gremlin`), giving four scores per model.
- **Prompt** (`utils/killtests/typed/prompts.py`):
  - the request-format description;
  - the same schema block as the free arms;
  - for 3-shot, the same three terrorist_attack examples as the free arms, written as typed
    requests (converted from their gold Cypher);
  - then the question.
- **Decoding:** temperature 0, max tokens 8192, 64 concurrent requests per model.
- **Parsing:** the first fenced block is taken, else the outermost `{...}`.
  - An unparseable reply or an invalid request (one that fails `validate` against the graph's
    card) is wrong on both backends.
  - **There is no repair turn**, because the free arms had none.
- **Execution:** compiled queries run read-only, with a 30 s timeout, against the same gold rows
  and the same normaliser as the free arms.

## The request format and its compilers

`utils/killtests/typed/` (request.py, cypher.py, gremlin.py).
- The format was designed from CypherBench's **training** split: its 25 MATCH shapes and 16
  RETURN shapes, all on graphs that are not test graphs. The test questions were not read.
- Every label, relationship and property must come from the graph's card. Relationships must
  run in the card's direction.

### Semantic decisions fixed before the run

1. **Sorting follows Cypher.** A missing value sorts last ascending and first descending,
   because CypherBench's gold answers were produced by Neo4j that way.
2. **Relationship uniqueness.** Two relationships of the same type in one pattern must be
   different relationships, as in one Cypher `MATCH`.
3. **Gremlin compiles patterns to a path walk, not `match()`.** In TinkerPop 3.8.0, `match()`
   returned nothing, or raised `ClassCastException`, on some cyclic patterns.

### Verification before the run (`utils/killtests/typed/verify.py`)

| Check | Cypher | Gremlin |
|---|---|---|
| Gold: 1,442 terrorist_attack training questions, against CypherBench's `answer_json`, where the gold Cypher itself reproduces (1,439) | 1.000 | 0.9986 |
| Differential: 3,000 random requests on a synthetic graph (missing values, lists, dates, cycles, time filters, duplicate names) | Cypher and Gremlin agree on 0.9997 | |

- The two remaining gold misses and the one remaining differential disagreement are ties in
  "top 1".
- The other three training graphs (art, biology, soccer) are 0.4–2.4 GB and were not loaded.
  The synthetic differential covers the shapes terrorist_attack lacks.

## Secondary measures

- The invalid-request rate and the unparseable rate per arm.
- Exact-records by CypherBench category.
- **Ceiling, computed only after the run:** the share of test questions whose gold Cypher
  converts to a typed request that reproduces the gold on both backends. **No compiler or
  format change is allowed after the run starts.** The ceiling is reported as-is.

## Procedure

```bash
uv run python -m utils.killtests.typed.verify --mode gold    # needs the verification stores on :5480/:6480
uv run python -m utils.killtests.typed.verify --mode diff --n 3000
KILLTESTS_CONCURRENCY=64 uv run python -m utils.killtests.typed.run default-model default-model-2
```

The code is frozen at tag `killtests-typed-run`.
