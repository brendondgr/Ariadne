# Protocol — EXP-2026-09-019, small-model Generic and planner necessity

Written from `docs/plans/2026-09-13-small-model-and-planner-necessity.md`. Steps
1 and 2 have run; 3–5 have not.

## Step 1 — what the endpoint is, and what it can take

`scripts/local_endpoint_probe.py`, in this order, refusing to continue past any
of them:

1. **Identity.** Resolve the alias and assert the served model id contains the
   expected substring. The id is read off the *response envelope*, never
   `GET /v1/models`, which reports relay configuration rather than what
   answered.
2. **Context ceiling.** Double `max_tokens` on a trivial prompt until the server
   refuses, binary-search the boundary, and record the refusal body verbatim.
3. **Concurrency.** Ten calls per rung at 1, 2, 4, 8, 12, 16 with a fixed prompt
   generating an identical 512 tokens each time, recording aggregate
   tokens/second, per-stream tokens/second, p50, p95 and load.

Hard stops: any error on a rung, a p95 above 4× the rung-1 p50, or a load
average above the core count. The ladder never climbs past a rung that failed,
and rung 1 runs alone first — a single-stream p50 above 20 s aborts the plan at
a cost of ten calls.

The chosen concurrency is the last rung whose aggregate throughput rose more
than 5% over the best seen; a plateau takes the lower rung, which leaves the box
responsive for the same output.

## Step 2 — does the planner need to run?

Two arms over the same 284 development questions (`bank-dev.json`), differing in
exactly one thing: where the plan comes from.

| | `generic_composed` (control) | `generic_planned` (treatment) |
| --- | --- | --- |
| Plan | replayed from the bank | produced by the planner |
| Runner | `run_deterministic` | `run_planned` |
| Generic primitives | on | on |
| Every LLM seam | off | off |
| `ARIADNE_REWRITE` | shipped default (off) | pinned off |

**The LLM posture is verified, not declared.** `iter_pipeline` applies its
`use_llm` argument as `dataclasses.replace(PlannerConfig.from_env(),
llm_enabled=use_llm)` and does the same to the specialist and synthesis configs,
so that argument *overwrites* whatever `PLANNER_LLM_ENABLED` and its siblings
resolved to. A model-free claim therefore cannot rest on the environment. It is
established by patching `socket.socket.connect` for a single question and
counting connections by port, with `utils.llm.token_meter()` bracketed around
the run.

Scored with `scripts/planner_cost_score.py`: deterministic gold coverage
(`deterministic_scores.coverage`), paired per question, overall and per tier,
plus a count of the questions where one arm retrieved records and the other
retrieved none — counted in *both* directions.

Deterministic gold coverage rather than a graded score is deliberate. Both arms
are model-free and byte-reproducible, so a difference cannot be grading noise or
run variance, and it costs seconds rather than the nine hours a judged pass
costs. The plan gates judging on this difference exceeding 0.02.

Also run: `scripts/mechanism_check.py` over the treatment arm, whose
`absence_contradictions` count must be 0 — a planner that retrieves less must
not start asserting that things are absent.

## Steps 3–5 — not yet run

The 2B narrator seam, the 2B specialist seam, and the 2×2 over
{authored plan, real planner} × {no model, 2B}.
