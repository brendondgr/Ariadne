# PROTOCOL — EXP-2026-09-008 Which local models can actually grade near the ceiling?

> Written 2026-09-06 00:05 EDT, **before any calibration judgment existed**.

## Question

On 2026-09-05, `gemma4-31B-mtp` returned **exactly 1.0 on all 150 `composerfix`
answers** and was saturated in 6 of 12 August bank cells. A grader with no spread
reports a contrast of zero whatever is true, and three separate near-misses
traced to it — including a tie-break one commit from being published as four
arm-order reversals.

That was discovered by accident. **Which locally available models can resolve
differences near 1.0, and which cannot?** Nobody has measured it.

## Hypothesis

**H1** `gemma4-31B-mtp` is saturated on the ceiling band — ≥95% at exactly 1.0.
Predicted from 2026-09-05; this is a replication on a different answer set.

**H2** `qwen38-27B-v2` is **not** saturated: it placed 11 of 120 below 1.0 on
`composerfix-dev`, so it should emit ≥3 distinct values on the ceiling band.

**H3** `gemma-4-26B-it` is **unknown and genuinely uncertain**. Being a Gemma it
may share the 31B's near-binary behaviour; being smaller and instruction-tuned
rather than MTP it may not. **This is the only cell whose outcome is not
predictable from existing data**, and it decides whether C-021 gets a second
opinion at all.

**H4** Every model separates the *low* band (`llm_query` answers) with sd > 0.20.
Saturation is a ceiling effect, not a general inability.

## Setup

One **frozen 60-answer set**, `docs/evaluation/experiments/calibration-2026-09-06/`,
seed 20260906, three bands of 20:

| band | source | expected level |
|---|---|---|
| `ceiling` | `composerfix-dev/deterministic` | ~0.98–1.00 |
| `mid` | `post-repair-2026-09-03/deterministic` | ~0.49 |
| `low` | `llm-query-split-2026-09-05/llm_query` | ~0.38 |

Each band is its own arm because `post-repair` and `llm-query-split` answer the
**same** dev questions and therefore share case ids; one directory would have
collided their judgment sidecars.

Same budget (32,768) and same prompt for every model — a cheaper pass would
confound grader with budget. Served model probed from the response envelope and
recorded; **the alias is never evidence** (`D-028`), and `default-model-2` served
two different families within six hours on 2026-09-05.

## Metrics

- **`ceiling_band_fraction_at_1`** — the decisive number.
- **`distinct_values`** per band — a grader emitting one value has no resolution.
- **`sd`** per band, and overall.
- **`usable_near_ceiling`** — `fraction_at_1 < 0.95` **and** `distinct_values > 2`
  on the ceiling band. Pre-registered here so it is not tuned to the result.

## What would falsify this

**H1 fails** if the 31B shows spread on this set — then 2026-09-05's saturation
was a property of those particular answers, not the model, and the warning now
in `CLAIMS.md` is too strong.

**H2 fails** if qwen is also saturated — then C-021's +0.0322 rests on a grader
that cannot measure it either, and the claim is in far worse shape than recorded.

**H3 has no prediction.** If `gemma-4-26B-it` is usable, Phase C gives C-021 its
first genuine second opinion. If not, *"no locally available model can adjudicate
this contrast"* is the result, and it explains in the paper's limitations why
the claim rests on one grader.
