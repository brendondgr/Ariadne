# ISSUES — EXP-2026-09-027

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

## 2026-09-15 — the generator first wrote the built cards, which completed experiments pin by hash
**Impact:** none on the numbers; `data/source_cards/attack.json` and `capec.json` were restored
byte-for-byte to the hashes EXP-2026-09-022 records before any arm ran.
**Cause:** the first version of `scripts/generate_relation_lexicon.py` updated the built card as
well as the overlay. **Resolution:** the script now writes only the overlay and the sidecar the
router reads; the built card is never touched.
**Paper implication:** none.

## 2026-09-15 — two CAPEC relationships have no generated words
**Impact:** HAS_EXECUTION_STEP and REQUIRES_RESOURCE carry no paraphrases.
**Cause:** the reasoning model spent its whole output budget thinking and returned nothing, at
16384 and again at 32768 tokens. **Resolution:** recorded as `ungenerated`; not hand-written.
**Paper implication:** the generated lexicon is what the model gave, gaps included.

## 2026-09-16 — run from the working tree, committed without change
**Impact:** `dirty: true`. **Cause:** the arm ran before the record commit. **Resolution:** commit
`311eb446` holds the code that ran. **Paper implication:** none.
