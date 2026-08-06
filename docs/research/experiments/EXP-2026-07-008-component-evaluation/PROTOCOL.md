# PROTOCOL — EXP-2026-07-008 Component-level evaluation

> **Back-filled 2026-08-06.** Reconstructed from the recorded method, not
> pre-registered.

## Question

Do the planner and the two query specialists meet their component-level
contracts — correct source routing, valid and safe queries, and execution
results matching snapshot-derived gold — independently of end-to-end answer
quality?

## Hypothesis

exploratory — no prior hypothesis.

## Setup

The planner is scored with its **deterministic** drafter (reproducible; the LLM
drafter is opt-in and not scored here). Both specialists are exercised against
the live Neo4j and Gremlin fixtures with results compared to gold derived from
the pinned snapshots.

## Data

43 planner cases (7 curated, 36 generated) split dev/holdout, plus 46 ATT&CK and
34 CAPEC specialist cases with snapshot-derived gold result sets. ATT&CK 19.0,
CAPEC 3.9.

## Metrics

| Metric | What it computes |
|---|---|
| Source precision / recall | Whether the plan routes to exactly the sources the question needs. Recall is the primary metric: missing a source is unrecoverable downstream, over-routing only costs time. |
| Sub-question quality | Mean of routing accuracy and dependency accuracy over the corpus. |
| Schema adherence | Whether every emitted plan validates against the plan schema. |
| Honesty | Whether unsupported or partial requests are declared rather than answered. |
| Query validity (VA) | Share of drafted queries clearing the safety gate, first-pass and post-retry. |
| Execution accuracy (EX) | Exact-set-match of the live result set against snapshot gold, plus precision/recall/F1. |
| Safety adherence | Bounded-execution audit over accepted queries, plus adversarial probe block rate. |
| Latency | p50/p95/p99 per stage, warm steady-state, with a cold-start comparison. |

## Baselines

None. These are contract checks against gold, not a comparison against an
alternative implementation.

## Procedure

```bash
uv run main.py --docker start
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run main.py --component-eval
```

## What would falsify this

Any query validity or safety figure below 1.0 would mean the gate leaks. Source
recall below 1.0 would mean the planner drops a source the question needs, which
no downstream stage can recover.
