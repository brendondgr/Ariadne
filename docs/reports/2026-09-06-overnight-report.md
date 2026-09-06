# Overnight run — 6 September 2026

*Generated Sunday 06 September, 03:28. Every number below is read from the files on disk at render time, so a phase that did not run cannot appear here as though it did.*

## What ran

| track | phase | outcome | time |
|---|---|---|---:|
| gemma31 | A-calibration | **done** | 4.4 min |
| gemma31 | B-llm_query-holdout | **done** | 28.5 min |
| gemma31 | B2-holdout-position2 | **done** | 42.0 min |
| qwen | A-calibration | **done** | 39.2 min |
| qwen | D-thinkcap-probe | **done** | 9.5 min |
| gemma26 | A-calibration | **done** | 208.1 min |
| gemma26 | C-c021-third-opinion | **not_run** | — |
| gemma26 | C2-holdout-third-family | **not_run** | — |

## The main question: which graders can see near the ceiling?

A grader with no spread reports a difference of zero whatever is true. Yesterday that nearly published four arm-order reversals that did not exist. This measures it directly: the same 60 answers, spanning the score range, graded by every model.

| model | ceiling band | mid band | low band | usable near ceiling? |
|---|---|---|---|---|
| **gemma4-31B-mtp** | 1.000 · 1 distinct | 0.425 · 3 distinct | 0.238 · 4 distinct | **NO — saturated** |
| **qwen38-27B-v2** | 0.980 · 3 distinct | 0.512 · 9 distinct | 0.379 · 11 distinct | **yes** |
| **gemma-4-26B-it** | 0.975 · 2 distinct | 0.624 · 5 distinct | 0.643 · 5 distinct | **NO — saturated** |

*"distinct" is how many different scores the model gave across 20 answers. A model that gave the same score to all 20 cannot tell them apart, and any comparison built on it is empty.*

## The held-back questions, now judged by two independent graders

288 questions the system had never seen, three ways of answering them, graded twice over by two different models — 3,456 judgments in all. This is the complete test the plan asked for.

**How each approach scored:**

| approach | qwen38-27B-v2 | gemma4-31B-mtp |
|---|---|---|
| schema-assembled (no templates, no model writing queries) | 0.6546 | 0.6464 |
| hand-written templates | 0.4862 | 0.4320 |
| a model writes the query | 0.4039 | 0.3678 |

**The comparisons, with the range each is confident about:**

| comparison | qwen38-27B-v2 | gemma4-31B-mtp |
|---|---|---|
| schema - templates | +0.1684 [+0.1340, +0.2049] | +0.2143 [+0.1637, +0.2659] |
| schema - model-written | +0.2507 [+0.2025, +0.2998] | +0.2786 [+0.2113, +0.3445] |
| templates - model-written | +0.0822 [+0.0362, +0.1308] | +0.0643 [-0.0080, +0.1333] — **could be zero** |

**What this says.** The schema-assembled approach beats both alternatives, and both graders agree by a wide margin — those two comparisons are safe. The third, templates against a model writing the query, is *positive under both graders but only statistically solid under one of them*. It was the same story on the earlier half of the questions, so this is a consistent property of who is judging rather than a fluke.

That matters for how the paper is framed: **lead with the comparisons both graders are sure about**, and report the third with its grader-dependence stated plainly.

## Does a third grader agree that writing your own exam flatters you?

**Not measured.** saturated on the ceiling band (0.95 at 1.0) — cannot adjudicate a near-ceiling contrast. This IS the result.

That is a result rather than a gap: if no available model can tell these answers apart, the claim rests on one grader for a reason we can state, and it belongs in the paper's limitations.

## Does capping the model's "thinking" help?

A setting had been sitting in the code for days, switched on but never actually tried against a running server. Tonight it was tried, on the same 30 questions as an earlier uncapped run so the two are directly comparable.

| | retrieved something | rejected as malformed |
|---|---|---|
| capped | **0 of 30** | **28 of 30** |
| uncapped | 3 of 30 | 4 of 30 |

**It makes things much worse.** Rejections go up sevenfold and nothing at all gets retrieved. Not one question worked with the cap that had failed without it. The setting should not be used, and that question is now closed for the cost of ten minutes.

*Caveats: 30 questions, one cap value, and these 30 are a hard slice — the uncapped run only managed 3 of them against about a third of the full set. The comparison between the two is what counts, not the raw rates. This does not change any published figure; those were all measured uncapped.*

*One thing worth admitting: the run's own progress counter initially reported all 30 as having retrieved something. It was counting the wrong field. The table above comes from re-reading the answers themselves.*

## Why the third grader was dropped

The plan was to have a third model grade the held-back questions as an extra check. The calibration run above disqualified it, for two separate reasons.

It gave only two different scores across twenty near-ceiling answers, so it cannot express a small difference at all. And more seriously, **it ranked the weaker set of answers above the stronger one** — 0.643 against 0.624, when the true order is the other way round. Every one of the held-back comparisons sits in exactly that range.

It would have taken about 32 hours to produce a comparison we already knew could not be trusted, so it was stopped before it wrote anything. **This is the calibration step paying for itself**: it was built to catch graders that cannot see small differences, and it also caught one that gets the order backwards — a failure nobody had thought to check for.

## What this night does not settle

- Nothing here re-measures the system. No questions were re-answered except the 30-question probe; every other number is a re-grading of answers that already existed.
- A grader that agrees is not proof of correctness. All of this tests whether conclusions survive a change of judge, not whether the judge is right.
- Two known scoring faults remain deliberately unfixed, because fixing them mid-comparison would break the comparison. Both would raise scores.
