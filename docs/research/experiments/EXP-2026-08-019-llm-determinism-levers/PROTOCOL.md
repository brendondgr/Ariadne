# PROTOCOL — EXP-2026-08-019

**Written before the run.**

## 1. The question

Q2's surviving half. The deterministic arms now carry an interval
(EXP-2026-08-015) and the LLM-in-the-loop arms do not: none has been run twice,
every figure quoting them is n=1, and `statistical_test` is null in every
manifest that mentions them.

The operator asked for something more useful than a measurement: **minimise the
variance**, and know what concurrency costs. This measures the levers rather than
assuming them.

## 2. What was already true and never written down

**Every graded call site already sends `temperature: 0`** — the planner drafter,
the intent classifier, the specialist query builder, the synthesis composer and
the prose narrator. Only `utils/specialists/evalset/author.py` samples at 1.0,
where phrasing variety is the point and nothing is scored.

That is a design property this record never stated, and stating it is half the
answer to Q2: **the obvious lever was already pulled.**

## 3. Why temperature 0 is not determinism

Greedy decoding still reduces floating point over whatever batch a request lands
in. Two identical prompts can diverge because a *different* request happened to
share their batch. Concurrency is exactly what changes batch shape, so **speed
and reproducibility are in tension** and nobody had priced it.

## 4. The levers, and which are under our control

| lever | status | reach |
|---|---|---|
| `temperature: 0` | already sent | removes sampling entirely |
| `top_p: 1` | added 2026-08-24 | removes nucleus truncation as a variable |
| `seed` (pinned 1729) | added 2026-08-24 | removes every remaining client-controlled source |
| concurrency | **measured here** | not fixable, only chosen |
| batch-shape determinism | **not under client control** | a server property; no client can make batched inference bit-exact |

## 5. Design

Four conditions over the same population, LLM claims arm, retrieval held
deterministic:

| condition | seed | workers | status |
|---|---|---|---|
| A | off | 16 | **reused** — EXP-2026-08-018's LLM arm, run before the seed landed |
| B | **on** | 16 | run |
| C | **on** | 1 | **deferred, and the reason is recorded rather than hidden** |
| D | **on** | 32 | run |

Three repeats each, all 120 catalogue questions, so every condition is measured
over the same population.

**Condition C is deferred on cost, not on interest.** Per-question composition
averages 56 s, so one repeat at a single worker is ~1.9 hours and three repeats
is **5.6 hours** — against 7 minutes at 16 workers. It is the condition most
likely to be reproducible and least likely to be *used*, so it buys the least
per hour. Its absence bounds the conclusion: B versus D can say whether raising
concurrency costs stability, and **cannot** say how much stability a fully
serialised run would recover.

**Measured per condition:** spread across repeats of claim count, unsupported
count, and gold-in-claims; plus the fraction of questions whose answer is
**byte-identical** across all three repeats, which is the sharpest form of the
question.

## 6. Hypotheses

**H1.** Seeding reduces spread at fixed concurrency (B < A).
**H2.** *(unfalsifiable here — condition C deferred.)* Concurrency 1 would be the
most reproducible, because batch shape stops varying. Recorded as a stated
expectation, never as a result.
**H3.** 32 workers is measurably less reproducible than 16 (D > B). **This is the
operator's actual question** — 64 concurrency is available and 32 was authorised.
If H3 fails, higher concurrency is free and 32 is safe for graded runs.

Stated plainly: **if B, C and D are indistinguishable, the tension in §3 is
theoretical here and graded runs may use whatever concurrency is fastest.** That
is a perfectly good outcome and would be reported as such.

## 7. Threats declared in advance

* **One server, one model, one day.** Per Q12 the relay serves
  `Ornith-1.5-35B-A3B-W4A16-SYM`; batch-shape behaviour is a property of that
  stack and nothing here transfers.
* **Byte-identity is a strict metric and may read 0 everywhere.** If so the
  spread statistics carry the result and the identity fraction is reported as
  uninformative rather than as a failure.
* **This measures the synthesis seam only.** The planner and specialist LLM
  seams have their own variance and are not covered; naming that gap is part of
  the result, since Q2 asked about "the LLM arms" and this closes one of three.
