# PROTOCOL — EXP-2026-07-009 End-to-end evaluation

> **Back-filled 2026-08-06.** Reconstructed from the recorded method, not
> pre-registered.

## Question

Does the assembled pipeline satisfy the four end-to-end metrics named in
`docs/goals.md` — cross-source answer accuracy, CAPEC to ATT&CK mapping recall,
provenance correctness, and analyst inspectability?

## Hypothesis

exploratory — no prior hypothesis.

## Setup

The full pipeline (probe, plan, specialists, synthesis) against the live Neo4j
and Gremlin fixtures, scored against snapshot-derived gold. The LLM judge is
opt-in via `--judge` and its output is segregated from the deterministic metrics.

## Data

The 120-question golden catalogue. Cross-source accuracy is scored over the 30
entries carrying a `must_correlate` set, plus 10 negatives that must surface
nothing. ATT&CK 19.0, CAPEC 3.9.

## Metrics

Definitions, taken verbatim in substance from the report:

| Metric | Definition |
|---|---|
| `cross_source_answer_accuracy` | Live cross-source join values against the snapshot-derived `must_correlate` set (exact-set-match plus precision/recall/F1). Negatives must surface none. |
| `capec_attack_mapping_recall` | Of the resolvable ATT&CK technique ids a CAPEC pattern maps to, the fraction the pipeline surfaced on the CAPEC side, micro-averaged. |
| `provenance_correctness` | Fraction of rendered-claim citations resolving to a retrieved record whose provenance is complete and whose recorded query was executed. Abstentions must carry a truthful proof. |
| `analyst_inspectability` | Mean of citation coverage, claim to record to query traceability, and abstention-proof completeness across every answer. |

The judge's faithfulness, groundedness, and evidence-sufficiency scores are
recorded under a `judge_` prefix and are **not** reproducible.

## Baselines

None.

## Procedure

```bash
uv run main.py --docker start
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run main.py --e2e-generate     # writes docs/evaluation/answers/
uv run main.py --e2e-eval --judge
```

## What would falsify this

A negative surfacing a join value would falsify the no-fabrication claim
outright. Provenance correctness below 1.0 would mean a rendered claim cites a
record that was never retrieved, which is the one failure this system is
designed to make impossible.
