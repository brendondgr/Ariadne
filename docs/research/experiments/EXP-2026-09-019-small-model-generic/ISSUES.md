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
