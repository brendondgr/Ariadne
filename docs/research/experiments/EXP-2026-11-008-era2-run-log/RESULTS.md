# RESULTS — EXP-2026-11-008 Era 2 Step 3: the run log and the agent contract

## 1. Headline

**Every gate passes.**
- **The crash sweep (G1).** A scripted run was killed after each of its 12 appends in turn.
  Every restart resumed to an envelope equal to the uninterrupted run's, with clock keys
  excluded, and no call was logged twice.
- **Schema (G2).** All 137 envelopes validate: 13 scripted, 120 recorded era-1 answers through
  the fast-path adapter, and 4 live.
- **Provenance (G3).** Every live model call names `gemma4-31b/106` and its token counts.

**The live checks.** Gemma 4 31B, driven entirely from the log, answered 3 of 3 runs. A live run
was killed right after its first model call; it resumed and finished without asking the model
again.

## 2. Results table

From `data/metrics.json` and `data/runlog.json`. One pass; n_runs = 1.

| | Expected | Outcome |
|---|---|---|
| G1 crash points resuming to the same envelope | 12 / 12 | **12 / 12** |
| G1 duplicated tool calls or results | 0 | **0** |
| G2 envelopes valid | all | **137 / 137** (fast path: 101 answered, 19 insufficient) |
| G3 live runs with complete provenance | all | **4 / 4** (3 runs and the resumed one) |
| E1 median append | < 1 ms | **0.015 ms** (p95 0.022 ms; 2,000 appends, 1 KB payload) |
| E2 8 concurrent writers × 250 appends | gap-free, ordered | **yes** |
| E3 live runs answered with `set:2` | 3 / 3 | **3 / 3**: resolve_entity → expand → finish, 3 model calls, 0 repairs |
| E4 step 1 asked again after the live crash | 0 | **0**: killed with 2 events logged; resumed, 3 model calls in all |

`data/live-events.jsonl` holds the complete event logs of the four live runs (52 events).

## 3. Figures

None.

## 4. Interpretation

**The log works as the plan needs it.** A run can be killed anywhere and resumed, paused for a
person and resumed, forked, and replayed. Every answer, from every path, is one validated
envelope. The plan's §4 contract is now code.

**The cost.** At 0.015 ms per event the log is free next to a model call, which takes seconds.

**The fast-path adapter is a stopgap.** The 120 recorded era-1 answers map onto the contract
(101 answered, 19 insufficient), but their envelopes have no sets: the era-1 pipeline has no
server-side handles. Step 5 adds the handles, and with them exact `answer.sets`.

## 5. Threats to validity

- **The crash sweep is scripted and short** (3 model turns, 12 appends). Longer runs pass
  through the same code paths, and the idempotence rules are per call and per exit, not per run
  length. A crash inside SQLite's own commit is SQLite's atomicity, which is not tested here.
- **The live question uses canned tools.** It shows the format and the log working with a real
  model, not retrieval.
- **One model.** Only Gemma 4 31B is open (operator, 2026-11-15).

## 6. What surprised us

Three crash windows would have broken the resume guarantee, and all three were fixed before the
sweep:
- a crash between a call and its result would have logged the call twice;
- a crash after `finish`'s result but before the envelope would have asked the model again;
- a crash after the envelope but before the state change would have left the run "running".

Every step in the driver is now idempotent: before writing, it checks the log for what is
already there.

## 7. Follow-ups

- **Step 5:** exact `answer.sets` on the fast path (handles), replacing the stopgap adapter's
  empty sets.
- **Step 11:** the loop grows from `utils/agent/runner.py`: the validator, the guards, and the
  prompt with the card summary.
- **Step 12:** clarification quality (when to ask) on top of the pause and resume proven here.

## 8. Reproduction

```bash
uv run python scripts/era2_runlog_check.py --out docs/research/experiments/EXP-2026-11-008-era2-run-log/data
```
