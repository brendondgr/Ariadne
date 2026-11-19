# RESULTS — EXP-2026-11-016 Era 2 Step 8 follow-up: the anchorless-scan fix, re-run

## 1. Headline

**The fix removes the defect it targeted, but F1 misses by one case.** Counted on T-lazy's
confidently-wrong answers:
- **Dev bank:** 0 anchorless scans (12 → 0 in all).
- **Variants T0–T5:** 1 (16 → 1). The bar was 0.

That case reached a scan by a route the fix does not cover: no id in the question, and a refused
cross-graph step. By the pre-registered rule, **no arm-level conclusion is drawn** from this run
(§7). The gates are reported as measured.

**Gates, T-lazy against E on one commit (458a2841):**
- **G1 fails.** Synonym tier: 0.6250, bar 0.80 (E 0.5500).
- **G2 fails.** Dev lost: 52, bar 25 (E 50).
- **G3 fails.** Original wording: 0.6083, bar 0.98 (E 0.6583).
- **G4 passes on dev and fails on variants.**
  - **Dev:** 0 confidently wrong against E's 4. Paired −4, interval [−8, −1].
  - **Variants T0–T5:** 51 against E's 36. Paired +15, interval [0, +31].

**Against EXP-2026-11-015, paired on the same items:**
- **Dev bank:** T-lazy's confidently-wrong count falls by 12, interval [−19, −6].
- **Original wording (T0):** records_exact rises by +0.092, interval [+0.033, +0.158].
- **Variants:** confidently wrong falls by 10, but the interval crosses zero [−24, +3].
- **E against itself,** the noise floor: dev confidently wrong moved by +3 [0, +7], with no code
  change.

## 2. Results table

Generated from `data/metrics.json` by `scripts/era2_catalog_score.py`. The comparison with
EXP-2026-11-015 is from `scripts/era2_scanfix_compare.py`, and is stored in `data/compare.json`
and under `vs_exp_2026_11_015` in `metrics.json`. The full tables are `tables/scoreboard.md`
and `tables/compare.md`.
- **One run per arm** (`n_runs: 1`). Every figure is a single run.
- **Intervals** are paired bootstraps: 2,000 resamples, seed 20261118. Variants are clustered
  by gold question.

### F1 and the gates (T-lazy against E)

| Check | Bar | T-lazy | E | Pass |
|---|---|---|---|---|
| F1 anchorless-scan CW, variants T0–T5 | 0 | 1 | 0 | **no** |
| F1 anchorless-scan CW, dev | 0 | 0 | 3 | yes |
| G1 synonym tier (T1 records_exact) | ≥ 0.80 | 0.6250 | 0.5500 | no |
| G2 dev lost | ≤ ⌊50/2⌋ = 25 | 52 | 50 | no |
| G3 original wording (T0 records_exact) | ≥ 0.98 | 0.6083 | 0.6583 | no |
| G4 confidently wrong, variants T0–T5 | ≤ E | 51 | 36 | no |
| G4 confidently wrong, dev | ≤ E | 0 | 4 | yes |

### records_exact per tier, and confidently wrong

| Arm | T0 | T1 | T2 | T3 | T4 | T5 | T6 | CW T0–T5 | dev lost | dev CW |
|---|---|---|---|---|---|---|---|---|---|---|
| R | — | 0.3917 | 0.3667 | 0.1782 | 0.0000 | 0.0000 | 0.0667 | 51 | — | — |
| E | 0.6583 | 0.5500 | 0.5667 | 0.4257 | 0.1538 | 0.0385 | 0.0667 | 36 | 50 | 4 |
| T-lazy | 0.6083 | 0.6250 | 0.5167 | 0.5644 | 0.2115 | 0.2308 | 0.0667 | 51 | 52 | 0 |
| T-full | 0.5667 | 0.6333 | 0.5333 | 0.5446 | 0.2115 | 0.2019 | 0.1000 | 44 | 46 | 0 |
| T-lazy-G | 0.6000 | 0.6083 | 0.5583 | 0.6436 | 0.2404 | 0.2500 | 0.1000 | 38 | 57 | 1 |

**T-lazy minus E, paired:**

| Tier | Difference | Interval |
|---|---|---|
| T0 | −0.0500 | [−0.1417, +0.0417] |
| T1 | +0.0750 | [−0.0333, +0.1750] |
| T3 | +0.1386 | [+0.0297, +0.2376] |
| T4 | +0.0577 | [−0.0385, +0.1538] |
| T5 | +0.1923 | [+0.1154, +0.2692] |

### This run minus EXP-2026-11-015, same arm, paired

| Arm | T0 | T4 | T5 | CW T0–T5 | dev lost | dev CW |
|---|---|---|---|---|---|---|
| E (noise floor) | −0.008 [−0.050, +0.033] | +0.038 [0, +0.087] | 0 | +3 [−7, +13] | −1 [−11, +9] | +3 [0, +7] |
| T-lazy | +0.092 [+0.033, +0.158] | 0 [−0.048, +0.058] | +0.029 [−0.039, +0.096] | −10 [−24, +3] | −4 [−12, +4] | −12 [−19, −6] |
| T-full | +0.017 [−0.042, +0.075] | −0.038 [−0.096, +0.010] | −0.029 [−0.077, +0.019] | −11 [−25, +1] | −3 [−10, +3] | −7 [−12, −2] |
| T-lazy-G | +0.050 [−0.008, +0.108] | −0.038 [−0.096, +0.019] | −0.010 [−0.077, +0.058] | +1 [−12, +13] | −3 [−12, +7] | −6 [−11, −2] |

### The scan guard

| Arm | set | questions with a scan refused | fixed by repair | still refused | legitimate scans blocked |
|---|---|---|---|---|---|
| T-lazy | variants | 13 | 11 | 2 | 0 |
| T-lazy | dev | 7 | 7 | 0 | — |
| T-full | variants | 11 | 11 | 0 | 0 |
| T-full | dev | 6 | 5 | 1 | — |
| T-lazy-G | variants | 4 | 4 | 0 | 0 |
| T-lazy-G | dev | 1 | 1 | 0 | — |

## 3. Figures

None.

## 4. Interpretation

### The fix works on the route it was built for

EXP-2026-11-015 traced T-lazy's anchorless scans to two routes. Both are closed in this run:
- **A question writes an id that is not in the graph.** T9999, the retired techniques and
  CAPEC-99999 now plan `describe` on the written id, and the answer is empty and exact.
- **An ATT&CK id is asked against CAPEC.** F-PART-01 now bridges through the join key.

On the dev bank, T-lazy's confidently-wrong count goes from 12 to 0. This is the largest paired
change in the run, and well outside E's run-to-run movement. The guard blocked no legitimate scan:
no refusal stayed on a question whose reference capture is a scan template.

### The guard did real work, unlike in the smoke run

The smoke run saw the guard fire on none of the 18 tuning items. Here it refused a scan on 13 T-lazy
variant questions and 7 dev questions.
- **On the dev bank,** the repair turn fixed all 7.
- **On the variants,** it fixed 11 of 13. The 2 still refused (F-CWE-04 T1, F-PART-02 T5) are
  lost answers, not wrong ones.

So the wording alone does not stop the scans; the hard stop is needed. The run cannot say how
much of the fall from 12 to 0 the wording did by itself (§5).

### F1's one miss is a different route

**T-lazy, F-REV-06 T5.** The question describes the email-collection sub-technique without its id
and asks how CAPEC relates to it.
1. The model resolved the sub-technique (step 1).
2. It tried a CAPEC step chained with `from_step`, which was refused: "from_step 'q2' is on the
   same graph".
3. On the repair turn it wrote a `TaxonomyEntry` scan where the bridge should be. That returns
   262 records against a gold of 2.

The guard did not fire, by design. The question writes no id, and no id lookup failed. This is
the same fallback (a whole-label scan for a step the model could not build), reached from a
refusal that does not say how to bridge.

**T-full, two cases (A-TAC-02 T5, A-MC-01 T4).** Both are vague "which methods…" paraphrases.
The model called no tool and planned a whole-label CAPEC scan. Neither question names an
entity, and a general "you looked something up and failed" trigger was deliberately left out to
spare real scans (PROTOCOL §The fix).

### Where the variant gap comes from

T-lazy's 51 confidently-wrong answers sit almost entirely on T4 (24) and T5 (25). E has 14 and 17
there.

The prediction said the excess was T4/T5 questions that E abstains on. That is only partly right.
On T-lazy's 51 items, E:
- **gives a partial answer on 25;**
- **is also confidently wrong on 15;**
- **is empty or abstains on 8;**
- **is exact on 3.**

So most of the gap is not E declining where typed answers. It is the typed plan committing to a
wrong anchor on heavy paraphrases where the English plan lands on something that overlaps the
gold. The same plans give typed its T5 gain, +0.192 [+0.115, +0.269]: typed is more often
exactly right and more often confidently wrong on the same hard tier.

### Gemma

Gemma's typed arm is the closest to E on safety: 38 confidently wrong against 36, and 1 against 4
on dev. Its T4/T5 gains are the largest of the typed arms (0.2404 and 0.2500). It loses the most
dev answers (57).

This run does not test it against the gates; T-lazy (Qwen) is the arm of record. Moving the
planner to Gemma would need its own protocol.

### Claims

None. This is an engineering measurement, with no paper claim (manifest `supports_claims: []`).

## 5. Threats to validity

- **One run per arm,** and E's own movement is the only noise estimate. E's dev confidently-wrong
  count moved from 1 to 4 with no code change. Three of its four are anchorless `*_scan`
  templates:
  - CAPEC-685 resources;
  - DET0285 detects, then sub-technique-of;
  - C0050 uses, then sub-technique-of.

  The English path can produce the same failure. A difference of a few answers is within noise;
  T-lazy's dev −12 is not.
- **The arms ran in three sittings on one commit**, not one chain:
  - **10:27–10:59:** dev E, T-lazy and T-lazy-G;
  - **11:00–13:11:** R, variant T-lazy and T-full, and dev T-full;
  - **13:12–14:21:** variant E and T-lazy-G.

  All ran on commit 458a2841, with a clean tracked tree and identity verified by token id before
  and after each arm. Both R captures were byte-identical. The store files did not change between
  sittings. "Back to back" holds per commit, not per process (ISSUES).
- **Model-less answers are found after the fact.** Two tunnel drops made three arms answer
  mostly without a model, and the harness did not notice (ISSUES). Those arms were re-run. Every
  kept arm has a normal count of `DeterministicDrafter` fallbacks (1–12, against 2–9 in
  EXP-2026-11-015). This check uses the planner's own field; no harness change was made mid-run.
- **The smoke items are in the measured banks** (PROTOCOL threats).
- **Wording and guard were measured together.** The guard refused a scan on 7 dev questions and
  13 variant questions, so it did part of the work. The run cannot say how many of those the
  wording alone would have prevented, or what the wording did by itself.

## 6. What surprised us

- **The guard fired.** It fired on nothing in the smoke run, but on 20 T-lazy questions here.
  The smoke items were too few to see it.
- **T0 improved.** It rose by +0.092, more than predicted (0.6083 against about 0.55). Part of
  this is the six T0 negative and cross-graph items, now exact. The rest is not attributed.
- **The T4 gain weakened.** It fell from +0.096 to +0.058, and its interval now spans zero. E's
  own T4 rose by +0.038, which accounts for most of the shift. The T5 gain held (+0.164 →
  +0.192).
- **E made anchorless scans too,** on the dev bank (above).

## 7. Decision rules applied

**Predictions, written before the run:**

| Prediction | Observed | Held? |
|---|---|---|
| F1: 0 and 0 | variants 1, dev 0 | **no** |
| Dev CW about 1, G4 dev passes | 0; passes | yes |
| Variants CW about 45 against E 33, G4 variants fails | 51 against 36; fails | verdict yes, size no |
| Residual is T4/T5 items E abstains on | T4/T5 yes (49 of 51); E abstains on 8 of them | partly |
| T0 about 0.55 (about 0.65 anchor-ignored), G3 fails | 0.6083 (0.6833); fails | verdict yes, value higher |
| T4/T5 gain over E within ±0.03 of EXP-2026-11-015's | T5 +0.029; T4 −0.038 | T5 yes, T4 no |
| G1 and G2 verdicts unchanged | both still fail | yes |

**The rules:**
- **F1 failed.** The rule says: "the guard or the wording missed a route. Diagnose it before
  anything else; no arm-level conclusion is drawn."
  - **Diagnosed (§4).** The route is a refused cross-graph step, repaired into a whole-label
    scan, on a question that names no id. T-full adds a no-tool scan on vague paraphrases.
  - **No arm-level conclusion is drawn.** This run does not decide whether the typed hand-off is
    as safe as English.
- **Reported, not a verdict.** Without the one F1 case, T-lazy would have 50 confidently-wrong
  variant answers against E's 36, and G4's variant part would still fail. The miss does not
  change the picture the "F1 passes, G4 fails on variants" rule would have given. That rule's
  outcome would be:
  - English stays the planned-path default;
  - the catalog continues into Step 9 with the guard and the not-found wording.
- **In every case the fix stays in the tree.** It touches only the typed path, which is off by
  default.

**Next is the operator's call.** The options:
- extend the guard and the `from_step` refusal to the bridge route, and re-run;
- add an abstention gate on typed answers for the T4/T5 confident misses;
- carry the typed catalog into Step 9's agent loop as it stands.
