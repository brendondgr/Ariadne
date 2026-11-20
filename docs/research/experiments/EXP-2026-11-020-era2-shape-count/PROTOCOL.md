# PROTOCOL — EXP-2026-11-020 Era 2 Step 9 Phase A: which retrieval shapes do the questions need?

Written 2026-11-20, before any external question was labelled. The items to label were drawn
(`sample`), and their sizes are below. No label existed when this was written.

## Question

What share of the questions available to this project does each retrieval operator cover,
cumulative in Step 9's operator order? Are Mind the Query's three gaps common enough in retrieval
questions to build?

## What was looked at before writing

- **Ariadne's own banks are structured and template-generated:**
  - **dev 284:** steps 0/1/2 = 35/167/82; 47 equality filters, no other filter op.
  - **gold 120:** 18 templates plus 40 federated cases; one scan of each graph.
  - **Step 6 tuning banks:** one-hop slots, except 13 out-of-coverage questions, which were
    written to be out of coverage (median per group, shortest chain, change over years,
    similarity).
- **AttackQA has 25,335 rows in 25 families.**
  - The relationship families are per-entity templates.
  - The description families (groups, software, techniques, campaigns, tactics) are free-form
    questions about one entity's text.
  - The "How does S use T", "How can M mitigate T" and "How can DC detect T" families
    (`relationships_uses_software`, `_mitigations`, `_detects`) ask about one link between two
    named entities. They are about 52% of rows.
- **CTIBench cti-ate** (60 rows) asks for techniques to be extracted from supplied text.

## Hypotheses (predictions)

- **H1 — own banks:** today's operations cover ≥ 0.98 of Ariadne's own banks (dev, gold with
  variants, Step 6 tuning). Only the 13 out-of-coverage questions need a new operator or fall
  outside.
- **H2 — AttackQA, weighted to its full size:**
  - `O4.verify` (one link between two named entities) is the largest new need, ≥ 0.40;
  - `O2`, `O3`, `O6`, `O7*` and `O8` together cover < 0.02;
  - outside retrieval (`X.textsearch`, `X.knowledge`) is 0.10 to 0.35, from the free-form
    description families.
- **H3 — the gaps:** `G1`, `G2` and `G3` each cover < 2% of the external retrieval questions,
  so none is built (Step 9 plan, Phase A decision rule).
- **H4 — cti-ate:** every row is `X.extract`.

## Setup

- **The rubric** (`docs/evaluation/shape-count-2026-11/RUBRIC.md`) defines the codes and how
  coverage is computed. A question is covered after operator k when every code it needs is a
  today code or an operator up to k.
- **Ariadne's banks are labelled by code** (rubric, last section), from their structured specs.
- **External and out-of-coverage questions are labelled by two labellers:**
  - **Labeller A:** Opus 5.5 at medium effort, as Claude Code subagents in batches. It labels
    every item.
  - **Labeller B:** Sonnet 5.5 at medium effort. It labels a fixed-seed 20% (135 items), blind
    to A.
  - Both get the rubric and the question text only; no family name, no other labeller's output.
- **Disagreements on the coverage stage** are settled by the experimenter, reading the question
  against the rubric. Each one is listed in `adjudicated.jsonl` with a reason.

## Data

**`scripts/count_question_shapes.py sample`, seed 20261120.** It draws 673 items:
- 600 AttackQA rows, stratified by family in proportion to size, at least 5 per family;
- all 60 CTIBench cti-ate rows;
- the 13 slotless questions of the Step 6 tuning banks.

The draw is byte-reproducible (md5 a85839ad… twice).

**What is committed and what is not:**
- Committed: row ids, families and labels.
- Not committed: external text. D-020 holds, and CTIBench is CC-BY-NC-SA.

**Sealed banks:**
- Not read: the held-out card banks, `bank-holdout.json`, the fresh set, and the held-out variants.
- The script opens only an allowlist and refuses sealed names. A unit test spies on file opens.

## Metrics

- **Stage share and cumulative coverage,** per source:
  - dev, gold, variants, step6, attackqa, cti-ate;
  - AttackQA weighted by `family size / sample size`;
  - "external retrieval": external items not labelled outside.
- **Code share:** the share of questions needing each code. Multi-code questions count once per
  code.
- **Agreement on the 135:**
  - Cohen's κ on the coverage stage;
  - exact stage agreement;
  - exact code-set agreement.

## Checks (Step 9 plan, Phase A)

| Check | Bar | On fail |
|---|---|---|
| Every item has a label set from the rubric's codes | 100% | fix and re-label the missing |
| κ on the stage | ≥ 0.80 | revise the rubric once and re-label both; if still below, report and stop for the operator's decision |
| `count` re-run | byte-identical outputs | fix nondeterminism |
| Sealed banks opened | 0 | stop and record |

## Decision rule (agreed 2026-11-20)

- A gap (`G1`, `G2` or `G3`) is built only if it covers ≥ 2% of the retrieval questions of any
  external source.
- Operators 1–8 are built regardless. The count orders the work and weights Phase G's probe set.

## Baselines

None. This is a census, not a comparison.

## Procedure

```bash
uv run --with pyarrow python scripts/count_question_shapes.py sample
# labeller A: every item of .cache/shape-count/items.jsonl → docs/evaluation/shape-count-2026-11/labels-a.jsonl
# labeller B: .cache/shape-count/items-second.jsonl         → docs/evaluation/shape-count-2026-11/labels-b.jsonl
# disagreements on the stage → adjudicated.jsonl
uv run python scripts/count_question_shapes.py count
```

## What would falsify this

- **H1 falls** if more than 2% of Ariadne's own questions need a new operator. That would mean the
  banks are less template-bound than they look.
- **H2 falls** if aggregates, ranks, grouping, time or paths reach 2% of AttackQA weighted.
- **H3 falls** if any gap reaches 2% of external retrieval questions. That gap is then built.
- **If κ stays below 0.80,** the rubric does not separate the shapes, and the counts are not
  reported as measured.
