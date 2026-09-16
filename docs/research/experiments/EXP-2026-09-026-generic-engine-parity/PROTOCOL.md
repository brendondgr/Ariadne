# PROTOCOL — EXP-2026-09-026 Generic-engine parity on the named defects

> Written 2026-09-15, before any run of this experiment. Plan:
> [`docs/plans/2026-09-15-open-question-correctness.md`](../../../plans/2026-09-15-open-question-correctness.md),
> Step 7. Control is the template cascade under the `anchor_first`
> configuration (EXP-2026-09-023); treatment is the same configuration with
> `SPECIALIST_GENERIC_ONLY=true` (the schema-derived primitives, no
> hand-written question shapes).

## Question

`EXP-2026-09-021` Step 3 measured the schema-derived engine losing to the
template cascade by 0.175 at T1 and 0.117 at T2, and the paired diff named the
categories: reverse-direction bridge questions (REV, PART), cross-source
mapping questions whose consumer got no seeds (MAP, NEG, CTT), and the CWE
chain. Tracing three of them through the generic path on 2026-09-15 found one
dispatch defect behind most of it: **the generic Gremlin path chooses the
cross-source bridge only when the sub-question's entities carry mapping
vocabulary**. An ATT&CK-shaped seed in a CAPEC sub-question ("which CAPEC
items line up with T1040") is bound as a CAPEC id and rejected by the
validator; "correspond to CAPEC-555" takes the native describe/hierarchy walk
and the ATT&CK consumer is skipped for want of seeds. Does fixing the
dispatch bring the generic engine to parity on those categories?

## Hypothesis

**H1.** With the dispatch rule "a joined, seeded sub-question takes the
bridge when its seeds belong to no label of this source (a reverse mapping),
when it names mapping vocabulary, or when it names no native relation at
all", the generic engine on the exposed bank is **within − 0.02 of the
template cascade** on T1, T2 and T3 `records_exact`, with no category where
templates win by more than two paired cases, and `wrong_entity` /
`catalogue_dump` not above the cascade's. Sealed bank: within − 0.02 at T3.

**Not predicted to close here:** the CWE chain (5 exposed cases), where the
CAPEC sub-question names a native relation *and* must project the join key
for its consumer; the generic bridge already walks the Weakness → pattern →
mapping path, but nothing in the dispatch knows the sub-question has a
consumer. Recorded if it remains.

## Setup

One tree. Arms `anchor_first` (templates; already measured) and `generic`
(same flags + `SPECIALIST_GENERIC_ONLY=true`), 32 workers, 600 s budgets.

## Data

Exposed bank (579), sealed bank (160).

## Metrics

As `EXP-2026-09-023`; paired per variant by category (the case id's middle
token). **Primary:** T1 `records_exact` gap, generic − templates, exposed.

## Procedure

```bash
T="--llm-timeout-s 600 --pipeline-timeout-s 600 --workers 32 --reference reference.json"
uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-holdout-2026-09 --rewrite generic $T --name scored_generic.json
uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-2026-09-15 --rewrite generic $T --name scored_generic.json
uv run python docs/research/experiments/EXP-2026-09-026-generic-engine-parity/data/report.py
```

## What would falsify this

- A T1/T2/T3 gap below − 0.02, or any category where templates win by more
  than two cases — then the named defects are not the whole gap and the
  templates are not retired; the surviving categories are listed.
- `wrong_entity` or `catalogue_dump` above the cascade's on any tier.
