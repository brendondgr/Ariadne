# RESULTS — EXP-2026-11-003 Model-written Cypher vs model-written Gremlin (kill test T1)

## 1. Headline

**Survives on three models.** With 3 examples, every model writes Cypher that returns exactly the
right records on about 0.90 of 200 CypherBench questions. Gremlin is far behind on all three:

| Model | Cypher 3-shot | Gremlin 3-shot | Gap (paired 95% CI) | Cypher 0-shot | Gremlin 0-shot |
|---|---|---|---|---|---|
| `swift15-flashnext` | 0.900 | 0.605 | −0.295 (−0.36 to −0.23) | 0.810 | 0.500 |
| Gemma 4 31B | 0.905 | 0.745 | −0.160 (−0.22 to −0.105) | 0.765 | 0.630 |
| Qwen 3.8 27B | 0.905 | 0.655 | −0.250 (−0.315 to −0.19) | 0.830 | 0.505 |

The kill rule needs, for every model, both languages ≥ 0.80 and within 5 points. It fires for none:
no model's Gremlin reaches 0.80. The verdict is no longer provisional.

**Added 2026-11-14.** The first run had one model. The other two ran afterwards on the same 200
questions (the recorded `t1/gold` stage, copied), with the same prompts, budget and scorer, via
`scripts/killtests_t1_model.py` at 64 concurrency. Section 2 below describes the first model in
detail; `data/score-gemma4-31b.json` and `data/score-qwen38-27b.json` hold the others.

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

- **Model identity.** The relay names models by slot, and the backends' own envelope names
  (`default-model-2` for Gemma, `default-model` for Qwen) were the reverse of their slots. The two
  added models were identified by tokenizer from returned token ids (Gemma: 2/105/106; Qwen
  3.5-family: 248045/248046). Their sizes are as stated by the operator, not verified.
- **Three models, all 27–35B class, all local.** No frontier API model was run.
- **Truncation (first model).** 48 Gremlin generations, and no Cypher ones, hit the 8,192-token limit and returned no
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
