# Issues — EXP-2026-09-019

## I-1 — "model-free" was a declaration, not a fact (resolved)

`iter_pipeline` applies its `use_llm` argument as
`dataclasses.replace(PlannerConfig.from_env(), llm_enabled=use_llm)`, and does
the same to the specialist and synthesis configs. That **overwrites** the
env-resolved value, so an arm pinning `PLANNER_LLM_ENABLED=false`,
`SPECIALIST_LLM_ENABLED=false` and `SYNTHESIS_LLM_ENABLED=false` still ran every
seam live against `ARIADNE_LLM_BASE_URL`.

`generic_planned` was wired to `run_rewrite`, which passes `use_llm=True`, and
so ran LLM-planned against `:9090` / `qwen38-27B-v2` while its own environment
said it had no model. Caught by patching `socket.socket.connect` for a single
question: the planner's `OpenAICompatibleDrafter` opened a connection to the
configured endpoint. Wall clock agreed — 89 to 241 seconds a question, against
0.16 once the posture was corrected.

Resolved by making the posture a parameter at the call site:
`_run_real_pipeline(..., use_llm=...)`, with `run_planned` (False) for this arm.
`run_meta` also stopped hardcoding `"planner": "deterministic"` regardless of
what ran. Locked by `utils/evaluation/tests/test_experiment_arms.py`.

## I-2 — the planner's limits travel with its plan (open)

`generic_planned`'s difference is attributed to "the plan" in the headline, but
the planner emits its own per-sub-question limits — observed plans carry
`max_result_rows: 1000` and `max_traversal_depth: 3` — where the gold-replay
path inherits the lifted bounds via `lift_task_limits`. Some share of the
−0.3814 may be the tighter limits rather than a worse decomposition. Separating
them needs a third arm holding the planner's decomposition and lifting its
limits. Not run.

## I-3 — `rewrite_off` and `rewrite_det` are affected by I-1 (open, not this experiment's to fix)

The same defect applies to EXP-2026-09-014's arms: their env pins every seam
`false` and their comment says "no language model anywhere", but they go through
`run_rewrite` and therefore ran with live seams. `run_rewrite` was deliberately
left at `use_llm=True` here, because those figures are published and changing
the posture would silently re-describe them. Whether they meant to be model-free
is a question for an amendment to that experiment, not a silent edit from this
one.

## I-4 — a pre-existing unrelated test failure

`utils/specialists/evalset/tests/test_variant_scoring.py::test_every_rewrite_mode_states_both_flags`
fails on `ARIADNE_REWRITE_DERIVE_RELATION` being an extra key in `REWRITE_ENV`.
Confirmed pre-existing: it fails with this experiment's changes stashed out.
Not touched.

## I-5 — Steps 3–5 not run

The 2B seams and the 2×2 are outstanding. The endpoint they will use is
characterised (`data/endpoint.json`) and its chosen concurrency is 4.

## I-6 — seeds not recorded

`seeds: []` in the manifest. Both Step 2 arms are model-free and deterministic,
so there is nothing to seed; this will stop being true at Step 3.

## I-7 — `make validate-research` is red repo-wide, from before this experiment

Three `pointer-hash-mismatch` rows fail the whole-record validation:
`EXP-2026-09-001/data/POINTERS.md` (`scripts/prepare_briefs.py`),
`EXP-2026-09-007/data/POINTERS.md` (`utils/evaluation/judge_answers.py`) and
`EXP-2026-09-012/data/POINTERS.md` (`docs/evaluation/experiments`). All three
were verified to fail with this experiment's run root moved out of the tree, so
none is caused by it. The third's hash *also* moves whenever anything is written
under `docs/evaluation/experiments`, which this experiment does — but it was
already stale beforehand. This experiment's own folder validates.

## I-8 — 11 of 284 claim *texts* differ, and the narrator is not the cause (open)

At n=284 the claim-identity gate reported 273 of 284 identical. The 11 that
differ do so in `text` and in nothing else: across all eleven, zero changes to
`entity_ids`, zero to `citations`, zero to `verdict`, and zero new unsupported
verdicts anywhere in the run. The facts are untouched; the wording of a
relationship is not.

The mechanism is in `utils/synthesis/composer.py`. `_REL_NOUNS` maps `DETECTS`
to "detected technique", and when that lookup does not apply the noun falls
through to the neighbour's LABEL — the fallback the table's own comment was
written to prevent, because it "asserts a hierarchy that does not exist". The
observed difference is exactly that fall-through: "has 1 detected technique:
T1491" against "has 1 technique: T1491".

**It is not the narrator.** Re-running the same question three times on the
narrator arm at one worker reproduces the control's wording every time, and
re-running the control on all eleven cases at one worker and at four workers
produces byte-identical claims in every pairing (0 differences across 3
comparisons x 11 cases). It appears only in a sustained full-bank run and does
not reproduce in isolation, which is why it is recorded here rather than fixed:
a defect that cannot be reproduced cannot be verified fixed.

This is a composer defect, not a small-model one, and it is reachable by every
arm in the project. Raised for its own investigation rather than repaired
inside an experiment about model size.

## I-9 — the specialist seam is not viable at 2B (Step 4 result, not a failure)

On the nine-question gate, `generic_local_full` returned **zero records on 9 of
9 questions** where the model-free control returned records on 9 of 9, and every
one of the nine queries differed from the control's. Counted at the level that matters — drafts submitted to
the gate, not questions — the seam produced **0 working queries out of 17**.

| | 4096-token budget | 16384-token budget |
| --- | ---: | ---: |
| Drafts reaching the gate | 17 | 16 |
| Rejected as empty | 11 | 8 |
| Rejection rate | 0.6471 | 0.5000 |
| Cleared the gate, then failed at the database | 6 of 6 | 8 of 8 |
| **Drafts that actually worked** | **0 of 17** | **0 of 16** |

Quadrupling the token budget is therefore not the missing ingredient, and this
is the reason the budget was made a call-time override rather than a constant:
the claim "a 2B cannot draft these queries" is only worth having if it was
tested. What the larger budget bought was a shift in *failure mode*, not in
outcome — fewer drafts truncated into nothing, and correspondingly more
malformed drafts reaching the database and erroring there.

The empty drafts are the model rambling rather than a context limit: the prompts
are ~870 tokens and the model spends the entire completion budget without
closing a query.

No rejection named `allowed_edge_patterns`. That is worth stating plainly
because the plan expected the allowlist gate to be what stopped a bad draft.
Instead the drafts were empty, and those that were not empty **reached the live
graph engines and failed there** — Gremlin `597: No such property: params`,
Gremlin `499: ... invalid parameters key of [[id]] - these are reserved names`,
and Neo4j `ParameterMissing`. Malformed model-written queries executing against
the database rather than being refused before it is a gate finding in its own
right, and it is not specific to a small model.

The plan's rule is that above a 25% rejection rate this seam is not viable at 2B
and the step records that rather than widening. The observed figure is a total
retrieval failure, so the full 284-question pass was not run.
