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
