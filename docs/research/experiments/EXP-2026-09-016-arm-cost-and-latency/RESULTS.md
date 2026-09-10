# RESULTS — EXP-2026-09-016, what each answering path costs

`Q38` is answered, in two regimes, with the concurrency stated beside each. On
the way the experiment found that **the arm carrying `C-023` silently runs as a
different arm** unless one environment variable is set (`ISSUES.md` `I-4`), and
that the pitch's headline cost ratio divides two different quantities (`A-2`).

---

## A-1 — Throughput, 284 development questions, 24 workers, one instance

Every arm here ran with `SPECIALIST_LLM_TIMEOUT_S=4096` and `ORCH_MAX_HOPS=5`,
matching `scripts/holdout_run.py`. See `I-4` for what the default does.

| path | wall clock | summed machine time | median/question | model calls | tokens | returned evidence | answers carrying a fallback reason |
|---|---|---|---|---|---|---|---|
| hand-written templates | 8.1 s | 0.03 h | 0.111 s | **0** | 0 | 259 / 284 | 0 / 284 |
| schema-derived | 1,168.6 s | 4.4 h | 12.7 s | **159** | 817,238 | 198 / 284 | 39 / 284 |
| model writes the query | 11,407.8 s | 70.3 h | 638.7 s | **413** | 5,818,658 | 96 / 284 | 0 / 284 |

**The schema-derived path is not free.** It disables the hand-written templates
but keeps LLM planning, an LLM specialist seam and the multi-hop retrieval loop.
`CLAIMS.md` already carries this — `C-023` is `partial` in part because "the
generic arm's narrator calls a model" — but no cost figure had ever shown it.
It costs **144x** the hand-written path.

| comparison | wall clock |
|---|---|
| schema-derived ÷ hand-written | **144x** |
| model-writes-query ÷ hand-written | **1,408x** |
| model-writes-query ÷ schema-derived | **9.8x** |

Only the hand-written path is genuinely model-free, at zero calls in every run
of this experiment.

## A-2 — The published 40,000x figure divides two different quantities

`docs/research/reports/2026-09-05-full-report.md` reports "about four seconds"
against "roughly two days of machine time", a ratio of "about forty thousand
times". The October pitch names it as one of two numbers that must land.

**The two-day half reproduces.** Summed machine time for the model-writes-query
arm is **2.93 days** here, against that report's "roughly two days".

**The ratio does not.** Four seconds is one arm's *wall clock*; two days is
another arm's *summed machine time*. At 24 workers those differ by 24x before
any real effect. Reconstructing the same construction on these numbers gives
**31,252x** — which identifies how the figure was formed and shows it is not
stable across nights.

Held to one quantity at a time, same questions, same concurrency, same machine:
**1,408x** on wall clock, **1,320x** on machine time.

**Recommendation.** Quote **about a thousand times**, or "three orders of
magnitude". It survives an engineer asking "per question or in total, and at
what concurrency?" Forty thousand does not.

## A-3 — Single-user latency, 20 questions, one worker

The number an analyst actually waits. A throughput figure divided by a question
count is not this number.

| path | median wait | mean | slowest | model calls |
|---|---|---|---|---|
| hand-written templates | 0.006 s | 0.041 s | 0.6 s | 0 |
| model writes the query | **182.0 s** | 283.5 s | 1,140.2 s | 34 |

Three minutes of waiting, per question, for the path that then returns evidence
on one question in three.

The `generic` latency cell is **not reported**: it ran before `I-4` was
understood and its settings do not match its throughput cell. Recording the gap
rather than a mismatched number.

The first observation of the `llm_query` latency run overlapped an orphaned
process for about 70 s (`I-3`). It ranks 13th of 20 by wall clock, so it is not
an outlier, and per the pre-registered rule nothing is excluded.

## A-4 — The expensive path also answers far less often

| path | questions returning evidence |
|---|---|
| hand-written templates | 259 / 284 |
| schema-derived | 198 / 284 |
| model writes the query | 96 / 284 |

Returning evidence is not correctness — `EXP-2026-09-005` and `-007` hold those
— but the cost comparison understates the gap. The honest sentence is "more
expensive **and** less useful", not "more expensive".

## A-5 — The quality column, completed on one bank

Graded 2026-09-10 by `relay/qwen38-27B-v2`, 16 workers on each of two instances,
over this experiment's own saved answers.

| path | judged correctness, dev n=284 |
|---|---|
| hand-written templates | 0.4946 |
| schema-derived | 0.6569 |
| model writes the query | **0.4043** (n=282) |

The first two are already on record for these exact questions
(`EXP-2026-09-005`); only the third was missing, which is why the cost table's
quality column had been mixing banks.

**It lands on top of the holdout figure.** `EXP-2026-09-007` reports 0.4039 for
this arm on the 288 held-back questions. The development half returns 0.4043 —
a difference of 0.0004, on a different question set, five days later, under a
separately configured run. That is a stronger cross-check than anything this
experiment set out to produce.

So the honest one-line summary of the whole cost exercise:

| path | cost against the hand-written path | judged correctness |
|---|---|---|
| hand-written templates | 1x | 0.4946 |
| schema-derived | 144x | 0.6569 |
| model writes the query | 1,408x | 0.4043 |

**Two of 284 could not be graded**, both because the judge returned a reply
missing every required field. Notably they are size-ranked 279th and 283rd of
284 — among the *smallest* answers, not the largest. `EXP-2026-08-021` found its
grading failures concentrated in the top 5% by size; this is the opposite, so
the two are not the same phenomenon and neither is size-driven truncation.

## A-6 — The judge counts the abstention template as fabrication

Found while checking a figure before quoting it, and it is not confined to this
experiment.

The deterministic abstention narrative reads: *"If you meant a specific entity,
name it or give its id (e.g. T1566, M1017, or CAPEC-98)."* The judge records
those three illustrative identifiers in its `hallucinations` field. On this run,
**160 answers were flagged and 157 of the flags are exactly that trio**; all 160
also abstained.

Taken at face value this arm "hallucinates on 57% of answers". It does not. It
prints a help string.

The artifact is present in committed runs too:

| run | judgments | flagged | of which the boilerplate ids |
|---|---|---|---|
| `EXP-2026-09-005` deterministic | 3,407 | 118 | 35 (30%) |
| `EXP-2026-09-005` generic | 3,123 | 255 | 137 (54%) |
| `EXP-2026-09-007` holdout generic | 1,152 | 186 | 128 (69%) |

**The bias has a direction.** It inflates hallucination counts in proportion to
how often an arm abstains, so it falls hardest on the generic arm — the one that
wins `C-023`. Correcting it would help the winner, which is exactly why it
should be corrected deliberately and disclosed, not quietly.

`fabricated_mapping` is clean at 0 across this run, and the pitch's
"zero fabricated claims" line comes from the deterministic verifier rather than
from this judge, so neither is affected. What is affected is any figure quoting
this judge's hallucination count. Filed as `Q48`.

## A-7 — Reporting discipline

Regimes reported apart, as pre-registered. No dollar figure: the models are
served on hardware this project does not pay for per token, so seconds and
tokens are the honest units and a dollar amount would be invented.
