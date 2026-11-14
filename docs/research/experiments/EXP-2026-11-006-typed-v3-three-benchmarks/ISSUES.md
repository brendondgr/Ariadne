# ISSUES — EXP-2026-11-006

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

## 2026-11-14 — Shared runner reused from EXP-2026-11-005
**Impact:** none on either experiment.
- `utils/killtests/t2c/run.py` gains a `KILLTESTS_EXPERIMENT=exp006` mode: parts A/B/C, the EXP-006
  arms, and v3 cards. The default mode is EXP-2026-11-005's, unchanged in behaviour; that run is
  at tag `killtests-exp005-run`.
- `t2c/load.py` writes v3 cards to `cards-v3/`, so EXP-2026-11-005's cards stay as run.
**Paper implication:** none.

## 2026-11-14 — Verification stores recreated
**Impact:** none. The verification containers (`killtests-verify-*`, ports 5480/6480) were
removed after EXP-2026-11-005 and recreated from the same images for v3's verification. The
fixture and terrorist_attack were reloaded, and node counts matched (1,629).
