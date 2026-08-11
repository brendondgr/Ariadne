# PROTOCOL — EXP-2026-08-003 Arm H against the blind holdout

## Question

`EXP-2026-08-002` found the deterministic pipeline's largest blind-set failure to
be structural: the hand-written templates serve only the relation direction the
development bank happened to ask. `group_techniques` binds the seed to
`Group.attack_id`, so a technique seed can never match, and the `groups` category
scored **0.00**.

`EXP-2026-08-001` (Arm H) replaced the template cascade with schema-driven
primitives that resolve direction from the declared facet rather than encoding
one. **Does that generalise to questions nobody wrote templates for?**

The question can come out either way. Arm H reached full coverage on the
development catalogue, but that catalogue was co-authored with the templates —
saturating it is weak evidence. A blind set is where a schema-driven layer
either transfers or does not.

## Hypothesis

Arm H's retrieval beats the template cascade's on the blind set, and the gain is
**concentrated in the reverse-direction categories** (`H-GRP`, `H-SW`) rather
than spread evenly. Everything else should be unchanged: the primitives were
never tuned on these questions and most categories already retrieve completely.

Falsified if the gain is diffuse (which would suggest a metric artifact rather
than the diagnosed defect), or if any category regresses.

## Setup

The **same 30-question blind bank**, run through the **same arm code** as
`EXP-2026-08-002`, differing only in `SPECIALIST_GENERIC_ONLY=true`. The bank is
loaded through `experiment_untruncated.py --bank`, the path that experiment used,
so no parallel harness has to be trusted separately.

Arm H had never seen these questions. They were authored blind to the template
inventory, and the Arm H primitives were written before this bank was merged into
`main` — the generic branch was developed against the 120-question development
catalogue only.

## Data

`utils/specialists/tests/golden/holdout_questions.json` — 30 questions, 12
ATT&CK / 8 CAPEC / 10 federated, 16 categories. See
[`../../datasets/cards/blind-holdout-30.md`](../../datasets/cards/blind-holdout-30.md).
Unmodified for this run.

## Metrics

**Retrieval only.** `gold_in_evidence` from
`utils/evaluation/retrieval_coverage.py`, computed identically for all three
arms over the same 30 questions, paired per question.

Arm A and Arm F judged correctness is quoted from `EXP-2026-08-002`'s committed
judgments **for diagnosis only** — to show *where* the retrieval gain lands
relative to where the judge found loss. It is not comparable to
`gold_in_evidence` and no combined figure is computed.

**Arm H is not judged.** That needs 30 independent Sonnet agents and was not run.

## Baselines

Arm A (deterministic) and Arm F (loop + claim-bound writer), both from
`EXP-2026-08-002`, paired per question.

## What would falsify this

A diffuse gain, or any category regressing. Also: if Arm H's residual failures
turned out to be spread across unrelated causes, the "one defect class" reading
would be wrong and the result would be a coverage number without a mechanism.
