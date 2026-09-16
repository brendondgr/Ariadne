# PROTOCOL — EXP-2026-09-027 A relation lexicon generated from the card's own glosses, offline

> Written 2026-09-15, before any run of this experiment. Plan:
> [`docs/plans/2026-09-15-open-question-correctness.md`](../../../plans/2026-09-15-open-question-correctness.md),
> Step 8. Control is `EXP-2026-09-025`'s `form_execute` arm on both banks.

## Question

The router matches a question's words against the labels and relationship
types a card declares and the one gloss sentence per relationship. 54 of the
exposed bank's 172 T1/T2 misses bind the right anchor and no relation because
the analyst's verb ("defend against", "stop", "rely on", "spot") is not in
the card. Does a lexicon of such words — generated **once, offline** per
declared relationship from nothing but the card's gloss and endpoints, filtered
against every routing token, committed and reviewable, and read at query time
by the same deterministic gloss index — bind those relations without a model
call per question, and without over-matching?

## Hypothesis

**H1.** With `ARIADNE_RELATION_PARAPHRASES=1` on top of `form_execute`, on the
exposed bank: the T1/T2 questions whose form binds no relation fall from 54 to
**≤ 20**; T1/T2 `records_exact` rise by **≥ 0.05** each (the deterministic rung
now binds the relation and the model is never asked); `wrong_entity` and
`catalogue_dump` unchanged on every tier; T6 unchanged. Sealed bank: T3 not
below control − 0.02, no tier's dump or wrong-entity rate up.

**Over-matching control.** A paraphrase word is dropped at generation time if
it is a label or relationship token of *any* card, so it can bind a relation
but never route a question to a source; and if the model offered it for two
relationships of the same card. The residual over-matching risk is a
paraphrase binding the wrong relation on a question that names none —
measured by `wrong_entity`, `catalogue_dump` and the paired broken count.

## Setup

`scripts/generate_relation_lexicon.py --dataset attack --dataset capec`: one
local-model call per declared relationship (30 calls), temperature 0, prompt
version `relation-lexicon-v1`; output committed under
`entity_descriptions.relationship_paraphrases` in the overlay and the card,
with the dropped words and reasons beside it. Then the harness arm
`paraphrases` = `form_execute` + `ARIADNE_RELATION_PARAPHRASES=1`, 32 workers,
600 s budgets, both banks.

## Data

Exposed bank (579), sealed bank (160). The generated lexicon is an artifact of
this experiment and is hash-pinned.

## Metrics

As `EXP-2026-09-023`; plus the count of T1/T2 rows whose rewrite trace binds no
relation. **Primary:** T1 `records_exact`, exposed, `paraphrases` arm.

## Procedure

```bash
uv run python scripts/generate_relation_lexicon.py --dataset attack --dataset capec
T="--llm-timeout-s 600 --pipeline-timeout-s 600 --workers 32 --reference reference.json"
uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-holdout-2026-09 --rewrite paraphrases $T --name scored_paraphrases.json
uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-2026-09-15 --rewrite paraphrases $T --name scored_paraphrases.json
uv run python docs/research/experiments/EXP-2026-09-027-relation-lexicon-from-glosses/data/report.py
```

## What would falsify this

- T1/T2 `records_exact` not up by 0.05, or `wrong_entity` / `catalogue_dump`
  up on any tier — the lexicon over-matches or binds the wrong relation; it is
  then narrowed to exact gloss forms only (i.e. not shipped).
- The generated words needing hand-editing to pass: the lexicon is then not
  "generated from the card" and the claim is withdrawn.
