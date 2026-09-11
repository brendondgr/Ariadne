# Correctness improvement diagnostic

## Question
Where should the next improvement experiment focus, given the existing development-set judge scores?

## Hypothesis
Exploratory — no prior hypothesis. Retrospective descriptive analysis, not an intervention or a new pipeline evaluation.

## Setup
Reuse EXP-2026-09-005 answers and only its original qwen judgment files (`.judgment.json`, `.judgment.pass2.json`). Exclude all later gemma sidecars. Average the two positions per case, then average cases. Pair arms by identifier. Preserve the published judge and gold; do not rescore.

## Data
Development rows in `docs/evaluation/composition/bank/post-repair-generic.json`, paired with `docs/evaluation/experiments/post-repair-2026-09-03/{generic,deterministic}/answers/`. Copy selected scores and category metadata into a committed CSV, with source hashes. No holdout case-level inspection. Published holdout aggregates may be quoted from EXP-2026-09-007 for context.

## Metrics
Mean judged correctness is a fractional rubric score, not the proportion of fully correct answers. Category headroom is `sum(1 - per_case_score) / total_cases`; it decomposes the overall distance from perfect, not causal failure attribution. Identify the CAPEC missing-pattern slice by the five relationships named in Q45 before inspecting its judged scores. A scenario replacing that slice's mean assumes all other cases unchanged: arithmetic, not a forecast. Never substitute retrieval recall for judged correctness.

## Baselines
Schema-derived (`generic`) and hand-written templates (`deterministic`) from the same historical run and judge protocol. No new candidate arm.

## Procedure
1. Extract paired scores into `data/cases.csv`, assert completeness and reproduction of original published aggregates, record source hashes.
2. Run the experiment's `figures/make_figures.py` to aggregate CSV into `data/metrics.json`, then generate tables, SVG/PDF figures and an HTML scenario explorer from those metrics.
3. Write interpretation and prioritized hypotheses in RESULTS.md. Run `make index`, `make validate-research` and `make check-docs`.

## What would falsify this
Failure to reproduce source means invalidates extraction. A large deficit identifies opportunity for diagnosis, not proof that a proposed fix will recover it. Subsequent interventions need a concurrent paired control, with correctness, groundedness, wrong-entity rate, abstention quality and latency measured together. The spent holdout is historical validation, not a fresh test for changes selected here.
