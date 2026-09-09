# PROTOCOL — EXP-2026-08-004 The bridge as an outer join

> Written retrospectively on 2026-09-09 from the plan file, the RESULTS, and the artifacts; this experiment ran before its protocol was recorded.

The file that stood here until 2026-09-09 was the unfilled scaffold template
(RESULTS A-1). What follows is reconstructed from: the parent plan
[`docs/plans/arm-h-generic-primitives.md`](../../../plans/arm-h-generic-primitives.md)
(committed `bf2e4c8`, 2026-08-09, which scopes Arm H and states that nothing
in it re-judges); the `hypothesis` field of `manifest.yaml`, written when the
folder was created; `EXP-2026-08-003` §4 and §7 item 1, which specified the
fix; the six-commit series "Bridge outer join (1/6)…(6/6)" (`6f14867`,
`618bc20`, `54421e0`, `1e8e16f`, `93da6d4`, `cce81c8`, 2026-08-10 23:18–23:55);
and `RESULTS.md`. Nothing below was pre-registered, and the direction of the
effect was known from `EXP-2026-08-003` §4 before the code changed.

## Question

`EXP-2026-08-003` left five gold identifiers unretrieved on the blind holdout
(`CAPEC-116`, `CAPEC-456`, `CAPEC-679`, `CAPEC-603`, `CAPEC-40`, in four
questions) and traced all five to one cause: `_generic_bridge` was an inner
join, so a CAPEC anchor with no ATT&CK mapping was dropped from the evidence
entirely. Does making the bridge an outer join recover all five **without
regressing** either question set? And of the blind loss that survives complete
retrieval (the "45%" of `EXP-2026-08-003` §3), how much is a small number of
named composition defects rather than diffuse judge deductions?

## Hypothesis

From `manifest.yaml`: the outer join recovers all five residual identifiers
with no regression on either set, and the surviving blind loss resolves to a
small number of named composition defects. Falsified by any regression, or by
the residual loss having no dominant named class.

## Setup

Arm H exactly as `EXP-2026-08-001` and `EXP-2026-08-003` ran it
(`SPECIALIST_GENERIC_ONLY=true`, un-truncation profile, LLM planner,
facet-chasing loop, claims-bound LLM narrator, `untruncated_env(arm="generic")`),
with one change reachable only under that flag:

* `_generic_bridge` (Gremlin) projects one row per anchor with its mappings
  folded into a possibly-empty list, instead of `.out(edge)` dropping anchors
  with no edge (`6f14867`, "Keep anchors that map to nothing");
* the CWE-anchored chain keeps its first hop an inner join (only patterns that
  exploit the weakness belong) and outer-joins its second (`618bc20`).

The hand-written templates (`capec_maps_to`, `cwe_chain`) were deliberately
**not** changed, so `test_generic_only_isolation.py` — byte-identical default
cascade against `freeze/holdout-v1` — still passes and the 2026-07-26 arm
figures stay comparable (ISSUES.md; later overtaken, see RESULTS A-3).

## Data

Two banks, both unchanged for this run:

* the 30-question blind holdout
  `utils/specialists/tests/golden/holdout_questions.json` (holdout-v1,
  `EXP-2026-08-002`; hashed in `EXP-2026-08-003`'s POINTERS);
* the 120-question golden catalogue (`../../datasets/cards/golden-catalogue-120.md`),
  already saturated at 1.0000 for this arm (`EXP-2026-08-001`), run to detect
  harm rather than gain.

## Metrics

All mechanical, computed by `utils/evaluation/retrieval_coverage.py` from the
answer artifacts; nothing judged.

| Metric | Definition |
|---|---|
| `blind_gold_in_evidence` **(primary)** | Mean over 30 blind questions of the fraction of gold identifiers present in the retrieved evidence. Success: 1.0000. |
| `dev_gold_in_evidence` | The same over the 120 catalogue questions. Success: unchanged at 1.0000. |
| fully covered / gold ids missing / evidence records | Counts, per set, before and after. |
| paired improved / regressed | Per-question comparison against the inner-join runs (`holdout-v1-generic`, `untruncated-generic-fixed`). Success: regressed = 0 on both sets. |
| `answer_gap` classes | `utils/evaluation/answer_gap.py` over `EXP-2026-08-002`'s committed **Arm F** judgments: for questions that retrieved completely, the class of the largest observable deficit (`under_enumeration`, `judge_nuance`, `unfaithful`, …) and its share of total loss. Characterises Arm F, not Arm H. |

## Baselines

Paired per question against `EXP-2026-08-003` (blind, inner join) and
`EXP-2026-08-001` (development, inner join); the template cascade's blind
figure from `EXP-2026-08-002`'s Arm F artifacts. No external system.

## Procedure

As reproduced in `RESULTS.md` §8, in this order on 2026-08-10:

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin

# blind, at 618bc20 (artifacts 23:28)
uv run python -m utils.evaluation.experiment_untruncated --arm generic \
  --bank utils/specialists/tests/golden/holdout_questions.json \
  --root docs/evaluation/experiments/holdout-v1-generic-outer --workers 4
# development, at 1e8e16f (artifacts 23:51)
uv run python -m utils.evaluation.experiment_untruncated --arm generic \
  --root docs/evaluation/experiments/untruncated-generic-outer --workers 4

uv run python -m utils.evaluation.retrieval_coverage \
  --root docs/evaluation/experiments/holdout-v1-generic-outer --arm generic \
  --reference-root docs/evaluation/experiments/holdout-v1 --reference-arm gold_loop_llm
uv run python -m utils.evaluation.answer_gap \
  --root docs/evaluation/experiments/holdout-v1 --arm gold_loop_llm \
  --judgment-root docs/evaluation/experiments/holdout-v1 --judgment-arm gold_loop_llm
```

## What would falsify this

Any question whose gold-in-evidence count falls on either set; any of the five
identifiers still missing; or an `answer_gap` decomposition in which no single
class carries most of the loss that survives complete retrieval. A rise in
evidence records with no rise in coverage on the development set was expected
(unmapped anchors now returned) and is not a falsifier.
