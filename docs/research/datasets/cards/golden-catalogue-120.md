# Dataset Card — Ariadne Golden Catalogue (120 questions)

**Version:** `120q-2026-07` · **Size:** 120 questions · **Authored by:** this project
**Used by:** EXP-2026-07-001 … -007, -009, -010

---

## What it is

The evaluation question set behind every judged number in this record. Each
question is paired with **computed gold** — gold assertions derived
programmatically from an independent parse of the raw MITRE sources rather than
hand-annotated — plus an authored plan, and an `expected_template` field naming
the query template that should answer it.

Questions span categories prefixed `A-` (ATT&CK), `C-` (CAPEC), and `F-`
(federated), across four difficulty tiers (easy, medium, hard, adversarial).
Category sizes range from **1 to 10 members**.

## How it was built

Generated from a gold bank that parses the raw ATT&CK and CAPEC sources
independently of the pipeline's own ingest, so the gold does not inherit the
pipeline's bugs. Includes negatives (questions that must surface nothing) and
boundary cases computed from the same bank.

## ⚠️ Limitations — read before quoting any number derived from this set

These are not minor caveats. They are the reason C-001 is `partial` and not
`supported`.

1. **There is no holdout.** All 120 questions were used during development.
2. **The questions were co-authored with the templates that answer them**,
   commit-for-commit, and each ships its `expected_template`. The set cannot
   distinguish *capability* from *coverage*: a near-ceiling score is exactly what
   a coverage artifact would look like. See [`../../DECISIONS.md`](../../DECISIONS.md) D-006.
3. **Every question is anchored** — each names an entity or an id. Nothing here
   measures open-ended analyst questions, which is precisely the regime where a
   template router is weakest. The design's *price* is unmeasured (C-014).
4. **Categories are small.** With 1–10 members per category, a single case moves
   a category mean substantially. Do not read per-category tables as stable.
5. **Anchors were sampled by mapping richness, not uniformly**, which biases the
   federated slice toward entities that happen to have rich cross-source
   mappings.
6. **Its own gold has not been audited.** The computed-gold approach is a partial
   answer to the KGQA benchmark-integrity problem — where average factual
   correctness across 16 published datasets is 57% — but "computed" is not
   "verified". See [`../../RELATED_WORK.md`](../../RELATED_WORK.md) `[G-KGQAGEN]`.

## What would fix it

30 questions authored blind by someone other than the author, against a frozen
template set, sampling anchors uniformly. That is open question **Q1**, it costs
about four days, and it gates the value of every other result in this record.

## Access

Generated as part of the evaluation set under `utils/specialists/evalset/`.
Rebuilt by the pipeline's own tooling; not distributed separately.

## Licence

Authored by this project. The *content* it asks about derives from MITRE ATT&CK
and CAPEC — see [`../DATASETS.md`](../DATASETS.md) and
[`NOTICE`](../../../../NOTICE).
