# ISSUES — EXP-2026-11-019

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

## 2026-11-20 — Gemma's id-as-name sometimes fails before the guard runs
**Impact:** None on the checks. Two Gemma items (F-CTT-02 T0, F-NEG-06 T6) passed the id as a name, and the lookup found no confident match. The step was refused with `ambiguous_anchor` before the guard could act, and the repair turn anchored the id.
**Cause:** The guard runs only after a lookup that finds something.
**Resolution:** Not widened. Watch the `ambiguous_anchor` refusals in Step 9's run.
**Paper implication:** None.

## 2026-11-20 — First attempt ran against a stale store manifest; discarded
**Impact:** None on the reported numbers. The first attempt's variant arms stopped at the preflight check ("Stale runtime manifest for neo4j: canonical hash mismatch"). Its dev arms ran, because they have no such check. All of its output was set aside unread for scoring (`data/stale-attempt-progress.log`).
**Cause:** The full test suite rewrites canonical graph files under `data/`. The standing order is full suite, then store reload, then run, and the reload was skipped.
**Resolution:** Both stores were reloaded (`uv run main.py --dataset attack --graph neo4j`, then `--dataset capec --graph gremlin`), and every arm was re-run. Only the second attempt is reported.
**Paper implication:** None.

## 2026-11-20 — The run used the working tree, not a commit
**Impact:** `code.dirty: true`. The smoke ran on 4f0aac6f plus the uncommitted guard, whose diff is `data/DIFFSTAT`: `utils/planner/typed.py` and its tests. That diff is this record's commit's `utils/` change, unchanged.
**Cause:** The prove-small rule: smoke first, then commit.
**Resolution:** Reproduce on the commit that adds this record.
**Paper implication:** None.

## 2026-11-20 — No seeds
**Impact:** None. There is no resampling; the model runs at temperature 0 and the comparison is per item.
**Paper implication:** None.
