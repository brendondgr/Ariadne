# PROTOCOL — EXP-2026-07-011 Portability audit

> **Back-filled 2026-08-06.** This is an **audit**, not a measured run. It is
> recorded as an experiment so that the portability claim carries a traceable ID
> like every other claim, not because anything was executed.

## Question

If the grant hosts hand over a real non-MITRE dataset, what transfers and what
has to be re-authored — and can the re-authoring cost be counted rather than
estimated?

## Hypothesis

exploratory — no prior hypothesis.

## Setup

A static read of the source tree as it stood on 2026-07-26, classifying each
layer as schema-agnostic, source-card-driven, or MITRE-specific. Template counts
are derived by AST parse rather than by reading prose:
`docs/plans/robustness/_overnight/derive_templates.py` extracts every
`QueryDraft(template="...")` literal, the method emitting it, the call graph
from the public entry points, and every `expected_template` value in the
question banks.

## Data

The repository itself. 25 distinct query template identifiers across two
builders.

## Metrics

Counts, not scores. There is **no primary metric** — nothing here was measured
against gold, and assigning one would misrepresent an audit as an experiment.

| Count | What it is |
|---|---|
| `distinct_query_templates` | Distinct template identifiers across both builders. |
| `templates_exercised_by_the_bank` | How many the 120-question catalogue actually reaches. |
| `mitre_specific_templates` | How many would need re-authoring for a new schema. |

## Baselines

None applicable.

## Procedure

```bash
uv run python docs/plans/robustness/_overnight/derive_templates.py
```

Then a manual layer-by-layer read of `utils/orchestration/`,
`utils/specialists/`, `utils/synthesis/`, and `utils/evaluation/`.

## What would falsify this

Finding MITRE-specific logic in a layer classified as fully portable — for
instance a hardcoded ATT&CK id in the orchestration graph or the synthesis
verifier.
