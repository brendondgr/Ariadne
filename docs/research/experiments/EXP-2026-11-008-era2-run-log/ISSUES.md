# ISSUES — EXP-2026-11-008

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

<!-- Entry template — newest first:

## YYYY-MM-DD — <one-line summary>
**Impact:** what this changes about the reported numbers (e.g. "seed 3 excluded; n=4 not 5 for this cell").
**Cause:** the mechanism, if known.
**Resolution:** what was done. "Not resolved" is a valid answer.
**Paper implication:** what must be stated in the paper because of this.

-->

## 2026-11-15 — Three crash windows found by reading the driver, before the sweep ran
**Impact:** None on the reported numbers. They were fixed in the committed code, so the sweep ran against the fixed driver.
**Cause:** Appends are atomic one at a time, but a run's step is several appends (`tool_call`, `tool_result`, `answer`, `envelope`, `state`).
**Resolution:** Every step checks the log before writing: a call already logged is not logged again, a `finish` with a result but no envelope is completed, and an envelope's state is repaired on read.
**Paper implication:** The log is replayable only because every step is idempotent. Say so when describing it.

## 2026-11-15 — One model
**Impact:** The live runs use Gemma 4 31B only.
**Cause:** Operator, 2026-11-15: only `:9090 default-model` is open. The registry marks the others closed.
**Resolution:** None needed for this step.
