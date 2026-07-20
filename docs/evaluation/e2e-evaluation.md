# End-to-End Evaluation

ATT&CK 19.0 · CAPEC 3.9 · full report (live), judge=llm

The assembled pipeline (probe → plan → specialists → synthesis) scored against snapshot-derived gold. The four end-to-end metrics and the unsupported-claim rate are deterministic and reproducible; the LLM judge's qualitative scores are opt-in and labeled where they contribute.

**Metric definitions**

- *cross_source_answer_accuracy*: Live cross-source join values vs the snapshot-derived must_correlate set (exact-set-match + precision/recall/F1); negatives must surface none.
- *capec_attack_mapping_recall*: Of the resolvable ATT&CK technique ids a CAPEC pattern maps to, the fraction the pipeline surfaced on the CAPEC side (micro-averaged).
- *provenance_correctness*: Fraction of rendered-claim citations resolving to a retrieved record whose provenance is complete and whose recorded query was executed; abstentions must carry a truthful proof.
- *analyst_inspectability*: Mean of citation coverage, claim->record->query traceability, and abstention-proof completeness across every answer.

## End-to-End Metrics

**Cross-source answer accuracy** — live join values vs snapshot `must_correlate`:

- exact-set-match (positives): 1.000 [0.89–1.00] (k=30/30)
- precision / recall / F1: 1.0 / 1.0 / 1.0
- no-fabrication (negatives): 1.000 [0.72–1.00] (k=10/10)

**CAPEC→ATT&CK mapping recall** — gold technique mappings surfaced:

- micro-recall: 1.0 (113/113 mappings, 30 entries)
- mean per-entry recall: 1.0

**Provenance correctness** — citations trace to complete, executed-query records:

- mean citation-provenance rate: 1.0
- fully-provenanced answers: 1.000 [0.97–1.00] (k=120/120)

**Analyst inspectability** — claim→record→query chains + abstention proofs:

- mean inspectability: 1.0
- citation coverage / traceability / abstention proofs: 1.0 / 1.0 / 1.0

## LLM Evaluator (judge)

Source: **llm** (120 LLM verdicts — NON-reproducible)

- mean faithfulness: 0.9733
- mean groundedness: 0.9342
- mean evidence sufficiency: 0.95
- mean unsupported-claim rate: 0.0 (deterministic)
- cross-source conflicts: 0 across 0 answer(s) (deterministic)

## By tier

| Tier | X-source exact | Mapping recall | Provenance | Inspectability |
|---|---|---|---|---|
| adversarial | 0.0 | 1.0 | 1.0 | 1.0 |
| easy | 0.0 | 1.0 | 1.0 | 1.0 |
| hard | 1.0 | 1.0 | 1.0 | 1.0 |
| medium | 1.0 | 1.0 | 1.0 | 1.0 |

## What this diagnoses

- LLM judge contributed 120 verdict(s) (source=llm); those qualitative scores are NON-reproducible — the deterministic proxy covers the rest.
