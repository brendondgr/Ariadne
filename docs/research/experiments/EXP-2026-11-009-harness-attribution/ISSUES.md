# ISSUES — EXP-2026-11-009

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

## 2026-11-15 — The first rerun recorded no stage timings; fixed and the three arms rerun
**Impact:** The first rerun at 3187ad51 saved no per-stage timings for `generic_planned`. The text-replace edit matched the gold-replay loop runner first, not `_run_real_pipeline`. Coverage figures were unaffected.
**Resolution:** `_run_real_pipeline` now records `run.timings`, and a test fails if it does not. All three arms were rerun back to back at the fixing commit, and the first rerun was discarded. Every rerun figure in RESULTS.md comes from the second rerun.

## 2026-11-15 — Pre-registered rule 5 misreads one kind of depth rejection; a post-hoc correction is reported beside it
**Impact:** The primary LLM downstream share is 0.162. With the correction it is 0.410. Both are reported; the primary stays the pre-registered figure.
**Cause:** Rule 5 assumed every `max_traversal_depth` rejection was an over-long chain built from the plan's own elements. 26 of the LLM losses are instead the query builder's fixed `repeat(...).times(3)` walk exceeding the plan's depth, in plans that named every authored relation.
**Resolution:** `recode_builder_walk` (labelled post-hoc, in a separate function) recodes exactly those 26. Its test checks it touches nothing else.
**Paper implication:** State the primary figure, the correction and its reason together. Never quote 0.41 alone.

## 2026-11-15 — The coder misses direction errors when authored traces under-report relations
**Impact:** The annotator found 6 `direction` errors in 40 sampled questions that the coder coded `other`, `relation` or `decomposition`.
**Cause:** Some authored resolve traces' `relationships` lists omit relations their queries use, so the orientation check had nothing to compare.
**Resolution:** Reported, not fixed. Fixing it would mean changing the coder after seeing the annotator's codes.

## 2026-11-15 — Where each step ran
**Impact:** None on the figures.
**Resolution:**
- The three reruns ran at 8b1e6e8f, the manifest's `code.commit`, on a clean tree.
- The coding, the packets, the agreement and the post-hoc correction were computed from those saved outputs. They used code committed together with these results; that code is pure and reads saved files only.

## 2026-11-16 — A-1's first attempt was stopped: the CAPEC Gremlin graph was empty
**Impact:** None on reported figures. The first A-1 attempt was stopped part-way through the LLM arm, and its folder was deleted before the rerun.
**Cause:** `ariadne-gremlin` restarted about an hour earlier with 0 vertices (an in-memory graph). Every CAPEC question would have retrieved nothing in all three arms.
**Resolution:** CAPEC was reloaded (`main.py --dataset capec --graph gremlin`, verified), and ATT&CK was reloaded into Neo4j to clear a stale-manifest warning (verified). All three arms then reran from scratch, back to back, at the same commit.
