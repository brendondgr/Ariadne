# PROTOCOL — EXP-2026-11-010 MiniCPM 4.7 35B against Qwen 3.8 27B on the kill tests' CypherBench part

Written 2026-11-15, before any MiniCPM generation on this benchmark.

## Question

The operator moved the one open model from Qwen 3.8 27B to MiniCPM 4.7 35B. Is MiniCPM in the
same accuracy range on the task era 2 depends on? The task is turning a question about a graph
into a query or a typed request, measured on EXP-2026-11-006 part A (CypherBench, 200 questions).
Or is it weak enough to justify asking the operator for Qwen back?

## Setup

- **The runner:** `utils/killtests/t2c/run.py`, part A, `KILLTESTS_EXPERIMENT=exp006`.
  - The arms are `cypher-3shot`, `gremlin-3shot`, `typed2-3shot`, `typed3-3shot`, plus the
    `typed3-3shot-repair` re-ask.
  - The prompts, compilers, executor and scorer are byte-identical to Qwen's run at f6946de0.
    The only changes since are the additive `reasoning` field on the relay client and
    `reasoning_chars` on each saved generation.
  - `max_tokens` is 8,192, temperature 0, and 32 requests run at a time.
- **Identity:** the runner identifies models by end-of-turn token, and that would file
  MiniCPM (248046) under `qwen38-27b`. Each MiniCPM output folder therefore gets a
  hand-written `run_header.json` naming `minicpm47-35b`. Before the run, the registry verifies
  that identity by token id plus the prompt fingerprint.
- **Two MiniCPM conditions**, in separate folders, back to back:
  - **M-on (primary):** thinking on, the server default. This is the closest to Qwen's
    `reasoning_effort=medium`.
  - **M-off:** `reasoning_effort=none`.
- **The Qwen reference:** EXP-2026-11-006 part A's saved per-question executions (Qwen 3.8 27B,
  `reasoning_effort=medium`).

## The replay check (first)

Qwen's saved part-A generations and repairs are copied into a new folder, then re-executed and
re-scored on today's tree and today's database. The scores must reproduce EXP-2026-11-006's
`typed3-3shot` 0.950 and `cypher-3shot` 0.860 to within 0.005. If they do not, the evaluation
side has drifted: the MiniCPM comparison is then made against the *replayed* Qwen scores, and
the drift is reported.

## Metrics

**Exact records** (EXP-2026-11-006's metric) per arm and condition, for each of:
- free Cypher;
- free Gremlin;
- typed2 and typed3 via Cypher;
- typed2 and typed3 via Gremlin.

Each comes with:
- the paired difference against Qwen over the same 200 questions, with a bootstrap 95% CI
  (`_paired_ci`);
- valid-request rate and repair count;
- reasoning-only replies (`raw` empty, `reasoning_chars` > 0);
- latency and completion tokens.

## Decision rule (fixed now)

The primary arms are typed3-3shot (Qwen 0.950) and free cypher-3shot (Qwen 0.860), for
condition M-on.

| Outcome on either primary arm | Recommendation |
|---|---|
| MiniCPM below Qwen by more than 0.05, and the CI's upper bound below 0 | **Ask the operator for Qwen back** |
| both arms within 0.05, or MiniCPM better | **Stay on MiniCPM** |
| anything in between | Report it as inconclusive, with the numbers; the operator decides |

## Expectations

No strong prior; MiniCPM's accuracy on these tasks has never been measured. Two things are
expected:
- M-off scores lower than M-on on free Cypher. Qwen's reasoning level mattered on part B in
  EXP-2026-11-005.
- Reasoning-only replies are rare, because these replies are code blocks, not one word.

## Threats, known now

- **One benchmark,** and one the typed format was shaped on (part A is development data for
  the format). It is fair for comparing models, not for claims about the format.
- **The Qwen reference ran three days ago.** The replay check covers the evaluation side; the
  generation side is identical code.
- **Temperature 0, one run.**

## Procedure

```bash
uv run python scripts/minicpm_vs_qwen.py replay
uv run python scripts/minicpm_vs_qwen.py run --condition on
uv run python scripts/minicpm_vs_qwen.py run --condition off
uv run python scripts/minicpm_vs_qwen.py compare --out docs/research/experiments/EXP-2026-11-010-minicpm-vs-qwen-cypherbench/data
```

## Amendment A-1 (written 2026-11-16, before the run): does today's Qwen match the saved Qwen?

The operator restored Qwen 3.8 27B on `:9090 default-model`. It was identified by end-of-turn id
248046 plus the server's default prompt rendering. That rendering injects a "Reasoning effort is
set to xhigh" system prompt, which MiniCPM's did not.

- **Run:** part A once more on today's Qwen, at `reasoning_effort=medium` as in EXP-2026-11-006.
  It uses 8 concurrent requests (the operator's limit today) and the same code, in a new folder.
- **Check:** it is the same model, behaving the same, if typed3-3shot→Cypher is within 0.03 of
  0.950 and free cypher-3shot is within 0.03 of 0.860.
  - The margin allows for temperature-0 nondeterminism under concurrency, which A-recovery
    measured on MiniCPM.
  - A larger gap is reported as a different deployment or behaviour, and the comparison above
    is then re-read against today's Qwen.
- **Also counted:** reasoning-only replies, which should be 0, as on 2026-11-14.
