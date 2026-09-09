# RESULTS — EXP-2026-09-008 — which local models can grade near the ceiling?

**Run 2026-09-06.** Protocol and the `usable_near_ceiling` criterion were written
before any calibration judgment existed.

---

## Headline

**Of three locally available graders, one can adjudicate a near-ceiling contrast
and two cannot.** One of the two does not merely lose resolution — it *reverses*
the ordering of mediocre and good answers in exactly the score range where every
arm of this project sits.

Saturation is a **ceiling effect, not a general inability**: all three models
separate the low band with sd > 0.26. A grader that looks fine on a spread-out
population can still be blind on a tight one, and correlation against a reference
will not show it.

---

## The decisive table

Ceiling band, n=20 per model, identical answers, identical prompt, identical
32,768-token budget. `usable_near_ceiling` ⇔ `fraction_at_1 < 0.95` **and**
`distinct_values > 2`, pre-registered.

| Grader (`served_model`) | mean | sd | at 1.0 | distinct | values emitted | usable |
|---|---|---|---|---|---|---|
| `gemma4-31B-mtp` | 1.0000 | 0.000 | **20/20** | **1** | `{1.0}` | ❌ |
| `gemma-4-26B-it` | 0.9750 | 0.109 | **19/20** | **2** | `{0.5, 1.0}` | ❌ |
| `qwen38-27B-v2` | 0.9800 | 0.051 | 17/20 | 3 | `{0.8, 0.9, 1.0}` | ✅ |

Every model is named by the string its own response envelope returned, never by
the relay alias (`D-028`). This matters here more than anywhere: `default-model-2`
served two different families within six hours on 2026-09-05.

## All three bands

| Grader | ceiling mean (distinct) | mid mean (distinct) | low mean (distinct) | overall sd |
|---|---|---|---|---|
| `qwen38-27B-v2` | 0.9800 (3) | 0.5125 (9) | 0.3785 (11) | 0.356 |
| `gemma4-31B-mtp` | 1.0000 (1) | 0.4250 (3) | 0.2385 (4) | 0.477 |
| `gemma-4-26B-it` | 0.9750 (2) | **0.6239** (5) | **0.6435** (5) | 0.390 |

---

## Hypotheses

| | Prediction | Outcome |
|---|---|---|
| **H1** | `gemma4-31B-mtp` ≥95% at 1.0 on the ceiling band | ✅ **Confirmed**, and at the limit: **100%**, one distinct value. A replication on a different answer set of the 2026-09-05 accident. |
| **H2** | `qwen38-27B-v2` emits ≥3 distinct values on the ceiling band | ✅ **Confirmed.** Exactly 3, 85% at 1.0. |
| **H3** | `gemma-4-26B-it` genuinely uncertain — the only unpredictable cell | ✅ **Resolved: unusable.** It fails *both* halves of the criterion, 0.95 at 1.0 (not < 0.95) and 2 distinct values (not > 2). It shares the Gemma near-binary behaviour. |
| **H4** | Every model separates the low band with sd > 0.20 | ✅ **Confirmed** for all three: 0.263, 0.399, 0.450. Saturation is a ceiling effect. |

All four hold. H3 was the cell that decided whether `C-021` could get a second
opinion, and the answer is that it cannot from any local model but one.

---

## The finding nobody predicted

`gemma-4-26B-it` **inverts the mid/low ordering.** It scores the *low* band at
**0.6435** against the *mid* band at **0.6239**, when the constructed ordering is
mid above low.

- The inversion sits in the **0.40–0.65** range. Every arm of this project scores
  inside it on the holdout (`generic` 0.6546, `deterministic` 0.4862,
  `llm_query` 0.4031 — `EXP-2026-09-007`).
- A grader that adds noise is survivable. A grader that reverses an ordering is a
  different failure, and it is **invisible to the correlation statistics this
  field reports.**
- The margin is small (0.0196) and n is 18 vs 20. We do not claim a calibrated
  effect size. We claim the ordering came out backwards on a set constructed so
  that it could not, and that is sufficient to disqualify the grader.

**Consequence, taken immediately.** The planned third-family holdout pass
(`C2-holdout-third-family`) was **stopped on this evidence with zero judgments
written**. Grading 288 × 3 answers with an instrument that inverts inside the
measured range would have produced a number that looked like a result.

---

## What this cost the record

- **`C-021`'s co-authorship gap is 0.0322 under `qwen38-27B-v2` and 0.0000 under
  `gemma4-31B-mtp`** (`EXP-2026-09-006`). The second number reads as a
  refutation. It is an instrument limit: a grader emitting one value in that band
  reports a contrast of exactly zero whatever is true.
- **Six of twelve cells** of the August cross-family re-grade are saturated under
  the second family.
- **`C-021` rests on one named grader because it has to.** That is a measurement,
  not an apology, and the paper should say so in those words.

---

## Incidental: the thinking cap, tested and closed

`LLM_THINKING_BUDGET=512` had been wired for days and never exercised against a
live endpoint. Paired on identical case ids against the settled uncapped run,
n=30:

| | records retrieved | gate-rejected |
|---|---|---|
| capped at 512 | **0** | **28** |
| uncapped | 3 | 4 |

**Verdict: do not use.** The cap eliminates retrieval entirely and raises gate
rejections sevenfold. No question retrieved under the cap that did not retrieve
uncapped.

*Mechanism.* The builder is a reasoning model. At 512 thinking tokens it emits
queries malformed enough for the pre-run gate to reject — the same failure shape
that defeated this arm four times before, in which **too small a bound is
downstream indistinguishable from a model with nothing to say.**

*Limits.* n=30, one cap value, one model, and the 30 are a hard slice — uncapped
retrieved on only 3 of them against ~31% bank-wide. **The absolute rates are not
representative; the paired direction is.** Not a judged comparison. This does not
replace the published `llm_query` figures, which ran uncapped.

**A measurement bug was found and fixed before any conclusion was drawn.** The
orchestrator's `with_evidence` counter read `records or results`, and `results`
counts sub-question slots including failures — so it reported **30/30 with
evidence when the truth was 0/30**. Caught by reading the answers rather than
trusting the metric.

---

## Limits of this experiment

- **n=20 per band per model.** Enough to establish that a grader emits one or two
  distinct values; not enough to estimate a resolution threshold.
- **Three models, all local.** No hosted frontier grader was tested. Whether the
  ceiling effect is a property of open-weight models at this scale, of these two
  families, or of LLM graders generally is **unknown and not claimed.**
- **One prompt, one budget, one temperature.** A different rubric might resolve
  where this one saturates. The result is about this instrument as this project
  uses it.
- **`gemma-4-26B-it`'s mid band is n=18, not 20.** Its llama.cpp endpoint stopped
  answering even a 16-token request for over 400 s. The ceiling band — the band
  the usability verdict depends on — completed at 20/20, so the verdict stands;
  the inversion finding rests on the short band and is reported with that caveat
  attached.
- **The bands are constructed from this project's own arms**, so "true ordering"
  means the ordering those arms produce under the reference grader, not a human
  label. `Q6` closed human grading as unavailable.

## Where this goes in the paper

It has no home in the outline yet and needs one. The draft
(`docs/research/paper/tmlr/ariadne-tmlr.tex`) currently gives it §5, leading,
on the grounds that TMLR's scope makes an evaluation-methodology result the part
that fits and that it needs no external system to be interesting. That placement
is still an open editorial decision.

---

## AMENDMENT A-1 (2026-09-09) — record repair: the manifest was a scaffold with results bolted on

**What was wrong.** `manifest.yaml` carried `status: complete` with
`date_completed: null`, `authors: []`, the template's placeholder prose in
`purpose` and `hypothesis`, `code.entrypoint: "<exact command>"`, `data.name`
/ `version` / `split` as `<dataset>` / `<version>` / `<split>` with
`n_examples: 0`, `compute.hardware: "<cpu/gpu, ram>"` with
`wall_clock_hours: 0.0`, and `llm.model: "<provider>/<model>@<version-or-date>"`
with `max_tokens: 2048` — although every state file in `data/` records the
served model and elapsed time. `data/POINTERS.md` was the empty template and
`data/metrics.json` did not exist. `ISSUES.md` was empty although
`code.dirty: true` and the RESULTS above document a measurement bug and an
endpoint stall.

**What is now recorded (old → new), and how each was established.**

| field | was | is | established from |
|---|---|---|---|
| `date_completed` | `null` | `2026-09-06` | last calibration sidecar mtime 03:25:16 (`state-gemma26.json` `finished`); write-up commit `4eb9b91` 2026-09-06 20:37 |
| `authors` | `[]` | `[brendondgr]` | git author of `45f3226`, `61e2838`, `03570c4`, `4eb9b91` |
| `purpose`, `hypothesis` | template text | filled from PROTOCOL.md §Question/§Hypothesis, H1–H4 quoted | PROTOCOL.md (written 2026-09-06 00:05, before any judgment) |
| `code.entrypoint` | `<exact command>` | `uv run python scripts/overnight_2026_09_06.py` | the driver's docstring; `phase_a()` is the calibration, `phase_d()` the thinking-cap probe |
| `data.*` | placeholders, `n_examples: 0` | calibration-2026-09-06 (60 answers, `selection.json` seed 20260906) + 30-case thinkcap slice; `hash` = sha256 of `selection.json` | `selection.json`; PROTOCOL.md §Setup |
| `compute.hardware` | placeholder | the three endpoints, worker counts and serving stacks | `ENDPOINTS` in the driver; PROTOCOL.md |
| `compute.wall_clock_hours` | `0.0` | `3.6` | first sidecar 2026-09-05 23:51:07 → last 2026-09-06 03:25:16, three tracks concurrent; per-track `elapsed_s` sum to 4.35 h |
| `llm.model` | placeholder | `relay/qwen38-27B-v2@2026-09-06`, with the two other graders named in a comment (`relay/gemma4-31B-mtp@2026-09-06`, `relay/gemma-4-26B-it@2026-09-06`) | `served_model` in `state-{qwen,gemma31,gemma26}.json`, read from the response envelope |
| `llm.max_tokens` | `2048` (template) | `32768` | `JUDGE_MAX_TOKENS` in the driver; PROTOCOL.md "Same budget (32,768)" |
| `llm.nondeterminism_note` | template | states n_runs 1 per band and that sd is across answers, not passes | the design |
| `related` | `[]` | `[EXP-2026-09-006, EXP-2026-09-007, EXP-2026-09-009]` | the experiments this RESULTS quotes, and the one that extends it |
| `metrics.primary` | `ceiling_band_fraction_at_1` (not a key in `values`) | `models_usable_near_ceiling` (1 of 3) | the headline verdict; the per-model `ceiling_fraction_at_1_*` keys hold the decisive numbers |

**Pointers.** `data/POINTERS.md` now lists the calibration tree, its
`selection.json`, the capped thinkcap run and the uncapped comparator, each
with bytes and SHA-256 as of 2026-09-09 (`utils.research_record.hashing`).
Nothing under those paths was written after 2026-09-06 03:26.
`docs/evaluation/experiments/holdout-spend-2026-09-05` is deliberately not
pointed: `data/state-gemma31.json` phases B/B2/B3 record 288 × 3 gemma
judgments written there, but those are EXP-2026-09-007's holdout grading, run
by the same overnight driver, and that experiment points at them.

**Metrics file.** `data/metrics.json` created with every `metrics.values`
entry copied from the manifest, plus the per-model per-band blocks from the
three state files and the thinkcap counts, so that every manifest number is
machine-readable from one file. The audit of 2026-09-09 (verify-b6, `r008.py`
/ `r008b.py`) recomputed every mean, sd, at-1 count and distinct-value set from
the sidecars and matched the manifest to 4 dp; nothing in `metrics.values`
changed.

**`supports_claims` stays `[]`.** This RESULTS is about what C-021 can rest
on, but CLAIMS.md does not cite this experiment as evidence for any claim,
and adding a link the ledger does not carry would be the ledger's edit to
make, not this experiment's.

## AMENDMENT A-2 (2026-09-09) — the holdout `llm_query` figure quoted above is superseded

§"The finding nobody predicted" (RESULTS.md line 70) quotes the holdout as
`llm_query` **0.4031** from `EXP-2026-09-007`, and
`data/thinkcap-probe.json` `does_not_replace` repeated it. EXP-2026-09-007
AMENDMENT A-1 (2026-09-07, after this write-up) recomputed all 3,456 holdout
sidecars and corrected that manifest value to **0.4039** (the 0.4031 came from
`judged-final.json`, a superseded roll-up). The other two holdout figures quoted
on the same line — `generic` 0.6546 and `deterministic` 0.4862 — were already
correct and are unchanged.

The prose above is left as written. `data/thinkcap-probe.json` is a data file
and was corrected in place: `does_not_replace` now reads `holdout 0.4039`
(was `0.4031`), with a `corrected_2026-09-09` field naming the change. Nothing
in this experiment's own metrics depends on the figure; the inversion argument
("every arm scores inside 0.40–0.65") is unaffected.

## AMENDMENT A-3 (2026-09-09) — two stale intermediates in `data/`, and where the correct values live

1. **`data/ceiling-resolution.json` `incomplete` says the mid/low bands of
   `gemma-4-26B-it` were "not measured".** That field was written at 01:17
   while the llama.cpp track was still running (it had stalled at 11/20 on the
   mid band). The track finished at 03:25:16 with mid **n=18** (two cases
   failed at the endpoint and are on disk as `*.judgment.gemma26.error.txt`)
   and low **n=20**; `data/state-gemma26.json` holds those final figures
   (mid 0.6239, low 0.6435), and they are what the three-band table (line 44),
   the Limits (line 141) and the manifest report. The inversion finding rests
   on the measured bands, not on unmeasured ones. The JSON keeps the original
   text verbatim and gains an `incomplete_superseded_2026-09-09` field saying
   this.
2. **`data/state-qwen.json` phase D records `with_evidence: 30`.** That is
   the value the orchestrator's counter reported before the bug described at
   lines 123–127 was found: it read `records or results`, and `results`
   counts sub-question slots including failures. The true figure, read from
   the 30 answers, is **0** with records > 0 and **28** gate-rejected
   (`data/thinkcap-probe.json`, and the manifest's
   `thinkcap512_records_retrieved` / `thinkcap512_gate_rejected`). The state
   file keeps the value as written and gains a `with_evidence_note_2026-09-09`
   field. Both are also logged in ISSUES.md.
