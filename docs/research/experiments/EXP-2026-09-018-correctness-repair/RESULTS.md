# RESULTS — EXP-2026-09-018 Correctness repair

**Status: planned. No result yet.** The protocol was pre-registered on
2026-09-11 before any repair code was changed; `PROTOCOL.md` holds the six
hypotheses, their thresholds and the kill gate. This file is filled in as the
steps complete, and nothing is written here that `data/metrics.json` does not
carry.

**Disclosure, to appear in the first paragraph of the finished write-up.**
`EXP-2026-09-005` repaired the *template* arm before comparing the arms.
Everything in this experiment repairs the *generic* arm, and so widens a gap
`C-023` already reports in the generic arm's favour. `C-023`'s evidence column
is amended, not replaced. Scoring corrections (`Q44`, `Q48`) are reported apart
from capability gains.

## Step 0 — recorded, corrected, pre-registered (complete, 2026-09-11)

No model, no judge.

- **Mechanism table recorded** as `EXP-2026-09-017` `AMENDMENT A-2`, with
  `data/mechanisms.py` and `data/mechanisms.csv` in that experiment. The
  assignment is first match over six predicates and reproduces the published
  0.6569 and 0.4946 exactly. The row that matters most: on the 67 dev questions
  where no mechanism fires, the generic arm scores **0.9675**.
- **`Q47`'s audit corrected** as `EXP-2026-09-016` `AMENDMENT A-8`. The
  2026-09-10 audit divided fallback counts by the number of *files* in each
  answer directory, which also holds two or more judgment sidecars per answer.
  Over answers the rates are **0.43** (dev), **0.30** (holdout) and **0.07**
  (expansion) against a healthy reference of 0.14. "No published figure is
  affected" is withdrawn. Every one of the 227 fallbacks is a narrator read
  time-out, not the specialist-seam failure `I-4` is about.
- **`Q49` indexed; `Q50`–`Q53` filed** in `OPEN_QUESTIONS.md`.
- **Holdout state pinned.** `scripts/holdout_seal.py` records `sealed: false` —
  the holdout was spent by `holdout-spend-2026-09-05`, 1,152 judgments per arm.
  `data/holdout_seal_prerepair.json` is that state before any repaired arm
  existed, so a later holdout answer is attributable to this experiment.
- **References captured** for `deterministic` and `generic_composed` over both
  banks at `cbb48502`, summarised in `data/reference/reference.json`.

| capture | n | mean gold coverage | zero-record |
|---|---:|---:|---:|
| dev / `deterministic` | 284 | 0.504786 | 25 |
| dev / `generic_composed` | 284 | 0.599039 | 77 |
| holdout / `deterministic` | 288 | 0.539585 | 26 |
| holdout / `generic_composed` | 288 | 0.636105 | 68 |

Two checks on the capture, both passed. The dev `deterministic` mean gold
coverage of **0.504786** is exactly `EXP-2026-09-005`'s. And the 77 zero-record
`generic_composed` dev cases fall into `A-2`'s mechanisms in exactly the
predicted counts — **34 `capec`, 21 `ns`, 16 `chain`**, plus 6 in `none` — which
is the mechanism attribution reproducing on a fresh run of a *different arm*
from the one it was derived on.

Two issues are recorded rather than smoothed over: the reference is not
byte-identical to the 2026-09-03 run and the difference is facet metadata
(`ISSUES` I-1), and the first capture ran against an empty CAPEC store and was
discarded (`ISSUES` I-2).

## Step 1 — Category and View seeds resolve in their own namespace (complete, 2026-09-11)

No model. `Q50`; the `ns` mechanism, 12.6% of the dev loss.

The generic Gremlin walk built its anchor with `_gremlin_vertex_id`, which sends
every bare CAPEC number to `capec:attack-pattern:<n>`. A Category or View vertex
does not carry that id. Both walk call sites now use a `_walk_candidate_ids`
that offers all three CAPEC namespaces for a CAPEC seed while keeping the single
canonical form for everything else — swapping in `_capec_candidate_ids` alone
would have been a regression, because it passes a `CWE-<n>` seed through
untouched where the join-owner traversal needs `cwe:<n>`. The join-owner query's
seed anchor also drops its `hasLabel`, since the canonical id is unique across
labels; both drafts now declare their id binding so the pre-run gate still
checks a filter the Gremlin parser can no longer see.

**H2 is read as pre-registered and it is not met.** The threshold was "zero-record
on the 23 non-D0 Category/View anchors falls from 21 to **0**". It falls to **1**.

| | before | after |
|---|---:|---:|
| `ns` slice, zero-record (n=23) | 21 | **1** |
| dev `generic_composed` mean gold coverage | 0.599039 | **0.632121** |
| dev `generic_composed` zero-record (n=284) | 77 | **56** |
| holdout `generic_composed` mean gold coverage | 0.636105 | **0.667945** |
| holdout `generic_composed` zero-record (n=288) | 68 | **50** |

The residual case has a cause, not an excuse. `D4-HAS_MEMBER-ChildOf-CAPEC-687`
is a Category-rooted **two-hop** question: the anchor now binds, and the walk's
branches are still guarded by `AttackPattern`, so nothing fires. That is the
`chain` mechanism (`Q51`), which Step 3 repairs — and it is why the plan orders
Step 3 after Step 1.

**No regression.** `deterministic` is byte-identical on both banks (0 of 284 and
0 of 288 changed). Of the 26 dev and 27 holdout `generic_composed` answers that
moved, coverage was **lost on none**; 20 of the 26 dev changes are `ns` cases and
5 are the join-owner anchor. `scripts/catalogue_regression.py` over a fresh
variant capture: 0 of 120 catalogue answers moved, gold recall 0.9161 unchanged.

The reference itself regenerates. Re-running the four model-free arms from a
clean checkout at the Step 0 commit reproduces **all 1,144** committed per-case
digests, so the control these repairs are measured against is not a one-off
capture. `ISSUES` I-3 records how that was established: Step 1's first
regression run overwrote the reference directory, the pre-commit hook caught it
as a pointer-hash mismatch, and the rebuild is what proved the reproducibility.

Tests: 1,156 passed across the specialist, synthesis, planner and kg_builder
suites. The one failure, `test_event_order_matches_streaming_contract`, fails
identically on the pre-repair tree and passes under `ORCH_MAX_HOPS=5`; the
committed `.env` pins it to 1. Pre-existing and unrelated.

## Step 2 — the five declared CAPEC edges are allowlisted (complete, 2026-09-11)

No model. `Q45`; the `capec` mechanism, 19.9% of the dev loss.

Five relationships the canonical snapshot carries — `HAS_PREREQUISITE`,
`HAS_INDICATOR`, `HAS_EXAMPLE`, `REQUIRES_RESOURCE`, `HAS_ALTERNATE_TERM` —
were declared in the CAPEC card's relationship types and absent from its
`allowed_edge_patterns`. The pre-run gate treats a relationship with no pattern
as forbidden, which is the right default, so it rejected every draft touching
them before it ran. ATT&CK's allowlist is empty and therefore unconstrained: the
more completely specified catalogue was the one being punished.

Each pattern is the endpoint pair the snapshot actually carries, not one
inferred from the edge's name. Two new tests keep the list from falling behind
again: every declared relationship type must have a non-empty pattern, and every
endpoint pair observed in `data/graphs/capec/canonical/relationships.jsonl` must
be allowlisted. The containment is deliberately one-way. Observed must be a
subset of allowed, which is the safety property; the reverse is not asserted,
because `HAS_REFERENCE` allowlists Category and View sources this snapshot does
not happen to carry and `ParentOf` is declared with zero observations, so
demanding equality would make a *smaller* dataset fail.

**The gate stays fail-closed and the card stays the sole permission source.**
The validator still rejects an edge with no pattern. It now also emits a
*warning* — an observation that does not change the verdict — when the schema
registry says the edge is real, so a lagging card is visible in the trace
instead of reading as an absent edge. Granting permission from the registry was
the alternative and was rejected: a gate whose permissions come from the thing
it is guarding is not a gate.

| | reference | after Step 1 | after Step 2 |
|---|---:|---:|---:|
| dev `generic_composed` mean gold coverage | 0.599039 | 0.632121 | **0.654044** |
| dev zero-record (n=284) | 77 | 56 | **33** |
| holdout mean gold coverage | 0.636105 | 0.667945 | **0.688673** |
| holdout zero-record (n=288) | 68 | 50 | **33** |

Step 2 alone changed **29** dev answers and **every one is in the `capec`
slice**. Within that slice the zero-record count falls from 34 to 11 and mean
gold coverage rises from 0.0000 to 0.1831. `H3` is about the *judged* mean and
cannot be read without the judge; it is settled in Step 6.

The 11 that still return nothing are not a residual of this defect. Four are D0
questions asking a View for a `REQUIRES_RESOURCE` edge that a View does not
have, where empty is the correct answer. The other seven are two-hop chains
(`HAS_MEMBER > HAS_EXAMPLE`, `MAPS_TO > HAS_INDICATOR` and so on), which is
`Q51` and Step 3.

**No regression.** `deterministic` byte-identical on both banks. Coverage lost
on no answer. The 240 adversarial gate probes still block at **1.0000** with 0
leaks and 0 breaches across both sources (183 ATT&CK, 57 CAPEC), re-run because
a gate changed. `scripts/catalogue_regression.py`: 0 of 120 catalogue answers
moved, gold recall 0.9161 unchanged. 1,274 tests pass, with the same
pre-existing `ORCH_MAX_HOPS` failure as Step 1.

One thing was caught by the regression rather than by review. Adding a
`warnings` key to every gate trace rewrote all 284 deterministic answers even
though nothing about their behaviour changed, and the diff reported 282 of 284
moved. The key is now emitted only when non-empty. An always-present new trace
field turns the recorded-answer regression into noise, which is the check that
would have caught a real regression.

## Serving capacity for Steps 5–8

Granted 2026-09-11: one endpoint, `default-model` on `:9090`, at **16
concurrent requests**. `PROTOCOL.md` records what that changes — roughly double
the wall clock for every judged step against `EXP-2026-09-016`'s two-instance
configuration, so Steps 6 and 7 are separate nights, and the `gemma4-31B`
ordering pass is dropped for want of a second healthy endpoint. The final result
will therefore rest on one grader family, which belongs in threats to validity.

## Steps 3–8

Not started.
