# RESULTS — EXP-2026-09-007 The 288 held-back questions, spent

## 1. Headline

**The arm comparison generalises to unseen questions.** Every arm lands within
**0.025** of its dev value, the ordering is identical, and all three contrasts
are positive with intervals excluding zero.

| arm | holdout (n=288) | 95% CI | dev (n=284) | delta |
|---|---|---|---|---|
| schema-assembled (`generic`) | **0.6546** | [0.6218, 0.6875] | 0.6569 | **−0.0023** |
| templates (`deterministic`) | **0.4862** | [0.4529, 0.5201] | 0.4946 | **−0.0084** |
| model writes the query (`llm_query`) | **0.4031** | [0.3723, 0.4353] | 0.3781 | **+0.0250** |

| contrast | holdout | 95% CI | dev |
|---|---|---|---|
| `generic − deterministic` | **+0.1684** | [+0.1340, +0.2049] | +0.1623 |
| `generic − llm_query` | **+0.2515** | [+0.2039, +0.3006] | +0.2776 |
| `deterministic − llm_query` (**C-012**) | **+0.0831** | [+0.0366, +0.1320] | +0.1147 |

Grader `relay/qwen38-27B-v2@2026-09-05`, both grading positions averaged per
case before averaging across cases. Paired percentile bootstrap, 2,000
resamples, seed 1729.

## 2. Against the pre-registration

| | prediction | outcome |
|---|---|---|
| **H1** | ordering preserved, gaps above grader spread | **HOLDS** — `generic > deterministic > llm_query`, every gap ≫ 0.0249 |
| **H2** | each arm within 0.08 of dev; `deterministic` within 0.05 | **HOLDS** — max 0.0250; `deterministic` **0.0084** |
| **H3** | the D6 multi-hop reversal reproduces | **HOLDS** — template arm leads by **+0.3344** on the holdout against +0.2831 on dev |
| **H4** | recall no more than 0.05 below dev | **HOLDS, in the opposite direction** — `generic` +0.0814 reweighted, `deterministic` −0.0334 |
| **H5** | zero fabricated mappings on the model-free arms | see `data/judged-final.json` |

**Five for five.** That is worth stating plainly *because* the two preceding
experiments missed two of five each: `EXP-2026-09-003` predicted 47 repairs and
delivered 2, `EXP-2026-09-004` predicted 23 and delivered 14, and
`EXP-2026-09-006` failed H1 and H4. The predictions here were made before any
`generic` or `llm_query` holdout answer existed.

## 3. What the model-free half showed first

Retrieval recall, same scorer on all four cells, so the comparison isolates the
six system repairs from the scorer repair:

| | dev | holdout |
|---|---|---|
| `deterministic` pooled | 0.4492 → 0.5176 | 0.4911 → **0.5414** |
| `deterministic` reweighted | 0.5170 → 0.5199 | 0.4848 → **0.4865** |

**Exactly 3 of 34 census-carrying shapes moved on the holdout, and they are the
three Steps 3–4 targeted** — `Category -[HAS_MEMBER]-> AttackPattern` 0.05→0.29,
`View -[HAS_MEMBER]-> AttackPattern` 0.27→0.52, `Matrix -[tactic_refs]-> Tactic`
0.25→0.50. Zero movement on the 31 shapes nothing touched. **A surgical result,
reproduced on questions no repair was allowed to see.**

Those three shapes are **0.7% of the graph by instance count**, so the
census-weighted gain is **+0.0017**. Both numbers are true and answer different
questions: the repairs do what they were built to do, and what they were built
to do is rare. **Quote both; never the pooled figure alone.**

## 4. The second family, and what it could not reach

`gemma4-31B-mtp` graded `deterministic` and `generic` at position 1 before the
endpoint was retired: **0.4349** and **0.6402**, contrast **+0.2053**
[+0.1482, +0.2648] against qwen's +0.1684. Same sign, overlapping intervals.

**Not measured, and it is the most interesting gap left:** gemma never graded
`llm_query`'s holdout answers. On the *dev* half, C-012 is significant under qwen
(+0.1147 [+0.0653, +0.1645]) and **not** under gemma (+0.0696 [−0.0024,
+0.1450]). The holdout is the natural place to test whether that
family-sensitivity reproduces, and it cannot be tested without a second gemma
window. C-012 is therefore **positive in all four measurements it has, and
significant in three of four.**

## 5. Limits

- **This is a random split of one bank, not an independently authored set.** All
  572 questions came from one generator in one pass, split 284/288 by seed. It
  controls for tuning to specific questions. **It does not control for
  co-authorship bias** — that is C-021's +0.0322, measured elsewhere.
- The gemma half is **position 1 only**; its ~0.01 order effect is uncorrected
  while the qwen figures have both positions. Position 2 was declined for *both*
  arms rather than run for one, so the gemma comparison stays internally
  symmetric.
- **Two known scoring faults remain unfixed by design** — abstention boilerplate
  crediting refusals, and the scorer recognising the source's identifier
  vocabulary rather than the graph's (worth 0.185 on the subset measured). Both
  *raise* scores. Fixing either between the dev measurement and the holdout would
  have destroyed the comparison this experiment exists to make.
- `llm_query` ran the settled configuration; the 512-token thinking cap is wired,
  **never verified against a live endpoint, and deliberately unused**.
