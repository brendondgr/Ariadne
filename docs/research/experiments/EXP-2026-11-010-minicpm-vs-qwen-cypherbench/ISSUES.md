# ISSUES — EXP-2026-11-010

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

## 2026-11-15 — 28% of MiniCPM's thinking-on replies were filed as reasoning; a post-hoc recovery is reported beside the primary result
**Impact:** The primary thinking-on figures count those replies as wrong. The post-hoc "recovered" column re-requests them and takes the answer from a provably unclosed think block, which moves typed3 0.730 → 0.815 and free Cypher 0.750 → 0.800. The decision is the same under both.
**Cause:** MiniCPM's chat template opens `<think>` in the prompt. When the model answers without thinking, it never emits `</think>` (248069), and vLLM's reasoning parser then files the whole reply as reasoning.
**Resolution:** Reported. The recovery is labelled post-hoc. It used re-requests rather than a replay: 159 of 222 reproduced the same reasoning length at temperature 0.

## 2026-11-15 — Code run commit
**Impact:** None on the figures.
**Resolution:** The three pre-registered runs (replay, on, off) used the code at 71fcfb7f. The `recover` subcommand and the third column of `compare` were added afterwards for the post-hoc analysis, and are committed with these results.

## 2026-11-16 — The Gremlin servers came back empty after a restart; A-1's first execution was void
**Impact:** The first execution of A-1 scored every Gremlin arm 0.000, typed ones included. The figures in RESULTS A-1 come from re-executing the saved generations after a reload. The Cypher side was unaffected.
**Cause:** `killtests-gremlin` (:6470) and `ariadne-gremlin` (:6455) hold their graphs in memory, and both restarted about an hour before the run with 0 vertices. `docker ps` still showed them Up.
**Resolution:** Reloaded with `python -m utils.killtests.t1.load` (only into an empty store; parity ok, 0 mismatches in 50 sampled nodes; report in `logs/killtests-2026-11/reload-2026-11-16/`) and `main.py --dataset capec --graph gremlin` (verified). Then only A-1's execute and score stages were re-run.
**Paper implication:** After any restart, check vertex counts before a run. A 0.000 on a compiled backend means an empty store, not a model result.
