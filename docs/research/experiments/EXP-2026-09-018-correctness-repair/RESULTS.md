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

## Step 3 — two-hop questions are answered as a chain (complete, 2026-09-11)

No model. `Q51`; the `chain` mechanism, 30.9% of the dev loss and the largest
single one.

Both builders resolved the shortest route from the anchor to each requested
label **independently** and unioned the results around the seed. "Which
techniques do campaign C0023's tools use" was therefore answered over the direct
`Campaign -USES-> Technique` edge. C0023 has **no** techniques on that edge and
**34** reachable through its five tools, so the answer was well-formed, cited,
and about a different question.

`chain_paths` routes between each *consecutive pair* of named labels and
concatenates. `relation_chain` does the same from the named *relationships*,
which is the only signal that can express the commonest shape in the bank —
`AttackPattern -CanAlsoBe-> AttackPattern -HAS_CONSEQUENCE-> Consequence` names
two hops and only two distinct labels, because the intermediate carries the
anchor's own label. Both refuse to return a partial route, so a chain that
cannot be resolved costs nothing and the star walk answers as before.

In Cypher the star is a genuine **fallback**, selected by a `CASE` rather than
unioned: a chained question that resolves rows must answer from them, and
unioning would keep the direct-edge records the chain exists to replace. In
Gremlin the chain legs are spent from the traversal budget first, because
cheapest-first ordering drops the two-step leg that carries the answer in favour
of one-step branches that do not.

| | reference | Step 1 | Step 2 | Step 3 |
|---|---:|---:|---:|---:|
| dev `generic_composed` mean gold coverage | 0.599039 | 0.632121 | 0.654044 | **0.667281** |
| dev zero-record (n=284) | 77 | 56 | 33 | **31** |
| holdout mean gold coverage | 0.636105 | 0.667945 | 0.688673 | **0.706696** |
| holdout zero-record (n=288) | 68 | 50 | 33 | **28** |

Step 3 alone moved 22 dev answers, 18 of them in the `chain` slice, with
coverage lost on none and nothing newly empty. Five went to perfect coverage:
`Campaign USES Software Technique` from 0.11 and 0.18, `Technique USES Software
Group` from 0.20 and 0.25, and `Technique HAS_SUBTECHNIQUE MITIGATES Mitigation`
from 0.50. The slice's mean gold coverage rises from 0.3626 to 0.4298.

### Two findings the measurement forced, both recorded rather than smoothed over

**Guessing a direction is worse than not chaining.** `relation_chain` first
broke ties towards `out`. That measured *worse than the label route alone* —
seven dev questions lost gold coverage and the dev mean fell from 0.6655 to
0.6534 — because a confidently wrong direction replaces a star branch that
sometimes caught the answer by accident. The failing questions are all reverse
asks: "which patterns are more specific cases of CAPEC-26" is inbound `ChildOf`,
and the schema cannot say so, because a self-referential relationship reaches its
own label either way. The chain now **abstains** on such a leg.

That abstention has a cost worth stating plainly. Every CAPEC nature —
`ChildOf`, `ParentOf`, `CanAlsoBe`, `CanPrecede`, `CanFollow`, `PeerOf` — is
self-referential, so the 27 dev questions whose first hop is one of them are
still unchained. **The `chain` mechanism's remaining loss is a direction problem,
not a chaining problem**, which is consistent with the blind holdout's drop being
concentrated in reverse-direction asks. It is not repaired here and belongs to
`Q51`'s follow-up.

**The gate attributed a label across a hop.** `hasLabel("Category")
.in("MEMBER_OF").out("HAS_EXECUTION_STEP")` is a correct two-leg walk; the
validator paired the *second* step with the nearest preceding `hasLabel` and
rejected the draft on the grounds that a Category has no execution step — true,
and not what that step is asking. Four dev questions had every draft refused. A
label now anchors the next step only; an unknown anchor was already handled, so
the edge type is still checked and the endpoint check is deferred to the next
`hasLabel`. The 240 adversarial probes were re-run after this and still block at
**1.0000**, 0 leaks, 0 breaches.

**No regression.** `deterministic` byte-identical on both banks.
`scripts/catalogue_regression.py`: 0 of 120 catalogue answers moved, gold recall
0.9161 unchanged. 1,170 tests pass, with the same pre-existing `ORCH_MAX_HOPS`
failure as Steps 1 and 2.

## Step 4 — the answer contract (complete, 2026-09-11)

No model. `Q52` and `Q53`; 19.1% of the dev loss between them.

The plan carries the ordered graph vocabulary, the seed ids and the limits and
nothing else, so the composer never stated the field that was asked for and no
builder filtered anything. `requested_slots` binds three things from the
question's own words against the card's declared vocabulary: the requested
property, a filter, and the relation an empty result must be reported as empty
*of*. Reading the text rather than extending the plan schema is an operator
decision of 2026-09-11 — a filled-in slot the live planner does not produce
would raise the benchmark without improving the shipped system.

**Nothing is guessed.** A property binds only when the question's words match
one declared property and no other; a filter value only when the registry has
*observed* that exact value on that property. Ambiguity is refusal, which is
Step 3's lesson applied. Over both banks the binder produces **zero wrong
filters**.

| | dev | holdout |
|---|---:|---:|
| gold filters bound correctly | 30 of 47 | 33 of 58 |
| of the misses, unanswerable as loaded (`Q54`) | 10 | 16 |
| wrong bindings | **0** | **0** |
| spurious bindings on unfiltered questions | 8 | 8 |

Six or seven of the spurious bindings on each bank are `taxonomy_name = WASC` on
a question that does ask for WASC entries; the gold encodes that in the
predicate rather than as a filter, so it is a bookkeeping disagreement, not a
wrong answer.

### H4 is met

The requested property now reaches a claim whatever shape its value is, which is
the gap the independent panel exhibited: the platforms of T1027.006 and the
contributors of T1530 were in the evidence and absent from the claims, because
the composer's attribute projection skips lists.

| requested values present in evidence, and rendered in the claims | before | after |
|---|---:|---:|
| dev, `generic_composed` | 11 of 27 | **30 of 30** |
| dev, `deterministic` | 15 of 31 | **31 of 31** |
| holdout, `generic_composed` | — | **22 of 22** |

The pre-registered threshold was 100% and it is met on both arms and both banks.
This is the claim `C-017` needed: the value no longer depends on a narrator that
had timed out on 43% of the run.

### H5 is met on one side of the system and cannot be on the other

The composer states what an enumeration was restricted to — 38 dev and 41
holdout answers carry the scope line — and the filter is pushed into the query
on the CAPEC side, where it removes out-of-filter records and loses no gold. On
the ATT&CK side it cannot be pushed at all, for a reason worth naming (`Q55`).

### Results

| | reference | Step 1 | Step 2 | Step 3 | Step 4 |
|---|---:|---:|---:|---:|---:|
| dev `generic_composed` mean gold coverage | 0.599039 | 0.632121 | 0.654044 | 0.667281 | **0.695685** |
| dev zero-record (n=284) | 77 | 56 | 33 | 31 | **31** |
| holdout `generic_composed` | 0.636105 | 0.667945 | 0.688673 | 0.706696 | **0.717691** |
| holdout zero-record (n=288) | 68 | 50 | 33 | 28 | **28** |
| dev `deterministic` mean gold coverage | 0.504786 | 0.504786 | 0.504786 | 0.504786 | **0.533190** |

Coverage is lost on **no answer** on either bank or either arm. The 240
adversarial probes block at 1.0000. `scripts/catalogue_regression.py`: 0 of 120
moved, gold recall 0.9161 unchanged. 1,296 tests pass, with the same
pre-existing `ORCH_MAX_HOPS` failure as Steps 1 to 3.

### `H6`'s byte-identity clause does not survive this step, and should not

`H6` says `deterministic` stays byte-identical. It does not: 141 of its 284 dev
answers change. **That is the repair, not a regression.** The answer contract is
a property of the shared deterministic composer, which is exactly what `C-017`
rests on, so gating it to the generic arm would have meant fixing the claim
everywhere except where the claim is made. The plan assumed the template path
would bind no slots; it reads the same question text and binds the same ones.

What is preserved, and is the right reading of the clause, is stronger than
"nothing moved": **the template arm's retrieval is untouched — record counts are
identical on all 284 and all 288** — and its composition changes only by gaining
claims, never losing coverage. The builders' filter push-down is gated on the
generic path, so no query changed for the template arm.

### Two data-layer defects this step found and did not fix

Both change the graph, so both carry a re-baseline of this experiment's
references and are decisions rather than fixes. They are filed and left open.

**`Q54` — two CAPEC properties were never parsed.** `Typical_Severity` and
`Likelihood_Of_Attack` appear 490 and 345 times in the pinned v3.9 catalogue by
this project's own discovery report, and the parser reads only XML *attributes*
plus `Description`, so neither reaches the graph. Ten dev and 16 holdout
filtered questions are unanswerable as loaded, and they are exactly the filters
the binder could not bind.

**`Q55` — Neo4j keeps four real properties and packs the rest into a string.**
`node_merge_cypher` writes `id`, `name`, `attack_id` and `stix_type`, and
serialises everything else into `properties_json`. The first filter push-down
emitted `$v IN coalesce(m.x_mitre_platforms, [])` against a store with no such
property; it matched nothing, silently, and cost 23 dev questions their whole
gold coverage. The push-down is now gated on the four native properties, which
means it refuses every Cypher filter today and will start working unchanged if
the loader is fixed.

Both were found by the regression rather than by review, which is the third time
in this experiment. The recorded-answer diff is the instrument.

## Serving capacity for Steps 5–8

Granted 2026-09-11: one endpoint, `default-model` on `:9090`, at **16
concurrent requests**. `PROTOCOL.md` records what that changes — roughly double
the wall clock for every judged step against `EXP-2026-09-016`'s two-instance
configuration, so Steps 6 and 7 are separate nights, and the `gemma4-31B`
ordering pass is dropped for want of a second healthy endpoint. The final result
will therefore rest on one grader family, which belongs in threats to validity.

## Steps 5–8

Not started. Steps 5 to 8 need the judge.
