# Protocol — SSE silence under concurrency

## Question

How long does the workbench's `/api/query` SSE stream stay **silent**, and how
often is that longer than the browser will tolerate?

The quantity is deliberately *not* latency. `web/lib/api.ts` cancels any stream
that delivers no bytes for `SSE_STALL_MS` (90 s, `web/lib/streamConfig.ts`), so
what decides whether an analyst sees an answer is the longest gap between
frames, not the total time. A run can take six minutes and be fine; a run that
goes quiet for 91 seconds is dead even if the server is still working happily.

## Conditions

| Condition | Code | What is different |
| --- | --- | --- |
| before | `4747f15` (pre-fix behaviour, measured on the running server) | pipeline emits nothing during an LLM stage |
| after | `84936c3` | `with_heartbeat` emits `: keepalive` every 10 s while a stage is quiet |

Both conditions: 12 questions fired concurrently, `drafter: "llm"`, `mode:
"query"`, every stage resolved to `:9090/default-model`, both graph backends
live.

## Procedure

1. Confirm every LLM stage resolves to the same endpoint: `GET /api/config`.
2. Start the API with a clean environment so it reads the current `.env`
   (see ISSUES.md — an inherited launcher snapshot otherwise pins the endpoint).
3. Run the probe:
   `uv run python utils/tests/sse_gap_probe.py --n 12 --api <endpoint>`
4. For each stream record: every frame's arrival time, whether it was an event
   or a keep-alive comment, the longest gap, and which frame preceded that gap.
5. Count the streams whose longest gap exceeds 90 s. That count — not the
   failure count the server reports — is the result.

## Measurement

- **Primary**: number of the 12 runs whose longest silence exceeds
  `CLIENT_STALL_BUDGET_S` (90 s).
- **Secondary**: worst silence in seconds; which pipeline phase preceded it;
  how many runs the server itself considered successful.

The gap between the primary metric and that last secondary is the entire point
of the experiment.

## Threats to validity

- Latency on a shared relay is not reproducible; see the manifest's
  `nondeterminism_note`. One "before" run and two "after" runs.
- Concurrency is the uncontrolled variable. A run overlapping a *previous*
  probe's tail (≈24 streams in flight) produced one outlier; recorded in
  RESULTS.md rather than dropped.
