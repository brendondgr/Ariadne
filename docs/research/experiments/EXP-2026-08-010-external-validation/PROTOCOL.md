# EXP-2026-08-010 — External validation

**Written 2026-08-21, before any number in this experiment existed.**
Hypotheses in §4 are pre-registered. They are not edited after the run; a
correction, if one is needed, is appended as a dated amendment.

## 1. Why

Every correctness figure this project has published comes from a question bank
Ariadne co-authored. Template banks carry a measured co-authorship bias of
**0.147**. The LLM-generated banks control for that but are still schema-aware,
and the record flags the gap in four places: Q1, Q16, `bank-2026-08-19/CARD.md`,
and the external audit's "Moderate" resource-novelty rating.

A web search on 2026-08-21 for human-authored ATT&CK or CAPEC question sets
returned none. That search conflated two distinct needs:

- **Q16** wants human *phrasing*. Nothing available supplies it. Still open.
- **Q1** wants questions written by someone who did not write the answering
  code. Two published benchmarks supply exactly that.

This experiment answers Q1.

## 2. Data

### X1 — CTIBench `cti-ate` (CC-BY-NC-SA-4.0)

60 rows, each an ATT&CK software page plus the techniques ATT&CK records that
software as using. Gold is MITRE's own mapping rolled to parent techniques.

Coverage against the loaded ATT&CK 19.0, measured before the run:

| | |
|---|---|
| rows | 60 |
| software present in ATT&CK 19.0 | 46 |
| absent | 14 (13 Mobile, 1 Enterprise: S0440) |
| gold ids recoverable from the graph | 291 / 292 = 0.997 |

### X2 — AttackQA, enumerative subset (Apache-2.0)

25,335 rows; roughly 3,200 in families whose answers enumerate ATT&CK
identifiers. Questions are used **verbatim**.

The dataset's `human_question` flag means *a human wrote the generator script*,
not *a human wrote the question*. It is used for nothing here. Recorded so it is
never later mistaken for human authorship.

## 3. Conditions and arms

Every published Ariadne arm replays a **pre-authored plan** carried in the bank
entry (`PLANNER_LLM_ENABLED=false`; "gold plan is replayed; planner never runs").
The bank supplies source, entity types and seed ids. Only `run_llm` reads the
raw question and plans it itself. Co-authorship is therefore structural, not only
phrasing, and the plan is a condition rather than a constant.

| arm | plan | composer | role |
|---|---|---|---|
| `oracle` | — | direct graph lookup | ceiling; isolates benchmark staleness |
| `deterministic` | given | templates | the arm the paper leads with |
| `generic` | given | LLM narrator, no templates | the strongest arm |
| `llm` | **from question text** | LLM | plan-free; what a user experiences |

**Plan-given** entries derive their plan from the external item by one rule,
declared here and applied without per-item judgement: the anchor is the
identifier the external row names, `source` is `attack`, and the entity types are
the two endpoint labels of the family's relation.

## 4. Pre-registered hypotheses

**H1 — retrieval holds.** Plan-given Ariadne recall lands within **0.05** of the
oracle's recall. Refuted if the gap exceeds 0.05.

**H2 — external scores fall below internal ones.** The internal banks produce
0.92–1.00. Co-authorship bias of 0.147 predicts a drop. Refuted if external
matches internal.

**H3 — precision is low for everyone, the oracle included.** ATT&CK 19.0 records
more uses than either benchmark's snapshot; reconnaissance shows the graph
returning 31 techniques where gold has 8. If the oracle's precision is as low as
Ariadne's, the shortfall is staleness rather than error.

**H4 — plan-free scores below plan-given.** The gap is the size of the structural
co-authorship advantage.

## 5. Metrics

Set comparison over extracted ATT&CK identifiers. **No language model
participates in the metric.** Per item and pooled: precision, recall, F1, exact
set match. The primary figure is `ariadne_minus_oracle_recall`.

Identifiers are extracted from an answer by one regex, applied identically to
oracle and Ariadne output, so no arm is advantaged by formatting.

## 6. Decisions

- **D-018** Oracle baseline: staleness and system error are otherwise indistinguishable.
- **D-019** No language model in the primary metric.
- **D-020** CC-BY-NC-SA-4.0 data is fetched at run time, never committed. Scores are ours.
- **D-021** Items whose gold is absent from ATT&CK 19.0 are excluded and counted, never silently dropped.
- **D-022** Gold granularity per source: cti-ate rolls to parent techniques; AttackQA keeps sub-techniques.

## 7. Threats to validity, stated in advance

- **Extraction over-credits.** An identifier mentioned in passing counts as
  asserted, which inflates recall. Exact-set match is reported alongside as the
  unforgiving counterpart, and the oracle is scored by the same extractor.
- **Version skew** is the reason the oracle exists. It is measured, not assumed.
- **Enterprise only.** Mobile and ICS are out of scope; CAPEC is untouched by
  both benchmarks.
- **Enumerative questions only.** Nothing here speaks to open-ended asks (Q4).
- **Machine-generated phrasing.** Q16 is not addressed and must not be reported
  as addressed.
