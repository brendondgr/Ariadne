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

---

# AMENDMENTS

## AMENDMENT A-1 (2026-09-09) — `n_runs` was 1 for three-repeat conditions; a latency sd corrected; the "wall clock per repeat" figures have no artifact; aggregates back-filled into `data/metrics.json`

**`n_runs`.** `manifest.yaml:45` recorded `n_runs: 1`; conditions B and D each
ran `--repeats 3` and every value in `metrics.values` is over three runs per
condition (condition A is EXP-2026-08-018's three unseeded repeats). Flagged by
OPEN_QUESTIONS Q34. **Old → new:** `n_runs: 1` → `3`.

**One sd.** `per_question_latency_s_w16.std` was `6.5`. Recomputed 2026-09-09
from the pointed `metrics-seeded-w16.json` as `wall_s_total/120` per run:
55.16 / 58.38 / 45.60 s → mean 53.05, sample sd **6.64**. **Old → new:** `6.5` →
`6.6`. Every other manifest value reproduces from the two pointed files:
B claims 518/493/427 (sd 47.0), unsupported 37/32/62 (sd 16.1), gold
0.6212/0.6585/0.6573 (sd 0.0212), fallbacks 15/18/9 (14.0, sd 4.58); D claims
568/588/554 (sd 17.1), unsupported 27/30/32 (sd 2.5), gold 0.6642/0.7386/0.7050
(sd 0.0373), fallbacks 26/26/33 (28.3, sd 4.04); w32 latency 84.51/85.90/86.19 →
85.5 sd 0.9; Pearson r over the nine LLM runs 0.6232.

**Unverifiable figures.** §"Throughput" gives "wall clock per repeat 398 s /
321 s" and the derived "19 % wall clock". Neither pointed file records elapsed
time — `wall_s_total` is `sum(elapsed_s)` over the 120 questions, i.e. summed
per-request latency, which is what the "per-request latency" row and the
manifest's `per_question_latency_s_*` are — and no log survives. The 398/321 s
figures were read from the console at the time and cannot be reproduced from
the record; the "19 %" inherits that. The direction of the throughput claim
does not rest on them (the latency and fallback rows do reproduce). Recorded
in ISSUES; the prose is left as written.

**`data/metrics.json`.** The file held only the two condition blocks (lists of
run objects), so none of the manifest's eight aggregates appeared in it. A
`manifest_metrics` object was added; the condition blocks are unchanged and
still equal the pointed files.

## AMENDMENT A-2 (2026-09-09) — the primary metric now names a recorded key

`metrics.primary` was `gold_in_claims_sd_across_repeats`, a descriptive label that matched no key in
`metrics.values`, so `INDEX.md` and `CURRENT.md` rendered this experiment's
headline as "not recorded". It now names `gold_sd_unseeded_w16` — the reference condition A spread the two levers were compared against. No value changed.
