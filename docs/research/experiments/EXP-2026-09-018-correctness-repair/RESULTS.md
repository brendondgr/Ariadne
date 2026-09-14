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

## Step 4b — the two data-layer defects, repaired (complete, 2026-09-11)

No model. `Q54` and `Q55`, both found by Step 4's regression. Done now, on the
operator's decision of 2026-09-11, because the cost while the steps are
model-free is a re-baseline; after the judged runs it would be a re-judge.

**`Q54`.** `normalize_attack_pattern` read an attack pattern's XML *attributes*
plus its `Description` child. `Typical_Severity` and `Likelihood_Of_Attack` are
child elements, so neither reached the graph. They are now read the same way
`Description` is: **488** severity and **344** likelihood values on
AttackPattern nodes, against 490 and 345 in the source, the difference being
patterns retired at load.

**`Q55`.** The Neo4j loader wrote four real node properties and packed the rest
into a `properties_json` string. It now also writes every scalar and every
homogeneous list of scalars as a real property, which Neo4j holds natively;
`properties_json` is still written complete, so every existing reader is
untouched. The rule lives in one place and the schema registry derives its
`is_native_property` from it, with a contract test asserting the two agree —
a builder must never emit a `WHERE` clause a store cannot answer, because that
matches nothing rather than erroring.

With the store able to answer, the Cypher filter push-down is enabled. The
check for the M1022 question is exact: 43 techniques mitigated by M1022 carry
the Windows platform, and the bank's gold for that question is 43 ids.

### The control had to be re-taken, and both are kept

A data change means the Step 0 reference no longer differs from the repaired
arms in *code* alone. A second pre-repair capture was taken at `e09c2571`
against the fixed data, so:

- against the **Step 0 reference** is the programme's whole effect, code and
  data together;
- against the **data-matched control** is the code alone.

| | Step 0 baseline | data-matched control | after Step 4b |
|---|---:|---:|---:|
| dev `generic_composed` mean gold coverage | 0.599039 | 0.626244 | **0.700967** |
| dev `deterministic` | 0.504786 | 0.510067 | **0.538471** |
| holdout `generic_composed` | 0.636105 | 0.658569 | **0.719427** |
| holdout `deterministic` | 0.539585 | 0.541321 | **0.552317** |

So the data fixes alone are worth **+0.027** on the development half and
**+0.022** on the holdout for `generic_composed`, and the code changes carry the
rest. Zero-record questions end at 31 of 284 and 28 of 288, from 77 and 68.
**Coverage is lost on no answer**, against either control, on either bank, on
either arm.

### One regression the step produced, and the rule that fixed it

Enabling the push-down made more properties bindable, and one bound wrongly:
"Which campaigns use the techniques mitigated by the **Boot Integrity**
mitigation, M1046?" bound `x_mitre_impact_type = Integrity`, because `Integrity`
is an observed value of that property and also half the mitigation's *name*. The
question's gold coverage halved.

A filter value is introduced by an ordinary word — "apply **to** Windows",
"**at the** Meta abstraction level", "rated Medium likelihood". A value sitting
immediately beside another capitalised word is part of a name. With that rule
the binder improves on both counts at once:

| | before Step 4b | after |
|---|---|---|
| dev gold filters bound | 30 of 47 | **37 of 47** |
| holdout gold filters bound | 33 of 58 | **40 of 58** |
| wrong bindings, either bank | 0 | **0** |
| spurious bindings, each bank | 8 | **4** |

Most of the remaining gain came from a second rule the fixed data made
possible: `Medium` is a value of both `Typical_Severity` and
`Likelihood_Of_Attack`, so the value alone is ambiguous and the binder refused
it. The question does say which — "rated Medium likelihood", "with a typical
severity of Medium" — so the property's own name breaks the tie. That is the
same declared vocabulary the property slot is bound from, not a second guess.

**No regression.** 240 adversarial probes block at 1.0000, 0 leaks, 0 breaches.
`scripts/catalogue_regression.py`: 0 of 120 moved, gold recall 0.9161 unchanged.
1,416 tests pass, with the same pre-existing `ORCH_MAX_HOPS` failure.
`EXP-2026-08-017`'s federation-isolation count was re-run because its pinned
CAPEC node file was rebuilt, and is unchanged at 0 rewritten nodes with 1,083
public ids promoted.

## Step 5 — the frozen-evidence comparison (complete, 2026-09-11)

The judge, `default-model` on `:9090` probed as `qwen38-27B-v2`, 16 workers.
One sitting, both compositions, each answer in both counterbalanced positions.

Every other step changes what is *retrieved*, so a judged difference could
always be retrieval. This one holds the evidence fixed: each saved
`EXP-2026-09-005` generic answer's `FederatedEvidence` is rebuilt from its own
`logic_flow.results` verbatim and recomposed. The same rows, two composers.

### The drift control passes, and the instrument reproduces itself

| | |
|---|---:|
| unchanged answers graded in both sets | 258 |
| paired mean difference | **+0.0020** |
| grader-repeatability SD (`EXP-2026-09-012`) | 0.0066 |

The re-graded original's **position-1 mean is 0.6569** — the published
`EXP-2026-09-005` figure to four decimal places, from a different session eight
days later. The two-position mean is 0.6588.

### Result

| | before | after | paired |
|---|---:|---:|---:|
| all 284 answers | 0.6588 | 0.6794 | **+0.0206** |
| the 26 whose claims changed | 0.6933 | **0.8981** | **+0.2048** |
| D1, property questions (19 of 35 changed) | 0.7057 | 0.8293 | **+0.1236** |
| D0 (3 changed) | 0.7007 | 0.8132 | +0.1125 |

**H4 is met on the judge as well as on the construction check.** The
deterministic half, on this same frozen evidence: requested values present in
the evidence and rendered in the claims go from **6 of 19 to 19 of 19**.

**H5 is not testable here and moves to Step 6.** The frozen evidence was
retrieved before the filter push-down existed, so no query carries a filter, so
the composer correctly states no restriction and **no D5 answer changed**. D5's
+0.0158 is 47 unchanged answers and means nothing. This is the honest reading:
the composer half of `H5` cannot be isolated on evidence that was never filtered.

### The kill gate tripped, and the defect was mine

The first judged pass recorded **2 `fabricated_mapping` flags against a
pre-repair 0** — the first non-zero this project has produced — and flagged
statements rose from 36 to 202 beyond the `Q48` boilerplate trio, which stayed
flat at 448 and 441.

One defect explained both. The enumeration claim stated *"restricted to
taxonomy name WASC"* over records that were not WASC, because the scope line was
emitted from the **bound filter** rather than from what the query had actually
done. On frozen evidence the filter was never applied, so the claim was simply
false, and the grader was right to call it fabricated.

A claim's warrant here is the **query**, not the records: a related neighbour
carries no properties, so a neighbour-side filter can never be verified from the
cited evidence. The scope line is now emitted only when the property appears in
the executed query — a necessary condition for the filter to have run, so its
absence is proof the restriction did not happen. One-way and conservative: it
can withhold a true scope line, never assert a false one.

Verified both ways: **0** scope lines on the frozen pre-push-down evidence,
**41** on the live post-Step-4b run where the filter is in the query. The
recomposed set was re-graded in both positions after the fix.

| | first pass | after the fix |
|---|---:|---:|
| `fabricated_mapping` | 2 | **0** |
| flagged statements | 643 | **494** (pre-repair 484) |
| answers whose claims changed | 62 | 26 |

The kill gate did its job. It was pre-registered before any number was seen, it
fired on the one thing that mattered, and the fix was to stop making a claim the
evidence could not carry rather than to soften the gate.

### What the control also measured, and it is a constraint on Step 6

**169 of the 258 unchanged answers moved in score.** Identical text, same judge,
same session, and a per-answer paired SD of **0.1424**. The aggregate is stable —
the mean of those 258 differences is +0.0020 — but the per-answer noise is
twenty times the repeatability figure `EXP-2026-09-012` reports, because that
figure is about a *mean* and this is about an *answer*.

The consequence is arithmetic. A tier of 50 answers has a standard error of
about 0.020, so a tier difference below roughly 0.06 is not distinguishable from
the judge. **D4's −0.0591 is exactly that**: 53 of its 55 answers were
unchanged, and the tier moved anyway. It is not a regression and must not be
read as one.

For Step 6 this bounds what can be claimed. `H1` asks for +0.10 on the 56-question
chain slice, which is about five standard errors and comfortably detectable.
Anything smaller than 0.06 on a single tier is not.

## Serving capacity for Steps 5–8

Granted 2026-09-11: one endpoint, `default-model` on `:9090`, at **16
concurrent requests**. `PROTOCOL.md` records what that changes — roughly double
the wall clock for every judged step against `EXP-2026-09-016`'s two-instance
configuration, so Steps 6 and 7 are separate nights, and the `gemma4-31B`
ordering pass is dropped for want of a second healthy endpoint. The final result
will therefore rest on one grader family, which belongs in threats to validity.

## Step 6 — the paired control (complete, 2026-09-13)

Every question answered twice, once on the pre-repair reference tree and once on
the shipped tree, in the same session, graded in both counterbalanced positions
and averaged per question. `scripts/paired_control_score.py --verify` reproduces
it. Read from `data/` and recomputed from the judgment sidecars.

| arm | reference | repaired | paired gain |
|---|---:|---:|---:|
| `deterministic` | 0.5011 | 0.6098 | **+0.1087** |
| `generic_composed` | 0.6563 | **0.9209** | **+0.2646** |
| `generic` | 0.7195 | **0.9247** | **+0.2052** |

Both halves ran on one tree per side and the reference half reproduces the
recorded Step 0 capture, so the gain is the repair and not the tree moving
underneath the comparison.

## Step 7 — the sealed fresh set (complete, 2026-09-13)

282 questions at seed 10140325, authored blind against briefs, sealed before use
(`scripts/fresh_seal.py --self-test` refuses a spent bank, and did refuse the
holdout on 3,456 judgments). Never asked, never graded. Both positions.

| arm | correctness | SE | `fabricated_mapping` |
|---|---:|---:|---:|
| `deterministic` | 0.5525 | 0.0197 | **0** |
| `generic_composed` | **0.9005** | 0.0102 | **0** |
| `generic` | **0.8991** | 0.0103 | **0** |

The two repaired arms are separated by **-0.0014**, which is inside the grader's
noise. On questions nothing here had ever seen, the language model in the
narrator seam buys nothing measurable over the model-free composition.

**The gaps were the hard cases, and closing them cost the LLM arm.** Eight
answers failed to grade on the first pass; all eight were among the largest in
the bank. Recovering them moved `generic` from 0.9043 down to **0.8991** and
`generic_composed` from 0.9037 to **0.9005**. A mean over the cases that
graded is a mean over the easy ones, and it flatters the slower arm by about
0.005. This is the third time tonight the same size-correlated loss appeared.

## Step 8 — the holdout regression (complete, 2026-09-14)

**Regression evidence only.** The holdout was spent by `holdout-spend-2026-09-05`
at 1,152 judgments per arm. These questions have been seen; this is a check that
the repair did not break the arms on a bank they were previously measured on,
and it must never be quoted as a capability figure. Position 1, 288 questions,
`data/holdout_regression.json`.

| arm | correctness | SE | `fabricated_mapping` |
|---|---:|---:|---:|
| `deterministic` | 0.5443 | 0.0193 | 3 |
| `generic_composed` | 0.8987 | 0.0104 | **0** |
| `generic` | 0.9014 | 0.0100 | **0** |

Paired: `generic` − `generic_composed` = **+0.0026** (SE 0.0044, not separable);
`generic_composed` − `deterministic` = **+0.3545** (SE 0.0204).

**The two banks agree.** The sealed fresh set and the spent holdout land within
0.003 of each other on both repaired arms — disjoint question banks, graded on
different nights. The repair generalises rather than fitting the fresh set.

**One asymmetry belongs in the record.** `deterministic` still produces 3
`fabricated_mapping` flags here where both generic arms produce none. The repair
removed the fabrication mode from the arms it targeted and did not remove it from
the template arm, which is consistent with the disclosure at the head of this
file: this experiment repairs the generic arm.

### What the judging cost, and what it nearly cost

All 26 ungraded `generic` cases sat **exactly at the 26,248-character prompt
cap** (~8,749 tokens) against a graded median of 13,416. They were slow, not
stuck, and they closed once the timeout was raised. Reporting 262 of 288 would
have repeated the Step 7 bias at four times the size.

## What the narrator seam costs (complete, 2026-09-14)

Single-user latency, one worker, the first 20 `bank-dev` questions, at the
budget the arm ships with and at the old 120 s default. `data/latency.json`.

| budget | s / answer | fallbacks |
|---|---:|---:|
| 120 s | 66.82 | 3 |
| 600 s | 67.95 | **0** |

Raising the budget costs **1.13 s per answer and removes every fallback**. The
timeout binds only on answers that were already slow, so the mean barely moves.
All three that fell back at 120 s are D6 cross-catalogue questions — the largest
answers in the bank. A budget never loses a random sample; it loses the biggest
answers, which is the same size-correlated failure that cost Step 7 its eight
gaps and the regression its twenty-six.

**Against the model-free arm, measured the same way: 0.05 s per answer.** The
narrator seam therefore costs roughly **1,340x in single-user wall time** for a
fresh-set difference of **-0.0014**, which is inside the grader's noise.

A withdrawal belongs here. `data/latency.json` previously recorded this ratio as
"roughly 90x". That divided generic's *per-answer* 66.82 s by generic_composed's
*total* for 20 questions — a unit mismatch that understated the cost about
fifteen-fold. The comparator has been re-measured rather than re-derived (1.0 s
for 20 questions at one worker) and corroborated by `EXP-2026-09-019`'s
independent 1-worker reading of the same configuration, 0.07 s mean. The old
string is kept in `comparison_withdrawn`. It never reached prose.

## T6 — entity fidelity under rewording (complete, 2026-09-13)

A different instrument from the judged bank: it asks whether an answer is about
the entity that was asked for at all, which a correctness score can hide behind
partial credit. `data/t6_rates.json`, n = 579 on the shipped tree.

| | shipped | best of 7 reference arms | worst |
|---|---:|---:|---:|
| `wrong_entity` | **0.0950** | 0.0930 | 0.1416 |
| `catalogue_dump` | **0.0915** | 0.0715 | 0.1760 |

Passes the plan's bar of "not above the reference": `wrong_entity` is the lowest
of the seven arm captures and `catalogue_dump` is below four of them. **Not a
paired comparison** — the variant captures differ in n — so it is a bound, not a
measured gain.
