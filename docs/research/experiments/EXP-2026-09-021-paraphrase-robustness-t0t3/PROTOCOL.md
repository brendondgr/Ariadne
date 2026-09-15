# PROTOCOL — EXP-2026-09-021 Paraphrase robustness at T0–T3

> Written 2026-09-15, before any run of this experiment. Plan:
> [`docs/plans/2026-09-15-paraphrase-robustness-t0-t3.md`](../../../plans/2026-09-15-paraphrase-robustness-t0-t3.md).

## Question

On the tiers the use case actually needs — the gold question verbatim (`T0`), the
same question with the verb changed (`T1`), the same question restructured
(`T2`), and the entity's exact name without its identifier (`T3`) — what does the
**shipped tree** extract today, and do either of two already-built levers close
the gap to a per-tier bar of 0.9?

`T4` (paraphrased name) and `T5` (description only) are out of scope as targets.
They are still run and reported, because a lever that helps `T0`–`T3` by breaking
them is not a lever we would ship.

## Hypothesis

**H1 (stale baseline).** `EXP-2026-08-020`'s Arm 0 ran at `0ae78c19`. The change
that resolves a named entity *before* the template ladder rather than at the
no-anchor fall-through landed at `9f02dc6b`, and the `EXP-2026-09-018` repair
landed after that. `T3` is exactly "exact name, no identifier", which is what the
reorder targets. So the current `T3` is **≥ 0.25**, against the recorded 0.0990.

**H2 (engine).** `T1` keeps the identifier, so entity resolution is not the
failure — selection of a template from surface vocabulary is. The schema-derived
primitives select on labels and declared relations and never read a verb. So
under `SPECIALIST_GENERIC_ONLY=true` the primitives beat the templates by
**≥ 0.10** at `T1` and `T2`.

**H3 (re-gate).** `EXP-2026-09-014`'s rewrite stage gained +0.1961 at `T3`
(0.2745 → 0.4706) and improved fidelity, and was refused by a rule requiring `T4`
**and** `T5` above 0.25. Judged against a `T0`–`T3` rule instead, it **passes**.

## Setup

One tree, `main` at the commit in `manifest.yaml`, three configurations over the
identical bank and the identical reference:

| Arm | Configuration | Question it answers |
|---|---|---|
| `baseline` | shipped defaults, `--rewrite off` | H1 |
| `primitives` | `SPECIALIST_GENERIC_ONLY=true`, `--rewrite off` | H2 |
| `rewrite` | shipped defaults, `--rewrite model` | H3 |

Held constant: the reference capture, the variant bank, `ORCH_MAX_HOPS=5`, the
worker count, and the graph snapshots (`attack` on Neo4j, `capec` on Gremlin,
both probed reachable before the run). No LLM is in the loop for `baseline` or
`primitives`; the `rewrite` arm's model rung is the only model call, and its
served identity is asserted from the response envelope.

## Data

`docs/evaluation/variants-2026-08-29/variants.json` — 579 variants authored for
`EXP-2026-08-020` from the 120-question golden catalogue:
`T1` 120, `T2` 120, `T3` 101, `T4` 104, `T5` 104, `T6` 30.
`sha256:428a23467ecf8aed…` (full hash in `manifest.yaml`).

The bank **over-samples the paraphrase tiers on purpose**, so a pooled figure
across tiers is an artifact of the sampling and is never produced. Every number
is per tier. Selection bias that does apply: the variants were authored against
the gold catalogue by the same programme that built the system, and `T3`'s 101
(rather than 120) reflects questions whose entity has no usable bare name.

`T0` is not in this file. It is the 120 gold questions re-run and scored against
their own capture — see Metrics.

## Metrics

Per tier, over the variants of that tier:

- **`records_exact`** — *primary.* The set of entity identifiers extracted equals
  the set its gold question extracted. Outcome, not interpretation: a variant
  that reaches the same records by a different query counts as a success.
- **`records_recall`** — fraction of the gold question's records recovered.
- **`recall | no-dump`** — the same, with catalogue dumps excluded. `EXP-2026-08-020`
  found `T3` recall was mostly dumping, so the two must be read together.
- **`queries_exact`** — emitted query strings identical. Strictest; diagnostic.
- **`catalogue_dump`** — result both ≥50 records and ≥10× the gold's size.
- **`wrong_entity`** — records returned, none of them in the gold answer.
- **`abstained`** — declined to answer.

**`T0` is a determinism control, not an accuracy figure.** It is produced by
capturing the 120 gold questions twice and diffing; 1.0000 means the tree is
reproducible, and anything below it invalidates every variant score in this
experiment because variants are scored against that capture.

**The bar.** Per tier on `records_exact`: `T1`, `T2` ≥ 0.9 and `T3` ≥ 0.85, with
`wrong_entity` ≤ 0.0950 and `catalogue_dump` ≤ 0.0915 (the `EXP-2026-09-018`
shipped reference). No pooled T0–T3 number is computed. Whether the bar belongs
on `records_exact` at all is an open operator question recorded in the plan §2:
the metric the use case cares about is judged correctness, which is scoped as an
optional later step and is **not** measured here.

## Baselines

`EXP-2026-08-020` Arm 0 (the August tier table) is the historical comparison, and
it is **not** a fair like-for-like: it ran on a different tree. That is the point
of arm `baseline`, which re-establishes the comparison on one tree. Arms
`primitives` and `rewrite` are each compared against `baseline` from the same
session, same reference, same bank.

`EXP-2026-09-014`'s `R0`/`R2` are a second historical reference for the rewrite
arm, on the 301-variant tune half rather than the full bank.

## Procedure

```bash
uv run main.py --graph health
uv run python scripts/variant_harness.py capture --out docs/evaluation/variants-2026-09-15 \
    --name reference.json --workers 8
uv run python scripts/variant_harness.py capture --out docs/evaluation/variants-2026-09-15 \
    --name reference_check.json --workers 8
# diff the two; identical is a precondition for everything below
uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-2026-09-15 \
    --name scored_baseline.json --rewrite off --workers 8 \
    --metrics ../../research/experiments/EXP-2026-09-021-paraphrase-robustness-t0t3/data/metrics_baseline.json
SPECIALIST_GENERIC_ONLY=true uv run python scripts/variant_harness.py compare \
    --out docs/evaluation/variants-2026-09-15 --name scored_primitives.json --rewrite off --workers 8 \
    --metrics ../../research/experiments/EXP-2026-09-021-paraphrase-robustness-t0t3/data/metrics_primitives.json
uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-2026-09-15 \
    --name scored_rewrite.json --rewrite model --workers 8 \
    --metrics ../../research/experiments/EXP-2026-09-021-paraphrase-robustness-t0t3/data/metrics_rewrite.json
```

## What would falsify this

- **H1** — `T3` below 0.15 on `baseline`. The name-resolution reorder did not
  reach this path, and `T3` depends entirely on the rewrite stage.
- **H2** — `primitives` within ±0.05 of `baseline` at `T1` and `T2`. Engine
  choice is not the lever for the tiers that keep their identifier, and the
  residual gap is intent selection, to be scoped as new work rather than
  configured away.
- **H3** — the rewrite arm fails any clause of the `T0`–`T3` ship rule in the
  plan §Step 4: `T3` gain < 0.10 over `baseline`, or any of `T0`–`T2` below
  `baseline` − 0.02, or `wrong_entity` > 0.0950, or `catalogue_dump` > 0.0915.

**A negative result on all three is a complete result** and is recorded as one,
with the residual gap stated as a number. `EXP-2026-09-020` `A-3` reasoned a
coverage bound from schema structure without running it and was 0.27 too high;
nothing in this experiment is claimed before it is measured.
