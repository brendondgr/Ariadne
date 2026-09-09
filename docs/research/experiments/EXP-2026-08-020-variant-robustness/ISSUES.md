# ISSUES — EXP-2026-08-020

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


## I-1 — The Gremlin store was silently empty at first capture (resolved before Arm 0)

The first reference capture showed 22 of 120 questions extracting nothing.
`uv run main.py --dataset capec --graph verify` reported **node count 0 against
an expected 4769**, while `--graph health` reported the backend *reachable* —
the container had restarted and the in-memory TinkerGraph went with it, and a
socket that answers is all "reachable" means.

After reloading CAPEC and ATT&CK the empties fall to **9**, every one of them a
by-design negative or excluded-at-load case, and the specialist golden tests go
from 1 failed to **170 passed**. No number in this experiment was taken against
the empty store.

**Carried forward:** liveness must be a content probe, and `--graph verify` is
the check, not `--graph health`.

## I-2 — Exact-name lookup is not missing; source selection is wrong

The plan for this work assumed exact-name resolution was unimplemented, because
`What are the mitigations for "Software Extensions"?` returns nothing. That
assumption is **wrong** and is corrected here before it can shape a fix.

`What is Software Extensions?` **resolves to T1176 today**, through a real
name-regex query. The mitigation phrasing fails for a different reason: it is
routed to **CAPEC**, which does not contain that entity.

Measured directly from `_match_card`:

| source | `id_hits` | `gloss_hits` | matched tokens |
|---|---|---|---|
| attack | **2** | 0 | `mitigation`, `software` |
| capec | 1 | **1** | `mitigation`, `software` |

Both matched two tokens, so `_select_sources` sees a **tie** and resolves it
with `max(live, key=lambda ds: (len(live[ds]), ds))`, which awards ties to the
alphabetically **later** dataset name. `capec` beats `attack` on the letter.

**The information needed to break that tie correctly was already computed and
then discarded.** `_match_card` separates an `id_hits` match — the token names a
real node label or relationship type — from a `gloss_hits` match, where the
token appears only in the card's prose description. ATT&CK matched `software`
against its actual `Software` label; CAPEC matched it inside a sentence.
`_select_sources` collapses both into one token set and counts them.

**Two subsystems read one word differently, and that is the deeper cause.** The
name extractor correctly lifts `Software Extensions` as an entity *name*. The
router simultaneously counts `software` as evidence for the *`Software` label*.
Any entity whose name contains a schema word inherits this.

This is the same species as the Q21 defect — routing decided by an alphabetical
tiebreak — in a different function. Fix deferred to Arm 2 so that Arm 0 measures
the shipped system.

## I-3 — Seeds were not recorded, and none apply (2026-09-09)

**Impact:** `seeds: []`. No number depends on a seed: the pipeline under test
runs with every LLM seam off and is byte-reproducible (the reference was
captured twice and matched), and the variant bank was authored by Sonnet in a
single unseeded pass whose output is frozen in `variants.json` and hashed in
POINTERS. Re-authoring would produce different variants; re-scoring the frozen
bank reproduces every arm.
**Resolution:** recorded. Nothing to fix.

## I-4 — The arms ran at different commits; the manifest can name one (2026-09-09)

**Impact:** `code.commit` now names `0ae78c1` (introduces `scored_arm0.json`,
the primary metric). Later arms ran at later trees: Arms 1–2 `2b48a91`, Arm 3
`a65bcd9`, Arm 4 `0dc748c`, Arm 5 `538d0c0`, Step 6 `f6893c8` / `446bc45` /
`b8c3b99`, Arm 6 `9f02dc6` (RESULTS A-1). `date_completed` corrected
2026-08-29 → 2026-08-31.
**Cause:** the experiment was a running log over three days and the manifest was
filled at Arm 0.
**Resolution:** per-arm commits recorded here and in POINTERS; the manifest
field carries the primary metric's commit.

## I-5 — `wall_clock_hours: 1.6` covers Arm 0 only (2026-09-09)

**Impact:** the field was recorded after Arm 0 and never revised. Elapsed time
for the other six arms and the Step 6 sweeps is not recoverable (artifact
mtimes span 2026-08-29 16:00–16:32, 2026-08-30 23:57 – 2026-08-31 00:13 and
2026-08-31 11:39, but authoring and idle time between them are unknown).
**Resolution:** left as recorded; read it as Arm 0's cost.
