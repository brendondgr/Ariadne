# RESULTS — EXP-2026-09-021 Paraphrase robustness at T0–T3

**Status: running.** `PROTOCOL.md` was pre-registered on 2026-09-15 with three
hypotheses and their falsifiers before any arm ran. This file is filled in as the
steps complete, and nothing is written here that `data/` does not carry.

Plan: [`docs/plans/2026-09-15-paraphrase-robustness-t0-t3.md`](../../../plans/2026-09-15-paraphrase-robustness-t0-t3.md).

**Scope, stated once.** `T0`–`T3` are the tiers in scope. `T4`/`T5` are reported
but are not targets; they exist here so that a lever which helps the tiers in
scope by breaking the others is visible rather than hidden. Every figure is per
tier — the bank over-samples the paraphrase tiers on purpose, so a pooled T0–T3
number would be an artifact of the sampling and none is produced.

## Step 1 — the instrument reproduces (complete, 2026-09-15)

No model, no judge. `data/metrics_reference.json`.

Variants are scored against their own gold question's captured behaviour, so a
reference that is not reproducible makes every downstream figure meaningless.
The 120 golden questions were captured twice on the shipped tree:

| | |
|---|---|
| captures | 2 |
| byte-identical | **yes** — `sha256:891a26147cc65672…` both times |
| questions | 120, **0 errors** |
| extracted nothing | 9 |

**`T0` = 1.0000**, and it is a *determinism control, not an accuracy figure*. It
says the tree reproduces itself; it says nothing about whether the answers are
right. Anything below 1.0000 here would have invalidated the experiment.

The 9 empty captures are expected: 8 are the bank's named negative and exclusion
controls — `T9999`, `G9999`, `C9999`, retired `T1002`/`T1004`, `CAPEC-99999`,
deprecated `CAPEC-557`/`CAPEC-91` — where returning nothing *is* the correct
behaviour.

**One defect blocked the start and is recorded as `I-1`**: the loader's staleness
check refused to run against a graph whose data had not changed
(`EXP-2026-09-018` `I-21`, still unfixed, second occurrence). Proved unchanged
two ways — the canonical manifest differs from the loaded one in exactly one key,
`build_timestamp`, and live counts match `expected_counts` per label on both
stores — then re-stamped by `scripts/revalidate_load_manifest.py`, which refuses
to re-stamp when either check fails.

## Step 2 — the shipped tree re-baselined (complete, 2026-09-15)

No model, no judge. 579 variants, 8 workers, 91 s.
`data/metrics_baseline.json`, `data/metrics_stable_subset.json`.

| tier | n | `records_exact` | `records_recall` | `recall \| no-dump` | `queries_exact` | abstained | `wrong_entity` | `catalogue_dump` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| T0 control | 120 | **1.0000** | — | — | — | — | — | — |
| T1 id + synonym | 120 | 0.3917 | 0.5470 | 0.5470 | 0.3750 | 0.1917 | 0.0833 | 0.0000 |
| T2 id + restructured | 120 | 0.3667 | 0.5230 | 0.5230 | 0.3500 | 0.1917 | 0.0833 | 0.0000 |
| T3 exact name | 101 | 0.1782 | 0.5006 | 0.4413 | 0.1089 | 0.4752 | 0.0990 | 0.1683 |
| T4 paraphrased name | 104 | 0.0000 | 0.0729 | 0.0000 | 0.0000 | 0.8173 | 0.1058 | 0.1923 |
| T5 description only | 104 | 0.0000 | 0.0397 | 0.0000 | 0.0000 | 0.8365 | 0.1058 | 0.1346 |
| T6 negative control | 30 | 0.0667 | 0.0109 | 0.0000 | 0.4667 | 0.9333 | 0.0667 | 0.0667 |

### The August comparison is not like-for-like, and reading it as one inverts it

`records_exact` asks whether a variant extracts what **its own gold question
extracts on the same tree**. `EXP-2026-09-018` changed what the gold questions
extract — deliberately. Against the August reference, **51 of 120** gold cases now
return a different `entity_ids` set and **74 of 120** emit a different query. The
target moved under the metric.

So the naive difference is an artifact. Restricting both runs to the **39 gold
cases whose captured behaviour is identical in both references** — same
`entity_ids` *and* same `queries` — gives the comparison on a fixed target
(`data/stable_subset.py` derives both columns from the four artifacts):

| tier | all variants (target moved) | **stable subset (like-for-like)** |
|---|---:|---:|
| T1 | −0.0750 | **−0.0257** (n=39) |
| T2 | −0.0583 | **0.0000** (n=39) |
| T3 | +0.0792 | **+0.0689** (n=29) |
| T4 / T5 / T6 | 0.0000 | 0.0000 |

**T1 and T2 did not regress.** On a target that did not move, T2 is unchanged to
four decimals and T1 is −0.0257 on 39 variants, which is one variant either way.
The apparent 0.06–0.08 decline in the left column is the repair changing the gold
answers, not the system getting worse at rewording. Anyone quoting the August
tier table against this one without this restriction will report a regression that
did not happen.

### H1 — not met, and the shortfall is the finding

> **H1**: the current `T3` is ≥ 0.25, against the recorded 0.0990.

**`T3` = 0.1782.** The direction is right and the size is not: +0.0792 on the full
tier, +0.0689 like-for-like, so the name-resolution reorder does reach this path
and roughly doubles it — from a very low base to a low one. The pre-registered
falsifier (below 0.15) is not triggered on the full tier; it *is* on the stable
subset at 0.1379, where n is 29. **H1 is recorded as not met.**

### What the repair actually bought at T3 was honesty, not accuracy

| T3 | August | now |
|---|---:|---:|
| `catalogue_dump` | 0.5248 | **0.1683** |
| `wrong_entity` | 0.1485 | **0.0990** |
| abstained | 0.2079 | **0.4752** |
| `records_exact` | 0.0990 | 0.1782 |

Dumping collapsed by two thirds and `wrong_entity` fell at **every** tier
(T1/T2 0.1083 → 0.0833, T4 0.1635 → 0.1058, T5 0.1731 → 0.1058). The system now
declines a `T3` question about as often as it answers one. That is the better
failure — an abstention carries its executed query as proof — but it is not the
bar, and it means `T3`'s remaining loss is now mostly *unanswered* rather than
*answered wrongly*.

### The gap to the bar, stated as a number

Against the bar in `PROTOCOL.md` — `T1`/`T2` ≥ 0.9, `T3` ≥ 0.85:

| tier | now | bar | gap |
|---|---:|---:|---:|
| T1 | 0.3917 | 0.9 | **−0.5083** |
| T2 | 0.3667 | 0.9 | **−0.5333** |
| T3 | 0.1782 | 0.85 | **−0.6718** |

`queries_exact` at `T1` is 0.3750 against `records_exact` 0.3917: at this tier
the system nearly always reaches the right records by reaching the right
*interpretation*, so the loss is interpretation, not execution. That is the
mechanism Steps 3 and 4 test.

## Step 3 — H2 is falsified, and the direction is the opposite (complete, 2026-09-15)

No model, no judge. `SPECIALIST_GENERIC_ONLY=true`, same bank, same reference,
57 s. `data/metrics_primitives.json`, `data/metrics_paired_engines.json`.

> **H2**: the primitives beat the templates by ≥ 0.10 at `T1` and `T2`, because
> they select on labels and declared relations and never read a verb.
> **Falsifier**: within ±0.05.

| tier | n | templates | primitives | difference |
|---|---:|---:|---:|---:|
| T1 | 120 | 0.3917 | 0.2167 | **−0.1750** |
| T2 | 120 | 0.3667 | 0.2500 | **−0.1167** |
| T3 | 101 | 0.1782 | 0.1089 | −0.0693 |
| T4 / T5 | 104 | 0.0000 | 0.0000 | 0.0000 |
| T6 | 30 | 0.0667 | 0.1000 | +0.0333 |

**Falsified past its own falsifier.** The prediction was +0.10 and the measurement
is −0.175 at `T1`: not "no effect", but a large effect with the sign reversed. The
reasoning behind `H2` — that an engine which never reads a verb cannot be hurt by
a changed verb — was wrong, and the paired table says why.

### There is no complementarity here, so no routing rule can rescue it

| tier | both | templates only | **primitives only** | oracle "either" |
|---|---:|---:|---:|---:|
| T1 | 26 | 21 | **0** | 0.3917 |
| T2 | 29 | 15 | **1** | 0.3750 |
| T3 | 11 | 7 | **0** | 0.1782 |

**Primitives solve a near-strict subset of what templates solve.** Across 341
variants at the three tiers in scope, primitives succeed on exactly **one**
variant that templates miss. The oracle upper bound on per-question selection —
what a chooser with perfect foreknowledge would score — is 0.3917 at `T1`,
**identical to templates alone**, and +0.0083 at `T2`, which is that one variant.

This is worth recording because it contradicts the shape `EXP-2026-09-020` found
twice on the development bank at the real planner, where union equalled oracle
pick-best for both engines (`A-1`) and both planners (`A-2`). **Complementarity is
not a property of the two engines; it is a property of that bank and that plan
source.** On anchored questions with a replayed plan the primitive path adds
coverage the templates lack; on reworded questions it adds nothing at all. Both
readings are now measured, and neither generalises to the other.

### Why the reasoning failed

`queries_exact` at `T3` is **0.0000** for primitives against 0.1089 for
templates, and abstention runs 0.3833 against 0.1917 at `T1`/`T2`. The primitive
path does not read the verb — and that is exactly the problem. Removing the
template ladder removes the only component that converts "defend against" into an
*intent*; the primitives are left selecting a relation from an anchor with less
information than the templates had, and they decline rather than guess. Their
fidelity is genuinely better for it (`catalogue_dump` at `T3` 0.1683 → 0.0594,
`wrong_entity` 0.0833 → 0.0667 at `T1`), which is the honest failure — but
abstaining twice as often is not the bar.

**Consequence for the plan.** `SPECIALIST_GENERIC_ONLY` must not be turned on for
the workbench on the strength of rewording robustness; it is measurably worse at
every tier in scope. Its case remains what it always was and is untouched by this:
templates cannot accept a question nobody wrote a template for. Step 5's scoping
is now the only remaining route to `T1`/`T2`.
