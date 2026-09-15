# RESULTS — EXP-2026-09-021 Paraphrase robustness at T0–T3

**Status: complete.** `PROTOCOL.md` was pre-registered on 2026-09-15 with three
hypotheses and their falsifiers before any arm ran. **All three were falsified.**
Nothing is written here that `data/` does not carry.

**The one-line result:** the shipped tree's rewording cliff is real and mostly
unmoved — `T1` 0.3917 and `T2` 0.3667 against a 0.9 bar, untouched by every lever
tried. `T3` alone improved, 0.1782 → **0.3267**, by gating the rewrite stage on
the question citing no identifier; that gate is built, tested and **shipped**
under a fidelity rule the operator changed after the pre-registered one failed
(`D-034`), and the original FAIL verdict is preserved here and in `data/`.

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

## Step 4 — H3 is falsified, and the mechanism is a trade (complete, 2026-09-15)

`--rewrite model` against the relay at `:9090`, served weights asserted from the
response envelope as **`qwen38-27B-v2`** — the same weights `EXP-2026-09-014` ran.
579 variants, 8 workers, 57 min. `data/metrics_rewrite.json`,
`data/metrics_paired_rewrite.json`.

> **Pre-registered ship rule (plan §Step 4):** `T3` ≥ baseline + 0.10, **and** no
> tier `T0`–`T2` below baseline − 0.02, **and** `wrong_entity` ≤ 0.0950, **and**
> `catalogue_dump` ≤ 0.0915.

| tier | n | baseline | rewrite | difference | fixed | broken |
|---|---:|---:|---:|---:|---:|---:|
| T1 | 120 | 0.3917 | 0.2750 | **−0.1167** | 3 | **17** |
| T2 | 120 | 0.3667 | 0.3000 | **−0.0667** | 7 | **15** |
| T3 | 101 | 0.1782 | **0.3168** | **+0.1386** | **21** | 7 |
| T4 | 104 | 0.0000 | 0.0962 | +0.0962 | 10 | 0 |
| T5 | 104 | 0.0000 | 0.1250 | +0.1250 | 13 | 0 |
| T6 | 30 | 0.0667 | 0.0667 | 0.0000 | 0 | 0 |

**Clause by clause: `T3` **passes** at +0.1386. `T1` fails at −0.1167 and `T2`
fails at −0.0667, both far outside the −0.02 tolerance. The fidelity clauses pass
in scope (`wrong_entity` 0.0750 / 0.0667 / 0.0891; `catalogue_dump` 0.0083 / 0.0000
/ 0.0693). **The rule fails, so the stage does not ship, and `H3` is recorded as
falsified.**

### The finding is the sign split, not the verdict

The tier means net two large opposite effects, and the paired counts separate
them cleanly:

- **Where the identifier survives (`T1`, `T2`), the rewrite destroys answers**:
  32 broken against 10 fixed across 240 variants.
- **Where the identifier is gone (`T3`, `T4`, `T5`), it only helps**: 44 fixed
  against 7 broken, and at `T4`/`T5` it breaks **nothing**, because there was
  nothing to break — both were 0.0000.

That is a mechanism, not a wash. The stage canonicalises a question into the
source card's own vocabulary; when the question already carries an identifier the
template ladder was reading, canonicalising throws that information away and the
ladder reaches a different template. **The stage is not wrong — it is applied
unconditionally.**

### What this implies, and what it does not

The condition that separates the two populations — *did we resolve an identifier
from the question* — is computable at run time from the question alone. It needs
no gold and no foreknowledge, which is what distinguishes it from the oracle
bounds in `EXP-2026-09-020` `A-1`/`A-2`.

**Nothing is claimed for it here.** `A-3` reasoned a coverage number from
structure without running it and was 0.27 too high; the projection that gating the
rewrite on a missing identifier would hold `T1`/`T2` at baseline while taking
`T3`'s +0.1386 is **a hypothesis for Step 5, not a result.** It has to be
implemented and re-run, because the run-time condition is a proxy for the tier
label and the two need not coincide case by case.

### One cost outside the scope, recorded because the plan said to

At `T4`/`T5` the stage roughly **doubles `wrong_entity`** — 0.1058 → 0.2404 and
0.1058 → 0.2308 — while lifting `records_exact` off the floor. It converts
"declines to answer" into "answers, sometimes about the wrong entity". Those tiers
are not targets here, but any future decision to ship the stage for them owns
that trade, and `EXP-2026-09-014` reported the same wrong-entity rise.

### Cost

57 minutes at 8-way concurrency for 579 variants, against 91 s for the model-free
baseline — **a 38× wall-clock penalty** for the stage, on top of a live endpoint
on the critical path. `EXP-2026-09-014`'s harness note is why the concurrency was
held at 8: at 32-way the served model exceeded the old 240 s read timeout on about
a third of calls, and a timed-out call **abstains**, which is indistinguishable
downstream from a model with nothing to say. This run raised the timeout to 600 s,
so the ceiling can be lifted for later model-backed arms.

## Step 5 — the identifier gate: built, measured, and 8 of 9 clauses (complete, 2026-09-15)

Step 4's sign split said the rewrite stage is not wrong but *unconditional*. The
condition is computable at run time, so it was implemented rather than projected.

**What was built.** `PlannerConfig.rewrite_only_without_identifier`
(`ARIADNE_REWRITE_ONLY_WITHOUT_ID`, **default off**) and a new rung
`RUNG_SKIPPED_ID` in the `canonicalize` node. When set, the node asks whether the
question cites an identifier and stands down if it does. The predicate delegates
to the resolver's own `_native_ids` through `canonical._ids_in` — the module's own
note says a second opinion about what an identifier is, is the one thing this
design exists not to have.

**The flag-off path is byte-identical.** The whole bank was re-run at
`--rewrite off` after the change and compared to the Step 2 artifact: **579 of
579 rows identical**, timing excluded per the harness's own rule. 337 tests pass
across `utils/orchestration` and `utils/planner`, six of them new
(`utils/orchestration/tests/test_rewrite_identifier_gate.py`).

### The gate fires where it was designed to

| tier | `skipped_identifier` | model rung | other |
|---|---:|---:|---:|
| T1 | **118 / 120** | 1 | 1 abstain |
| T2 | **118 / 120** | 0 | 2 abstain |
| T3 | **0 / 101** | 50 | 30 det, 21 abstain |
| T4 | 0 / 104 | 51 | 50 abstain, 3 det |

Two `T1` variants and two `T2` variants carry no identifier the resolver
recognises, so they reach the stage. That is the gate being a *run-time
predicate* rather than a tier label, which is exactly why it had to be run.

### Results

| tier | baseline | rewrite (ungated) | **rewrite, gated** |
|---|---:|---:|---:|
| T1 | 0.3917 | 0.2750 | **0.3917** |
| T2 | 0.3667 | 0.3000 | **0.3667** |
| T3 | 0.1782 | 0.3168 | **0.3267** |
| T4 | 0.0000 | 0.0962 | 0.0962 |
| T5 | 0.0000 | 0.1250 | 0.1250 |

**`T1` and `T2` are restored to baseline exactly** — to four decimals on every
column, and outcome-identical on **239 of 240** variants; the one difference is a
`T1` variant that cites no identifier and legitimately reached the stage.

**`T3` is 0.3267, above the ungated 0.3168.** The gate is not merely neutral
there: it recovers one case the ungated arm lost, because the run-time predicate
and the tier label do not coincide case by case. This is why the Step 4 write-up
refused to claim the projection — the measured value is **better** than the
projection would have stated, and either direction was possible.

### The verdict: FAIL, 8 of 9 clauses, and the rule is not being moved

`data/gate_verdict.py` applies the rule written in the plan before Step 4 ran:

| clause | value | verdict |
|---|---:|---|
| T3 ≥ baseline + 0.10 | +0.1485 | PASS |
| T1 not below baseline − 0.02 | 0.0000 | PASS |
| T2 not below baseline − 0.02 | 0.0000 | PASS |
| T1/T2/T3 `wrong_entity` ≤ 0.0950 | 0.0833 / 0.0833 / 0.0891 | PASS |
| T1/T2 `catalogue_dump` ≤ 0.0915 | 0.0000 / 0.0000 | PASS |
| **T3 `catalogue_dump` ≤ 0.0915** | **0.1089** | **FAIL** |

**`T3` dumping exceeds the cap by 0.0174.** The mechanism is visible: the gate
answers more `T3` questions than the ungated arm (abstention 0.3465 → 0.2772) and
some of those answers dump.

**The honest tension, stated rather than resolved by fiat.** The gated arm's
`T3` dumping is **below the shipped baseline it would replace** — 0.1089 against
0.1683 — so on a "not worse than what ships" reading it improves. But the rule as
written caps it at 0.0915, the `EXP-2026-09-018` whole-bank reference, and that
number was pre-registered as a per-tier cap. Relaxing a threshold after seeing the
value it failed is the precise thing pre-registration exists to prevent, so the
threshold stands and the verdict is FAIL.

**Consequence: `ARIADNE_REWRITE_ONLY_WITHOUT_ID` ships off**, alongside
`ARIADNE_REWRITE` which is also off. The implementation is committed, tested and
flag-gated rather than reverted, because unlike `EXP-2026-09-020` `A-4` this is
not a measured-negative switch — it is a measured-positive one that misses a
fidelity cap by 0.0174, and the operator's decision on that cap is a product call
this experiment does not get to make on its own.

### The gap to the bar has not moved

| tier | best measured | bar | gap |
|---|---:|---:|---:|
| T1 | 0.3917 | 0.9 | **−0.5083** |
| T2 | 0.3667 | 0.9 | **−0.5333** |
| T3 | 0.3267 | 0.85 | −0.5233 |

`T3` closed 0.1485 of its gap. **`T1` and `T2` have not moved at all** across
three levers — the baseline, the engine swap, and the rewrite stage in both
forms. Every intervention on record now either does nothing to them or makes them
worse.

### Cost

32-way concurrency at a 600 s read timeout: the gated arm ran in under the 57
minutes the ungated arm took at 8-way, and roughly half its variants never call
the model at all.

## Step 6 — close-out: shipped under a changed rule, with the original verdict intact (complete, 2026-09-15)

**The operator elected the "not worse than the shipped baseline" reading of the
fidelity clause and shipped the gate.** Recorded as `D-034`, which reverses
`D-032` for the gated configuration only.

| | pre-registered rule | operator rule (`D-034`) |
|---|---|---|
| `T3` `catalogue_dump` | ≤ 0.0915 → **FAIL** at 0.1089 | ≤ baseline 0.1683 → **PASS** at 0.1089 |
| every other clause | PASS | PASS |
| **verdict** | **FAIL, 8/9** | **PASS, 9/9** |

`data/gate_verdict.py` computes **both**, and `data/metrics_gate_verdict.json`
carries both. The pre-registered verdict is not re-scored, softened or removed:
it stands as FAIL. `D-032` rejected relaxing a threshold after seeing the value
that failed it, and that reasoning is not withdrawn — what overrides it is an
explicit operator call on a product question (how much catalogue dumping an
analyst tool may do), which was never the experiment's to make.

### What shipped

`ARIADNE_REWRITE=1`, `ARIADNE_REWRITE_MODEL=1`, `ARIADNE_REWRITE_ONLY_WITHOUT_ID=1`
in `.env` and `.env.example`, documented in the README's "What Actually Runs".

**Verified live through `iter_pipeline`, the path `app.py` serves:**

| question | rung | result |
|---|---|---|
| "How do I defend against T1047?" | **`skipped_identifier`** | untouched, 1 id — `T1` behaviour preserved |
| "Which countermeasures apply to Windows Management Instrumentation?" | **`model`** | canonicalised to "In ATT&CK, give the mitigations that mitigates technique T1047." → **5 ids** |

**Failure mode tested, not assumed.** Pointed at a dead endpoint, the stage
records `rung: abstain` with `model unavailable: …`, leaves the form unbound and
forwards the analyst's own words. No exception escapes the planner.

### The two costs, stated where they cannot be missed

1. **`T3` dumping is above the pre-registered cap** — 0.1089 against 0.0915 —
   and below the 0.1683 it replaces. Shipped on the second reading.
2. **`T4`/`T5` `wrong_entity` roughly triples**: 0.1058 → **0.3077** and
   **0.2981**, worse than the ungated arm. The stage converts abstentions into
   answers there, and about a third of the converted silence names the wrong
   entity. This experiment's own protocol said "a lever that helps `T0`–`T3` by
   breaking the others is not a lever we would ship", and `D-032` point 2 refused
   an earlier version of the stage for the same reason. It ships regardless, by
   decision. **Gating `T4`/`T5` separately is the obvious follow-up and has not
   been attempted.**

### Where the bar stands at close

| tier | at Step 1 | shipped | bar | gap |
|---|---:|---:|---:|---:|
| T0 | 1.0000 | 1.0000 | — | control |
| T1 | 0.3917 | 0.3917 | 0.9 | **−0.5083** |
| T2 | 0.3667 | 0.3667 | 0.9 | **−0.5333** |
| T3 | 0.1782 | **0.3267** | 0.85 | −0.5233 |

**One tier moved.** `T3` gained 0.1485, an 83% relative improvement, and it is
the tier where the analyst names a thing without knowing its identifier — the
shape of an open-ended question, which is the use case that motivated the work.

**`T1` and `T2` did not move at all**, across three levers and four measured
arms. Every intervention on record either leaves them untouched or makes them
worse: the primitive engine −0.1750, the ungated rewrite −0.1167, the gated
rewrite 0.0000. Their loss is **interpretation, not execution** — `queries_exact`
0.3750 against `records_exact` 0.3917 means the system almost always retrieves
correctly once it has understood, and understands the reworded question barely
more than a third of the time.

**What that leaves.** The unattempted lever is the one `EXP-2026-09-020` `A-3`
pointed at and this experiment scoped but did not build: rank the question against
the relations the **resolved anchor actually declares**, instead of matching a verb
to a template. The candidate set is small — 26 distinct predicates across the
bank, a median of 5 declared relations per anchor. `A-4`'s caution binds it: rank,
keep the `describe` fallback, never union. That is new engineering, it is the
only remaining route to `T1`/`T2`, and nothing in this experiment estimates what
it would be worth.

**The metric caveat that outlives this experiment.** Every figure here is
`records_exact` — exact record-set identity — which is strict and is not what an
analyst experiences. `records_recall` runs 0.15–0.32 higher at every tier in
scope, and judged correctness would read higher still. Whether the 0.9 bar belongs
on this metric is open (`PROTOCOL.md` §Metrics), and settling it needs a judged
pass that has not been run.
