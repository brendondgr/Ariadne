# RESULTS — EXP-2026-09-014 Hybrid rewrite stage

**Every figure here is read from `data/metrics_R*.json`.** Arms R2 and R3 are the
mean over three runs with the cache cleared between them; `±` is the population
standard deviation across those three runs, not a confidence interval.

Any figure written as a delta (`+0.243`, `−0.105`) is the difference of two
figures tabulated here; every other number is a key in `data/`.

Split: the **tune half**, 301 of the 579 frozen variants. The `report` half and
`bank-holdout.json` are unread. Served weights: `qwen38-27B-v2`, probed from a
response envelope on every arm.

## The pre-registered ship rule is not met

> Ship only if T4 and T5 `records_exact` are both > 0.25, AND T6 `wrong_entity`
> ≤ 0.1000 and `catalogue_dump` ≤ 0.0667.

**T4 0.0880 ± 0.0089 and T5 0.1635 ± 0.0089. Both fail.** The flags stay off.

The T6 half of the gate passes and improves — `wrong_entity` 0.1111 → 0.0556,
`catalogue_dump` 0.1111 → 0.0371 — but that is not enough on its own, and §"The
cost the gate did not cover" below is why it should not be read as reassurance.

## `records_exact`, per tier

| tier | n | R0 off | R1 det | R2 model (inst. A) | R3 model (inst. B) |
|---|---|---|---|---|---|
| T1 | 63 | 0.4921 | 0.4921 | 0.4921 ± 0.0000 | 0.4921 ± 0.0000 |
| T2 | 63 | 0.4921 | 0.4603 | 0.4762 ± 0.0000 | 0.4762 ± 0.0000 |
| T3 | 51 | 0.2745 | 0.3529 | **0.4706 ± 0.0160** | **0.4706 ± 0.0000** |
| T4 | 53 | 0.0000 | 0.0000 | 0.0880 ± 0.0089 | 0.0943 ± 0.0000 |
| T5 | 53 | 0.0000 | 0.0000 | **0.1635 ± 0.0089** | **0.1698 ± 0.0000** |
| T6 | 18 | 0.1111 | 0.1111 | 0.1111 ± 0.0000 | 0.0926 ± 0.0262 |

Non-dumping recall, which is the honest recall figure:

| tier | R0 | R1 | R2 | R3 |
|---|---|---|---|---|
| T3 | 0.4089 | 0.4721 | 0.6618 | 0.6563 |
| T4 | 0.0000 | 0.0000 | 0.1363 | 0.1407 |
| T5 | 0.0000 | 0.0000 | 0.2027 | 0.2124 |

**T4 and T5 move off 0.0000 for the first time.** EXP-2026-08-020 reported
exactly 0.0000 on 208 questions across every arm it tried; this is the first
configuration in this project's record that retrieves the gold records for a
question that never names its entity. It reaches about a third of the anchor
ceiling Step 3 measured (T4 0.4528, T5 0.5660), so most of the reachable gap is
still not converted.

## The cost the gate did not cover

The pre-registered gate watched T6 only. It should have watched T4 and T5, where
the stage does its work:

| `wrong_entity` | R0 | R1 | R2 | R3 |
|---|---|---|---|---|
| T4 | 0.1321 | 0.1509 | **0.2516** | **0.2642** |
| T5 | 0.1132 | 0.1132 | **0.2453** | **0.2390** |
| T6 | 0.1111 | 0.1111 | 0.0556 | 0.0741 |

**Confident-and-wrong roughly doubles at T4 and T5.** Abstention falls at the
same tiers (T4 0.6415 → 0.4465, T5 0.7736 → 0.4465), so the stage converts
silence into answers, and roughly half of the converted silence is an answer
about the wrong entity. Set against the gain — T5 `records_exact` 0.0000 →
0.1635 for `wrong_entity` 0.1132 → 0.2453 — the stage buys **0.16 right for
0.13 wrong** at T5, and **0.09 right for 0.12 wrong** at T4.

Catalogue dumps improve everywhere (T4 0.2453 → 0.1509, T5 0.1509 → 0.0755,
T6 0.1111 → 0.0371), so the new wrong answers are *specific* wrong answers, not
the catalogue. That is a different failure from the one the engine used to have,
and it is the worse one for this project's value proposition.

## Understanding, separated from retrieval

Slot accuracy against `slot_gold.json` (R2 mean):

| tier | anchor | relation | target label | `form_exact` | model consulted |
|---|---|---|---|---|---|
| T1 | 1.0000 | 0.2400 | 0.1176 | 0.4603 | 0.2381 |
| T2 | 1.0000 | 0.2400 | 0.2059 | 0.4921 | 0.4286 |
| T3 | 0.5098 | 0.3651 | 0.5938 | 0.2484 | 0.6863 |
| T4 | 0.1761 | 0.1304 | 0.4118 | 0.0818 | 0.8931 |
| T5 | 0.2516 | 0.2174 | 0.4706 | 0.0943 | 0.9497 |
| T6 | 0.0000 | 0.7083 | 0.6667 | 0.0000 | 0.7222 |

Three things this says that `records_exact` cannot:

- **The anchor is the binding constraint at T4/T5**, not the relation. It is
  right 0.18–0.25 of the time against a recall@5 ceiling of 0.45–0.57, so the
  chooser converts under half of what the list makes available. More candidates
  would not help; a better chooser would.
- **T6 `slot_anchor` is 0.0000 and stays there.** An invented identifier is
  never matched to a real entity. The negative control holds at the slot level,
  not merely at the record level.
- **`form_exact` at T1/T2 is only ~0.47 while `records_exact` is ~0.49.** The
  form is often wrong in a slot that does not change what is retrieved — the
  relation slot mostly — so slot accuracy is stricter than record identity and
  the two must not be quoted as if they measure the same thing.

## Two serving instances, three runs each

R2 and R3 address two vLLM instances of the **same checkpoint** on different
GPUs (operator, 2026-09-08). This is a cross-instance repeatability block, not a
model comparison, and no cross-model claim may be drawn from it.

The result is that the seam is **highly reproducible**: sd ≤ 0.0160 on every
tier of R2 and 0.0000 on all but T6 of R3, and the two instances differ by at
most 0.0063 on any tier. Call health per run: 2–4% unavailable, 41–45 of 195
picks refused by the gate, 23–30 explicit model declines.

This answers the open half of Q2, and it answers it opposite to the way the
first (confounded) attempt suggested. **The apparent run-to-run variance of an
LLM arm in this pipeline was infrastructure, not the model.** Under the 240 s
call timeout and the 120 s pipeline budget the same arm swung 0.0755 ↔ 0.1509 at
T5; with both bounds lifted the spread is 0.0089. Any variance figure for an LLM
arm must be reported beside its call-failure rate or it is not interpretable.

## The cache

At T4/T5 the model is consulted on 89–95% of questions and the cache hits 90–92%
of them on replay. The cached replay reproduces the arm to within 0.02 on every
tier while costing no model time, which is what makes re-running an LLM arm
affordable — the thing Q2 has needed since August.

## What the deadline costs, separately

Run under the **shipped** `PIPELINE_TIMEOUT_S=120`, the same arm scores T1
0.4180, T3 0.4052, T5 0.1258 (`data/deadline120/`). The rewrite's model call is
charged against the budget retrieval needs, and 20 questions with a
byte-identical canonical question returned different records across runs purely
on how much of the 120 s survived. **Under the shipped budget the model rewrite
loses records it would otherwise retrieve**, and the T1 "regression" first
attributed to the rewrite was the clock: at 900 s, T1 returns to 0.4921, exactly
the no-rewrite baseline. See ISSUES.md.

## The deterministic arm, alone

R1 is byte-reproducible and needs no model. It is **+0.0784 at T3** with T3
dumps down 0.1765 → 0.1373, and **−0.0318 at T2**. Case by case it is 5 better,
3 worse. It binds every slot on 106 of 301 questions; the rest abstain, mostly
because the relation slot cannot be filled — `USES` is unreachable from the word
"use", which is a router stopword (ISSUES.md).

## Federated questions get none of the benefit, and a little of the cost

Split by bank (`data/metrics_by_bank.json`), R0 against R2 run 3 at the clean
budget, with the 120 s figure beside it because the two say different things:

| tier | single R0 → R2 | federated R0 → R2 | federated R2 @120 s |
|---|---|---|---|
| T1 | 0.5455 → 0.5455 | 0.3684 → 0.3684 | 0.1053 |
| T2 | 0.5455 → **0.5682** | 0.3684 → **0.2632** | 0.0000 |
| T3 | 0.3636 → **0.6061** | 0.1111 → 0.1667 | 0.1111 |
| T4 | 0.0000 → **0.1429** | 0.0000 → 0.0000 | 0.0000 |
| T5 | 0.0000 → **0.2286** | 0.0000 → 0.0000 | 0.0000 |
| T6 | 0.1667 → 0.1667 | 0.0000 → 0.0000 | 0.0000 |

Every gain the stage makes is on **single-source** questions, where it is
monotonically non-harmful: unchanged at T1 and T6, +0.023 at T2, **+0.243 at
T3, +0.143 at T4, +0.229 at T5**. Restricted to this half the stage is close to
the pre-registered bar at T5 (0.2286 against 0.25) and still short at T4.

Federated questions get **none** of it — T4 and T5 stay at 0.0000 — and pay
−0.105 at T2. The five-slot form has one relation slot and a federated question
is a chain, so the rewrite delivers the first hop and the second hop's records
are gone. `slot_gold.json` records only an anchor for all 40 federated
questions, so this could not have been caught at the slot level either.

**A correction worth stating plainly.** The first analysis of this split was run
on the 120 s arm and reported the federated tiers collapsing to 0.0000 — read
there as the form's structural limit. At the clean budget T1 federated is
*unchanged* at 0.3684 and T2 falls only to 0.2632. Most of what looked like the
form was the deadline. What survives is narrower and still real: the form cannot
express a chain, so federated questions gain nothing, and T2 loses a little.

## Conclusion

The stage does what it was designed to do and not enough of it. It is the first
configuration to move T4/T5 off zero, it does so reproducibly across two
instances and three runs, its negative control holds at the slot level, and its
catalogue dumps fall everywhere. It also doubles confident-and-wrong at the two
tiers it helps, misses the pre-registered threshold by a factor of two to three,
cannot express a federated question at all, and cannot pay its own latency inside
the shipped pipeline budget.

**Recommendation: leave both flags off.** The measured next steps, in the order
the numbers rank them, are in OPEN_QUESTIONS.md.
