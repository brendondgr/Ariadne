# Arm H — closing the generic-primitive capability gap

**Created:** 2026-08-09. **Mode:** direct on `main`, no worktree.

## Why

The Arm G control (`EXP-2026-07-007`) scored 0.6388 against Arm F's 0.9956 — a
−0.3568 correctness gap, three times what LLM planning costs. Re-analysis of the
committed judgment files with `utils/evaluation/failure_terminus.py` localised
every lost point:

| Terminus | Cases | Points lost | Share |
|---|---|---|---|
| `seed_lost` | 19 | 17.17 | 40.1% |
| `incomplete_retrieval` | 20 | 14.70 | 34.3% |
| `retrieval_empty` | 7 | 6.60 | 15.4% |
| `other` (bounded scans) | 4 | 2.65 | 6.2% |
| `unfaithful` | 6 | 0.95 | 2.2% |
| `pipeline_timeout` | 1 | 0.80 | 1.9% |

Zero `projection_gap` and zero `property_gap`: every gold id that reached the
evidence reached the answer. The loss is entirely in query construction.

The gap is **not** MITRE domain knowledge. It is three missing capabilities in
the schema-driven layer, each expressible against a source card alone:

1. **Join projection** — emit neighbour *ids* for any edge whose target matches
   the card's declared `join_key`, so a dependent federated hop receives seeds.
2. **Composition** — chain two declared relationships, and intersect two seeded
   anchors.
3. **Anchor/direction resolution** — derive the anchor label from the seed's id
   scheme and the direction from the card's declared edge endpoints.

Plus two smaller defects: seedless enumerations misroute to `describe_by_name`
instead of `label_scan`, and `generic_neighbors` collapses edge direction so
inbound and outbound `USES` are indistinguishable (the sole cause of all six
hallucinations).

## Freeze constraint

`freeze/holdout-v1` (at `974e85a`) forbids behavioural change under
`utils/specialists/` until the blind holdout reports; `docs/research/OPEN_QUESTIONS.md`
confirms it has not. Every change here is confined to code reachable **only**
when `SPECIALIST_GENERIC_ONLY=true`. Shared templates — `_describe`,
`_capec_neighbors` as Arm F uses it, `_capec_maps_to` — are not modified.
Step 6 proves this with a test rather than asserting it.

## Steps

0. **Fixtures and true baseline.** Reload both graphs; record the reference
   pass/fail set. *(Gremlin was empty: 73 specialist tests failed for that reason
   alone. After reload: 362 pass, 1 fail — the known `ORCH_MAX_HOPS=1` env pin,
   which passes at `ORCH_MAX_HOPS=5`.)*
1. **Join projection.** `gremlin/builder.py` generic branch + `gremlin/normalizer.py`.
2. **Composition: chaining.** `cypher/builder.py` and `gremlin/builder.py`.
3. **Composition: intersection.** `cypher/builder.py`.
4. **Anchor and direction resolution.** `gremlin/builder.py`, new generic-only helper.
5. **Scan routing and direction projection.** Both builders.
6. **Freeze-safety proof.** `utils/specialists/tests/test_generic_only_isolation.py`.
7. **Re-run and record.** New experiment folder; mechanical retrieval metrics
   compared against the Arm G baseline.

Each step is validated and committed separately. Nothing is pushed.

## What this plan does not do

It does not re-judge. Judged correctness requires 120 independent Sonnet agents
via the Workflow tool, which is a separate, operator-authorised step. This plan
delivers the mechanical retrieval metrics — failure terminus, gold-in-evidence
coverage, join-value production — which is what the diagnosis was built on and
what the fixes are aimed at.
