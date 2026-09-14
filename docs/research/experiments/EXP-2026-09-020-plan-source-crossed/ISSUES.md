# Issues — EXP-2026-09-020

## I-1 — the metric is retrieval, and the decision it informs is about answers

**What it is.** Every figure here is deterministic gold coverage. That is what
makes a four-cell, 284-question comparison affordable and immune to grading
noise, and it is not the judged correctness scale on which `EXP-2026-09-018`
reports 0.9005.

**Why it is recorded rather than resolved.** The engine difference at the real
planner is +0.0261, which clears the 0.02 threshold `EXP-2026-09-019` set for
warranting a judged pass — but barely, and not separably. A judged pass on the
two planner cells would say whether +0.0261 of retrieval is worth anything to an
analyst. It has not been run.

**What it does not threaten.** The *contrast* between the two plan sources is
measured on one metric throughout, so the interaction of −0.1923 and the sign
flip by tier do not depend on the metric choice.

## I-2 — the tier labels are the bank's, not a difficulty measurement

The sign flip is reported over `easy` / `medium` / `hard` / `adversarial`, which
are authored labels carried by `bank-dev.json`. They were not validated against
any independent difficulty estimate here. The flip is large (−0.1586 against
+0.1127) and monotone in the labels, so it is reported; a routing rule built on
it should be validated on a held-out set before it ships.

## I-3 — `Q58`'s bounds confound is cancelled for the engine effect and not for the plan effect

`generic_planned` inherits the planner's own per-plan limits
(`max_result_rows: 1000`, `max_traversal_depth: 3`) where the gold-replay path
inherits lifted bounds, which is why `Q58` is open against the plan-effect
column. Both cells of the engine comparison at the real planner take the same
bounds from the same planner, so the term cancels there. Stated because the
opposite assumption — that a known confound taints every number in a table —
would be the easy and wrong reading.

## I-4 — `deterministic` here is 0.6428, and the 2026-09-11 reference capture was 0.5048

Not a discrepancy. The reference in `EXP-2026-09-018` Step 0 was taken at
`cbb48502`, before the repair; this ran on the shipped tree after it. The
direction and rough size match the repair's judged paired gain for the same arm
(0.5011 → 0.6098), which is the cross-check that makes the two readings
consistent rather than contradictory.

## I-5 — `dirty: true`, and exactly what was uncommitted

The arm under test was committed at `2001d2a0` before the run, and no code file
was modified afterwards. But the working tree was not clean: a **concurrent
session** held modified files under `EXP-2026-09-019` (its `RESULTS.md`,
`ISSUES.md` and `data/POINTERS.md`) and untracked judgment sidecars under
`docs/evaluation/experiments/small-model-generic-2026-09-13/twobytwo/`, and this
session held uncommitted edits under `EXP-2026-09-012`.

**None of it can reach this run.** All of it is documentation and grading output
for other experiments; nothing under `utils/`, `scripts/` or `api/` was modified
between the commit and the four runs. The four cells were written back to back
from one tree, which is the property the comparison actually depends on.

Recorded rather than asserting a clean tree, because `dirty: false` would have
been false.
