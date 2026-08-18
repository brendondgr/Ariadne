# PROTOCOL — EXP-2026-08-005 Binding consistency and direction resolution

**Written before the run.** The plan it executes is
[`docs/plans/binding-and-direction-portability.md`](../../../plans/binding-and-direction-portability.md),
committed at `65651fe` before any code changed.

## 1. The question

`EXP-2026-08-002` scored `groups` 0.00 and `software` 0.06 on a blind bank. The
diagnosis on record is that the hand-written templates encode the relation
direction the development bank happened to ask. This experiment asks a narrower
and more useful question: **is that a fact about MITRE templates, or the absence
of a check that any dataset would need?**

The defect has a portable shape. Routing chose an anchor label from an entity
*mention*; binding took its values from the task's seed ids; no component owned
the question of whether the two agree. Both halves are answerable from schema
the repository already derives from the canonical artifacts.

## 2. Method

1. **Learn** per-label identifier schemes from `nodes.jsonl` — a value's shape,
   case-folded with digit runs collapsed. Three-valued: an opaque property
   (more shapes than the cap) judges nothing.
2. **Audit**, read-only, by driving both builders across bank-derived and
   schema-derived task shapes and asking the registry whether each bound value
   could inhabit the property it filters. This produces the inventory *before*
   any repair, so the repair cannot be scoped to the two routes the blind set
   happened to surface.
3. **Guard**: a binding mismatch becomes a pre-run gate failure, so an
   impossible query abstains with a reason instead of returning an empty result
   that reads as "there are none".
4. **Repair**: a template resolves which end of its edge was seeded from the
   learned schemes, and flips the filter when the schema licenses exactly one
   repair.
5. **Measure** both banks against a worktree of the pre-change tree.

## 3. Pre-registered additivity claim

The repair may reach **only** task shapes that previously emitted a
structurally unsatisfiable query. Therefore:

* `utils/specialists/tests/fixtures/frozen_default_queries.json` is unmodified
  and `test_generic_only_isolation.py` passes.
* The forward direction of every changed template is byte-identical, asserted
  against strings recorded in `test_direction_repair.py` rather than
  regenerated from the code under test.
* The 120-question development catalogue reports **0 improved, 0 regressed**.

A development-set movement in either direction falsifies the claim and makes
every arm figure from 2026-07-26 non-comparable. That is the failure this
protocol is designed to detect.

## 4. Runs

Fixtures reloaded first (`--dataset capec --graph gremlin`; the Gremlin store
was empty), then, at `ORCH_MAX_HOPS=5`:

```bash
uv run python -m utils.evaluation.experiment_untruncated --arm deterministic \
  --root docs/evaluation/experiments/binding-fix-dev --workers 4
uv run python -m utils.evaluation.experiment_untruncated --arm deterministic \
  --bank utils/specialists/tests/golden/holdout_questions.json \
  --root docs/evaluation/experiments/binding-fix-holdout --workers 4
```

The same two commands run from a worktree at `ec01fe7` — the last tree before
any behavioural change — produce the baselines, then
`utils.evaluation.retrieval_coverage` pairs them.

The committed `untruncated` root is **not** used as the reference: it predates
several fixes and would credit this change with their gains.

## 5. What this cannot answer

`gold_in_evidence` is retrieval. It cannot see whether the recovered rows reach
the answer, and it cannot see precision. No arm here is judged.
