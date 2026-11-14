# RESULTS — EXP-2026-11-004 Typed requests compiled to Cypher and Gremlin (the T1 typed arm)

## 1. Headline

**Survives the pre-registered rule on both models.** When the model fills in a typed request and
code compiles it, the result is **the same on Cypher and on Gremlin, for every question**.

On 3-shot exact-records:
- **Qwen 3.8 27B: 0.955 on both backends.** That is above free Cypher (0.905; +0.05, CI 0.01 to
  0.09) and far above free Gremlin (0.655; +0.30, CI 0.23 to 0.37).
- **Gemma 4 31B: 0.895 on both backends.** That is level with free Cypher (0.905; −0.01, CI
  −0.06 to 0.035) and above free Gremlin (0.745; +0.15, CI 0.085 to 0.22).

**Ceiling:** every one of the 200 test questions is expressible as a typed request that
reproduces the gold on both backends (1.000 / 1.000). So the misses below are the models'
form-filling, not the format's coverage.

## 2. Results table

From `data/metrics.json`. The questions, gold rows, stores and normaliser are those of
EXP-2026-11-003, and the free-arm figures are each model's own run there. One run each.

| Model | Arm | typed via Cypher | typed via Gremlin | free Cypher | free Gremlin |
|---|---|---|---|---|---|
| Gemma 4 31B | 0-shot | 0.805 | 0.805 | 0.765 | 0.630 |
| | **3-shot** | **0.895** | **0.895** | 0.905 | 0.745 |
| Qwen 3.8 27B | 0-shot | 0.875 | 0.875 | 0.830 | 0.505 |
| | **3-shot** | **0.955** | **0.955** | 0.905 | 0.655 |

Paired differences, typed minus free, with 95% CIs:

| Model | Shots | typed minus free Gremlin | typed minus free Cypher |
|---|---|---|---|
| Gemma 4 31B | 0 | +0.175 (0.095 to 0.255) | +0.04 (−0.03 to 0.105) |
| | 3 | **+0.15 (0.085 to 0.22)** | −0.01 (−0.06 to 0.035) |
| Qwen 3.8 27B | 0 | +0.37 (0.295 to 0.45) | +0.045 (−0.015 to 0.105) |
| | 3 | **+0.30 (0.23 to 0.37)** | **+0.05 (0.01 to 0.09)** |

**The kill rule** (`data/killrule.json`):
- **H2** (typed beats free Gremlin by at least 0.10) holds for both models.
- **H3** (typed within 0.05 of free Cypher) holds for both models.
- **H1** (backends within 0.02) holds exactly: in all 800 typed generations, the two backends
  agree on correctness.

**Reply status, 3-shot:**
- Gemma: 189 valid, 11 invalid.
- Qwen: 199 valid, 1 invalid.
- Unparseable: none at 3-shot (one per model at 0-shot).

**By category, 3-shot typed:**
- Weakest for Gemma: union 0.43 (21 questions) and optional-match 0.67.
- Weakest for Qwen: `(n*)` 0.83 and optional-match 0.80.
- Every other category is 0.90 or higher for both.

## 3. Figures

None.

## 4. Interpretation

- **The typed path is backend-independent by construction, and it held.** Free generation's
  accuracy depends on the language: a 16- to 25-point drop from Cypher to Gremlin for these two
  models. The typed path's accuracy does not.
- **Against free Cypher, typed requests are level or better.** Qwen beat its own free Cypher
  (+0.05, CI excludes 0). Gemma was level. "Little headroom against Cypher" (EXP-2026-11-003)
  turned out to be enough for one model to win outright.
- **The remaining errors are form-filling errors, not coverage.** The ceiling is 1.000. Gemma's
  11 invalid 3-shot requests are all "either/or" (union) questions:
  - in 9, it wrote `any_of` as references to edges it had already named (`[["r0"], ["r1"]]`),
    which the format does not accept;
  - in 2, it reused an edge name across branches.

  A format that accepts edge references, or one repair turn showing the validator's message,
  would likely recover most of these. Both are changes for a new, separately registered run.
- **Typed requests are cheaper to produce.** Median completion tokens at 3-shot:

  | Model | typed | free Cypher | free Gremlin |
  |---|---|---|---|
  | Gemma | 739 | 604 | 1,078 |
  | Qwen | 765 | 549 | 1,069 |

  Typed requests cost about the same as free Cypher, and less than free Gremlin.

## 5. Threats to validity

- **The format was designed from CypherBench's own template catalogue** (training split). The
  test questions come from the same templates, so the ceiling of 1.000 says the format covers
  *this benchmark's* question shapes, not arbitrary questions. The two test graphs were not
  used in design.
- **Semantic choices follow the benchmark's gold.** Missing values sort as Neo4j sorts them.
  That favours matching CypherBench's answers. It is applied identically on both backends.
- **Two models, both local and 27–35B class,** one run each. The free-arm runs were made the
  previous day with the same weights, identified by tokenizer token ids.
- **No repair turn,** matching the free arms. A repair turn would likely raise the typed arm
  further, and would be a different comparison.
- **The CypherBench graphs are easy, Wikidata-derived ones** (see EXP-2026-11-003).

## 6. What surprised us

- **Typed beat free Cypher for Qwen.** The prior expectation (EXP-2026-11-003) was at most
  parity against Cypher.
- **Gremlin's `match()` step is unreliable on cyclic patterns** in TinkerPop 3.8.0 (empty
  results or `ClassCastException`). The compiler walks patterns instead. Free-written Gremlin
  that uses `match()` inherits this.
- **Gemma's union failures were a format-usability issue,** not a reasoning one: it wrote a
  sensible request the format did not accept.
