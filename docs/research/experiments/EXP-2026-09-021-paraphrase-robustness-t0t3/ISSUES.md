# ISSUES — EXP-2026-09-021

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

## 2026-09-15 — I-1 The loader's staleness check refused the run again (I-21 recurrence)

**Impact:** none on any figure. The run was blocked for ~10 minutes, not
corrupted; the reference capture that follows the repair is byte-reproducible.

**Cause:** `EXP-2026-09-018` `I-21`, unfixed. `utils/graph_loader/verify.py`
compares the `canonical_manifest_hash` recorded at load time against a fresh
`file_sha256` of `canonical/manifest.json`, and that file embeds a
`build_timestamp`. Another session rebuilt the canonical artifacts at
2026-09-15T04:37:58Z, roughly 13 seconds after the stores were loaded from the
04:32 build, so the file hash moved and the preflight refused to start with
"Stale runtime manifest for neo4j: canonical hash mismatch."

**Resolution:** proved the data unchanged, then re-stamped. The evidence is
stronger than `I-21`'s, because the manifest that was loaded was recoverable:

1. the recorded hash matches `_backups/canonical-20260915T043745Z/manifest.json`
   (attack) and `_backups/canonical-20260915T043747Z/manifest.json` (capec), and
   diffing each against the current canonical manifest gives **exactly one
   differing key, `build_timestamp`** — every data digest is byte-identical;
2. live counts equal the manifest's `expected_counts` on both stores, per label:
   attack 4,369 / 27,669 and capec 6,374 / 8,582, **zero** label mismatches.

`scripts/revalidate_load_manifest.py` performs both checks and re-stamps only
when both hold, recording old hash, new hash and evidence in a `revalidations`
entry on the load manifest. It exits non-zero rather than re-stamping when the
backup for the recorded hash is missing or when anything beyond `build_timestamp`
differs — so it cannot paper over a real change. `uv run main.py --dataset attack
--graph verify` passes after it.

**Paper implication:** none. But `I-21`'s underlying defect is still open and has
now cost two runs: the check should hash the canonical manifest's `hashes` block
rather than the file that contains a timestamp. Filed again rather than fixed
here, because altering a loader safety gate is not in this experiment's scope —
the script makes the workaround fail-closed and auditable in the meantime.

## 2026-09-15 — I-2 `make validate-research` carries three pre-existing pointer mismatches

**Impact:** none on this experiment's figures. `make index` is current and this
experiment validates; the three errors belong to other, completed experiments.

**Cause:** `EXP-2026-07-011` pins hashes of `utils/specialists/cypher/builder.py`
and `utils/specialists/gremlin/builder.py`, both of which have changed since (the
`EXP-2026-09-018` repair, among others). `EXP-2026-09-012` pins a directory hash
of `docs/evaluation/experiments`, which grows every time any run commits its
judgment sidecars.

**Resolution:** not resolved here, deliberately. Both are `complete`
experiments, and D-008's append-only rule says a completed experiment is
corrected by amendment in its own folder, not by a silent re-hash from an
unrelated one. Recorded so that a validator failure seen during this experiment
is not mistaken for something this experiment broke. Neither artifact was touched
by this work.

**Paper implication:** none, but the pointer rows in those two experiments are
stale and should be amended by whoever next works in them.
