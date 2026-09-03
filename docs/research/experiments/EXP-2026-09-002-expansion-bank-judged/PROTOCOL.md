# PROTOCOL — EXP-2026-09-002 The expansion bank, judged

> **Recorded after the run, from a plan written before it.** The run executed
> [`docs/plans/2026-09-02-overnight-expansion-run.md`](../../../plans/2026-09-02-overnight-expansion-run.md),
> committed at `46a051d` on 2026-09-01T23:47 — **26 hours before the run started**
> and before any arm had answered a question. This file restates that plan; it
> does not invent one. The experiment folder was created on 2026-09-03 because
> the plan named the ID (`EXP-2026-09-002`) and nobody created the folder, not
> because the protocol is reconstructed. See ISSUES.md I-6.

## Question

On a question bank that reaches **every** shape the pinned sources support —
34 edge types rather than the 12 the committed banks reach — does the
hand-written template cascade still hold its own against a path that assembles
queries from the schema at run time?

This has an answer that could come out either way, and the two outcomes mean
different things:

- **Level, or templates ahead.** The catalogue's 0.0000 gap (EXP-2026-08-015)
  generalises. C-023's "the precision advantage is conditional on the schema the
  templates were written for" stands as written, and the condition is *schema*.
- **Generic ahead.** The 0.0000 was a property of the *question set*, not of the
  schema. The condition on C-023 is not schema but **vocabulary** — templates
  hold only inside the shapes they were authored for, on any schema including
  their own. That is a materially stronger and more general claim.

Secondary questions, all pre-registered in the plan:

1. **Direction.** EXP-2026-09-001 A-4 (same shape, both ends) and A-5
   (aggregate over all forward vs all reverse questions) disagree in sign.
   A-5's comparison is confounded — forward and reverse questions are about
   *different* edges. Resolve with a paired contrast.
2. **The property-read anomaly.** A-5 found D1 (read one property) scoring
   *below* both single-hop tiers, which the difficulty ordering does not
   predict. Classify the failures by cause, without a model.
3. **Abstention at scale.** Previously tested on 4 questions. The bank carries 61.

## Hypothesis

Stated in the plan, §"Direction contrast" and §"What the night is for":

> Templates and the schema-derived generic path were expected to remain **close**
> on ATT&CK/CAPEC, as they are on the catalogue, because this is the schema the
> templates were written for. The coverage cost of templates was expected to
> appear only off-schema.

On direction: no prior — the plan's stated purpose was to settle a contradiction,
not to confirm a direction.

## Setup

Three arms over the **same 284 dev questions**, same stores, same composer, same
grader, same night. The only variable is how the query is produced:

| Arm | How the query is produced | Model in the loop? |
|---|---|---|
| `deterministic` | The template cascade — fixed parameterised queries picked by rules | No |
| `generic` | Assembled at run time from the source cards' own schema | No |
| `llm_query` | A model is shown the schema, resolved seeds, gate constraints and a repair loop, and writes the Cypher/Gremlin itself | Yes |

Held constant: both live stores (Neo4j + Gremlin Server, fixture QA passed at
preflight), the safety gate, the evidence normalizer, the deterministic composer,
and the grader. The `deterministic` and `generic` arms carry **no model at all**
and are byte-reproducible.

## Data

**The expansion bank, dev half.** 284 of 572 questions, `sha256:ad99afb1…`,
built by EXP-2026-09-001 A-5 and carded at
[`docs/evaluation/composition/bank/MANIFEST.md`](../../../evaluation/composition/bank/MANIFEST.md).

- Authored by 20 Opus 5 subagents from briefs stating **only** the subject of
  each question and the property or edge to ask about — never the answer. Gold
  was computed **first**, independently, from the raw STIX and CAPEC XML.
- Split dev/holdout by `sha256(spec_id)` parity **before anything was run**:
  284 / 288. **The 288-question holdout was not touched by this experiment**,
  and preflight recorded it as sealed.
- Seven tiers: D0 unanswerable (61), D1 property read (63), D2 one hop forward
  (77), D3 one hop reverse (89), D4 two hop (117), D5 constrained (105),
  D6 cross-source (60).

**Selection bias, stated plainly:** the bank deliberately **over-samples** the
shapes nothing has ever asked about, because that is where defects hide. Pooled
accuracy over it is therefore **not** a natural-distribution estimate, and the
bank card says so. Any figure quoted as representative must be reweighted by
`meta.reweighting.census_instances`.

## Metrics

**`judged_correctness`** — an LLM grader reads each written answer and scores it.
Population: all 284 dev questions, per arm. Every answer graded **twice** with
**grading order counterbalanced per block** (`utils/evaluation/grading_order.py`),
because EXP-2026-08-022 measured a ~0.01 position effect in which whichever
condition grades second scores lower. Reported figure is the mean over all
judgments (568 per arm at 2 × 284).

**`direction_paired_mean_delta`** — for each edge shape asked from **both** ends,
`recall(forward) − recall(reverse)`; then the mean over shapes. Positive means
forward was easier. Pairing is **on shape, not on anchor**: pairing on
`(shape, anchor)` yields only 2 pairs because the draw never asks one entity both
ways, whereas pairing on shape gives 20 and still removes the confound A-5 has.
This is a **model-free** measure computed from retrieved evidence against
snapshot-derived gold.

**`*_empty_query_rate`** — of the failures in a tier, the fraction where the
system **built a query successfully and the query returned zero rows**. This
distinguishes "did not understand the question" and "could not build a query"
from "looked in the wrong place", which have different fixes. Model-free.

**`abstention_rate`** — of the 61 D0 questions, which have no answer, the
fraction where the system returned nothing. Failures are sub-classified as
`returned_the_anchor_only` (mild — the subject echoed back) or
`returned_unrelated_neighbours` (serious). Model-free.

> **Two measures, two populations — never compare them.** The judged arm scores
> and the model-free recall in EXP-2026-09-001 A-5 answer different questions
> over different sets by different instruments. The judged numbers rank the three
> arms against each other and are used for nothing else.

## Baselines

Two, both good-faith rather than strawmen:

- **`deterministic`** is the shipped system and the incumbent — the thing C-023
  is about.
- **`llm_query`** is the same construction as EXP-2026-08-008's baseline: the
  model receives the real schema, the resolved seed identifiers, the constraints
  the gate enforces, the output-column convention, and a repair loop that feeds
  gate rejections back. It is denied only the templates.

## Procedure

```bash
# 16 phases, ordered by value rather than dependency, so an interruption leaves
# the most important questions answered. State in overnight-state.json; a
# restart skips completed phases.
uv run python scripts/expansion_overnight.py

# The three model-free analyses run BEFORE grading, deliberately — they answer
# what the night is for, and grading is the long pole (4.9 h for one arm).
uv run python scripts/score_bank.py            # phase: score
uv run python scripts/direction_contrast.py    # phase: direction
uv run python scripts/anomaly_triage.py        # phase: anomalies
uv run python scripts/morning_report.py        # phases: report:early, report:final

# Run afterwards, once the llm_query arm's failure mode was noticed:
uv run python scripts/builder_budget_probe.py
```

## What would falsify this

Written before the run, and both branches fired:

- **The primary hypothesis** (templates close to generic on the home schema) is
  falsified by a judged gap materially larger than the grader's own ~0.0050
  spread and the ~0.01 order effect. **It was: the gap is 0.1642.**
- **The direction question** is settled *against* a single answer if the paired
  contrast's interval spans zero while individual shapes show large gaps in both
  directions. **It did: −0.0797 ± 0.1088 se, with 3 shapes favouring forward and
  10 favouring reverse.**
- **The empty-query diagnosis** would be wrong if the D1 failures were spread
  across causes — misparsed question, no template matched, gate rejection.
  **They were not: 63 of 63 built a query that returned no rows.**
