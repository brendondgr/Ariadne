# PROTOCOL — EXP-2026-11-002 Label-free calibration: conformal thresholds set on card-generated questions, applied to real ones

Written 2026-11-13, before any code for this experiment ran. Kill test T3.

## Question

An abstention threshold for entity grounding normally needs hundreds of labelled real
questions. If questions are generated from the source card, so their right answer is known by
construction, does a conformal threshold calibrated only on them hold its target miscoverage
on real, human-style questions? And does stratifying by a vocabulary-distance covariate
correct the shift?

## Hypothesis

- **H1:** the distance-stratified zero-label threshold keeps realised miscoverage on real
  questions within α + 0.02 (α = 0.10).
- **H2:** it is closer to the target than the unweighted zero-label threshold.

The published evidence (OnlySynth in SPI, arXiv 2505.13432) expects the unweighted variant to
under-cover.

## Setup

- **Task:** entity grounding. Given a question, choose its anchor entity from a candidate list.
- **Candidates:** the identical construction as EXP-2026-11-001 (pinned ids, else BM25 top-5
  per dataset). This experiment reuses that experiment's candidate stage.
- **Scorer:** the decider on `:7500`, `choice` over the candidates plus "none of these",
  temperature 1.0. `p(c)` is its probability for candidate `c`.
- **Nonconformity score:** `s = 1 − p(gold)`. If the gold entity is not among the candidates,
  `s = 1`.
- **Prediction set:** `{c : 1 − p(c) ≤ Q}`. The system answers when the set holds exactly one
  candidate, and otherwise abstains or asks.
- **Vocabulary distance** of a question: the share of its content tokens absent from the
  dataset's name and alias vocabulary. It is cut into three strata at the synthetic tertiles,
  fixed on synthetic data before any real question is scored.

### Synthetic questions (zero real labels)

- Entities are sampled across labels, weighted by degree band. They exclude every anchor in
  either variant bank and in `drawn_anchors.json`.
- Each entity is written at four tiers:
  - **id**, e.g. "What does T1047 do?";
  - **exact name**;
  - **paraphrase:** the model on `:9090` rewrites the name conceptually without its words;
  - **description-only:** the model rewrites the node description as a one-line reference.
- A leak check rejects any paraphrase or description containing a name token
  (df ≤ 1%), an alias or the id. Rejected items are regenerated once, then dropped and
  counted.
- Question frames come from a fixed list of 12 templates (describe and relation frames),
  chosen at random per item.

### Calibrators, each producing `Q`

1. **OnlySynth-unweighted:** the ⌈(1−α)(N+1)⌉-th smallest synthetic score.
2. **OnlySynth-stratified:** the same within each distance stratum (Mondrian). A real question
   uses its own stratum's `Q`.
3. **OnlyReal-30:** split conformal on 30 real labelled questions.
4. **SPI-30:** Algorithm 1 of SPI with m = 30 real and N synthetic scores, β = 0.4, using the
   paper's window, rank-bound and transporter formulas (eq. 6–8, 11).

Variants 3 and 4 use the same 30 real questions. These are drawn with a fixed seed from the
development bank, and are excluded from evaluation.

## Data

- **Real evaluation set:** tiers T1–T5 of both variant banks, single-source only, minus the 30
  calibration questions. T6 is excluded because it has no gold anchor.
- **Gold anchor:** `slot_gold.json`.
- **Synthetic set:** 1,000 entities × 4 tiers, before leak drops.

## Metrics

- **miscoverage:** over real evaluation questions, the share whose gold is not in the
  prediction set. Reported pooled and per stratum, with bootstrap 95% CIs (2,000 resamples).
- **answer_rate:** the share with a singleton set.
- **selective_error:** the share of singleton answers that are wrong.
- For SPI and OnlyReal, the mean and SD over 100 redraws of the 30 real labels. The fixed draw
  is the headline.

## Baselines

OnlyReal-30 (label-using, guaranteed) and SPI-30 (label-using, synthetic-assisted) are the
standard methods. OnlySynth-unweighted is the naive zero-label method the literature reports
failing.

## Procedure

```bash
KILLTESTS_SMOKE=1 uv run python scripts/killtests_run.py --only t3
uv run python scripts/killtests_run.py --only t3
uv run python -m utils.killtests.analysis t3
```

## What would falsify this

**Kill rule**, evaluated mechanically on the pooled real evaluation set. The idea is dead if
either holds:
- neither zero-label variant has `miscoverage ≤ α + 0.02 = 0.12`;
- `|miscoverage(stratified) − α| ≥ |miscoverage(unweighted) − α|`, i.e. stratification is no
  better.

## Pre-run amendments (2026-11-13, after the smoke run, before the full run)

1. **"None of these" is a label.** In the first smoke run, about a fifth of synthetic questions
   had no gold entity among the candidates. With their score fixed at `s = 1`, the α = 0.10
   threshold became 1.0: every prediction set was every option, and miscoverage read 0
   vacuously. The label space is therefore the candidates plus "none of these", which the
   decider already scores:
   - the gold label is the gold entity when it is a candidate, else `none`;
   - `s = 1 − p(gold label)`;
   - the system **answers** when the prediction set is a single entity, and **abstains** when it
     is `{none}`;
   - `selective_error` compares an answer with the gold entity.
2. **Vacuity guard.** A calibrator whose threshold is ≥ 1 (the set is every option) is reported
   as `vacuous` and does not count as holding the target. `full_set_rate` and
   `gold_absent_rate` are reported with every miscoverage figure.
3. **Real-question scores come from EXP-2026-11-001's decide stage.** It uses the same
   candidates and the same anchor prompt, so the two experiments share one scorer.
