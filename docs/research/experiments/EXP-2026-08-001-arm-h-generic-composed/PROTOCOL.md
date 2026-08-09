# PROTOCOL — EXP-2026-08-001 Arm H — generic primitives with composition, join projection and anchor resolution

> Written while the run was in flight, not after it. The predictions in
> §Hypothesis are quantitative and were committed before any full-run artifact
> was read; the smoke evidence they rest on is the per-question output of the
> ten-, fourteen- and eight-question spot checks recorded in the Arm H commits
> (`925f2a3`, `b6c4f12`). Honest caveat: this is **not** a clean
> pre-registration, because those spot checks had already shown the direction of
> the effect on 30 of the 120 questions. It is recorded that way in `ISSUES.md`
> rather than dressed up.

## Question

Arm G established that removing every hand-written template costs −0.3568
correctness. Is that gap **domain knowledge** — things a template author knows
about ATT&CK and CAPEC that no schema declares — or is it a **capability** gap
in the schema-driven layer, closable using only what the source card and the
derived schema registry already declare?

The question has an answer that could come out either way. If the gap is
knowledge, adding generic capabilities will move retrieval a little and leave
most of the deficit standing.

## Hypothesis

**The gap is capability, not knowledge.** Three additions — cross-source join
projection, composition (multi-hop chaining and two-anchor intersection), and
anchor/direction resolution — will close most of the retrieval deficit without
one MITRE-specific literal entering the builder.

Concretely, against Arm G's committed per-question artifacts:

| Prediction | Arm G | Arm H predicted |
|---|---|---|
| `seed_lost` cases | 19 | 0 |
| `retrieval_empty` cases | 7 | ≤ 2 (the F-PART boundary pair may legitimately stay empty) |
| `incomplete_retrieval` cases | 20 | ≤ 5 |
| `answer_coverage` | 0.8979 | ≥ 0.97 |
| Cases whose gold-in-evidence **decreases** | — | 0 |

The last row is the one that matters most: a change that trades one category
for another is not a fix.

## Setup

Identical to Arm F/Arm G in every respect except the query builder's
generic branch. `SPECIALIST_GENERIC_ONLY=true`, the un-truncation profile, the
LLM planner, the facet-chasing loop, and the claims-bound LLM narrator, exactly
as `untruncated_env(arm="generic")` sets them. Arm F (`gold_loop_llm`) and Arm G
(`generic`) differ by that one flag and nothing else, which is what makes the
contrast clean.

What changed, all of it reachable only under that flag:

* `_generic_bridge` (Gremlin) — walks the declared `JoinKeyEndpoint`'s
  `via_edge` and projects its key property, in either direction, prefixing the
  declared path from a non-anchor seed to the label that owns the edge.
* `_generic_chain` (Cypher) — breadth-first over the derived schema registry to
  every requested label, one independently-aggregated `OPTIONAL MATCH` per
  branch.
* `_generic_intersect` (Cypher) — nodes adjacent to every seed, when the seeds
  carry different identifier prefixes.
* `_generic_walk` (Gremlin) — registry-driven `union` walk resolving the anchor
  label from the resolved task and the direction from the declared facet.
* Bounded scans require a definitional cue before routing to a name lookup.

## Data

The same 120-question golden catalogue, all questions, fixed order — the same
artifact Arm G ran against, so the comparison is paired per question. See
[`../../datasets/cards/golden-catalogue-120.md`](../../datasets/cards/golden-catalogue-120.md)
for provenance and the co-authoring limitation, which this experiment does
**not** address and does not claim to.

## Metrics

The primary metric here is **not** judged correctness. This run is scored
mechanically, from the artifacts:

| Metric | What it computes |
|---|---|
| `answer_coverage` **(primary)** | Fraction of gold ids reaching the retrieved evidence, over 120 questions. Deterministic. |
| `gold_in_evidence_cases` | Questions whose gold set is fully present in the evidence. |
| terminus distribution | `utils/evaluation/failure_terminus.py`, per class, against Arm G's. |
| `regressions` | Questions whose gold-in-evidence count fell relative to Arm G. |

Judged correctness requires 120 independent Sonnet 5 agents via the Workflow
tool — a separate, operator-authorised and billed step. It is **not** run here,
and no correctness number may be quoted for Arm H until it is. That is the
honest boundary of this experiment and it is stated in `RESULTS.md` too.

## Procedure

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm generic --root docs/evaluation/experiments/untruncated-generic-fixed --workers 4
uv run python -m utils.evaluation.failure_terminus \
  --root docs/evaluation/experiments/untruncated-generic-fixed --arms generic
```

## Baselines

Arm G (`EXP-2026-07-007`), paired per question. No external system: the study
still has no counterfactual baseline, which remains its largest structural
limitation and is recorded in
[`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md), not glossed here.

## What would falsify this

If the terminus distribution barely moves — if `seed_lost` and
`retrieval_empty` survive in numbers — then the missing ingredient is
domain knowledge after all and C-003 stands as written. Equally, if coverage
rises while any question's gold-in-evidence falls, the change is a trade rather
than a fix and must be reported as one.

A result here does **not** touch C-012. No LLM writes Cypher or Gremlin in this
arm either; the free-form generation baseline remains unbuilt.
