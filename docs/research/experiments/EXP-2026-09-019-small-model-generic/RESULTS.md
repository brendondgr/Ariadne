# Results — EXP-2026-09-019

Status: **running**. Steps 1 and 2 are complete; Steps 3–5 have not run.
Every number here is read from `data/endpoint.json`, `data/endpoint-gemma-4-26B-it.json`
and `data/planner_cost.json`.

## Step 1 — the endpoint

The alias in the plan was wrong, and the identity gate is what caught it.
`local` on the `:4000` relay answers `gemma-4-26B-it`, and did so on both
probes. MiniCPM5-2B is served by the llama.cpp router on `:7070`, where the
gate passes: served id `minicpm-5-2B`.

### Concurrency, `minicpm-5-2B` at `:7070`

Ten calls per rung, an identical 512 generated tokens per call, 32-core host.

| Concurrency | Wall | Aggregate tok/s | Per-stream tok/s | p50 | p95 | load |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 37.0 s | 73.0 | 73.0 | 3.69 s | 3.72 s | 2.8 |
| 2 | 20.3 s | 133.2 | 66.8 | 3.96 s | 4.43 s | 3.3 |
| **4** | 12.8 s | **210.5** | 62.3 | 4.44 s | 4.49 s | 3.3 |
| 8 | 12.7 s | 212.7 | 43.4 | 8.29 s | 8.79 s | 2.9 |
| 12 | 12.9 s | 209.9 | 40.4 | 8.88 s | 12.89 s | 2.6 |
| 16 | 12.9 s | 210.2 | 40.5 | 8.86 s | 12.85 s | 2.6 |

**Chosen concurrency: 4.** Throughput saturates at roughly 210 tok/s from rung 4
onward; rungs 8 through 16 buy nothing and cost roughly double the latency. No
rung errored and no guard tripped, so the full ladder ran.

### The same ladder on `gemma-4-26B-it`, for contrast

Recorded under protest of the identity gate and kept because it makes the
comparison free (`data/endpoint-gemma-4-26B-it.json`). Single-stream 91.0 tok/s,
knee also at concurrency 4 at 140.0 tok/s aggregate, and rung 8 tripped the p95
guard so rung 12 never ran.

The 2B is **slower single-stream** than the 26B (73 vs 91 tok/s) and **faster in
aggregate** (210 vs 140): it parallelises where the larger model does not. Load
never passed 4.4 of 32 cores on either, so the bound is memory bandwidth rather
than CPU.

### Negative result: the context ceiling cannot be probed

Both servers accepted `max_tokens` all the way to the probe cap of 1,048,576
without refusing — no error, no body. They clamp silently. The budget for Steps
3–5 must therefore come from the model card, not from the endpoint. This is the
opposite of the `:9090` behaviour the plan was written against, where the 400s
were the signal.

## Step 2 — the planner costs a great deal

Both arms completed 284/284.

| | `generic_composed` | `generic_planned` |
| --- | ---: | ---: |
| Gold coverage (mean) | 0.8611 | 0.4797 |
| Wall clock, 284 questions, 8 workers | 4.0 s | 17.1 s |

**Paired difference: −0.3814** (sd 0.4413, standard error 0.0262, n = 284),
separable by the `|difference| > 2·SE` rule. Both arms are deterministic, so this
is not run variance, and no model was in either, so it is not grading noise.

On **77 of 284 questions the planner retrieved nothing where the authored plan
retrieved records.** The reverse never happened: zero questions where the
authored plan retrieved nothing and the planner retrieved something. Eight
questions returned nothing on both sides.

### Per tier

| Tier | n | Mean difference |
| --- | ---: | ---: |
| D0 | 36 | −0.3333 |
| D1 | 35 | −0.3157 |
| D2 | 40 | −0.3117 |
| D3 | 44 | −0.4055 |
| D4 | 55 | −0.2981 |
| D5 | 47 | −0.5025 |
| D6 | 27 | −0.5534 |

Every tier loses. The loss concentrates in D5 and D6 — the chained and
cross-catalogue tiers, where a plan has the most structure to get wrong.

### What does not degrade

`scripts/mechanism_check.py` over the treatment arm reports **0 absence
contradictions across 284 answers**. The planner arm retrieves less; it does not
start asserting that things are absent. One mechanism improves rather than
degrades: the name-search slice rises from 0.0443 to 0.4443 coverage, with its
zero-record count falling from 21 to 11.

### What this means for every figure that rests on 0.92

The Generic tier's headline is a ceiling for retrieval and composition **given a
correct plan**, and this is the first measurement of what producing that plan
costs. It is not a small correction. The difference exceeds the 0.02 threshold
the plan set for a judged pass by a factor of nineteen, so the judged read is
warranted; it has not been run yet.

The difference is not attributed to the planner *alone*. `generic_planned` runs
the real pipeline, so the planner's own per-plan limits travel with it — the
observed plans set `max_result_rows: 1000` and `max_traversal_depth: 3` rather
than the lifted bounds the gold-replay path inherits. Separating "the planner
chose a worse decomposition" from "the planner chose tighter limits" is not done
here and is recorded in `ISSUES.md` as I-2.
