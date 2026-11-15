# PROTOCOL — EXP-2026-11-008 Era 2 Step 3: the run log, the agent contract, crash and resume

Written 2026-11-15. The code and its offline tests already pass, but the measurements below have
not been run: the overhead benchmark, the crash sweep as a recorded artifact, and both live runs.

## Question

Does the append-only run log make an agent run:
- resumable after a crash at any point,
- pausable for a clarification,
- forkable and replayable,
- and is every answer it returns a valid envelope?

What does the log cost per event? Does it hold with the real model, not only a scripted one?

## Hypothesis

- **G1 (gate, from the v2 plan): a crashed run resumes to the same envelope.** A scripted run is
  killed (`os._exit`) after each of its appends in turn, every point from the first to the last.
  Each restarted run finishes with an envelope that equals the uninterrupted run's, byte for byte,
  excluding clock keys and the run id. No tool call or tool result is logged twice.
- **G2 (gate): every envelope validates against the JSON Schema.** This covers:
  - every envelope produced by the scripted runs;
  - the 120 recorded era-1 pipeline answers, converted by the fast-path adapter;
  - the live runs.
- **G3 (gate): provenance is complete.** Every `model_call` event in the live runs names its
  served model as the registry name plus the verified token id (`gemma4-31b/106`), and carries
  token counts.
- **E1 (expectation): appends are cheap.** The median append is under 1 ms with SQLite in WAL
  mode and `synchronous=NORMAL`, measured over 2,000 appends of a 1 KB payload.
- **E2 (expectation): concurrent writers are safe.** 8 writers (4 processes and 4 threads) × 250
  appends to one run give gap-free, unique sequence numbers, and each writer's own events stay in
  order.
- **E3 (expectation): the live model finishes from the log.** Gemma 4 31B, driven through the
  log, answers the canned two-tool question ("How many matches did Norway play?") with
  `finish` citing `set:2`, in each of 3 runs.
- **E4 (expectation): a live crash resumes without asking again.** A live run killed right after
  its first `model_call` is logged resumes and finishes. On resume it runs the pending calls
  without asking the model again: the resumed run has no second `model_call` with `step` = 1.
  The envelope may differ from an uninterrupted run, because the live model is not
  deterministic. It must still validate.

## Setup

- `utils/agent/{contracts,log,rebuild,runner}.py` at the commit recorded in `manifest.yaml`.
- The scripted model and canned tools are in `utils/agent/tests/scripted.py`.
- The live model is `gemma4-31b` (relay `:9090`, alias `default-model`), the one model the
  operator has open.
  - Its identity is verified by token id before each run.
  - Temperature 0, `max_tokens` 16,384.

## Data

- **Synthetic:** the scripted Norway question.
- **The 120 recorded answers:** `docs/evaluation/answers/*.json`, for the fast-path adapter.

## Metrics

Each item is listed with what it checks:
- `crash_points` and `crash_points_equal`: G1;
- `duplicate_calls`: G1;
- `envelopes_valid` and `envelopes_total`: G2;
- `provenance_ok_runs`: G3;
- `append_ms_median`, `append_ms_p95`: E1;
- `concurrent_seq_ok`: E2;
- `live_answered` out of `live_runs`: E3;
- `live_resume_repeated_step1`: E4, should be 0.

## Baselines

None. This step is plumbing, and no accuracy is measured.

## Procedure

```bash
uv run python scripts/era2_runlog_check.py --out docs/research/experiments/EXP-2026-11-008-era2-run-log/data
```

## What would falsify this

- **G1 fails** if any crash point gives a different envelope or a duplicated call. The resume
  guarantee would then be false, and Step 3 is not done.
- **G2 or G3 failing** blocks the commit until fixed.
- **E1–E4 are expectations.** A miss is reported as is. A median append over 1 ms would matter
  only if the loop's latency ever came close to it.
