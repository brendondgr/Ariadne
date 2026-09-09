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

---

## AMENDMENT A-1 (2026-09-09) — Record repair: the pointer table was empty, and four bookkeeping fields were stale or placeholders

Written from the 2026-09-09 audit (`verify-b5.md`), the sidecars, the two
state files and `git log`. The audit re-ran `scripts/cross_family_rollup.py`
(sidecars only, output to a scratch path) and diffed it against
`data/rollup.json`: **no differences** — every mean, sd, pair accounting,
verdict and dropout entry reproduces. No result changes.

1. **Pointers.** `data/POINTERS.md` was the unfilled template. The 14 answer
   directories this experiment graded (12 bank cells + `composerfix-dev` +
   `composerfix-holdout`), the 1,320 sidecars it wrote, the five
   EXP-2026-08-021 sidecars per bank answer it read, the two scripts and the
   three committed `data/` files are now listed with hashes. The directories
   are shared with other experiments' sidecars, so the tree hashes will move
   whenever any pass writes there; each row says which files are this
   experiment's.
2. **`grading_failures.n`: 1338 → 1320.** 1,338 matches no count on disk.
   This experiment wrote 510 `.g31` + 510 `.g31p2` + 150 `.q38b` + 150
   `.q38bp2` = **1,320** sidecars (counted 2026-09-09); the two failures
   (I-2) are 2 of those attempts, both cleared on retry. The origin of 1,338
   is not recoverable (ISSUES I-9).
3. **ISSUES I-2 and I-6 are mid-run snapshots.** I-2 says `H-SUB-01`'s
   `.q38b` is *"outstanding; retry queued"*: the retry ran and
   `H-SUB-01.judgment.q38b.json` exists (the `.error.txt` beside it is the
   trace of the first attempt), which is what the manifest comment *"both
   cleared on retry"* already said. I-6's counts — `.g31`/`.g31p2` n = 689,
   `.q38b` n = 149 — were taken while the passes were running; final counts
   are **1,020** and **150** (plus 150 `.q38bp2`). Both entries are left as
   written.
4. **`wall_clock_hours`: 0.0 → 2.7.** First sidecar written 2026-09-05
   10:52, last 13:36. The qwen state file starts at 12:06 and reports
   `attempted: 0` for three of its four cells because those sidecars already
   existed — written before the per-track state file replaced the shared one
   (I-4) — which is why the state files understate the window.
5. **`code.commit`: 18dc024 → 514ddda.** `18dc0249…` (10:44:41) is the plan
   commit (*"Plan the last two measurements"*); `514ddda8fcdb53d6fad9306c70e92a32dc3e5476`
   (10:54:24) is the pre-registration that created this folder and
   `scripts/cross_family_regrade.py`. `dirty: true` stays: six commits landed
   inside the 10:52–13:36 window (`9bf0edb` 11:29, `186622c` 11:30, `91ac5ff`
   11:57, `a6fc52a` 11:59, `5cffc8b` 12:24, `bf8e5c9` 13:14 — the ISSUES,
   manifest and RESULTS of this experiment being written while it ran) and the
   per-track state-file fix (I-4) was applied mid-run; the exact uncommitted
   state at each cell's start is not recoverable (ISSUES I-8).
6. **Later use.** EXP-2026-09-007 spent the holdout on 2026-09-05 after this
   experiment's H1 failed, under DECISIONS D-029 (*"the holdout was judged
   anyway, on the operator's explicit call, with the failure recorded and
   travelling with the result"*). `related` gains EXP-2026-09-007. The gemma
   track also graded the 284 dev `llm_query` answers in
   `llm-query-split-2026-09-05` in the same window (state file); those are not
   in this rollup and are pointed with that caveat.
7. `environment.lockfile`: env/requirements.lock → null (never written;
   ISSUES I-8). `data/metrics.json` created from `metrics.values`.
