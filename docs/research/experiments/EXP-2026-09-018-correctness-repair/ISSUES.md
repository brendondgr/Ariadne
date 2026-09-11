# ISSUES — EXP-2026-09-018

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

## I-1 — The pre-repair reference is not byte-identical to `EXP-2026-09-005`, and the difference is facet metadata

**Impact:** none on any number, but it changes what `H6` can assert. `H6` is
written as "`deterministic` is byte-identical on both banks". Read against the
*2026-09-03* run that is already false at the pre-repair commit, so `H6` is read
against **this experiment's own Step 0 reference**, captured in the same session
as the repaired arms.

**Cause:** re-running `deterministic` over `bank-dev.json` at `cbb48502`
reproduced 224 of 284 answers byte-for-byte after stripping the clock keys
(`timing_ms`, `wall_s`). The other 60 differ only inside
`logic_flow.results[].records[].facets`: the 2026-09-03 run emits some facets
twice, once with the neighbour label `AttackObject` — the superlabel every node
carries — and once with the specific label, where the current run emits only the
specific one. Gold coverage, record counts, claims and abstentions are identical
on all 60.

**Not run-to-run noise.** Re-running `deterministic` a second time *in the same
session* reproduced 284 of 284. The arm is deterministic; what moved is between
2026-09-03 and now.

**Resolution:** the Step 0 reference is the baseline for every Step 1–4 diff and
for `H6`. `data/reference/capture.py` sorts `facets` lists before digesting, so
a facet re-ordering cannot be mistaken for a behaviour change; the unsorted
reading is recorded here so the instability is not hidden by the normalisation.

**Paper implication:** none directly, but it is a second instance of the effect
`Q46` names — an identical arm read across sessions is not an identical read —
and it is a concrete reason the paired control in Step 6 must be concurrent.

## I-2 — The first reference capture ran against an empty CAPEC store

**Impact:** the first Step 0 capture was discarded and re-run. No number from it
is reported anywhere.

**Cause:** the Gremlin container was up and healthy enough to accept
connections, and its graph held **zero vertices**. Every CAPEC sub-question
returned zero records with no error: the capture completed, wrote 284 answers,
and reported dev `deterministic` mean gold coverage of 0.3147 against the true
0.5048. The only external sign was the Gremlin server's own metrics reporting
`op.eval count=0`.

**Resolution:** `uv run main.py --dataset capec --graph gremlin` reloaded 6,374
vertices and 8,582 edges; the capture was deleted and re-run. The re-run's dev
`deterministic` mean gold coverage is 0.504786, which matches
`EXP-2026-09-005`'s saved answers exactly, and its `generic_composed`
zero-record cases fall into `EXP-2026-09-017` `A-2`'s mechanisms in exactly the
predicted counts (34 `capec`, 21 `ns`, 16 `chain`).

**Paper implication:** none. It is recorded because an empty store is
indistinguishable downstream from a system that retrieves nothing — the same
failure shape as `EXP-2026-09-016` `I-1` and `I-4` — and because every run in
this experiment must be preceded by a fixture check for that reason.
