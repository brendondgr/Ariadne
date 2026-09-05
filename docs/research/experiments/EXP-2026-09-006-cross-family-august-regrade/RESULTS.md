# RESULTS — EXP-2026-09-006 The August ordering under a second grader family

## 1. Headline

**Every claim-bearing comparison survives a change of grader family, and two of
five pre-registered hypotheses failed.** Across 510 frozen answers re-graded by
`gemma4-31B-mtp` and `qwen38-27B-v2`, both named by probe: **zero contrast sign
flips** on C-012, C-021 and C-022, and **one arm-ordering reversal in 23 pairs**
— on a pair neither grader resolves and neither claim uses.

The most useful thing the experiment produced was not a confirmation. It is
that **`gemma4-31B-mtp` has no resolution at the ceiling**: it scored **1.0000
on all 150 `composerfix` answers** and is fully saturated in **6 of 12** bank
cells. Read unguarded, that instrument reports C-021's gap as **+0.0000** and
would have looked like a refutation of the paper's methodological headline.

## 2. Results

### The pre-registered hypotheses

| | prediction | outcome |
|---|---|---|
| **H1** | zero arm-ordering reversals | **FAILED — 1 of 23 pairs** |
| **H2** | C-021 gap positive and > 0.02 under both named graders | **HOLDS under qwen (+0.0322); unmeasurable under gemma** |
| **H3** | C-022 stays indistinguishable from zero | **HOLDS — 6 readings, all ≥ 0, all under the ±0.06 floor** |
| **H4** | between-family offset ≥ 10× within-family spread | **FAILED — 0.0355 against 0.0036–0.0249** |
| **H5** | disagreement concentrates on the weak arm | **HOLDS, harder than predicted — 6 saturated cells** |

### C-021 — co-authorship bias, and it shrinks again

| grader | catalogue (120) | blind (30) | gap |
|---|---|---|---|
| unidentified, August | 0.9833 (n=119) | 0.9350 | **+0.0483** |
| **qwen38-27B-v2, named** | 0.9905 | 0.9583 | **+0.0322** |
| gemma4-31B-mtp | 1.0000 | 1.0000 | +0.0000 — **saturated** |

**Quote +0.0322 with the grader and date beside it.** The claim has now been
restated downward three times — 0.1472 → 0.0483 → 0.0322 — and every restatement
came from removing a confound rather than from new data. **It survived each one.**

### C-012 and C-022 — sign-stable under both families

| bank | contrast | qwen | gemma | gemma bound |
|---|---|---|---|---|
| 19 | C-012 `deterministic − llm_query` | **+0.4260** | +0.4000 | upper |
| 20 | C-012 `deterministic − llm_query` | **+0.5298** | +0.5500 | upper |
| 19 | C-022 `federated − merged` | +0.0608 | +0.0500 | upper |
| 20 | C-022 `federated − merged` | +0.0581 | +0.0400 | two-sided |

C-012's margin is 8–15× the between-family offset. C-022's six readings (with
the two historical passes) are all ≥ 0 and all inside the ±0.06 question-sampling
floor at n=30 — **a null that now survives a change of family.** The exact
`+0.0000` on `bank20260820` that `CLAIMS.md` already flagged as an artifact is
confirmed as one: both named graders read +0.0400 and +0.0581 there.

### The one reversal

`gold_loop_llm` versus `generic_composed` on `bank20260820`: qwen **+0.0276**
(paired sd 0.0854), gemma **−0.0033** (paired sd 0.0287). Neither grader
resolves the pair — gemma's margin is inside its own within-family spread. **H1
is recorded as failed and the test was not redefined afterwards**; see
`ISSUES.md` I-7 and `DECISIONS.md` D-029.

## 3. Interpretation

**What may now be said that could not be said yesterday.** Every judged claim in
the record names its grader and has been checked under a second family. The
provenance table's line — that C-012, C-021 and C-022 are *"graded by a model
nobody can name"* — is discharged.

**What the failures buy.** H4's miss is informative: the family change moves
levels by ~0.036, roughly 1.4–10× the within-family spread rather than the order
of magnitude assumed. `EXP-2026-08-021`'s caution was slightly too strong.
Levels remain unquotable; the reason is now measured rather than asserted.

**The instrument finding is the transferable one.** The two graders differ in
*shape*, not level: **gemma grades close to binary, qwen grades with partial
credit.** That single fact explains gemma's higher spread on mixed banks, its
all-1.0 on a near-ceiling bank, and its wider arm gap on identical answers. It
also means **a second grader is not automatically a check** — on any comparison
where the arms sit near 1.0, gemma is not a weaker instrument but a null one.
Three separate near-misses in this experiment trace to it (`ISSUES.md` I-1),
including a tie-break that was about to be reported as four reversals.

## 4. Limits

- Two families is not a panel, and neither is provider-hosted.
- ±0.06 question-sampling at n=30 dominates every margin below 0.06, C-022's
  included. A null over 30 questions is still a null over 30 questions.
- `composerfix-dev` versus `composerfix-holdout` is unpaired by construction —
  different questions — which is what the claim is about, not a defect.
- Nothing here re-measures the *system*. No pipeline ran; no graph was read.
