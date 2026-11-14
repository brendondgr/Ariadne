# RESULTS — EXP-2026-11-003 Model-written Cypher vs model-written Gremlin (kill test T1)

## 1. Headline

**Survives, provisionally (one model).** With 3 examples, `swift15-flashnext` writes Cypher that
returns exactly the right records on **0.900** of 200 CypherBench questions, but Gremlin only
**0.605**. The gap is −0.295 (paired 95% CI −0.36 to −0.23). Without examples it is 0.810
against 0.500 (−0.31, CI −0.38 to −0.24).

The kill rule needs both languages ≥ 0.80 and within 5 points, so it does not fire: Cypher
clears 0.80 and Gremlin does not.

## 2. Results table

From `data/score.json`. There are 200 questions (100 `flight_accident`, 100 `nba`), stratified
by CypherBench category. 800 generations, all served by `swift15-flashnext`. One run.

| Arm | exact_records | flight_accident | nba | ran | runtime error | empty reply |
|---|---|---|---|---|---|---|
| cypher-0shot | 0.810 | 0.79 | 0.83 | 197 | 3 | 0 |
| cypher-3shot | **0.900** | 0.97 | 0.83 | 199 | 1 | 0 |
| gremlin-0shot | 0.500 | 0.46 | 0.54 | 158 | 21 | 21 |
| gremlin-3shot | **0.605** | 0.65 | 0.56 | 156 | 17 | 27 |

By category, 3-shot, Cypher / Gremlin:

| Category | Cypher | Gremlin |
|---|---|---|
| (n) | 1.00 | 0.80 |
| (n\*) | 0.92 | 0.92 |
| (n)-(m0) | 0.67 | 0.33 |
| (n)-(m0\*) | 0.97 | 0.87 |
| (n)-(m0)-(m1\*) | 0.92 | 0.75 |
| (n)-(m0\*),(n)-(m1\*) | 0.95 | 0.76 |
| (n)=(m0) | 1.00 | 0.00 |
| comparison | 1.00 | 0.34 |
| optional-match | 0.67 | 0.60 |
| three-node group-by | 0.75 | 0.31 |
| time-sensitive | 0.67 | 0.33 |
| union | 0.86 | 0.38 |

## 3. Figures

None.

## 4. Interpretation

- **Free generation is good in one language and poor in the other.** On these two graphs a
  current local model writes Cypher well enough (0.90) that a typed-request path has little
  headroom against it. Against Gremlin there are about 30 points of headroom.
- **The Gremlin gap is concentrated in compositional shapes:** comparisons, a shared middle
  node, group-by and union. Single-hop lookups are close.
- **The comparison that carries information is typed requests against *both* languages.** On
  this evidence, typed requests have room to win against Gremlin, not against Cypher.
- **The shot examples help Gremlin about as much as Cypher** (+0.105 against +0.09). Three
  examples do not close the gap.

## 5. Threats to validity

- **One model.** The plan requires several sizes; the relay had one healthy alias. This
  verdict is provisional until it is re-run with two or more.
- **48 Gremlin generations, and no Cypher ones, hit the 8,192-token limit** and returned no
  query (27 with examples, 21 without). They are counted wrong. Even if every one were right,
  Gremlin with examples would be 0.74: still under 0.80, and still at least 16 points behind.
- **API version drift.** 10 of the 79 wrong Gremlin answers with examples use `decr`/`incr`,
  which TinkerPop removed in 3.5 (now `desc`/`asc`). Correcting all of them as well bounds
  Gremlin at about 0.79. The verdict does not change.
- **The CypherBench graphs are easy, Wikidata-derived ones.** Two of eleven graphs, 200
  questions.
- **The mirror is verified, not assumed:**
  - counts are equal;
  - 50 sampled nodes are equal;
  - 30 hand-written Gremlin queries and the 3 shot examples all match the reference Cypher.

## 6. What surprised us

- **Cypher was high for a small local model** (0.81 with no examples, 0.90 with three). The two
  smallest test graphs are probably among the easiest in the benchmark.
- **The model sometimes reasons itself out of the budget on Gremlin** and never on Cypher, which
  points to uncertainty rather than difficulty alone.
