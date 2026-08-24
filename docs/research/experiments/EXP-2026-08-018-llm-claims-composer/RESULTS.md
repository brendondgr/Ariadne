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
