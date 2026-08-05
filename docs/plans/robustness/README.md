# Robustness — parallel work plans

Four self-contained briefs, split so that separate agents can run them
concurrently without touching each other's files. Each one is written to be
handed to an agent with **no prior conversation context**: it states its own
scope, its prohibitions, its verification criteria and its deliverables.

They exist because the parent plan
(`docs/plans/branch-a-publication-readiness-plan.md`) mixes work with very
different safety profiles. Some of it is mechanical and checkable against files.
Some of it silently invalidates an experiment if done carelessly. Some of it
fabricates citations if done unattended. Those should not be in one document,
and they should not be given to one agent.

| # | Plan | Runs when | Touches | Safe unattended |
|---|---|---|---|---|
| 01 | [Overnight-safe work](01-overnight-safe-work.md) | Tonight | `docs/`, `.env.example`, git tags, docstrings | **Yes**, within its prohibitions |
| 02 | [Holdout question generation](02-holdout-question-generation.md) | After 01 completes | New files only, under a detached checkout | **Only with the write-lock in §3** |
| 03 | [Deferred work](03-deferred-work.md) | Reference document | Nothing | N/A — it is a register, not a task list |
| 04 | [Related-work research program](04-related-work-research-program.md) | Now, in parallel | A **separate repository** | Partly — acquisition yes, claims no |

## Ordering and independence

**01 must finish before 02 starts.** Plan 01 creates the `freeze/holdout-v1`
tag, and Plan 02 runs against that tag. Running them concurrently produces a
holdout measured against a moving target, which is worse than no holdout.

**04 is fully independent of 01–03** and touches a different repository
entirely. Start it now. It is the long pole for the Positioning axis (currently
0/4) and it does not depend on any experimental result.

**03 touches nothing.** It is the register of what is deliberately not being
done yet and why, so that a later agent — or a later you — does not pick up a
deferred item without understanding what it was waiting on.

## The one rule shared by all four

Every number, citation and claim written by any of these plans must be
**traceable to a file or a retrieved document**. Not to memory, not to the
parent plan, not to a previous agent's summary. Where something cannot be
verified, it gets recorded as unverified rather than smoothed over. The project
is at 1.875/4 partly because the documentation drifted from the code; these
plans are the correction, and they fail if they reintroduce the same problem in
new files.
