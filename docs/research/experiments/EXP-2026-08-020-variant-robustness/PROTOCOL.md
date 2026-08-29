# PROTOCOL — EXP-2026-08-020 Variant robustness of card-grounded routing

## Question

The deterministic router matches a question's words against the node labels and
relationship types each source's schema card declares, case-folded and exact,
with a trailing `s` as its entire morphology. **How much of its measured
correctness survives ordinary paraphrase, and where exactly does it break?**

The answer could come out either way. The router reads real schema vocabulary
and the golden questions were written by people holding that vocabulary, so it
is possible the vocabulary is natural enough that paraphrase costs little. It is
also possible that every golden number is a property of how the questions were
worded.

## Hypothesis

**H1.** Record identity falls monotonically across tiers T1→T5, and the drop is
not uniform: T1–T2 (identifier retained, wording changed) lose less than T3–T5
(identifier removed), because the identifier alone is enough to reach the anchor
even when no schema word matches.

**H2.** The dominant failure at T4–T5 is **not** abstention but **silent
downgrade** — the question falls through to the generic `describe` primitive,
which returns the right anchor with the wrong information and passes every
internal check. Measured as: `wrong_entity` plus non-abstaining partial recall
exceeding the abstention rate.

**H3 (negative control).** T6 questions, about entities that do not exist,
return nothing. Any T6 that returns records is a fabrication the verifier cannot
catch, because each record is genuinely retrieved.

## Setup

The shipped deterministic pipeline, every LLM seam off
(`PLANNER_LLM_ENABLED`, `SPECIALIST_LLM_ENABLED`, `SYNTHESIS_LLM_ENABLED`,
`CONVERSATION_LLM_ENABLED` all false), `ORCH_MAX_HOPS=5`. Three live sources:
ATT&CK in Neo4j, CAPEC in Gremlin, both reloaded and `--graph verify`-passing on
2026-08-29 after the Gremlin store was found holding 0 nodes.

Held constant across every arm: the questions, the graphs, the gold reference.
Only the router changes.

## Data

**Reference:** the 120-question golden catalogue
(`utils/specialists/tests/golden/{attack,capec,federated}_questions.json`), 46 /
34 / 40. Card: `../../datasets/cards/golden-catalogue-120.md`.

**Variants:** authored by **Claude Sonnet** subagents, 12 batches of 10, one
agent per batch, from the contract in
`utils/specialists/tests/fixtures/variant_prompt.md`. Six tiers:

| tier | keeps | removes |
|---|---|---|
| T1 | identifier | the schema's word |
| T2 | identifier | the sentence shape |
| T3 | the entity's exact name | identifier |
| T4 | the idea of the name | identifier, exact name, all schema words |
| T5 | only the description | identifier, name, all schema words |
| T6 | nothing — negative control | — |

**Selection bias, stated.** The variants derive from the golden catalogue, which
is itself co-authored with the templates (C-021, bias measured at 0.0483). So
this experiment measures robustness *relative to that catalogue*, not absolute
robustness. It cannot be a substitute for a question set drawn independently,
and the T5 tier is the closest the project has come to one.

**Anti-circularity.** The variant author (Sonnet) is a different model family
from any interpreter later built on the local model (Ornith-1.5-35B). Had the
same family done both, this would measure self-consistency — the failure mode
C-021 exists to name.

## Metrics

Every metric is computed by comparing a variant's run against **its own gold
question's captured run**, never against a hand-written expectation.

- **`records_exact` (PRIMARY)** — the set of entity identifiers surfaced by the
  variant equals the set surfaced by the gold question. Identifiers include both
  record anchors and their `related` items, because a question about T1176's
  mitigations returns *one* record whose five mitigations live in `related`;
  scoring anchors alone would call that identical to a bare describe.
- **`records_recall`** — fraction of the gold question's identifiers the variant
  also found. Partial credit, over variants whose gold set is non-empty.
- **`queries_exact`** — the emitted query strings match verbatim. Strictest:
  identical queries mean an identical interpretation. A variant that reaches the
  same records through a *different* query is a success on the primary metric
  and a failure here, and that gap is reported rather than collapsed.
- **`claims_exact`** — the composed claim texts match.
- **`abstained`** — the variant declined, or returned no identifiers. **An
  outcome, not a failure.** Never pooled with a wrong answer.
- **`wrong_entity`** — the variant returned identifiers and **none** of them is
  one the gold question found. The failure mode nothing downstream catches,
  because every claim is genuinely grounded in a genuinely retrieved record.

Reported **per tier**. A pooled figure would average vocabulary matching and
entity resolution — two different problems with two different fixes — into one
uninterpretable number.

## Baselines

**Arm 0 (baseline)** is the shipped router, measured before any change. Every
later arm is compared against it on the same variants.

The **T0 control** is the gold questions themselves re-run through the harness:
it must score exactly 1.0000 `records_exact` against the reference. Anything
else means the harness is broken, not the system, and no other number may be
read until it does.

## Procedure

1. Capture the gold reference; run it twice and require byte-identity.
2. Author variants; gate them mechanically for tier honesty (a T3+ carrying an
   identifier, or a T4/T5 carrying a schema word, is rejected and recorded).
3. **Arm 0** — score all variants against the reference. This is the baseline.
4. **Arm 1** — deterministic lexicon (stemming, bounded edit distance, gloss
   promotion) wired into the router behind a flag. Re-score.
5. **Arm 2** — name-bearing question routing. Re-score.
6. **Arm 3** — candidate retrieval over canonical names and descriptions.
   Re-score.
7. **Arm 4 (conditional)** — gated interpreter, only if a measured gap survives
   Arms 1–3, run three times for spread.

Between every arm: the **recorded-answer regression** over both catalogue banks,
diffed with clock keys excluded. A routing change that moves a catalogue answer
is a regression until proven otherwise.

## Threats to validity

- **The variants are model-authored.** A sample must be human-read; an external
  benchmark's own audit put generated items at 65% correct. Unaudited generated
  gold is not gold.
- **The catalogue is co-authored with the templates**, so the reference itself
  sits at the favourable end of C-021's measured bias.
- **`records_exact` is strict.** A variant that finds a superset — the right
  answer plus extra neighbours — scores 0 on the primary metric while a reader
  might call it correct. `records_recall` is reported alongside for exactly this
  reason, and neither is quoted without the other.
- **Tier honesty is enforced lexically, not semantically.** A T5 that avoids
  every schema word but is still trivially recognisable is not caught by the
  gate; only the human sample catches that.
