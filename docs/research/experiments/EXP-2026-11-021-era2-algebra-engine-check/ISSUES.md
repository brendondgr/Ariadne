# ISSUES — EXP-2026-11-021

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

## 2026-11-20 — the measured stores were reloaded mid-experiment, on purpose
**Impact:** none on the gate. The verification pair carries the differential. The measured stores
were rebuilt and reloaded once, for the storage change the operator chose (amendment 4).
**Cause:** the change alters how the stores hold values, so it needs a reload.
**Resolution:** today's answers were captured before (in a pinned worktree, on freshly reloaded
stores) and after, then diffed (`docs/evaluation/algebra-2026-11/store-fix/`). Phase F ran tree
against tree on the reloaded stores.
**Paper implication:** none. Figures quoted after this date come from the new storage.

## 2026-11-20 — the work was done by subagents and reviewed
**Impact:** none on the figures.
**Cause:** the compilers, the fixture and its expected answers, the differential and the store
fix were written by Opus 5.5 subagents. The semantic fixture's writer had not read the
compilers.
**Resolution:** each report was reviewed. Two first-draft compiler choices were sent back (expand
prefixes, exact Gremlin reach). Every figure here was re-run or re-read from the outputs.
**Paper implication:** none.

## 2026-11-20 — the H3 snapshot uses placeholder seeds
**Impact:** 8 of the 11 documented H3 differences come from steps whose anchors are filled in at
run time. The snapshot gives them one seed per graph (T1047, CAPEC-66), so some seeds have
another label than the step states.
**Cause:** a recorded variant step does not record its run-time seeds.
**Resolution:** classified as `anchor_of_another_label` under amendment 4 and reported apart from
unexplained mismatches.
**Paper implication:** none.
