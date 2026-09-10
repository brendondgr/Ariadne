# PROTOCOL — EXP-2026-09-016, what each answering path costs

**Pre-registered 2026-09-09, 23:20 EDT, before any run.** Closes the half of
`C-012` that has never had a number, filed as `Q38`.

---

## 1. The question

`C-012` reads: *routing to a fixed library of validated parameterised templates
outperforms letting an LLM plan and generate the queries, in correctness **and
in cost***. Every experiment behind it measures correctness. No wall clock and
no token total has ever been recorded for the `llm_query` arm against the
cascade, so half the claim is asserted.

The October pitch plan names "4 s vs ~2 days, 40,000x" as one of two numbers
that must land in the room. It is traceable to a report, not to a manifest, and
a reviewer who asks "per question or in total, and at what concurrency?"
deserves an answer that does not require a pause.

## 2. What is measured

Three answering paths over the **dev half** of the expansion bank (284
questions). The holdout half stays sealed.

| path | what it is |
|---|---|
| `deterministic` | hand-written templates, no model anywhere |
| `generic` | schema-derived primitives, no model anywhere |
| `llm_query` | the model plans and writes the queries |

Per path, four quantities:

- `wall_clock_s_total` — the whole arm, at the stated worker count.
- `wall_s` per question — median and p95, from each artifact's `run_meta`.
- `prompt_tokens` / `completion_tokens` — read off the transport by the meter
  added in `e5a47b6a`, not estimated from question counts.
- `calls` — counted separately, because a server that omits usage contributes
  zero tokens and a zero total must not read as a path that spent nothing.

## 3. Two regimes, reported separately

This is the part the existing figure elides, and conflating them is how a cost
claim becomes unfalsifiable.

**Throughput.** All 284 questions, 24 workers. Answers "what does it cost to
run the evaluation", which is the number every prior figure in this repository
is implicitly quoting.

**Single-user latency.** A stratified subsample of 40 questions, **1 worker**.
Answers "what does an analyst wait for one question", which is the number a
ReliaQuest engineer is actually asking about and which no run here has ever
produced. A throughput figure divided by a question count is not this number
and must never be presented as it.

The subsample is drawn by fixed seed 20260909 from the dev half, stratified by
source (`attack`, `capec`, `federated`), and the drawn ids are written to
`data/latency_sample.json` before the first run.

## 4. Pre-declared reporting rules

- The ratio between paths is reported **within a regime**, never across.
- Cost in dollars is not reported. The models are locally served, so a dollar
  figure would require a price for hardware this project does not pay per
  token. Tokens and seconds are the honest units.
- `wall_s` includes the pipeline's own deadline. A question that hits the
  budget is recorded at the budget and flagged, not dropped, and the count of
  such questions is reported beside the median.
- If the `llm_query` arm's token total comes back zero, the finding is that the
  server does not report usage. That is written down as a gap, and the seconds
  are still reported.

## 5. Order of work, and what is dropped

The two model-free paths need no GPU and can run after the instances are
withdrawn at 08:00. `llm_query` cannot. So `llm_query` runs first in both
regimes, and if the clock runs out the latency subsample is cut from 40 to 20
before anything else is dropped.

Nothing here changes shipped behaviour. The only code change is the meter,
which records and does not steer.
