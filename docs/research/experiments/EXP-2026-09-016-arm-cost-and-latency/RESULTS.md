# RESULTS — EXP-2026-09-016, what each answering path costs

`Q38` is answered. The cost half of `C-012` now has a number, in two regimes,
with the concurrency stated beside each.

---

## A-1 — Throughput, 284 development questions, 24 workers, one instance

| path | wall clock | summed machine time | median per question | p95 | model calls | tokens | returned evidence |
|---|---|---|---|---|---|---|---|
| hand-written templates | 3.7 s | 0.02 h | 0.111 s | 1.840 s | 0 | 0 | 259 / 284 |
| schema-derived | 14.0 s | 0.09 h | 1.018 s | 2.295 s | 0 | 0 | 198 / 284 |
| model writes the query | **11,407.8 s** | **70.32 h** | **638.713 s** | 2,464.033 s | 413 | 5,818,658 | **96 / 284** |

The model arm spent 1.45 calls per question — it retries — and 5.8 million
tokens, read off the transport by the meter rather than estimated.

`C-012`'s cost half is supported, and by a wide margin. It is also the first
time the margin has had a number attached at a stated concurrency.

## A-2 — The published 40,000x figure does not survive being made like-for-like

`docs/research/reports/2026-09-05-full-report.md` reports "about four seconds"
against "roughly two days of machine time", a ratio of "about forty thousand
times", and the October pitch names it as one of two numbers that must land.

**The two-day half reproduces.** Summed machine time for the model arm is
**2.93 days** tonight against that report's "roughly two days" — same quantity,
same order, on a different night.

**The ratio does not, because it divides two different quantities.** Four
seconds is the deterministic arm's *wall clock*; two days is the model arm's
*summed machine time*. At 24 workers those differ by a factor of 24 before any
real effect. Reconstructing that same construction on tonight's numbers gives
**68,416x** — which confirms how the figure was formed and shows it is not
stable.

Held to one quantity at a time, on the same 284 questions at the same
concurrency on the same machine:

| comparison | against hand-written | against schema-derived |
|---|---|---|
| wall clock | **3,083x** | 815x |
| summed machine time | **2,923x** | 760x |

**Recommendation for the pitch.** Quote **about three thousand times**, or say
"three to four orders of magnitude" and move on. It is defensible under
questioning, which forty thousand is not, and it is not a weaker claim in any
way an audience will feel.

## A-3 — The expensive path also answers far less often

| path | questions returning evidence |
|---|---|
| hand-written templates | 259 / 284 |
| schema-derived | 198 / 284 |
| model writes the query | 96 / 284 |

Returning evidence is not the same as being correct, and this is not a
correctness figure — `EXP-2026-09-005` and `-007` hold those. But it means the
cost comparison understates the gap: the model arm is roughly three thousand
times more expensive *and* comes back empty on two questions in three.

The honest sentence is "more expensive and less useful", not "more expensive".

## A-4 — Reporting discipline

The two regimes are reported apart, as pre-registered. No dollar figure is
given: the models are served on hardware this project does not pay for per
token, so seconds and tokens are the honest units and a dollar amount would be
invented.

`ISSUES.md` `I-1` records that this arm answers nothing at all, with no model
call, if run without the settled configuration — the failure mode that would
have produced a confident, plausible, entirely inverted cost table.
