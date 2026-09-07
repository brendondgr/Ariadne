# RESULTS — EXP-2026-09-007 The 288 held-back questions, spent

## 1. Headline

**The arm comparison generalises to unseen questions.** Every arm lands within
**0.025** of its dev value, the ordering is identical, and all three contrasts
are positive with intervals excluding zero.

| arm | holdout (n=288) | 95% CI | dev (n=284) | delta |
|---|---|---|---|---|
| schema-assembled (`generic`) | **0.6546** | [0.6218, 0.6875] | 0.6569 | **−0.0023** |
| templates (`deterministic`) | **0.4862** | [0.4529, 0.5201] | 0.4946 | **−0.0084** |
| model writes the query (`llm_query`) | **0.4039** | [0.3723, 0.4353] | 0.3781 | **+0.0258** |

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

---

# AMENDMENT A-1 (2026-09-07) — four manifest values were taken from a superseded file

**Four of this experiment's recorded metrics were wrong.** They have been
corrected in `manifest.yaml`; this amendment records what they were, how it was
adjudicated, and why the error was systematic rather than random.

| metric | was | is | source of the correction |
|---|---|---|---|
| `llm_query_holdout` | 0.4031 | **0.4039** | recomputed from sidecars |
| `deterministic_minus_llm_query_holdout` | 0.0831 | **0.0822** | recomputed |
| `generic_minus_llm_query_holdout` | 0.2515 | **0.2507** | recomputed |
| `second_family_generic_minus_deterministic` | 0.2053 | **0.2143** | recomputed |

Three metrics were already correct and are unchanged: `generic_holdout`
(0.6546), `deterministic_holdout` (0.4862), `generic_minus_deterministic_holdout`
(0.1684).

## How it was adjudicated

Not by preferring one file over another. All **3,456 judgment sidecars** were
re-read from
`docs/evaluation/experiments/holdout-spend-2026-09-05/**/answers/*.judgment.{qw,qwp2,gem,gemp2}.json`
and the figures recomputed under the documented aggregation — **positions
averaged per case, then averaged across cases**. The recomputation reproduces
`data/judged-two-family-final.json` exactly and disagrees with the manifest in
the four cells above.

## Why it happened, which is the part worth keeping

The manifest was populated from **`data/judged-final.json`**, an intermediate
roll-up, and never updated when the complete two-family roll-up landed. That file
**documents its own incompleteness in its own fields**:

```
grader_second : "relay/gemma4-31B-mtp@2026-09-05 (position 1 only, deterministic+generic)"
not_measured  : ["gemma on llm_query holdout answers", "gemma position 2 on any arm"]
```

**Every one of the four wrong values lies inside what that file declares it did
not measure.** `0.2053` is the second family's *position-1-only* figure for
generic − deterministic; the position-averaged value is `0.2143`. The others are
the same shape.

So this is not a transcription slip. A number was copied out of a file that said,
in a field named `not_measured`, that the number was not final — and nothing read
that field. **The error was disclosed at the moment it was made and still
survived for two days**, which says the defect is in the reading, not the writing.

## What changes, and what does not

- **No conclusion moves.** Every corrected value keeps its sign and its
  significance verdict. `deterministic − llm_query` remains positive under both
  families and interval-significant under one.
- **The paper's own characterisation was wrong** and is corrected with it. Its
  appendix described this as a disagreement "in the fourth decimal (0.0831 vs
  0.0822; 0.4031 vs 0.4039)". Two of the four errors are larger than that, and
  `0.2053` vs `0.2143` is a third-decimal difference of 0.009.
- **The twelve confidence-interval bounds quoted in the paper now exist as
  manifest metrics.** They were previously quoted from a sidecar with no
  manifest provenance — which is precisely what `scripts/verify_paper_numbers.py`
  flagged when it was written the same night, on its first run.

## The check that found it

`scripts/verify_paper_numbers.py` did not find the wrong values directly. It
found that **twelve numbers in the paper's most contested table had no manifest
source at all**, and tracing them to their origin is what surfaced the four
errors sitting beside them. A traceability check earns its keep by making
provenance visible, not by validating arithmetic.

# AMENDMENT A-2 (2026-09-07) — the dev-half comparison figures were outside the record

The paper's templates-versus-generation table has two rows. The **holdout** row
traced to this manifest (after A-1). The **development** row traced to nothing:
its six figures lived in
`docs/evaluation/composition/bank/two-grader-judged.json`, an evaluation
artifact outside every experiment's `data/` directory, and were therefore
invisible to the record and to any check over it.

They are the reference half of this experiment's own comparison — `judged-final.json`
carries them in a field literally named `dev` — so they belong here, and are now
recorded as `dev_*` metrics.

| | qwen38-27B-v2 | gemma4-31B-mtp |
|---|---|---|
| `deterministic` | 0.4946 | 0.4175 |
| `generic` | 0.6569 | 0.6659 |
| `llm_query` | 0.3781 | 0.3478 |
| `deterministic − llm_query` | **0.1147** [0.0653, 0.1645] | **0.0696** [−0.0024, 0.1450] |

**Nothing here is a new measurement.** The numbers are unchanged; only their
provenance is. That is the whole point: a figure quoted in a paper from a file
no check can see is indistinguishable, to a reader, from one that was never
computed.

**The general defect, which is not fixed by this amendment.** Evaluation
artifacts under `docs/evaluation/` are not part of the research record and are
not scanned by anything. Two of tonight's three findings — the four wrong
holdout metrics (A-1) and this — are both cases of a number that mattered living
somewhere nothing looks. A rule that says "every number cites an EXP id" is only
as good as the set of places the checker reads.

# AMENDMENT A-3 (2026-09-07) — a rounding convention, stated because it bit

`second_family_deterministic_minus_llm_query` was briefly recorded as **0.0642**
and is **0.0643**. The unrounded difference is `0.0642734…`, which rounds to
0.0643; subtracting the two already-rounded arm means (0.4320 − 0.3678) gives
0.0642.

The value is trivial. The convention is not, and it is now stated:

> **Contrasts are computed from unrounded means and rounded once, at the end.**
> They are never derived by subtracting published four-decimal figures.

A reader who recomputes a contrast from this paper's arm means will land one
ten-thousandth away from the contrast the paper reports, and will be right to
ask which is wrong. Neither is: they are different operations, and only one of
them is the estimator.

This surfaced because `scripts/verify_paper_numbers.py` refused to match the
paper's 0.0643 against a manifest carrying 0.0642 — the last untraced number in
the paper, and the check was correct to flag it.

# AMENDMENT A-4 (2026-09-07) — the body of this file was stale against its own A-1

`AMENDMENT A-1` corrected four manifest metrics. **It did not correct this file's
own results table**, which went on quoting `llm_query` at **0.4031** — one of the
four values A-1 had just declared wrong — with the delta derived from it
(`+0.0250`). Both are corrected: **0.4039** and **+0.0258**.

**The same defect, one level up.** A-1's finding was that a number was copied out
of a file that declared itself incomplete and nothing re-read the source. This is
a number left in place after the source was corrected, in the very document
announcing the correction.

**How it was found**, and this is the useful part: `verify_paper_numbers.py` was
written to check the *paper* against the manifests. Pointing it at this
`RESULTS.md` instead took one flag. **Any document in the record can be checked
this way and none of them are**, which is a larger gap than the number it caught.

The per-arm confidence intervals in the table above ([0.6218, 0.6875] and the
rest) remain unrecorded as manifest metrics. They are noted rather than fixed
here: only the *contrast* intervals are quoted in the paper, and those were
recorded under A-1.
