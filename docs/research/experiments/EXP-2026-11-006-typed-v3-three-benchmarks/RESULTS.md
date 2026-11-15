# RESULTS — EXP-2026-11-006 Typed request format v3 on three benchmarks

## 1. Headline

**Killed on the held-out benchmark.**
- **Part C (Mind the Query):** typed v3 at 3-shot scored **0.240** (Gemma) and **0.218** (Qwen),
  against free Cypher at 0.693 and 0.684 and free Gremlin at 0.362 and 0.247.
  - **H2 (beats free Gremlin by 0.10) fails for both models:** −0.122 and −0.029.
  - **H3 (within 0.05 of free Cypher) fails for both:** −0.453 and −0.467.
  - **Backends agree on every request (H1 holds).**
- **Part B (development):** the v3 fixes work on the benchmark they were designed from. typed3
  rose by about 0.18 over typed2 and now matches free Cypher.
- **Part A (CypherBench):** no regression.

`n_runs: 1`. Every figure is one pass over the question set at temperature 0, with paired
bootstrap 95% CIs over questions; there is no spread over runs.

## 2. Results table

Exact-records accuracy at 3-shot, from `data/metrics.json` (`killrule.json` holds the rule inputs
and CIs). Typed arms are scored on the Cypher backend; the Gremlin backend gives the same figure
except where noted.

| Part | Model | typed3 | typed2 (v2 prompt) | free Cypher | free Gremlin | typed3 − free Gremlin [95% CI] | typed3 − free Cypher [95% CI] |
|---|---|---|---|---|---|---|---|
| **C** held out (450) | Gemma 4 31B | **0.240** | 0.171 | 0.693 | 0.362 | −0.122 [−0.169, −0.076] | −0.453 [−0.500, −0.404] |
| | Qwen 3.8 27B (medium) | **0.218** | 0.173 | 0.684 | 0.247 | −0.029 [−0.073, 0.011] | −0.467 [−0.513, −0.420] |
| **B** development (390) | Gemma | 0.362 (Gremlin 0.349) | 0.182 | 0.351 | 0.226 | +0.123 [0.072, 0.177] | +0.010 [−0.046, 0.072] |
| | Qwen | 0.377 (Gremlin 0.367) | 0.203 | 0.400 | 0.164 | +0.203 [0.154, 0.249] | −0.023 [−0.077, 0.033] |
| **A** CypherBench (200) | Gemma | 0.945 | 0.950 | 0.905 | 0.750 | +0.195 | +0.040 |
| | Qwen | 0.950 | 0.945 | 0.860 | 0.635 | +0.315 | +0.090 |

**Pre-registered rule and expectations:**

| | Gemma | Qwen | |
|---|---|---|---|
| C-H1 backends within 0.02 | holds (1.000 agree) | holds (1.000) | |
| C-H2 typed3 Gremlin ≥ free Gremlin + 0.10 | **fails** | **fails** | kill |
| C-H3 typed3 Cypher ≥ free Cypher − 0.05 | **fails** | **fails** | kill |
| B1 typed3 ≥ typed2 + 0.10 | holds (+0.179 [0.144, 0.221]) | holds (+0.174 [0.136, 0.215]) | |
| B2 (H2, H3 on part B, reported only) | both hold | both hold | |
| A1 typed3 ≥ typed2 − 0.02 | holds (−0.005) | holds (+0.005) | |

**A2: Qwen at `medium` against its earlier `xhigh` figures (part A, EXP-2026-11-005):**

| Arm | `xhigh` | `medium` |
|---|---|---|
| free Cypher | 0.905 | 0.860 |
| free Gremlin | 0.655 | 0.635 |
| typed2 | 0.905 | 0.945 |

The lower setting costs the free arms a little and the typed arm nothing. On CypherBench,
Qwen's typed advantage over free Cypher grows from 0 to +0.09.

**Lenient rescoring** (`data/sensitivity.json`, exploratory): duplicates ignored and column
subsets allowed (`set_proj`), applied the same way to every arm.

| Part | Model | typed3 | free Cypher | free Gremlin |
|---|---|---|---|---|
| C | Gemma | 0.3756 | 0.7733 | 0.4667 |
| C | Qwen | 0.4 | 0.7644 | 0.3822 |
| B | Gemma | 0.5256 | 0.7359 | 0.5282 |
| B | Qwen | 0.5333 | 0.7462 | 0.2821 |

The part-C kill does not depend on the scorer. Under `set_proj`, typed3 still trails free Cypher
by about 0.37 on part C and does not beat free Gremlin by 0.10 for either model.

**By source and graph, part C, typed3 / free Cypher:**

| | Gemma | Qwen |
|---|---|---|
| Complex Aggregation (224) | 0.14 / 0.60 | 0.11 / 0.64 |
| Complex Retrieval (226) | 0.34 / 0.78 | 0.32 / 0.73 |
| healthcare | 0.39 / 0.91 | 0.33 / 0.86 |
| er | 0.23 / 0.66 | 0.21 / 0.69 |
| wwc | 0.10 / 0.51 | 0.11 / 0.51 |

## 3. Figures

None in this folder. The findings page (published separately) charts the table above.

## 4. Interpretation

**The typed format does not generalise to a benchmark it was not shaped by.** The reason is the
same as on Text2Cypher before v3, coverage, now on a harder benchmark.

1. **Mind the Query is out of v3's reach more often than Text2Cypher was.**
   - 288 of 450 gold queries (64%) use a feature v3 has no operator for, or return more than one
     aggregate. On Text2Cypher the share is 73 of 390 (19%) (`data/miss-sources.json`, regex).
   - In a hand-judged sample of 40 (`data/expressibility-sample.json`, post hoc), 19 (0.475) are
     expressible in one v3 request. The 21 that are not:

     | Reason | Count |
     |---|---|
     | Several aggregates per row ("total matches and average goals") | 9 |
     | Grouping by a property value rather than a node (by gender, by year) | 5 |
     | Columns from two variables (a player and the minute of the goal) | 5 |
     | Arithmetic | 1 |
     | Gold error | 1 |

2. **Inside coverage, typed matches free Cypher once the scorer stops punishing its row shape.**
   On the 19 expressible sample questions:

   | Arm | Gemma strict | Gemma `set_proj` | Qwen strict | Qwen `set_proj` |
   |---|---|---|---|---|
   | typed3 | 9 | 16 | 9 | 17 |
   | free Cypher | 12 | 18 | 13 | 17 |

   The strict losses come from v3 returning each entity once plus its key column. Mind the
   Query's gold keeps duplicate rows (a movie title once per viewer) and returns only the asked
   property.

3. **The model forces out-of-reach questions into the format rather than failing.**
   - Over all of part C, Qwen wrote a valid request for 362 of 450 questions. Only 98 of those
     were right, against 240 for free Cypher on the same questions.
   - On part B the same comparison favoured typed (147 vs 137).
   - A valid request that answers a narrower question (one aggregate of the two asked) is the
     dominant failure, not invalid requests.

4. **Part B shows the gap-driven fixes do what they were built for.**
   - typed3 gained about 0.18 over the v2 prompt on Text2Cypher and closed the gap to free Cypher.
   - Under the part-C rule it would have survived part B.
   - That is the development result the protocol said not to count as generalisation, and part C
     confirms the caution: patching the gaps of one benchmark did not cover the next.

**Claims:** this moves the typed-coverage kill (EXP-2026-11-005) from one benchmark to two. A
fixed typed request format of this kind cannot be the generation target on realistic question
sets: about half of the questions need operators it lacks, and the model does not abstain.
- **What stays positive:** on questions it can express, the format compiles to both backends
  with identical results (1.000 on parts A and C) and lifts Gremlin to Cypher's level.
- **That points to a hybrid** (typed where expressible, free Cypher otherwise), which this
  experiment did not test.

No entry in `CLAIMS.md` changes.

## 5. Threats to validity

- **The strict scorer and v3's row shape.** v3 de-duplicates by entity and always returns the
  key. Mind the Query's gold does neither, which costs typed several points inside coverage
  (finding 2). The lenient rescoring removes most of this, and the verdict holds under it.
- **Gemma's token cap.** 161 of 450 part-C typed3 replies were cut off before any JSON
  (ISSUES.md). Qwen never capped and was killed as well.
- **Mind the Query is LLM-written, and its gold LLM-generated.** People judged the gold, but did
  not write it. 1 of the 40 sampled gold queries is wrong; the strict scorer treats every arm
  the same against it.
- **One pass, two models, 3-shot only, one prompt wording per arm.**
- **The expressibility sample is post hoc and judged by one annotator,** with the outcomes
  visible. It is a description, not a test.

## 6. What surprised us

- **Free Cypher is far better on Mind the Query than on Text2Cypher** (0.69 against 0.35–0.40),
  while typed fell. The held-out benchmark is easier for the free baseline and harder for the
  format, which is the worst case for this design.
- **Validity hides failure.** Qwen produced valid typed requests for 80% of part C, yet they were
  right only 27% of the time. A format that accepts a narrower question than the one asked turns
  "cannot express" into "confidently wrong" instead of an error the system could catch.
- **The v3 fixes generalised in a narrow sense.** typed3 beat typed2 on part C as well, by +0.069
  [0.047, 0.093] for Gemma and +0.044 [0.024, 0.067] for Qwen, but the gain was a quarter of part
  B's.

## 7. Follow-ups

- **Hybrid routing.** Typed where the request is expressible, free Cypher otherwise, with an
  explicit "not expressible" answer the model can give. This needs a router and an abstention
  signal, and should be tested on a fourth benchmark or a fresh Mind the Query split.
- **Lenient-by-design scoring.** Record whether the format's de-duplicated, keyed row shape
  should be the scoring contract; it is the right contract for a retrieval engine and the
  wrong one for these benchmarks.

## 8. Reproduction

```bash
scripts/killtests_exp006_run.sh > logs/killtests-2026-11/exp006-run.log 2>&1
KILLTESTS_EXPERIMENT=exp006 uv run --with pyarrow python -m utils.killtests.t2c.analysis6
```

The expressibility sample (`data/expressibility-sample.json`) was judged by hand; its draw is
`random.Random(20261115).sample(questions, 40)` over `logs/killtests-2026-11/mtq/gold.json`.
