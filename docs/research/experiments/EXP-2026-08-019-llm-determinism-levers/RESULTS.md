# EXP-2026-08-019 — Both hypotheses refuted, and concurrency corrupts the metric

**Status:** complete. Neither lever did what was expected, and the reason is more
useful than the hypotheses were.

## The headline

Three conditions, three repeats each, all 120 catalogue questions, LLM claims arm:

| condition | seed | workers | claims sd | unsupported sd | gold mean | gold sd | fallbacks | per-question |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **A** | off | 16 | 44.1 | 2.1 | 0.6817 | 0.0207 | 21.3 | 65.1 s |
| **B** | on | 16 | 47.0 | **16.1** | 0.6457 | 0.0212 | **14.0** | **53.0 s** |
| **D** | on | 32 | **17.1** | 2.5 | **0.7026** | 0.0373 | **28.3** | **85.5 s** |

## H1 — seeding reduces spread. **Refuted.**

Gold sd is **0.0212 seeded against 0.0207 unseeded** — indistinguishable. Claims
sd is marginally *worse* (47.0 against 44.1).

The seed is not inert, though: it moved the **mean** (0.6457 against 0.6817). So
pinning it changes what the model produces without making it more stable, which
is the worst of both readings and needs saying plainly.

**Why the lever fails here.** The variance is not sampling variance — temperature
was already 0, so there was no sampling to remove. It comes from **timeout and
fallback**, which is upstream of anything a sampling parameter can reach.

The seed stays. It costs nothing, it removes a genuine degree of freedom, and
"we pinned it" is a better sentence than "we did not". But **it must not be
reported as a variance reduction**, because it is not one.

## H3 — 32 workers is less reproducible than 16. **Refuted, and the real finding is worse.**

On the simple reading, 32 workers is *more* stable: claims sd falls 47.0 → 17.1
and unsupported sd falls 16.1 → 2.5. Taken alone that would say "raise
concurrency, it is free".

**It is not free.** Raising workers 16 → 32:

* **per-request latency rises 61%** (53.0 s → 85.5 s) — the server is saturated,
  not idle;
* **timeouts double** (14.0 → 28.3 of 120) at the standing 120 s read timeout;
* **measured quality rises** (0.6457 → 0.7026), which is the part that matters.

### The metric is contaminated by its own failure mode

Across all nine runs, **Pearson r(fallbacks, gold) = +0.62**. More timeouts →
*higher* measured quality.

The mechanism is mechanical, not subtle: a timeout falls back to the
**deterministic composer**, which scores **0.8184** against the LLM's ~0.68. So
every failed LLM call replaces a weak answer with a strong one, and the arm looks
better the more often it fails.

**At 32 workers a fifth of the "LLM arm" is not the LLM arm.** The condition that
appears best is the one measuring itself least.

That is the finding, and it generalises beyond concurrency: **any harness with a
fallback to a stronger path will report improvement when the primary path
degrades.** Every LLM-arm figure in this record should be read with its
engagement rate beside it, and EXP-2026-08-018's numbers are reported that way
for exactly this reason.

## Throughput, since it is the practical question

| | w16 | w32 |
|---|---:|---:|
| wall clock per repeat | 398 s | **321 s** |
| per-request latency | **53.0 s** | 85.5 s |
| fallbacks / 120 | **14.0** | 28.3 |

**32 workers buys 19% wall clock and costs a doubling of timeouts.** For an
ungraded job — drawing banks, bulk generation, anything where a fallback is
harmless — take the throughput. For a **graded** run, 16 is the better setting
and the reason is not determinism but *engagement*: at 32 the arm under test
stops being the arm under test.

## Recommendation

| use | concurrency | why |
|---|---|---|
| bank authoring, bulk non-graded work | **32** (or higher) | fallback is harmless; take the 19% |
| any graded LLM arm | **16** | keeps engagement high; a timeout silently swaps in a better composer |
| any run whose figure will be quoted | **report engagement beside the score** | the correlation above makes the score unreadable without it |

The operator's 64-slot ceiling is not the binding constraint. **The 120 s read
timeout is**, and it is the knob worth revisiting before concurrency is.

## Threats

* **Condition C (workers=1) was deferred** on cost — 5.6 hours against 7 minutes
  (PROTOCOL §5). So this bounds what raising concurrency costs and **cannot** say
  how much a fully serialised run would recover. H2 is unfalsified, not
  supported.
* **Three repeats.** The sd figures are indicative; no interval is claimed, and
  the unsupported-sd of 16.1 in condition B is driven by a single run (62 against
  32 and 37).
* **One server, one model, one day** — `Ornith-1.5-35B-A3B-W4A16-SYM` per Q12.
  Saturation behaviour is a property of this stack and transfers nowhere.
* **Only the synthesis seam.** The planner and specialist LLM seams have their
  own variance and are untouched; Q2 closes one of three.
* **r = +0.62 on n = 9** is a direction, not an effect size. The *mechanism* is
  certain — fallback lands on a composer measured at 0.8184 — and the
  correlation is corroboration rather than the evidence.
