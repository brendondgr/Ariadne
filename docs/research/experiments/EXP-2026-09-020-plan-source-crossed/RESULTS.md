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
