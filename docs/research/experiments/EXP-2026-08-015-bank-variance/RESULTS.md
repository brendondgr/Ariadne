# EXP-2026-08-015 — The first interval, and a live defect the fixed banks never reached

**Status:** complete. Twenty bank-runs over two populations, retrieval only.

## The headline

| population | templates | generic | templates − generic | 95% CI |
|---|---|---|---|---|
| **catalogue** (ATT&CK + CAPEC) | 0.9900 (sd **0.0225**) | **1.0000** (sd **0.0000**) | **−0.0100** | [−0.0233, **+0.0000**] |
| **identity** (foreign schema) | 0.2392 (sd 0.0674) | 0.8514 (sd 0.0890) | **−0.6121** | [−0.6720, −0.5530] |

Ten anchor-disjoint banks per population, **measured disjoint** rather than
assumed: 0 overlapping pairs out of 45, 0 shared anchors, in both populations
(see ISSUES I-1 for why that check exists).

**The upper bound of the catalogue CI is exactly +0.0000.** Across 300 fresh
anchors the template arm never once beat the generic arm on retrieval — not on a
single bank. That is a stronger statement than the small mean.

## What the intervals settle

**Q2's premise was wrong, and stating that is the first result.** "Re-run each
arm ten times" would have produced ten byte-identical numbers: both arms are
LLM-free, so pipeline variance on this path is **zero by construction**. The
variance that exists is in which anchors you drew, and nothing in the record had
ever measured it.

**H1 — the catalogue gap is small with an interval touching zero. Held.**
Consistent with EXP-2026-08-007's judged finding that the arms are
indistinguishable where the templates were written to serve.

**H2 — the identity gap is large, clear of zero, and noisier. Held.** −0.6121
with a CI nowhere near zero. It also *confirms* EXP-2026-08-011's +0.5893 point
estimate from an independent draw, which that experiment could not do for itself.

**H3 — within-arm sd is non-trivial in both populations. Refuted, informatively.**
The generic arm on the catalogue has sd **exactly 0.0000**: 1.0000 on all ten
banks, 300 anchors, no exceptions. The variance on the catalogue is *entirely*
the template arm's, and §"the defect" shows it is not sampling noise at all.

So a single 30-question draw is a noisy instrument **on the identity schema**
(sd 0.067–0.089, meaning ±0.07 is ordinary) and is not noisy at all on the
catalogue. Blind figures over foreign schemas need intervals; blind retrieval
figures over the catalogue are stable.

## The defect this found

The template arm's entire catalogue variance is **three questions in two banks**,
and they are not noise — they are one template failing on a whole class of
anchor:

| bank | case | anchor | abstraction | gold | retrieved |
|---|---|---|---|---|---|
| 9006 | H-ABS-01 | CAPEC-466 | Standard | CAPEC-94 | **0 records** |
| 9006 | H-ABS-02 | CAPEC-207 | Standard | CAPEC-22 | **0 records** |
| 9010 | H-ABS-01 | CAPEC-182 | Standard | CAPEC-137 | **0 records** |

`capec_hierarchy_chain` emits a **fixed two-hop chain**:

```
.out("CHILD_OF").as("parent").out("CHILD_OF").as("grandparent")
.select("ap","parent","grandparent")
```

That `select` is an inner join over three positions. All three anchors are
**Standard** abstraction and their parent is already **Meta** — CAPEC-94,
CAPEC-22 and CAPEC-137 each have zero parents — so there is no grandparent, the
select matches nothing, and the query returns **not even the parent the gold
asked for**.

**This is the same class of defect as the outer-join failure fixed in
EXP-2026-08-004 and EXP-2026-08-006**, in a template those fixes did not reach.

**Why no earlier bank caught it.** holdout-v1's `H-ABS` anchors happened to be
Detailed-level, three levels below Meta, so the two-hop chain resolved. The
defect is invisible to any bank whose abstraction anchors sit low enough, and two
fixed banks are two samples. **Resampling found in ten draws what two banks had
hidden through six experiments** — which is a better argument for this method
than the intervals are.

**Deliberately not fixed here.** A builder change moves recorded numbers and
needs its own experiment plus a recorded-answer regression diff. Filed as Q22.

## An honest reading of the catalogue number

`gold_in_evidence` on the catalogue is **saturated for the generic arm** and
within 0.01 of saturation for the template arm. A metric at ceiling cannot
detect improvement, and this experiment's catalogue half should be read as:

* **positive:** retrieval generalises. Ceiling is not an artifact of the two
  co-authored banks — it holds on 300 anchors no arm had seen, which extends
  EXP-2026-08-006's "saturated on both banks" from 2 banks to 12.
* **limiting:** the catalogue gap **cannot be priced by this metric**. The
  −0.0100 is real but it is a coverage cliff on one template, not a measure of
  how the arms differ. Pricing the catalogue gap requires a *judged* metric,
  which is the deferred half.

The identity half has no such problem: 0.2392 against 0.8514 is nowhere near a
ceiling, and its interval means what it says.

## Threats

* **Retrieval, not correctness.** Retrieval is necessary, not sufficient. The
  judged half is deferred by decision, not by oversight; `experiment_untruncated`
  wrote exactly the artifacts a judge pass consumes.
* **Machine-authored phrasing** (ISSUES I-3). These banks are as *blind* as
  holdout-v1 but explore a narrower band of phrasing than a human would. The
  interval is over **anchor draws**, not over ways of asking.
* **Identity banks are unequal in size** (17–26 questions, ISSUES I-2) because
  the pool thins as exclusions accumulate. Per-bank n is in `metrics.json`; the
  identity sd is an upper bound on stability, not a like-for-like of the
  catalogue's.
* **The identity figures are not comparable to EXP-2026-08-011's.** Both arms
  score higher here (0.2392/0.8514 against 0.1140/0.6923) because the bridge and
  routing fixes landed in between and the bank composition differs. The **gap**
  replicates; the levels are a different measurement.
* **Two populations, two scorers.** The catalogue uses `retrieval_coverage`
  against bank gold; identity uses `identity_sweep`'s own per-question recall
  against tenant gold. They are reported side by side and **never pooled**.

---

# AMENDMENTS

## A-1 (2026-08-24) — Q22 fixed: the catalogue gap was one template, and closing it takes the gap to exactly zero

The defect this experiment found is repaired. `capec_hierarchy_chain` now makes
**both** ancestor hops `optional()` instead of requiring parent *and* grandparent
in one `select`, which is the same outer-join correction EXP-2026-08-004/006
applied to the bridge templates. The normalizer gained one guard: an "ancestor"
equal to the anchor is skipped, since `optional()` re-labels the anchor into the
parent slot when it has no parent.

**Re-run over the same ten banks, deterministic arm, same runner:**

| | before | after |
|---|---:|---:|
| mean `gold_in_evidence` | 0.9900 | **1.0000** |
| sd | 0.0225 | **0.0000** |
| banks below ceiling | 2 (9006, 9010) | **0** |

**Regression: 15 of 300 answers changed, and all 15 are `H-ABS-*`** — the
question kind this template serves. Nothing else moved, on any bank, once clock
keys (`timestamp`, `elapsed_s`, `wall_s`, `timing_ms`, `run_meta`) are excluded.

Of those 15, three were the empty results this experiment reported and now return
the ancestor gold asks for (`bank9006/H-ABS-01` went from `[]` to
`['CAPEC-466', 'CAPEC-94']`). The other twelve already scored 1.0000 and still
do, with **identical retrieved ancestors** — they changed only in record ordering
and dedup metadata.

### What this changes in the headline

**The catalogue row of §"The headline" is superseded.** With the defect fixed:

| population | templates | generic | difference |
|---|---|---|---|
| catalogue | **1.0000 (sd 0.0000)** | 1.0000 (sd 0.0000) | **0.0000** |

The −0.0100 was *entirely* the defect. Both arms are now saturated at exactly
1.0000 with zero variance across 300 unseen anchors, which strengthens rather
than weakens the reading in §"An honest reading of the catalogue number": the
metric is at ceiling for **both** arms and can no longer distinguish them at all.
Pricing the catalogue gap still requires a judged metric.

**The identity figures are untouched** — that population never routed to this
template, and its runs were not re-executed.

**What does not change:** this experiment's *method* result stands exactly as
recorded. Resampling found in ten draws a defect two fixed banks had hidden
through six experiments, and the fix confirms it was real rather than a scoring
artifact. That remains the strongest argument here.

## AMENDMENT A-2 (2026-09-09) — the pre-fix catalogue numbers were still canonical in the manifest; date, sample size, model and pointers corrected

**Withdrawn values.** A-1 superseded the catalogue row of §"The headline" on
2026-08-24, but `manifest.yaml:70–72` and `data/metrics.json` still carried the
pre-fix figures as current, and the `hypothesis` field (line 21) still reads
*"H1 … HELD (−0.0100, upper bound exactly +0.0000)"*. The manifest now records:

* `catalogue_templates` **0.9900 (sd 0.0225, n 10)** → withdrawn 2026-08-24,
  replaced by `catalogue_templates_post_q22` = **1.0000 (sd 0.0000, n 10)**;
* `catalogue_paired_difference` **−0.0100 (sd 0.0225, n 10)** — the value the
  `primary` label `gold_in_evidence_templates_minus_generic` referred to on the
  catalogue — → withdrawn 2026-08-24, replaced by
  `catalogue_paired_difference_post_q22` = **0.0000 (sd 0.0000, n 10)**;
* `primary` now names `catalogue_paired_difference_post_q22`.

The hypothesis text is not rewritten; read H1 as *held, and the residual gap was
a defect: after Q22 the gap is exactly 0.0000 and H1's interval question is
moot because both arms sit at ceiling on every bank* (A-1). The identity
values are unchanged.

**The post-fix numbers have no surviving artifact.** A-1 reports a re-run "over
the same ten banks, deterministic arm, same runner" giving 1.0000 sd 0.0000 and
"15 of 300 answers changed". The Q22 commit `152639b` (2026-08-24 17:18) touched
only RESULTS.md, CLAIMS/OPEN_QUESTIONS, `builder.py` and `normalizer.py`; the
on-disk `catalogue/runs/**` trees are the *pre-fix* runs (no file newer than
`catalogue/metrics.json`, 14:32, and rescoring bank 9006 / 9010 with
`retrieval_coverage.score_arm` gives 0.9333 / 0.9667, the pre-fix values). So
the post-Q22 values are recorded from A-1's prose and are reproducible only by
re-running the sweep at or after `152639b`. Recorded in ISSUES I-4.

**Sample size.** `manifest.yaml:40` said `n_examples: 483 # 300 catalogue + 183
identity`. The ten identity banks hold 26 + 24 + 18 + 18 + 18 + 17 + 18 + 18 +
18 + 18 = **193** questions (per-bank `n` in `identity/metrics.json`; counted
again in each `bank.json`). **Old → new:** 483 → **493** (300 + 193).

**Date.** `date_completed: 2026-08-23` preceded `date_started: 2026-08-24`. The
banks were authored 2026-08-24 13:49–14:05, the folder committed at `c8a4a3e`
14:34 and A-1 at `152639b` 17:18. **Old → new:** `2026-08-23` → `2026-08-24`.

**Model.** `llm.model` was the alias `relay/skynet@2026-08-23`. Every
`bank.json` records `author_model: "skynet …"` — the alias, not a model. The
banks were authored on 2026-08-24, for which `docs/evaluation/README.md`
§"The model behind skynet" records `MIRALABS/Ornith-1.5-35B-A3B-W4A16-SYM`
(operator, from the serving side; the same model EXP-2026-08-018/019 identify
later that day). **Old → new:** `relay/skynet@2026-08-23` →
`relay/Ornith-1.5-35B-A3B-W4A16-SYM@2026-08-24`. The basis is the README era
table, not a response envelope (ISSUES I-5). The Author is not in the answer
path, so no reported number depends on this.

**Pointers.** POINTERS rows 9–10 recorded *set digests* against the directory
`docs/evaluation/variance-2026-08-23/`; the validator hashes a directory as a
tree, so they could never verify. Both old digests (`sha256:6ac87b79…`,
`sha256:f1b8bf75…`) still reproduce under their own definition (SHA-256 over
sorted files of path bytes + contents), i.e. the banks are unchanged. Replaced
by a tree hash over `banks/` (`sha256:89c0efc0…`, 621,212 B) and ten file
hashes, one per identity `bank.json`, all computed with
`utils.research_record.hashing` on 2026-09-09.

**A count.** §"The headline" says "300 fresh anchors". `holdout_meta.anchor`
over the 300 catalogue questions gives **299** distinct anchors: bank 9006
draws one anchor twice within the bank. Cross-bank disjointness (0 overlapping
pairs of 45) is unaffected.
