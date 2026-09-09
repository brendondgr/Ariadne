# RESULTS — EXP-2026-09-009 — three seeded runs of the query-writing arm

**Run 2026-09-06.** Three generations, six grading passes, 1,704 judgments.
Hypotheses were pre-registered before any run; none has been edited.

---

## Headline

**The seed barely matters. The grader decides the answer.**

Across-seed spread is **0.0089** against a 0.03 threshold — the arm is stable, and
`C-012`'s single-draw provenance was not the problem. But the same three runs
produce **opposite orderings** under the two grader families, and the reversal is
large: `deterministic − llm_query` is **+0.1012** under one grader and
**−0.2885** under the other.

The second grader emitted **two distinct values** across all 852 of its
judgments. It is precise, repeatable, and measuring almost nothing.

---

## Results

| Arm | qwen38-27B-v2 | gemma4-31B-mtp |
|---|---|---|
| `generic` (reference, `EXP-2026-09-005`) | 0.6600 | 0.6698 ± 0.0084 *(9 passes)* |
| `deterministic` (reference) | 0.4924 | 0.4169 ± 0.0033 *(10 passes)* |
| **`llm_query` (this experiment, 3 seeds)** | **0.3912 ± 0.0084** | **0.7054 ± 0.0142** |

Per-seed, `llm_query`:

| Seed | qwen | gemma |
|---|---|---|
| 1729 | 0.3805 | 0.6937 |
| 20260906 | 0.3923 | 0.7254 |
| 424242 | 0.4009 | 0.6972 |

All references are **same-grader**: gemma figures come from gemma passes on the
same 284-question bank. Comparing a gemma-graded arm to a qwen-graded one would
manufacture the very effect this experiment is about.

## Hypotheses

| | Prediction | qwen | gemma |
|---|---|---|---|
| **H1** | `generic > deterministic > llm_query` in all runs | ✅ holds | ❌ **fails** — `llm_query` (0.7054) exceeds `generic` (0.6698) |
| **H2** | across-seed SD < 0.03 | ✅ 0.0084 | ✅ 0.0142 |
| **H3** | `deterministic − llm_query` positive in all runs | ✅ **+0.1012** | ❌ **−0.2885** |

**Balanced estimate** (per-seed mean of the two families; counterbalancing gives
every seed position sum 2, so the ~0.01 position effect cancels): means
0.5371 / 0.5589 / 0.5491, **SD 0.0089 — H2 holds.**

---

## H2 is the result we came for, and it is clean

`C-012` rested on one draw. The concern was that run-to-run spread might be the
same size as the `+0.0831` margin, in which case one draw established nothing.

**It is not.** Spread is 0.0084 (qwen), 0.0142 (gemma), 0.0089 (balanced) — an
order of magnitude below the margin. Whatever is wrong with `C-012`, **it is not
that the arm is noisy.**

## H1 and H3 fail, and the failure is about the instrument

Taken at face value, gemma says a model writing the queries **beats** both other
arms. That would overturn the paper's §6. It should not be taken at face value,
for a reason that is measured rather than argued:

**gemma emitted exactly two values — `{0.0, 1.0}` — across all 852 judgments in
this experiment.** qwen emitted 15. A grader with two levels cannot express an
ordering among three arms; it can only report what fraction of answers it deems
acceptable.

`EXP-2026-09-008` pre-registered `distinct_values > 2` as a usability floor.
**This pass fails that floor**, and it was written down before this data existed.

### The mechanism, partly identified

**98.2% of these answers are abstentions.** The arm emitted an empty query and
declined. Split by that:

| | gemma | qwen |
|---|---|---|
| mean on abstentions | **0.7014** | 0.4023 |
| mean on non-abstentions | 0.4000 | 0.3200 |

152 cases have gemma `CORRECT` against qwen `PARTIAL`. The rationales agree on
the facts and differ on policy — gemma: *"honestly abstained… stating that no
records were found is the correct response"*; qwen: *"honest but incomplete… never
states AN1549 or the expected platform."*

This is the **abstention-crediting scoring fault** the record already carries as a
known limitation. What is new is its size, and that it is **grader-dependent**:
worth ~0.30 of correctness on an abstention-saturated population, which is larger
than any effect this project reports.

### What the mechanism does *not* explain

On the holdout, `llm_query` abstained **71.2%** and gemma scored those abstentions
at **0.4098** — not 0.70 — while emitting 13 distinct values. Abstention rate
alone therefore does **not** account for tonight's behaviour. Something further
distinguishes these two populations and **we have not identified it.** Recorded as
open rather than explained away.

Ruled out: grading position. All three gemma passes were binary at positions 0, 1
and 2 (`EXP-2026-08-022`'s position effect is ~0.01, three orders too small
anyway).

### Precision without resolution

The strongest single observation here. Gemma's ten repeat passes on
`deterministic` agree to **SD 0.0033**; nine on `generic` to **0.0084**. It is one
of the most *repeatable* instruments in this record — and on this population it
emits two values.

**Repeatability is not resolution, and reliability statistics cannot tell them
apart.** A grader that always says the same thing is perfectly reliable and may
still be blind.

---

## Consequences

1. **`C-012` is not weakened by run-to-run noise** — H2 settles that. Its
   provenance problem was never the single draw.
2. **`C-012` cannot be stated as holding under both grader families on this
   population.** The second family cannot adjudicate it here at all. The paper
   must say that, and must not average the two families into one number.
3. **`EXP-2026-09-008`'s resolution floor is not only a ceiling effect.** It was
   found on near-perfect answers; this finds the same collapse on a homogeneous
   *low* population. **Homogeneity, not altitude, appears to be the trigger** —
   and that is a stronger and more general claim than the original.
4. **Abstention rate should be a pre-flight check before any gemma grading pass**,
   with a refusal threshold. Discovering it afterwards is how tonight went.
5. **The published holdout figures are unaffected.** Gemma emitted 10–17 distinct
   values per arm there. Checked before this was written.

## Limits

- **Three seeds.** A spread, not a distribution. `n_runs: 3` now, not 1.
- The `deterministic` and `generic` references are prior runs on the same bank,
  not re-run alongside. `deterministic` is byte-identical across runs
  (`EXP-2026-09-010`) so this is safe for it; `generic` narrates with a model and
  its own spread is `EXP-2026-09-011`, unrun at the time of writing.
- One grading failure of 284 on seed 424242 (judgment returned without required
  fields). Zero on the other two. Its seed's qwen mean is over n=283.
- H1/H3 are adjudicated against reference figures rather than simultaneous
  re-runs. A stricter design would re-run all three arms per seed.

---

## AMENDMENT A-1 (2026-09-09) — record repair: the manifest was a scaffold with results bolted on

**What was wrong.** `manifest.yaml` carried `status: complete` with
`date_completed: null`, `authors: []`, template prose in `purpose` and
`hypothesis`, `code.entrypoint: "<exact command>"`, `data.name` / `version` /
`split` placeholders with `n_examples: 0`, `compute.hardware: "<cpu/gpu, ram>"`
with `wall_clock_hours: 0.0`, and `llm.model: "<provider>/<model>@<version-or-date>"`
with `max_tokens: 2048` — although `data/judge-state.json` names both served
models and `data/run-state.json` records the bank hash and every elapsed time.
`data/POINTERS.md` was the empty template, `data/metrics.json` did not exist,
and `ISSUES.md` was empty although `code.dirty: true` and one grading failure
is disclosed in Limits.

**What is now recorded (old → new), and how each was established.**

| field | was | is | established from |
|---|---|---|---|
| `date_completed` | `null` | `2026-09-06` | last grading pass `finished` 22:22:28 (`judge-state.json`); completion commit `40bebd3` 22:26 |
| `authors` | `[]` | `[brendondgr]` | git author of `c8ad1a7`, `9f66921`, `40bebd3` |
| `purpose`, `hypothesis` | template text | filled from PROTOCOL.md; H1–H3 quoted with outcomes | PROTOCOL.md (2026-09-06, before any run) |
| `code.entrypoint` | `<exact command>` | `scripts/seeded_repeats.py --workers 32` then `scripts/seeded_repeats_judge.py --arm llm_query --workers 32` | the scripts' docstrings; `--arm` was added at `1de8b53` (22:58), after these passes ran with `llm_query` as the only arm |
| `data.*` | placeholders, `n_examples: 0` | `bank-dev.json`, dev half, 284, `hash` = the pre-flight sha256 | `run-state.json` `preflight.bank_sha256`; re-hashed 2026-09-09, identical |
| `compute.hardware` | placeholder | the two `:9090` aliases, served models, 32 workers | PROTOCOL.md §Design; `run-state.json` `preflight.served` |
| `compute.wall_clock_hours` | `0.0` | `4.4` | generation 17:57–19:07 (`elapsed_s` 1607 + 1485 + 1119), grading 19:34–22:22 (`judge-state.json` `finished` stamps and `wall_s`) |
| `llm.model` | placeholder | `relay/qwen38-27B-v2@2026-09-06` (generation and grader family 1), with family 2 `relay/gemma4-31B-mtp@2026-09-06` in a comment | `judge-state.json` `served`, read from the response envelopes |
| `llm.max_tokens` | `2048` (template) | `32768` | `--llm-max-tokens 32768` in `scripts/seeded_repeats.py`; PROTOCOL.md "max_tokens 32768" for grading |
| `llm.nondeterminism_note` | template | states that the seed is varied and recorded and that the spread is the quantity | PROTOCOL.md §Prior evidence |
| `metrics.values.qwen_distinct_values_this_population` | `15` | `17` | see A-4 |
| `metrics.values.deterministic_minus_llm_query_qwen_vs_exp005_reference` | absent | `0.1034` | see A-2 |
| `related` | `[]` | `[EXP-2026-09-005, -007, -008, -010, -011]` | the experiments this RESULTS quotes |

**Pointers.** `data/POINTERS.md` now lists the seeded-repeats tree, the bank
file, the two `post-repair-2026-09-03` reference directories and the holdout
`llm_query` directory read for the cross-check, each with bytes and SHA-256 as
of 2026-09-09. The seeded-repeats tree has not been written to since
2026-09-06 22:22. The `post-repair` directories carry sidecars from later
grading passes (`.pass2`, `.gemma_r3`…`.gemma_r10`) that this experiment does
not read; their answer files are unchanged since 2026-09-03.

**Metrics file.** `data/metrics.json` created with every `metrics.values`
entry, the per-pass scores and spreads from `judge-state.json`, and the
reference figures with their provenance (A-2). The 2026-09-09 audit
(verify-b6, `r009.py`) reproduced every per-seed mean, both family SDs and the
balanced SD exactly from the sidecars.

## AMENDMENT A-2 (2026-09-09) — the qwen reference figures are not the ones EXP-2026-09-005 records

§Results (lines 27–28) labels `generic` **0.6600** and `deterministic`
**0.4924** as "(reference, `EXP-2026-09-005`)". EXP-2026-09-005's manifest
records `generic_judged` **0.6569** and `deterministic_judged` **0.4946** —
the averages of its two grading positions. 0.6600 and 0.4924 are the means of
the single position-0 pass (`*.judgment.json`, no suffix) on
`post-repair-2026-09-03`; the `.pass2` passes give 0.6537 and 0.4967. All four
were recomputed from the sidecars on 2026-09-09.

The gemma references on the same lines (0.6698 ± 0.0084 over nine passes,
0.4169 ± 0.0033 over ten) are correctly labelled as multi-pass means and
reproduce from the `*.judgment.gemma*.json` sidecars. The two families'
references were therefore constructed differently — single-pass for qwen,
multi-pass for gemma — and the RESULTS does not say so.

**Consequence for the manifest.** `deterministic_minus_llm_query_qwen`
**0.1012** is 0.4924 − 0.3912 and rests on a reference EXP-2026-09-005 does
not report. With EXP-2026-09-005's 0.4946 the contrast is **0.1034**, now
recorded under the new key
`deterministic_minus_llm_query_qwen_vs_exp005_reference`. The original key is
kept because it is what the RESULTS computed and quotes. Sign, H1 and H3 are
unchanged under either reference; the gemma contrast (−0.2885 = 0.4169 −
0.7054) is unaffected.

## AMENDMENT A-3 (2026-09-09) — the `+0.0831` holdout margin is superseded by `0.0822`

PROTOCOL.md lines 17 and 95–96 and RESULTS.md line 60 quote C-012's holdout
margin as **+0.0831**. EXP-2026-09-007 AMENDMENT A-1 (2026-09-07, after this
write-up) recomputed all 3,456 holdout sidecars and corrected
`deterministic_minus_llm_query_holdout` to **0.0822** (and `llm_query_holdout`
0.4031 → 0.4039). The argument of §H2 — that the across-seed spread (0.0084 /
0.0142 / 0.0089) is an order of magnitude below the margin — holds identically
at 0.0822. The prose is left as written; the manifest's `purpose` names both
figures.

## AMENDMENT A-4 (2026-09-09) — four small figures, restated from the sidecars

1. **Distinct values.** Line 73 says "qwen emitted 15" and the manifest
   recorded `qwen_distinct_values_this_population: 15, n: 851`. Per seed the
   qwen pass emitted 15 / 16 / 15 distinct correctness values; pooled over
   all 851 usable judgments — which is what `n: 851` describes — it emitted
   **17** ({0.0, 0.05, 0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.55, 0.6, 0.7,
   0.75, 0.8, 0.85, 0.9, 1.0}). The manifest value is corrected in place
   (15 → 17). Gemma's "2 across 852" is exact. The conclusion — a two-level
   grader cannot express a three-arm ordering — does not depend on whether
   qwen's count is 15 or 17.
2. **Judgment count.** Line 3 says 1,704 judgments. 1,704 were attempted;
   **1,703** are usable — one qwen judgment on seed 424242 came back without
   its required fields (Limits, line 148; `grading_failures: 1, n: 1704`).
3. **Balanced means.** Lines 51–53 give 0.5371 / 0.5589 / 0.5491. Computed
   from the unrounded per-seed means they are 0.5371 / 0.5588 / 0.5490; the
   RESULTS figures were averaged from the already-rounded per-family means.
   The balanced SD 0.0089 is the same either way.
4. **The abstention predicate is not stated.** §"The mechanism, partly
   identified" reports 98.2 % abstentions (278/283), gemma 0.7014 and qwen
   0.4023 on them, but "emitted an empty query and declined" matches no single
   artifact field. The nearest definition — `evidence_volume.records == 0` on
   the seed-424242 answers — gives 277/283 = 0.979, gemma 0.7040, qwen 0.4023:
   within one case. The holdout cross-check (lines 102–104: abstained 71.2 %,
   gemma 0.4098, 13 distinct values) reproduces under the same definition as
   70.1 %, gemma 0.4307 position-averaged / 0.4158 at position 1, and 13
   distinct values exactly. The recorded figures stand as written; the
   predicate that produced them is logged as unrecovered in ISSUES.md.
