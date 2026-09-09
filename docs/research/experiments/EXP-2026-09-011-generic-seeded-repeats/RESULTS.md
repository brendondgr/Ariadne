# RESULTS — EXP-2026-09-011 — how much does the primary result move across seeds?

**Run 2026-09-06/07.** Three seeded generations, six grading passes, 1,704
judgments. Hypotheses pre-registered before any run; none edited.

---

## Headline

**The wording moves. The score does not.**

`EXP-2026-09-010` established that `generic` — the arm carrying this project's
primary result — words **143 of 276** answers differently on a rerun at the same
seed, in the field the grader reads. The obvious worry was that the paper's
headline sat on a number that wanders.

It does not. Across three seeds the judged score has a **balanced across-seed SD
of 0.0039**, and the gap it supports is **0.1623** — **forty-one times** the
spread.

| Seed | block q1 | pos | block q2 | pos | balanced |
|---|---|---|---|---|---|
| 1729 | 0.6646 | 0 | 0.6394 | 2 | **0.6520** |
| 20260906 | 0.6451 | 1 | 0.6444 | 1 | **0.6448** |
| 424242 | 0.6468 | 2 | 0.6394 | 0 | **0.6431** |

**Balanced SD 0.0039**, range 0.0089. Reference figure for this arm on this bank
is **0.6569** (`EXP-2026-09-005`); all three seeds sit within 0.014 of it.

## Hypotheses

| | Prediction | Outcome |
|---|---|---|
| **H1** | `generic > deterministic` in all runs | ✅ **holds** — lowest seed 0.6431 against 0.4946 |
| **H2** | across-seed SD < 0.03 | ✅ **holds** — 0.0039, an order of magnitude under |
| **H3** | the gap exceeds 3×SD | ✅ **holds** — 3×SD = 0.0116 against a 0.1623 gap |

H3 as pre-registered names the **holdout** gap (0.1684) while the spread is
measured on the **dev** half. That mismatch is in the protocol as written. Both
comparisons are reported and both hold; the same-population one (0.1623) is the
meaningful test and is quoted above.

---

## What this settles

**The `EXP-2026-09-010` finding is real but bounded, and now the bound is
measured.** Both statements are true and neither cancels the other:

- `generic` is **not** deterministic. It words the majority of its answers
  differently between runs.
- The judged score is **stable to 0.004**.

The reconciliation is the architecture doing its job. Retrieval, coverage,
claims and evidence are byte-identical across runs (`EXP-2026-09-010`); the
verifier admits claims against those fixed records; so the narrator's freedom is
freedom over *phrasing*, not over *content*. A grader scoring what was asserted
sees the same assertions in different words.

**That is a stronger result than determinism would have been.** A system whose
prose is fixed proves nothing about whether its scores are robust to prose. This
one varies the prose across 52% of answers and moves 0.004, which is evidence
about the *measurement*, not just the system.

## What it does not settle

- **Three seeds is a spread, not a distribution.** `n_runs: 3`.
- The spread is measured on the **dev half**. The holdout was answered once and
  is spent; nothing here says its figures would be equally stable, only that the
  same arm on the same bank is.
- **Same grader throughout.** Both blocks are `qwen38-27B-v2`
  (`default-model-2/-3/-4`). This is position-balanced *repeatability*, not
  cross-grader agreement. The second family was unavailable — its GPU was
  reserved — and `EXP-2026-09-009` showed that family can produce an opposite
  ordering on a population like this, so **cross-grader stability is not claimed
  and should not be inferred.**
- It does not localise *which* wording changes are inert. That every one of them
  is inert is an inference from the aggregate, not a per-answer finding.

---

## Incidental: the grading-order effect, replicated a third time

The two blocks are the same grader over the same answers, differing only in when
they ran:

| block | graded | mean |
|---|---|---|
| q1 | first | **0.6522** |
| q2 | second | **0.6411** |

**−0.0111 for being graded second.** `EXP-2026-08-022` measured −0.0088 on
byte-identical answers; `EXP-2026-09-009`'s qwen half showed a ~0.01 spread of
the same shape. Three independent measurements, all near 0.01, all in the same
direction.

This is why the design counterbalances rather than grading in a fixed order.
Un-counterbalanced, the block effect alone (0.0111) would be **nearly three times
the entire across-seed signal** (0.0039) and would have been reported as seed
variance. The counterbalancing did not merely tidy the estimate — it prevented a
wrong conclusion.

## Consequences for the paper

1. **§5's figures may be quoted as point estimates.** The arm's spread is 0.0039;
   the effect is 0.1623.
2. **Limitation 5 narrows.** `generic` is no longer "a single draw of a
   stochastic process whose spread we have not measured". The spread is measured
   and it is small. The wording instability stays in the paper as a finding.
3. **§11 gains a number it was carrying as a bound.** It can now state both that
   52% of answers are re-worded and that the score moves 0.004.
4. **The grading-order caveat gets a third citation**, which makes it a property
   of the instrument rather than an anecdote about one experiment.

---

# A-1 RESULTS (2026-09-07) — six seeds

Grading completed 13:01 across `default-model` and `default-model-2`, both
probed as `qwen38-27B-v2`. Same bank, same two counterbalanced blocks.

| seed | set | q1 | q2 | balanced |
|---|---|---|---|---|
| 1729 | pre-registered | 0.6646 | 0.6394 | 0.6520 |
| 20260906 | pre-registered | 0.6451 | 0.6444 | 0.6448 |
| 424242 | pre-registered | 0.6468 | 0.6394 | 0.6431 |
| 31337 | extension | 0.6556 | 0.6616 | **0.6586** |
| 8675309 | extension | 0.6382 | 0.6343 | **0.6363** |
| 271828 | extension | 0.6444 | 0.6370 | 0.6407 |

| set | n | mean | SD |
|---|---|---|---|
| pre-registered | 3 | 0.6466 | **0.0039** |
| extension | 3 | 0.6452 | **0.0097** |
| **all six** | 6 | **0.6459** | **0.0074** |

Range across six: **0.0224**.

## The finding the amendment pre-committed to reporting

**Three seeds understated the spread by roughly half.** A-1 recorded, before this
data existed, that if the six-seed SD came out materially larger it would be
reported as a finding with both figures quoted. It is 0.0074 against 0.0039 —
**1.9×** — so both are quoted, and **0.0074 is the number to use.**

The extension trio alone gives 0.0097, higher than either. The means agree
closely (0.6466 and 0.6452, a difference of 0.0014), so this is dispersion being
better sampled rather than the two sets measuring different things.

**This is what "a spread, not a distribution" meant.** Three points is enough to
show a quantity is small and not enough to say how small. The original limits
section said so; the extension is what turning that caution into a number looks
like.

## Hypotheses, re-evaluated on six

| | on 3 seeds | on 6 seeds |
|---|---|---|
| **H1** ordering holds | ✅ | ✅ lowest 0.6363 against 0.4946 |
| **H2** SD < 0.03 | ✅ 0.0039 | ✅ **0.0074** |
| **H3** gap > 3×SD | ✅ 41:1 | ✅ **0.1623 against 0.0222, 7.3:1** |

All three still hold. **H3's margin narrows from 41:1 to 7.3:1** — comfortable,
and no longer the extravagant ratio three seeds implied.

## Limits

- **The two sets were graded in separate sessions**, hours apart, on different
  endpoint pools (three aliases, then two). A session effect cannot be
  separated from seed variance here, and the extension trio's higher internal SD
  is consistent with either. Six seeds in one session would settle it and were
  not run.
- Still one arm, one bank, one grader family.
- Six points remain a small sample. The direction of the correction — spread
  larger than three seeds showed — is the kind of movement that continues with
  more seeds more often than it reverses.

## Consequence

**The paper should quote 0.0074, not 0.0039.** The conclusion is unchanged: the
wording variation `EXP-2026-09-010` measured does not reach the judged score, and
the effect is an order of magnitude above its own noise. What changes is that the
claim is made on six draws rather than three, at a less flattering and more
defensible number.

---

## AMENDMENT A-2 (2026-09-09) — record repair: the three-seed SD is withdrawn from the manifest, and the scaffold fields are filled

**The withdrawal.** A-1 above (2026-09-07) concluded "**the paper should
quote 0.0074, not 0.0039**", but `manifest.yaml` kept
`metrics.primary: balanced_across_seed_sd` = **0.0039** (three seeds) with
`n_runs: 6`. On 2026-09-09 `balanced_across_seed_sd` was moved from
`metrics.values` to `metrics.withdrawn` (`withdrawn_on: 2026-09-07`,
`replaced_by: EXP-2026-09-011:six_seed_balanced_sd`) and `metrics.primary` now
points at **`six_seed_balanced_sd`** = 0.0074. The three-seed value is not
deleted — A-1 says it "stands as reported" as the figure H1–H3 were adjudicated
against — but it is no longer a current value. `balanced_range` (0.0089) and
`gap_over_3sd_ratio` (13.99) remain in `values` as descriptive of the
pre-registered three-seed subset; their six-seed counterparts
(`six_seed_balanced_range` 0.0224, `gap_over_3sd_ratio_six_seed` 7.31) are the
quotable ones. `judgments_total` (1,704) is the three-seed count;
`judgments_total_six_seed` (3,408, zero failures) is added beside it.

One clarification on the headline: line 18 says the gap is "forty-one times"
the spread and the manifest's `gap_over_3sd_ratio` is 13.99. Both are correct
with different denominators — 0.1623 / 0.0039 = 41.6, 0.1623 / (3 × 0.0039) =
13.9 — and the six-seed line 161 uses the 3×SD form (7.3:1).

**What else was wrong.** `manifest.yaml` carried `status: complete` with
`date_completed: null`, `authors: []`, template prose in `purpose` and
`hypothesis`, `code.entrypoint: "<exact command>"`, `data.*` placeholders with
`n_examples: 0`, `compute.hardware: "<cpu/gpu, ram>"` with
`wall_clock_hours: 0.0`, and `llm.model: "<provider>/<model>@<version-or-date>"`
with `max_tokens: 2048`. `data/POINTERS.md` was the empty template,
`data/metrics.json` did not exist, and `ISSUES.md` was empty although
`code.dirty: true` and PROTOCOL A-1 records two script defects.

**What is now recorded (old → new), and how each was established.**

| field | was | is | established from |
|---|---|---|---|
| `date_completed` | `null` | `2026-09-07` | last extension pass `finished` 12:59:59 (`judge-state-extension.json`); six-seed commit `e5453fd` 13:03 |
| `authors` | `[]` | `[brendondgr]` | git author of `bc95277`, `112088b`, `923f5bd`, `e5453fd` |
| `purpose`, `hypothesis` | template text | filled from PROTOCOL.md; H1–H3 quoted with three- and six-seed outcomes | PROTOCOL.md (2026-09-06) and A-1 |
| `code.entrypoint` | `<exact command>` | `seeded_repeats.py --arm generic --workers 32` then `seeded_repeats_judge.py --arm generic --seeds preregistered`; `--extra-seeds` / `--seeds extension` for A-1 | the scripts (`--seeds` added at `228a700`, PROTOCOL A-1) |
| `data.*` | placeholders, `n_examples: 0` | `bank-dev.json`, dev half, 284, `hash` = pre-flight sha256 | `run-state.json` `preflight.bank_sha256`; re-hashed 2026-09-09, identical |
| `compute.hardware` | placeholder | narrator `:9090/default-model`; grading `default-model-2/-3/-4` then `default-model/-2`, all probed as qwen38-27B-v2; 32 workers | `run-state.json`, `judge-state.json`, `judge-state-extension.json` `served` |
| `compute.wall_clock_hours` | `0.0` | `5.7` | generation `elapsed_s` sum 4,174 s; grading 00:59–02:47 and ~10:15–13:00 from the `finished` stamps and `wall_s` |
| `llm.model` | placeholder | `relay/qwen38-27B-v2@2026-09-07` | every `served` entry in the three state files |
| `llm.max_tokens` | `2048` (template) | `32768` | PROTOCOL.md `--llm-max-tokens 32768`; 32,768 per grading pass |
| `metrics.primary` | `balanced_across_seed_sd` | `six_seed_balanced_sd` | A-1 |
| `metrics.values.balanced_across_seed_sd` | `0.0039` | withdrawn (see above) | A-1 |
| `metrics.values.judgments_total_six_seed` | absent | `3408` | 3,408 `*.judgment.q{1,2}.json` on disk, zero `.error` on the extension seeds |
| `related` | `[]` | `[EXP-2026-08-022, EXP-2026-09-005, -007, -009, -010]` | the experiments this RESULTS quotes |

**Pointers.** `data/POINTERS.md` lists the six-seed tree and the bank file
with bytes and SHA-256 as of 2026-09-09; the tree has not been written to
since 2026-09-07 12:59. **Metrics file.** `data/metrics.json` created with
every `metrics.values` entry, the withdrawn block, the per-pass scores and
spreads from both judge-state files, and the six balanced means. The
2026-09-09 audit (verify-b6, `r011.py`) reproduced all twelve block means, the
six balanced means, the 0.0039 / 0.0097 / 0.0074 SDs, both ranges, the
−0.0111 block effect and both ratios exactly from the sidecars, with
`served_model` = `qwen38-27B-v2` on every one of the 3,408.

## AMENDMENT A-3 (2026-09-09) — 283 stale error sidecars on seed 1729, and what `errors: 283` in `judge-state.json` means

`seed-1729/generic/answers/` holds **283 `*.judgment.q1.error.txt`** files
beside its 284 `*.judgment.q1.json` judgments, and `data/judge-state.json`
records `qwen1-1729: {n: 284, mean: 0.6646, errors: 283}`. The error files all
read `judge call failed after 3 attempts: HTTP Error 502: Bad Gateway`: the
first `.q1` pass on that seed hit a dead endpoint, was retried (the pass
summary shows three attempts of 95 / 94 / … cases), and completed with all
284 judgments written. The `.error.txt` files are leftovers of the failed
attempt; `n: 284` is the count that grades, and every reported figure is
computed over 284. No judgment is missing on any of the six seeds (3,408
sidecars, none failed). Logged in ISSUES.md; the files are left in place
because deleting raw output is not this record's to do.
