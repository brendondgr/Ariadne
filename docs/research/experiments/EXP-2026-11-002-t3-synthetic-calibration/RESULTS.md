# RESULTS — EXP-2026-11-002 Label-free calibration (kill test T3)

## 1. Headline

**Killed by the pre-registered rule's second clause; the first clause held.** At α = 0.10:
- **The zero-label threshold held on real questions.** Unweighted miscoverage is **0.091**
  (95% CI 0.065–0.120) and stratified is **0.084**. Both are within α + 0.02, and neither is
  vacuous.
- **Stratification failed the rule.** By vocabulary distance it moved *further* from α
  (|0.084 − 0.10| = 0.016 against 0.009), so "stratified is better" fails, and the rule as
  written kills the experiment.

The zero-label unweighted threshold answered **0.317** of real questions, against 0.189 for
SPI-30 and 0.127 for OnlyReal-30. Both label-using methods over-covered, at 0.046 and 0.031.

## 2. Results table

From `data/evaluate.json`. There are 3,792 synthetic questions (948 entities × 4 tiers, no
rewording dropped) and 417 real evaluation questions (T1–T5, both banks, minus 30 labelled).
One system run.

| Calibrator | labels | Q | miscoverage (95% CI) | answer rate | selective error | mean set size | full-set rate |
|---|---|---|---|---|---|---|---|
| OnlySynth-unweighted | 0 | 0.9887 | **0.091** (0.065–0.120) | **0.317** | 0.083 | 2.41 | 0.204 |
| OnlySynth-stratified | 0 | per stratum 0.980 / 0.993 / 0.983 | **0.084** (0.058–0.113) | 0.321 | 0.090 | 2.44 | 0.201 |
| SPI-30 (β = 0.4) | 30 | 0.9966 | 0.046 (0.026–0.065) | 0.189 | 0.063 | 3.07 | 0.257 |
| OnlyReal-30 | 30 | 0.9983 | 0.031 (0.017–0.048) | 0.127 | 0.075 | 3.58 | 0.288 |

Over 100 redraws of the 30 labels, miscoverage is 0.098 ± 0.038 for SPI-30 and
0.095 ± 0.063 for OnlyReal-30. The fixed draw is the headline above.

Miscoverage by split, unweighted / stratified:
- dev (n=297): 0.088 / 0.088;
- confirm (n=120): 0.100 / 0.075.

Selective error on confirm is 0.171 / 0.162, against 0.044 / 0.062 on dev.

Unweighted miscoverage by real tier (n):

| T1 id (59) | T2 id fragment (58) | T3 name (99) | T4 paraphrase (99) | T5 description (102) |
|---|---|---|---|---|
| 0.017 | 0.000 | **0.182** | 0.071 | 0.118 |

Top-1 accuracy:
- **synthetic:** id 0.776, name 0.658, paraphrase 0.246, description 0.749;
- **real:** T1 0.898, T2 0.793, T3 0.424, T4 0.636, T5 0.725.

Mean vocabulary distance is 0.368 for synthetic questions and 0.395 for real ones.

## 3. Figures

None.

## 4. Interpretation

- **The idea underneath survives in narrower form.** Card-generated grounding questions, with
  no real labels at all, gave a conformal threshold whose realised miscoverage on real questions
  was 0.091 against a 0.10 target. That is the claim the literature expected to fail (OnlySynth
  under-covers in SPI's experiments).
- **The zero-label threshold beat both label-using baselines in practice.** It answered about
  1.7× as often as SPI-30 and 2.5× as often as OnlyReal-30, at similar selective error.
- **What died is the specific correction.** Stratifying by vocabulary distance did not move
  miscoverage toward α. Pooled, there was no shift for it to correct (synthetic and real
  distances differ by 0.03).
- **The real under-coverage is conditional, by tier.** Exact-name questions miss 0.182, and
  description-only questions 0.118. Distance strata do not capture that axis. A tier-conditional
  (Mondrian-by-tier) threshold is the natural next variant; it would be a new, separately
  registered test.

## 5. Threats to validity

- **The real questions are themselves model-authored.** The T4/T5 variants were written by a
  model from gold questions, and the synthetic rewordings by another, so the two distributions
  are closer than human questions would be to either. This is the main reason the result may
  not transfer.
- **One decider at temperature 1.0, one rewording model** (`swift15-flashnext`).
- **Confirmation selective error is 0.17**, high against dev's 0.04 to 0.06. Answered
  questions on the holdout are wrong noticeably more often.
- **Distance tertile cuts were fixed on synthetic data** (0.273 / 0.500). Real strata sizes are
  122 / 187 / 108.

## 6. What surprised us

- **Naive synthetic calibration held its target here.** It fails in the paper that defines it.
- **Exact names were the hardest tier,** not descriptions: real T3 top-1 accuracy is 0.42. A
  name like "Phishing" collides with dozens of similarly named entities across both stores.
