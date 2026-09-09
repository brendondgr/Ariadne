# EXP-2026-08-018 — The gates fire. The composer is 67× slower and worse.

**Status:** complete. All five tests report, and the pre-registered decision rule
selects its third branch: **keep, never default**.

## The headline

| arm | rep | composer used | claims | unsupported | gold-in-claims | wall s |
|---|---:|---|---:|---:|---:|---:|
| deterministic | 1 | `deterministic` 120 | 730 | **0** | **0.8184** | **116.3** |
| llm_claims | 1 | `llm` 104, fell back 16 | 614 | 33 | 0.6765 | 6,739.5 |
| llm_claims | 2 | `llm` 96, fell back 24 | 528 | 36 | 0.7045 | 8,491.5 |
| llm_claims | 3 | `llm` 96, fell back 24 | 554 | 32 | 0.6641 | 8,216.4 |

## T2 first, because it is why this experiment exists

**The verifier gates fire on LLM-proposed claims: 32–36 cuts per run.** Against
**zero** in every deterministic configuration ever measured.

EXP-2026-08-014 ablated all four gates over 888 claims and found each cut
nothing. That was true and vacuous — the deterministic composer builds claims
*from* retrieved records, so a violating claim is unconstructible. **C-017's
central property has never been testable until now**, and it now is.

Which gate does the work is lopsided and specific:

| gate | cuts |
|---|---:|
| `correlated` | **92** |
| `grounded` | 19 |
| `resolvable` | 1 |
| `cited` | **0** |

*(across all three repeats; the harness records at most four reasons per answer,
so these are relative weights rather than exact totals.)*

**The model's characteristic error is asserting a cross-source correlation the
join index does not back** — claiming a CAPEC pattern corresponds to an ATT&CK
technique when no shared join value links them. It essentially never emits an
uncited claim, which is what a well-followed prompt looks like; it does invent
*relationships between* things it correctly cited.

That is exactly the failure a claim-level verifier is for, and exactly the one a
prose-only LLM seam would never have exposed.

## T1 — engagement, and a caveat that changes how to read it

The composer runs on **96–104 of 120** questions. The 16–24 fallbacks are **not
composer defects**: 14, 23 and 22 of them respectively are **read timeouts at
120 s**. Only one or two per run are malformed JSON, and one hit the token
budget.

**So the engagement rate is a property of the timeout, not of the model.** A
longer timeout would raise it and make T5 worse; the two cannot be improved
together. Reported as measured rather than tuned.

The hybrid caught every one and recorded `fallback_reason` — the fallback path
works, which is its own small result.

## T3 — grounding is materially worse

**0.6817 mean (sd 0.0207) against the deterministic composer's 0.8184** — a gap
of **−0.1367** in the share of gold identifiers reaching a *supported* claim.

Retrieval was identical in both arms, so this is composition alone. Two causes
compound: the LLM proposes fewer claims (565 mean against 730, **−23%**), and
some of what it does propose is then cut. **Under-enumeration is the larger
term** — this is the same weakness recorded elsewhere as the composer's
under-enumeration ceiling, now measured against a deterministic control.

## T4 — variance, and the first LLM-arm spread in the record

| metric | mean | sd | range |
|---|---:|---:|---|
| claims | 565.3 | **44.1** | 528 – 614 |
| unsupported | 33.7 | 2.1 | 32 – 36 |
| gold-in-claims | 0.6817 | **0.0207** | 0.6641 – 0.7045 |

Every LLM figure in this study is n=1. This is the first with a spread attached,
and it is **not negligible**: ±0.02 on gold means two runs of the same arm on the
same questions can differ by more than several inter-arm gaps this project has
reported elsewhere.

**This run predates the seeded sampling landed the same day**, so it is the
*unseeded* baseline and is reused as condition A of EXP-2026-08-019.

## T5 — cost

**116.3 s against a mean of 7,815.8 s: 67× slower.**

C-004 priced the deterministic path at 637× cheaper than the LLM-planned arm.
This is the same shape of result for a different seam, and it is the reason the
decision below is not "keep and default to it".

## The decision, against the rule written before the numbers

PROTOCOL §5 pre-registered three branches:

* **Delete** — required a high fallback rate *or* gates never firing. Gates fired
  32–36 times per run. **Not selected.**
* **Keep** — required only that the gates fire. Satisfied.
* **Keep-but-never-default** — required gates firing *and* T3 or T5 materially
  worse. **T3 is −0.1367 and T5 is 67×. Selected.**

**`OpenAICompatibleComposer` stays, as an instrument rather than a shipping
path.** It is the only configuration in which C-017's property can be tested at
all, and deleting it would have made that property permanently unfalsifiable —
which is precisely the trap C-017 has been in since it was written.

`SYNTHESIS_LLM_CLAIMS` stays **default-false** and should never be enabled
outside an experiment. The recommendation is recorded in Q20.

## Threats

* **One model, one quantisation, one day.** Per Q12 the relay now serves
  `Ornith-1.5-35B-A3B-W4A16-SYM`, not the Gemma build the July arms used.
  Nothing here transfers to another model, and the 67× is a property of a 35B
  MoE at 4-bit on this hardware.
* **The gates firing is not the gates being right.** A cut claim might have been
  true. This shows the mechanism engages; whether each cut was correct needs a
  judge and was not bought.
* **T3's gap is partly under-enumeration, not unfaithfulness.** Fewer claims
  means less gold carried, independent of whether what *was* claimed is sound.
  The two are not separated here.
* **The 120 s timeout is load-bearing** and was not chosen for this experiment —
  it is the standing `.env` value. A different timeout moves T1 and T5 together.
* **Three repeats is a small n for a spread.** The sd figures are indicative,
  not confidence intervals.

---

# AMENDMENTS

## AMENDMENT A-1 (2026-09-09) — `n_runs` was 1 for a three-repeat arm; "wall s" is summed latency, not wall clock; `data/metrics.json` restructured

**`n_runs`.** `manifest.yaml:45` recorded `n_runs: 1` while the entrypoint ran
`--repeats 3` and every LLM-arm value in `metrics.values` is a mean and sample
sd over three runs (`n: 3`). OPEN_QUESTIONS Q34 flagged this. **Old → new:**
`n_runs: 1` → `3`. The deterministic control ran once (it is byte-reproducible)
and its values keep `n: 1`.

**"wall s" is not wall clock.** `wall_s_total` in the sweep output is
`sum(elapsed_s)` over the 120 per-question rows (`scripts/composer_arm_sweep.py`
line 212), i.e. summed per-request latency at 16 concurrent workers, not elapsed
time. So the "wall s" column of §"The headline", "116.3 s against a mean of
7,815.8 s" in §T5, and the manifest's `wall_s_llm_arm` / `wall_s_deterministic_arm`
are summed latencies. The **67× ratio is unaffected** (both sides are the same
quantity). `compute.wall_clock_hours: 6.5` was Σ latency over the three LLM
repeats (23,447.4 s → 6.5 h), not the time the run took; the elapsed time at 16
workers was never recorded (EXP-2026-08-019 reports ≈398 s per w16 repeat for
its seeded runs, which is the right order of magnitude but not this run).
**Old → new:** `wall_clock_hours: 6.5` → `null`, with an ISSUES entry. The
metric names `wall_s_*` are kept because they are the artifact's names; read
them as summed latency.

**`data/metrics.json`.** The sweep emitted a JSON *list* of four run objects, so
the manifest's aggregates (33.6667, 0.6817, 565.3333, 98.6667, 7815.8) appeared
nowhere in it — they are means the sweep never wrote. The file is now
`{runs: [the four objects, unchanged], manifest_metrics: {...}}`. Verified
2026-09-09 by recomputing from the run objects: unsupported 33/36/32 → 33.6667
sd 2.0817; gold 0.6765/0.7045/0.6641 → 0.6817 sd 0.0207; claims 614/528/554 →
565.3333 sd 44.1059; engaged 104/96/96 → 98.6667 sd 4.6188; wall_s 6739.5/
8491.5/8216.4 → 7815.8 (sd 942.2 from the rounded inputs; the recorded 941.4 is
a rounding difference and is left as recorded). No script reads this file
(`make_arm_comparison.py` reads only the July arms), so nothing else changed.

## AMENDMENT A-2 (2026-09-09) — the primary metric now names a recorded key

`metrics.primary` was `unsupported_claims_cut_by_the_verifier`, a descriptive label that matched no key in
`metrics.values`, so `INDEX.md` and `CURRENT.md` rendered this experiment's
headline as "not recorded". It now names `unsupported_claims_llm_arm` — the mean number of claims the verifier cut per LLM-composer run. No value changed.
