# RESULTS — EXP-2026-11-005 Typed request format v2, and every arm on a second benchmark

## 1. Headline

**Part B is killed by the pre-registered rule, on both models. The cause is the format's
coverage, not backend dependence or form-filling where the format applies.**

- On 390 Text2Cypher questions, typed v2 (3-shot) scores **0.182 (Gemma)** and **0.208 (Qwen)**
  on both backends. Free Cypher scores 0.359 and 0.400; free Gremlin 0.192 and 0.156.
- **H1 (backend independence) holds exactly.** Cypher and Gremlin agree on every one of 2,340
  typed requests per model.
- **H2 and H3 fail.** Typed does not beat free Gremlin by 0.10 for either model, and it is
  17 to 19 points below free Cypher.
- **Why** (exploratory; §4):
  - A hand-judged random sample of 40 questions finds only **18 (45%) expressible in v2**.
  - The largest gap is a single missing operator, **ranking by an aggregate**, as in "top 3
    suppliers by number of products". It accounts for 11 of the 40.
  - On the expressible 18, typed scores 15 (Gemma) and 18 (Qwen) against free Cypher's 16 and 16.
    So where the format can say the question, the EXP-2026-11-004 result reproduces on a new
    benchmark.
- **The scorer does not explain the kill.** Text2Cypher's gold keeps duplicate rows and adds
  columns the question does not ask for. Rescoring every arm with duplicates ignored and column
  subsets allowed raises free Cypher to 0.746 and typed only to 0.333 / 0.356 (§4.2).

**Part A** (format v2 on the original 200 CypherBench questions):
- **The fix worked where it was aimed.** Gemma's union accuracy went 0.429 → 0.905, and its
  overall 0.895 → 0.920.
- **It cost Qwen.** Qwen went 0.955 → 0.905, so A1 fails for Qwen.
- **Cause:** v2 allows edge references in `any_of` but not in `optional`, and both models carried
  the reference form over into `optional` (ISSUES.md).

## 2. Part B results

From `data/metrics.json` and `data/killrule.json`. Exact-records (pre-registered scorer), one run.
Qwen's part B ran at `reasoning_effort=medium`; see ISSUES.md.

| Model | Shots | free Cypher | free Gremlin | typed v2, Cypher | typed v2, Gremlin | typed v2 + repair |
|---|---|---|---|---|---|---|
| Gemma 4 31B | 0 | 0.336 | 0.182 | 0.177 | 0.177 | |
| | **3** | **0.359** | **0.192** | **0.182** | **0.182** | 0.192 |
| Qwen 3.8 27B | 0 | 0.400 | 0.172 | 0.179 | 0.179 | |
| | **3** | **0.400** | **0.156** | **0.208** | **0.208** | 0.221 |

Paired differences at 3-shot, with 95% CIs:

| Model | typed minus free Gremlin (H2 needs ≥ +0.10) | typed minus free Cypher (H3 needs ≥ −0.05) |
|---|---|---|
| Gemma 4 31B | −0.010 (−0.046 to 0.026) | −0.177 (−0.221 to −0.133) |
| Qwen 3.8 27B | +0.051 (0.018 to 0.087) | −0.192 (−0.238 to −0.146) |

**Rule:** killed if H2 fails for any model or H3 fails for every model. Both fail for both
models, so **killed**. **H1 holds:** `backends_agree` = 1.0 for every typed arm and model.

**By graph** (3-shot, typed / free Cypher / free Gremlin):

| Graph (n) | Gemma | Qwen |
|---|---|---|
| movies (146) | 0.253 / 0.342 / 0.158 | 0.253 / 0.397 / 0.151 |
| northwind (157) | 0.115 / 0.331 / 0.210 | 0.153 / 0.401 / 0.127 |
| fincen (87) | 0.184 / 0.437 / 0.218 | 0.230 / 0.402 / 0.218 |

**Crowdsourced (human-written) subset, n = 15, descriptive only.** typed 0.267 / 0.267, free
Cypher 0.333 / 0.200, free Gremlin 0.067 / 0.200 (Gemma / Qwen).

**Request status (typed v2, 3-shot):**
- Gemma: 269 valid, 90 invalid, 31 unparseable.
- Qwen: 285 valid, 105 invalid.
- One repair turn lifts valid requests to 313 and 339, but correctness only by 0.010 and 0.013.
  Most invalid requests are attempts to say something the format cannot.

**Budget:** replies that hit the 8,192-token cap were common for Gemma (71 free-Gremlin, 31 typed
at 3-shot) and rare for Qwen at `medium` (26 free-Gremlin, 0 typed).

## 3. Part A results

Same 200 questions, stores and gold as EXP-2026-11-003/004. 3-shot unless stated.

| Model | typed v1 | **typed v2** | v2 + repair | free Cypher | free Gremlin |
|---|---|---|---|---|---|
| Gemma 4 31B | 0.895 | **0.920** | 0.945 | 0.905 | 0.745 |
| Qwen 3.8 27B | 0.955 | **0.905** | 0.930 | 0.905 | 0.655 |

- **v2 minus v1:** Gemma +0.025 (−0.015 to 0.07); Qwen −0.05 (−0.085 to −0.02). **A1 holds
  for Gemma and fails for Qwen.**
- **v2 minus free Gremlin:** +0.175 (0.11 to 0.24) for Gemma, +0.25 (0.175 to 0.325) for Qwen.
- **v2 minus free Cypher:** +0.015 (−0.03 to 0.055) for Gemma, 0.00 (−0.045 to 0.045) for Qwen.
- **0-shot v2:** Gemma 0.870 (v1 0.805), Qwen 0.865 (v1 0.875).
- **A2 holds.** Gemma's union category (n = 21): 0.429 → 0.905. Qwen's: 0.952 → 1.000.
- **The regression is one category.** Optional-relationship questions (n = 15): Gemma 0.667 →
  0.333, Qwen 0.800 → 0.333. Every invalid 3-shot request is an edge reference inside `optional`.
- **Backends agree on all 1,200 part-A typed requests.**

## 4. Exploratory analyses (post hoc)

### 4.1 Expressibility, by hand, on a random sample

`data/expressibility-sample.json`:
- **Sample:** 40 questions, a seeded shuffle (20261114) of the selection, first 40.
- **Judgement:** for each, could a perfect filler of v2 answer it under the lenient scorer?
  Judged by Claude Opus 5.5 from the gold Cypher and the v2 format text; not independently
  checked.

| Category | n of 40 |
|---|---|
| **Expressible in v2** | **18** |
| Ranking by an aggregate (top-k by a count or average per group) | 11 |
| Numbers stored as text (`toFloat(o.freight)`) | 4 |
| List or string functions (`size(r.roles)`, word counts) | 3 |
| Averages per group | 1 |
| Separate MATCH clauses (uniqueness differs) | 1 |
| Gold errors (absent property; reversed edge) | 2 |

Arms on the sample, counted correct under the lenient scorer (§4.2), at 3-shot:

| Subset | Model | free Cypher | free Gremlin | typed v2 | typed v2 + repair |
|---|---|---|---|---|---|
| Expressible (18) | Gemma | 16 | 14 | 15 | 17 |
| | Qwen | 16 | 11 | **18** | **18** |
| Not expressible (22) | Gemma | 13 | 9 | 0 | 0 |
| | Qwen | 17 | 1 | 0 | 1 |

On the not-expressible 22, the typed arms score 0 in 43 of 44 cases, which supports the hand
judgement. The one exception is a false positive of the lenient scorer. For "Which person has the
highest average rating for movies they wrote?", Qwen's repaired request returned the maximum
single rating. That value happens to equal the gold's average-rating column, which the
column-subset rule accepts. The same leniency can credit any arm. The sample is small:
45% expressible has a 95% interval of about 30% to 61%.

### 4.2 Scorer sensitivity

`data/sensitivity.json` and `utils/killtests/t2c/sensitivity.py`:
- **Method:** every saved part-B query is re-executed, and every arm is scored three ways.
  - **strict:** the pre-registered rule. It reproduces the run's scores exactly for every arm.
  - **set:** duplicate rows ignored.
  - **set_proj:** duplicates ignored, and a different column count allowed if one side's
    projection equals the other.
- **Typed** is scored on its Cypher compilation.

| Model (3-shot) | Scorer | free Cypher | free Gremlin | typed v2 | typed + repair |
|---|---|---|---|---|---|
| Gemma | strict | 0.359 | 0.192 | 0.182 | 0.192 |
| | set | 0.387 | 0.213 | 0.223 | 0.233 |
| | set_proj | 0.746 | 0.490 | 0.333 | 0.362 |
| Qwen | strict | 0.400 | 0.156 | 0.208 | 0.221 |
| | set_proj | 0.746 | 0.285 | 0.356 | 0.387 |

The gold's extra columns cost every arm, free Cypher most. Under no scorer does typed come within
0.05 of free Cypher.

### 4.3 Regex taxonomy of typed misses where free Cypher was right

`data/taxonomy.json`. This is pre-registered as exploratory; it undercounts gaps.

| Model | Misses | Gold uses a regex-detected gap feature | Remainder |
|---|---|---|---|
| Gemma | 79 | 27 | 52 |
| Qwen | 86 | 26 | 60 |

The regexes catch WITH chains, list functions, aggregate-then-filter, EXISTS and similar. They
miss "ORDER BY count(...) LIMIT k" written in one clause, and numbers stored as text. §4.1 shows
that most of the "remainder" is also format gap, not fill error.

## 5. What this means

1. **The backend-independence result holds on new data.** The typed layer gave identical answers
   on Cypher and Gremlin for all 4,680 part-B requests, as for all 1,200 in part A.
2. **The accuracy result holds only inside the format's coverage.** On CypherBench (coverage
   1.000, by construction) typed matches or beats free Cypher. On Text2Cypher, coverage is about
   45%. Inside it, typed matches free Cypher; outside it, typed cannot answer.
3. **The next format version is specified by the gaps, in priority order:**
   1. rank by an aggregate: `top` over `count_per` or a per-n aggregate, with order and limit;
   2. aggregates per group;
   3. numeric coercion for numbers stored as text (a card-level type annotation);
   4. edge references in `optional` (part A).

   On the sample these would cover about 30 of 40 questions. That is an estimate, not a
   measurement, and it needs its own pre-registered run on a held-out benchmark.
4. **A hybrid is the obvious fallback:** typed when the request validates, free generation
   otherwise. It is not measured here. On Gremlin backends the fallback inherits free Gremlin's
   weakness.

## 6. Provenance

- **Code:** frozen at tag `killtests-exp005-run` (aa31340c). After the tag, three changes, all in
  ISSUES.md: the analysis and resume scripts (f276e998); the per-model reasoning setting
  (7151c4ae); and the sensitivity script (this commit).
- **Runs:**
  - Part A: 2026-11-14 01:09–01:19.
  - Part B: 01:19–08:14, invalid (relay outage). Resumed 10:09 at 64 concurrent and stopped
    (429s), then 11:28 at 16 (identification failed). The final pass ran 11:58–13:06 at 16, with
    Qwen at `medium`. Zero generation errors remain.
- **Models:** identified by tokenizer before every pass: `default-model` = Gemma 4 31B (last token
  106), `default-model-2` = Qwen 3.8 27B (248046).
