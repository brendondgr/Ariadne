# ISSUES — EXP-2026-09-012

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

## 2026-09-09 — `code.dirty: true`: the audit script was uncommitted when its output was written
**Impact:** provenance only.
**Cause:** `code.commit` is `fe45e68` (2026-09-07 02:50).
`scripts/recompute_audit.py` and this directory were committed together in
`b3e4bf5` at 02:54:56; the two audit JSONs in `data/` are dated 02:52:40 and
02:53:59. The script has not changed since, so the committed version is the
one that ran.
**Resolution:** `dirty: true` kept, as it was true at the moment of the run.
**Paper implication:** none.

## 2026-09-09 — the 22-cell aggregation's code is not on record
**Impact:** the RESULTS table can be reproduced only under an inferred
grouping rule (RESULTS A-2), and two of its figures — 117 passes and the
`deterministic` mean SD 0.0073 — are not reproduced (115 and 0.0068).
**Cause:** `scripts/recompute_audit.py` produces the per-cell means; the
across-pass grouping and SDs were computed in-session from its JSON by code
that was never committed, and PROTOCOL's suffix rule omits the pooling of
`.c015`/`.c022rev*` and of `.bld*` that the table requires.
**Resolution:** not resolved. The recomputed values are recorded beside the
originals in the manifest (`*_recomputed_2026_09_09`) and `data/metrics.json`
holds the rule that reproduces everything else.
**Paper implication:** quote the median 0.0066 and max 0.0242, which reproduce
exactly; do not quote "117 passes" or the `deterministic` arm mean without
this caveat.

## 2026-09-09 — `seeds: []` and `n_runs: 1` are correct and mean nothing was run
No generation and no grading took place: this is a deterministic
re-aggregation of sidecars other experiments wrote. There is no seed to
record and one analysis pass.

## 2026-09-09 — two audit files in `data/`, one of which includes a contaminated cell
See RESULTS A-3: `recompute-audit.json` is canonical (218 cells);
`2026-09-07-recompute-audit.json` (219 cells) is the earlier copy kept for
the record.

## 2026-09-09 — the input tree has changed since the analysis
See RESULTS A-3: two audited cells now hold 1,704 judgments (EXP-2026-09-011's
extension), and `data/POINTERS.md` hashes the tree as of 2026-09-09, not as
read on 2026-09-07.

## 2026-09-09 — the manifest was a scaffold until the record repair
See RESULTS.md A-1 for every field filled on 2026-09-09 (old → new). The
`llm:` block was deleted; two metric keys were added.
