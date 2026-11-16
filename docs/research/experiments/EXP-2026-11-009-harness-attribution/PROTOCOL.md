# PROTOCOL — EXP-2026-11-009 Era 2 Step 4: where the planned path loses, and whose fault it is (RQ5, Q57, Q58)

Written 2026-11-15, before any question was coded and before any arm was run.

**What was looked at first, disclosed.** Two looks at the data shaped this protocol, and both
are reported rather than hidden:
- **A pilot of 10 random lost questions** (deterministic planner) was read to build the codebook.
- **Aggregate features** were counted over both lost sets:

  | Feature | Deterministic | LLM |
  |---|---:|---:|
  | anchor written in the planner's text | 77 / 77 | 105 / 105 |
  | anchor in the text but not bound by the resolver | 19 | 38 |
  | gate rejected an over-long chain | 23 | 47 |
  | the LLM's own plan named the authored relations | — | 69 |

The expectations below are therefore informed, not blind. The cause of any single question was
not decided before the coder and the second annotator ran.

## Background: a correction

The era-2 plan v2 (§1.4) read EXP-2026-09-019 as "swapping the model in the planner cost
+0.0000". That reading is wrong:
- In every EXP-2026-09-019 arm the **planner was deterministic** (`planner: false`, zero model
  calls).
- The swapped model was a 2B **narrator**, which writes prose after retrieval and cannot move
  retrieval coverage. +0.0000 is what the design guarantees, not a finding about planners.
- The −0.3814 is the **deterministic planner's** cost against the authored plan.

The record has one LLM-planner arm on the same 284 questions: EXP-2026-09-020 A-2,
`generic_planned_llm`, with Gemma 4 26B as the drafter and every other seam off. That is the
arm this experiment uses for the model half.

## Question

When a planner replaces the authored plan and the answer comes back empty, **where in the
pipeline is the answer lost?**
- For the LLM planner: is the loss already in the model's plan, or does the harness lose a
  plan the model got right (the parsing, the gate, the query builders)? This is RQ5.
- Separately (Q58): how much of the −0.3814 is the planner's tighter limits rather than its
  decomposition?

## Populations

From `docs/evaluation/experiments/plan-source-2026-09-14/`. All 284 dev questions, three saved
arms:

| Arm | Plan source | Saved coverage |
|---|---|---:|
| `generic_composed` | authored plan | 0.8611 |
| `generic_planned` | deterministic planner | 0.4797 |
| `generic_planned_llm` | Gemma 4 26B planner | 0.4858 |

- **L_det:** the questions where `generic_planned` retrieved 0 records and `generic_composed`
  retrieved records. n = 77, which is the 77 of Q57.
- **L_llm:** the same definition for `generic_planned_llm`. n = 105.
- **Both:** n = 38 questions are in both sets.

## The pipeline and the two stages

The pipeline runs in this order:
1. the planner's output, `observed_plan`: source, sub-question text, entities (LLM only) and
   limits;
2. the resolver, which binds seed ids from the sub-question's *text* and labels and relations
   from the entities;
3. the gate;
4. the query builder;
5. execution.

**Stage `plan`:** the planner's own output was already wrong. For the LLM planner this is the
model's decision.

**Stage `downstream`:** the plan named the right things and the harness lost them.

The LLM planner's output format has **no seed-id field**. Seeds are always re-read from its
English by the resolver, whereas the authored plan hands seeds over directly. That asymmetry is
part of the harness, and it is what `english_reread` measures.

For the deterministic planner every stage is harness, because its "plan" is rules. Its
plan-stage causes name *which part* of the harness to fix.

## Codebook: exactly one cause per question, the first one in pipeline order

Notation:
- `A` is the authored arm's executed results.
- `P` is the planner arm's executed results.
- `OP` is the planner's `observed_plan`.
- The **anchor** is the authored seed ids that appear in the question text, or else the first
  authored result's seeds.

| Order | Cause | Stage | Rule |
|---|---|---|---|
| 1 | `source` | plan | The source of the authored first step is not among `OP`'s sources. |
| 2 | `shape` | plan | The authored plan is an attribute lookup (template `describe`) and no `P` result is. |
| 3 | `relation` | plan | The plan's schema elements miss an authored relation. For the LLM, the plan's elements are `OP` entities; for the deterministic planner, they are `P`'s resolved labels and relations. |
| 4 | `english_reread` (mechanism `resolver_changed_schema`) | downstream | LLM only: `OP` entities contain every authored relation, but `P`'s resolved relations do not. |
| 5 | `relation` (mechanism `superfluous_schema`) or `english_reread` (mechanism `resolver_added_schema`) | plan / downstream | The gate rejected a chain for exceeding `max_traversal_depth`. It is downstream when the resolver added labels or relations that are not in the LLM's `OP` entities; otherwise it is plan. |
| 6 | `decomposition` | plan | A step was skipped because the step it depends on failed, or the plan's step count differs from the authored plan's and a step returned nothing. |
| 7 | `limit` | plan | `OP` depth is below the authored path length, or `OP`'s row limit is below the authored record count. |
| 8 | `entity` | plan | No anchor id appears in `OP`'s text. |
| 9 | `english_reread` (mechanism `seeds_dropped`) | downstream | An anchor id appears in `OP`'s text, but no `P` result bound it as a seed. |
| 10 | `direction` | downstream | The anchor and relations are bound, and the `P` query traverses an authored relation only in the opposite orientation to the `A` query (Cypher arrows, Gremlin `in`/`out`). |
| 11 | `missing_operator` | plan | Assigned only by an annotator: the question needs an operation the plan format cannot state. |
| 12 | `other` | — | Nothing above applies. |

**First in pipeline order is conservative for RQ5.** When a plan error and a downstream error
co-occur, the plan error wins, so the downstream share is a lower bound. Every applicable flag is
also recorded, so the multi-label counts are reported alongside.

## Second annotator

- **Who:** an independent subagent (Claude Sonnet 5.5, medium effort) codes a random 20 of
  L_det and a random 20 of L_llm (seed 20261115).
- **What it gets:** the codebook and a per-question evidence packet: the question, the
  authored and planned executed steps (source, labels, relations, seeds, template, query, error
  or summary) and the observed plan. It does not see the automatic code.
- **Reported:** exact-cause agreement and Cohen's κ, stage agreement, and every disagreement
  listed.

## The third arm (Q58) and the reruns

All three arms are model-free, run back to back from one commit on today's tree and today's
graphs:

1. `generic_composed`: the authored plan at lifted limits (20,000 rows, depth 3);
2. `generic_composed_capped` (new): the authored plan at the deterministic planner's limits
   (1,000 rows, depth 3, as observed on all 334 of its sub-questions);
3. `generic_planned`: the deterministic planner.

From these:
- (1) − (2) is the **limits effect**.
- (2) − (3) is the **decomposition effect**.
- (1) and (3) also check that the September figures reproduce on today's tree.

`generic_planned_llm` cannot be rerun: its model, Gemma 4 26B, is not served, and the only open
model is down for a swap. It stays a saved arm. Its tree is EXP-2026-09-020's.

**Model-free at the socket.** The runs execute in-process under a guard that refuses and counts
every connection to the model ports (9090, 4000, 7070, 7500). The count must be 0.

**Per-stage timing.** `iter_pipeline`'s `plan_ms`, specialist timings and `total_ms` are now
saved on every planned answer. They are reported for `generic_planned` as a table: the median
and p95 of each stage.

## Metrics

- Cause counts per population (first-in-order), stage shares, and multi-label flag counts.
- Causes on the 38 questions both planners lost (same cause or not).
- Per tier (D0–D6).
- Agreement and κ.
- Coverage of the three rerun arms, with the paired differences and their standard errors.
- Socket-guard attempts.
- Stage timing.

## Hypotheses and expectations

- **Gate G1:** every question in L_det and L_llm gets exactly one cause.
- **Gate G2:** zero model-port connections during the three reruns.
- **E1 (the RQ5 read):** the downstream share of L_llm, read with pre-set bands:

  | Downstream share | Reading |
  |---|---|
  | ≥ 0.50 | "mostly harness" (RQ5's provisional answer confirmed) |
  | 0.25 to under 0.50 | "mixed" |
  | under 0.25 | "mostly model" |

  Expected: **mixed or better**, given the 38 dropped seeds in the pilot counts.
- **E2:** for the deterministic planner, the plan-stage causes (`relation`, `source`, `shape`,
  `decomposition`) are the majority of L_det.
- **E3 (Q58):** the limits effect is small, |(1) − (2)| ≤ 0.02. Nearly all of the −0.3814 is
  then decomposition.
- **E4 (drift):** today's `generic_composed` and `generic_planned` are within 0.01 of 0.8611
  and 0.4797. A larger drift is reported, and only today's runs are compared with each other.
- **E5 (the plan's anticipation, kept even though the pilot argues against it):** D5 and D6 are
  dominated by `decomposition`.
- **E6:** the second annotator agrees on at least 75% of exact causes, with κ ≥ 0.6. Lower
  agreement is reported, and the codebook rules that produced the disagreements are named.

## Procedure

```bash
uv run python scripts/harness_attribution.py rerun  --root docs/evaluation/experiments/harness-attribution-2026-11-15
uv run python scripts/harness_attribution.py code   --out docs/research/experiments/EXP-2026-11-009-harness-attribution/data
uv run python scripts/harness_attribution.py packets --out docs/research/experiments/EXP-2026-11-009-harness-attribution/data
# second annotator (subagent) writes data/annotator2.json from data/packets/
uv run python scripts/harness_attribution.py agree  --out docs/research/experiments/EXP-2026-11-009-harness-attribution/data
```

## What would falsify this

- **If E1 comes out "mostly model",** RQ5's provisional answer is wrong. Step 11's expectation
  drops, and Step 7's decision models matter more (plan v2, Step 4, "What the result decides").
- **If E3 fails** (the limits effect is over 0.02), Q58's fix is partly a configuration change.
  That is reported as such.
- **If E6 fails badly** (κ < 0.4), the automatic codes are not a measurement. The analysis then
  reports flags only, not single causes.

## Amendment A-1 (written 2026-11-16, before the run): the model half on Qwen 3.8 27B

The operator retired Gemma as a basis for comparison, and this experiment's model half came from
a saved Gemma 4 26B planner arm. This amendment reruns that half on the open model.

**Runs.** All are on one commit and one tree, back to back, over the 284 dev questions, with
`--workers 32` (the operator gave the server to this work):
1. `generic_composed`, model-free;
2. `generic_planned`, model-free;
3. `generic_planned_llm` on Qwen 3.8 27B (`:9090 default-model`) at `reasoning_effort=medium`,
   sent through the new opt-in `LLM_REASONING_EFFORT`. Its identity is verified by the
   registry (token id plus default-rendering fingerprint) before and after.

Runs 1 and 2 go under the socket guard. Run 3 cannot, because it calls the model.

**Coding.** The same coder, rules and bands as the main protocol, over L_qwen: the questions
`generic_planned_llm` retrieves nothing on and `generic_composed` retrieves records on.

**Primary:** the downstream share of L_qwen under the pre-registered rules, read with the same
bands (≥ 0.50 mostly harness; 0.25–0.50 mixed; < 0.25 mostly model).

**Secondary, now named in advance:** the builder-walk reading (`recode_builder_walk`), which was
post-hoc in the main run. Also reported:
- coverage of the three arms;
- the paired differences of each against `generic_composed`;
- the cause table;
- the overlap of L_qwen with the deterministic planner's lost set.

**Expectation:** the "mixed" band, by both readings. Wrong relation choice stays the largest
single cause.

**No second annotator** is run for this amendment. The coder's agreement was measured in the
main run (κ 0.71) and the rules are unchanged.
