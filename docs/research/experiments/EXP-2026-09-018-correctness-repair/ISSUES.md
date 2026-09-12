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

## I-3 — Step 1's first regression run overwrote the reference it was measured against

**Impact:** none on any number. Every Step 1 figure was re-derived after the
reference was rebuilt, and the rebuilt reference reproduces all 1,144 committed
digests exactly.

**Cause:** the Step 1 model-free regression re-ran the four arms into the same
`--root` the Step 0 reference occupies, so the "before" capture was replaced by
the "after" one. The diff then compared each capture against the committed
`reference.json` digests and reported the right answer by luck: the digests were
already committed, so the comparison survived the loss of the files behind them.

**Caught by:** the pre-commit research-record hook, as four
`pointer-hash-mismatch` findings against `data/POINTERS.md`. The hashes in that
file were the only thing that noticed, which is the case for hashing raw output
at all.

**Resolution:** the repaired capture moved to `repair-after-step1-*`; the
reference re-created by stashing the repair and re-running the four arms at
`e09c2571`; `capture.py --verify` confirms 284/284, 284/284, 288/288 and 288/288
reproduce. `capture.py` now takes `--after <prefix>` and **refuses** to diff the
reference prefix against itself, so the same mistake fails loudly. Every later
step writes to its own `repair-after-step<n>-*` prefix.

**Paper implication:** none. It is recorded because the reference's ability to
regenerate is itself a result worth having — the model-free arms are
byte-reproducible from a clean checkout, which is what makes them usable as a
control at all.

## I-4 — Running the test suite rebuilds the canonical artifacts and staleness-locks the live stores

**Impact:** none on any number. It cost two aborted variant captures.

**Cause:** part of `utils/kg_builder/tests` writes into the real `data/` tree
rather than a temporary one, rebuilding `data/graphs/<dataset>/canonical`. The
rebuild is deterministic — `nodes.jsonl` and `relationships.jsonl` compare
identical to the backup every time — but the manifest's hash changes, and
`utils.graph_loader.preflight` compares the *runtime* manifest against it. So
after any full test run, `scripts/variant_harness.py` aborts with
`PreflightError: Stale runtime manifest`, for both datasets in turn.

**Resolution:** not fixed here; it is a test-isolation defect outside this
experiment's scope. The working rule for the remaining steps is to reload both
stores before any harness capture that follows a test run:
`uv run main.py --dataset attack --graph neo4j` and
`uv run main.py --dataset capec --graph gremlin`.

**Paper implication:** none. Worth noting that the preflight did its job — it
refused to measure against a store it could not verify, which is the opposite of
the silent-empty-store failure in `I-2`.

## I-5 — The scope line asserted a restriction the evidence could not carry

**Impact:** the first judged pass of Step 5 is discarded and re-run. Its numbers
appear nowhere except as the before column of the fix's own table.

**Cause:** Step 4's enumeration claim appended ", restricted to <property>
<value>" whenever a filter slot was bound, without checking that the filter had
been applied. On the frozen evidence — retrieved before the filter push-down
existed — it had not, so the claim stated a restriction that was simply false.
The grader recorded 2 `fabricated_mapping` flags against a pre-repair 0, and
flagged statements rose from 36 to 202 beyond the `Q48` boilerplate trio.

**Resolution:** the scope line is emitted only when the property appears in the
executed query. A related neighbour carries no properties, so a neighbour-side
filter can never be verified from the cited records; the warrant is the query.
The test is one-way — a property absent from the query cannot have been filtered
on — so it can withhold a true scope line but never assert a false one. 0 scope
lines on the frozen evidence, 41 on the live post-Step-4b run. Re-graded in both
positions: `fabricated_mapping` back to 0, flagged statements 494 against a
pre-repair 484.

**Paper implication:** none for the figures, but the kill gate's value is worth
stating. It was pre-registered before any number was seen, it fired on the one
thing that mattered, and it cost three hours of re-grading — which is what a
gate is for.

## I-6 — The judge's per-answer noise is twenty times its reported repeatability

**Impact:** bounds every tier-level reading in this experiment, including
Step 6's.

**Cause:** not a defect, a measurement. Of the 258 answers whose claims did not
change between the two frozen compositions — identical text, same judge, same
sitting — **169 received a different score**, with a paired per-answer SD of
**0.1424**. `EXP-2026-09-012`'s 0.0066 is the repeatability of a *mean*; this is
the repeatability of an *answer*, and the two are not the same quantity.

**Consequence:** a tier of 50 has a standard error near 0.020, so a tier
difference under roughly 0.06 is indistinguishable from the grader. D4 moved
−0.0591 in Step 5 with 53 of its 55 answers unchanged; that is noise and is
reported as noise.

**Resolution:** not resolved and not resolvable by this experiment. Recorded so
that `H1`'s +0.10 threshold on 56 questions is read as about five standard
errors rather than as a bare number, and so that no smaller per-tier movement is
claimed in Step 6.

## I-9 — A stash-and-checkout cycle silently reverted committed source

**Impact:** none on any figure. Caught before any run was scored.

**Cause:** the Step 6 re-run needed the reference commit checked out and back,
and the working tree was carried across on `git stash`. The pop conflicted, and
resolving the conflict restored `verifier.py`, `canonical.py` and two test files
to a state *older than the commit they had already been committed in*
(`5d8833c1`). The tree compiled and looked right; the absence claim's facet
check and its per-relation test were simply gone.

**Found by:** the test suite, on a single assertion about the enumeration's
scope line. Nothing else would have caught it, and the next nine-hour grading
run would have measured a build missing three of the four fixes it was meant to
verify.

**Resolution:** every source file this experiment touches was diffed against
`5d8833c1` and the three that had regressed were restored from it; the two
changes made *after* that commit were re-applied on top. A file-by-file
comparison against the last commit that touched it is now part of preparing a
run, not something to notice afterwards.

**Paper implication:** none, but it is the second time in this experiment that a
check written for one purpose caught something else entirely — the pre-commit
hash gate caught the reference being overwritten (`I-3`), and the unit tests
caught this.

## I-10 — The narrative omitted the answer it had already composed

**Impact:** part of the `capec` slice's fall in Step 6, and not measured
separately before the fix.

**Cause:** `_narrative` assembled prose from `fact` and `enumeration` claims and
ignored `absence` ones. So "what prerequisites does CAPEC-689 require" produced
the claim *"capec:category:689 has no prerequisites"* and a narrative that
talked about the category's members instead. The structured claim carried the
answer; the sentence a reader sees did not.

The phrasing was also wrong: rendering the identifier literally gave "has no
**has prerequisite**".

**Resolution:** an absence claim now **leads** the narrative, because it is the
answer and everything else is context about the anchor. `_relation_noun` strips
the verb the sentence already carries and pluralises, falling back to the
source's own identifier where no clean noun exists — `MAPS_TO` and `MEMBER_OF`
end in a preposition and `CanAlsoBe` is not a noun phrase, and forcing them gave
"no tos", "no member ofs" and "no canalsobes".
