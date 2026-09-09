# ISSUES — EXP-2026-08-017

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

## 2026-09-09 — Federated input files rebuilt after the count; original pointers no longer hold the data
**Impact:** the two federated pointers (`data/graphs/attack/canonical/nodes.jsonl`, `data/graphs/capec/canonical/nodes.jsonl`) no longer hash to the values recorded on 2026-08-24 (`sha256:1aaf5046…` / `sha256:53725a89…`). The files were rebuilt 2026-09-07 17:31; CAPEC grew from 4,769 to 6,374 nodes. No copy of the originals survives (gitignored build output). The recorded federated figure (0 rewritten) was re-verified on the rebuilt files on 2026-09-09; the merged pointer is intact and reproduces 1,083 / 189 exactly.
**Cause:** the catalogues were rebuilt by later work; this experiment's POINTERS said that a mismatch would mean exactly that.
**Resolution:** rows re-hashed to the rebuilt files; original hashes preserved in RESULTS A-1. `date_completed` also corrected 2026-08-23 → 2026-08-24 (commit 889508f).
**Paper implication:** quote the census as of 2026-08-24; the federated denominator on current data is 10,743, not 9,138.
