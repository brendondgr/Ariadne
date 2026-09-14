# Results — EXP-2026-09-020

Status: **complete**. Every number here is read from `data/metrics.json`, which
`data/build_metrics.py` composes from the run artifacts.

**The finding in one line: the primitive engine's advantage over hand-written
templates is contingent on having a good plan, and production does not have
one.** At the authored plan primitives lead by **+0.2184**; at the real planner
the lead falls to **+0.0261 and is not separable**.

## Why this experiment exists

`EXP-2026-09-018` measured templates against schema-derived primitives and the
primitives won decisively — 0.9005 against 0.5525 judged, on a sealed set. That
comparison, like every headline this programme has published, ran against a
**human-authored plan that is replayed**. `app.py` does not replay a plan:
`api/services/query.py` calls `iter_pipeline`, so the planner executes.

No arm on record was production's configuration. Every `deterministic`-family
arm drives `run_deterministic`, which replays the authored plan. So the question
actually being asked — *should the shipped workbench swap its query-construction
engine* — had one measured cell out of the two that matter.

`deterministic_planned` is `generic_planned` with one flag inverted
(`SPECIALIST_GENERIC_ONLY`). Both drive `run_planned`; both execute the planner;
both load `SynthesisConfig` by the same route. All four cells ran on one tree,
model-free and byte-reproducible, 284/284 each.

## The 2×2

Deterministic gold coverage, 284 development questions, paired per question.

| | **authored plan** | **real planner** *(what `app.py` does)* |
|---|---:|---:|
| **hand-written templates** | 0.6428 | **0.4536** |
| **schema-derived primitives** | **0.8611** | 0.4797 |

Zero-record counts, same order: 22 and **55** for templates, 9 and **85** for
primitives.

### The engine effect — the question that was asked

| Plan source | primitives − templates | SE | Separable |
|---|---:|---:|---|
| authored plan | **+0.2184** | 0.0233 | **yes** |
| real planner | **+0.0261** | 0.0255 | **no** |

**Interaction: −0.1923.** The two variables interact strongly, which is the
opposite of what `EXP-2026-09-019` found for the *model* seam, and it is why the
corner cells are misleading on their own.

### The plan effect — and templates survive it better

| Engine | real planner − authored plan | SE | Retrieved nothing where the other retrieved |
|---|---:|---:|---:|
| templates | **−0.1892** | 0.0241 | 45 |
| primitives | **−0.3814** | 0.0262 | 77 |

**A bad plan costs the primitive engine roughly twice what it costs the
templates.** The mechanism is visible in the zero-record counts: under the real
planner primitives return nothing on 85 of 284 questions against templates' 55,
and on **51 questions templates retrieved records where primitives retrieved
nothing**. A template constrains the shape of the query, so a poor decomposition
still lands on something defensible; a primitive follows the plan literally, so
a poor decomposition becomes a poor traversal. The generality that makes
primitives able to answer anything is the same property that makes them
faithful to a bad instruction.

### The effect changes sign by tier

| Tier | n | primitives − templates, at the real planner |
|---|---:|---:|
| easy | 35 | **−0.1586** |
| adversarial | 36 | **−0.1389** |
| hard | 129 | **+0.0659** |
| medium | 84 | **+0.1127** |

The aggregate +0.0261 is a cancellation, not an agreement. Templates win where
the question is routine or adversarial; primitives win where it is hard or
medium. Reporting only the mean would hide both.

## What this means for `app.py`

**A straight swap is not supported.** Setting `SPECIALIST_GENERIC_ONLY=true` in
the shipped workbench buys +0.0261 coverage that this experiment cannot
distinguish from zero, while raising zero-record answers from 55 to 85 — the
analyst-visible failure mode of "I found nothing" — and losing 51 questions that
templates answered.

**What the evidence does support is routing, not replacement.** The tier table
is a routing rule with the sign of the effect on both sides of it. That is also
the honest form of the generality argument: templates cannot accept a question
nobody wrote a template for, so the primitive path is still what makes the
system open-ended — it is just not, at production's plan source, uniformly
better at the questions templates *can* take.

**The real target is the planner.** It costs −0.1892 to templates and −0.3814 to
primitives, and it is the largest term in every cell of this table. Fixing it
raises both engines and is what would make the swap worth making: the
primitives' +0.2184 at an authored plan is what is available if the planner
reaches that quality.

## What this does not say

- **The metric is retrieval, not correctness.** Gold coverage is deterministic
  and model-free, which is what makes a 284-question 2×2 affordable and immune
  to grading noise; it is not the judged score the 0.9005 headline is. A judged
  pass on the two planner cells is warranted — the engine difference clears the
  0.02 threshold, though barely and not separably — and has not been run.
- **It does not withdraw `EXP-2026-09-018`.** 0.9005 against 0.5525 stands as
  measured, at the plan source it was measured at. This experiment establishes
  that the figure does not transfer across a change of plan source, which is a
  limit on its scope rather than a correction to its value.
- **`Q58`'s confound does not reach the engine comparison.** The self-planning
  arm inherits tighter per-plan bounds (`max_result_rows: 1000`,
  `max_traversal_depth: 3`), which is why `Q58` is open against the *plan*
  effect. Both cells of the engine comparison at the real planner inherit the
  same bounds from the same planner, so that term cancels. It still applies to
  the plan-effect column.

## Amendment A-1 — run both engines instead of choosing one (2026-09-14)

The 2×2 above was read as a choice, and the choice is the wrong frame. Both
engines cost **0.095 s per answer single-user with the planner running**, so
running both costs about a tenth of a second in parallel. Scoring the union of
what they retrieve — a gold id counts as found if *either* engine found it —
against each alone, on the same 284 questions at production's plan source:

| Configuration | Gold coverage | Empty answers |
|---|---:|---:|
| templates only | 0.4536 | 55 |
| primitives only | 0.4797 | 85 |
| **both, evidence merged** | **0.5862** | **34** |
| both, oracle pick-best | 0.5862 | — |

**The merge equals the oracle.** Picking the better engine per question with
perfect foreknowledge scores exactly what merging scores, to four decimals. The
two engines' evidence sets are **complementary rather than competing**, which
means the routing rule I recommended earlier is unnecessary: there is nothing to
predict, because taking both loses nothing against choosing perfectly.

**+0.1064 over the better single engine** — four times the +0.0261 that choosing
between them is worth, and it needs no tier classifier, no held-out validation of
a routing rule, and no model.

Empty answers fall from 55 (templates) and 85 (primitives) to **34**. That is the
analyst-visible failure mode, down 38% against the better single engine.

### A rule that needs no foreknowledge, if merging is too invasive

| Rule | Coverage |
|---|---:|
| prefer primitives, fall back when they retrieved nothing | **0.5713** |
| prefer templates, fall back when they retrieved nothing | 0.5020 |

The first captures 87% of the merge benefit with a one-line condition, and is the
cheaper thing to ship first.

### What this does not establish

- **Merging more evidence is not proven free.** More records reaching the
  composer could raise wrong-entity or catalogue-dump rates; `EXP-2026-09-018`'s
  T6 instrument is the thing that would catch it and has not been run on a merged
  configuration. The coverage gain is measured; the fidelity cost is not.
- **Still retrieval, not judged correctness**, and still at a plan source that
  loses 0.38 to the authored path. Merging raises the floor; it does not reach the
  0.8611 ceiling, and the planner remains the dominant term.
- The 34 questions where **both** engines retrieve nothing are a planner
  diagnostic set, not an engine one.

## Amendment A-2 — two planners are complementary; one planner is not better (2026-09-14)

`A-1` found the two query engines complementary. The same question for the
*planner*, which `A-1` established is the dominant term: `generic_planned_llm` is
`generic_planned` with an LLM drafter and every other seam still off, run against
`gemma-4-26B-it` on the local relay. All 284 questions.

| | Gold coverage | Empty answers |
|---|---:|---:|
| deterministic planner | 0.4797 | 85 |
| LLM planner | 0.4858 | 114 |
| **both planners, evidence unioned** | **0.6596** | **46** |
| oracle pick-best | 0.6596 | — |
| authored plan (ceiling) | 0.8611 | 9 |

**Union − deterministic = +0.1799** (SE 0.0208, n=284, separable by a factor of
nine). It is by a wide margin the largest single improvement measured on this
programme's planning stage.

**The LLM planner is not better.** Alone it is worth **+0.0061**, which is noise.
Every reading that treats "use a model to plan" as the finding here is wrong. The
value is entirely in *complementarity* — and the evidence for that is the same
signature `A-1` found: **union equals oracle pick-best to four decimals**. The two
planners select different correct relations, neither dominates, and taking both
loses nothing against choosing perfectly.

### The complementarity is visible in the tiers

| Tier | n | LLM − deterministic |
|---|---:|---:|
| adversarial | 36 | **−0.3056** |
| easy | 35 | −0.1000 |
| hard | 129 | **+0.0535** |
| medium | 84 | **+0.1108** |

The aggregate +0.0061 is a cancellation of two large opposite effects, which is
exactly the shape `A-1` reported for the engines. A programme that had only read
the aggregate would have discarded the LLM planner as worthless.

### A caution recorded against myself

The first read of this arm, at 73 of 284 answers, reported the LLM planner at
**−0.1637 and separable** — the opposite conclusion. The bank is ordered by tier
and `--limit` takes the first N by name, so that slice was entirely `D6`
cross-catalogue questions, the tier the LLM planner loses worst. The interim
figure was quoted before the run finished. **Partial results from this bank are
not a random sample of it**, and nothing from a `--limit` slice should be read as
an estimate of the whole.

### What this does not establish

- Retrieval, not judged correctness, and the merged configurations have never
  been through the `T6` entity-fidelity instrument. Three unions now stack
  (engines, facets, planners) and every one of them puts more records in front of
  the composer. `EXP-2026-09-018` records `catalogue_dump` at 0.0915 on the
  shipped tree; that is the number a merged configuration has to be held to.
- The LLM planner costs about 12 s per question against the deterministic
  planner's 0.095 s — a live model on the critical path, where every other union
  measured today is free.
- 0.6596 against a 0.8611 ceiling. The union closes 47% of the planner gap and
  leaves the rest.

## Amendment A-3 — the ceiling cannot be replayed, but most of it can be reached without selecting anything (2026-09-14)

**The authored plan cannot be shipped.** `utils/specialists/evalset/spec_bank.py`
builds it from a `spec`, and that same `spec` produces the question text *and*
`ex_gold`. Replaying it hands the system the traversal that defines the correct
answer, so using it in production would require knowing the answer in order to
plan the query. This is recorded as `Q57` and is not an engineering obstacle.

**What the ceiling represents, however, is reachable by a different route.**
0.8611 is what the engine achieves when handed a correct traversal. The planner
has been trying to *select* that traversal from the question text, and three
deterministic selectors and one LLM all fail to clear 55% predicate accuracy. The
measurement below says selection is the wrong goal.

### The candidate set is tiny

| | |
|---|---:|
| distinct predicates in the whole 284-question bank | **26** |
| declared relations per anchor label, median | **5** |
| … mean / max | 8.9 / 19 |
| gold predicate is declared on its anchor | **78.6%** of legs |

Most labels carry one or two relations. `Mitigation`, `Software`, `View` and
`DataComponent` each declare exactly one — for those there is nothing to select.
`AttackPattern` is the outlier at 19.

### So ask them all

| | Coverage | Cost |
|---|---:|---|
| planner today | 0.4797 | 1 query |
| **exhaustive single-hop union (upper bound)** | **0.7350** | median **2** queries, **0.19 s**; worst 38 queries, 3.6 s |
| authored-plan ceiling | 0.8611 | — |

Querying every relation the anchor declares and unioning the results reaches an
upper bound of **0.7350** — 67% of the distance from today's planner to the
ceiling — and it needs no relation selection at all, no model, and a median of a
fifth of a second. On 190 of 284 questions the gold traversal is included **by
construction**.

### What it cannot reach, and why

The remaining 94 questions are **compressed multi-hop triples**: the authored
leg `Analytic -[HAS_TECHNIQUE]-> Tactic` is really
`Analytic -> DetectionStrategy -> Technique -> Tactic`, so `HAS_TECHNIQUE` is not
declared on `Analytic` at all. Reaching those needs two-hop exhaustive expansion,
which squares the fan-out; `utils/specialists/schema/paths.py` already does the
breadth-first search, so the machinery exists, but the cost and the precision
consequence are unmeasured.

### The precision consequence is the real open question

Every union recorded in this experiment — engines (`A-1`), planners (`A-2`), and
now relations — puts more records in front of a composer that enumerates what it
is handed. `EXP-2026-09-018` records `catalogue_dump` at 0.0915 and
`wrong_entity` at 0.0950 on the shipped tree. **No merged configuration has been
through that instrument.** Coverage is a recall measure and cannot fall when
evidence is added, so every figure in this amendment is guaranteed to look good
by construction. T6 is the check that says whether the answers are still about
what was asked, and it must run before any of this ships.
