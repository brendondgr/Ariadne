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

## I-11 — The join key has one declared direction and a question can run either way along it

**Impact:** 21 of the 27 federated development questions return **zero
records** — 24% of the repaired arm's remaining judged loss, and the largest
single untouched block.

**Cause:** `dependency_map` decides producer and consumer from the join key's
declared endpoints. `attack-technique-id` says CAPEC *produces* technique ids
(it walks `MAPS_TO` to reach them) and ATT&CK *consumes* them (its records carry
`attack_id` natively). That is correct for "which techniques does CAPEC-66 map
to" and exactly backwards for "which CAPEC patterns correspond to T1555, and
which CWE weaknesses do those exploit", where ATT&CK holds the seed and CAPEC is
the only store that can answer.

So the first hop is routed to ATT&CK and asks for `MAPS_TO` and `AttackPattern`,
neither of which ATT&CK models; it returns nothing. The second hop is then told
its producer yielded no join values and is **skipped without running**. Both
hops return zero and the question scores near zero.

**Two of three parts resolved.** A sub-question that names its own identifiers
is no longer treated as a consumer (`carries_its_own_seeds`), and a consumer
whose producer yields nothing now takes seeds from the *request* — the analyst's
own words, verbatim, never invented (`request_seeds`). The CAPEC hop is now
seeded with `T1555` where it previously received nothing.

**The third part is open.** Seeded with an ATT&CK technique id, the CAPEC
builder anchors on it as though it were a CAPEC identifier
(`hasLabel("AttackPattern").has("id", within(ids))`) and matches nothing. It
needs to enter through the mapping edge instead — from the `TaxonomyEntry`
carrying that id, backwards along `MAPS_TO` to the patterns, and on to the
second leg. `_generic_bridge` already reverses when the *plan* names `MAPS_TO`
and `TaxonomyEntry`; here the plan does not, because it assumed the first hop
would supply CAPEC ids. This is a builder change of similar size to the chained
walk and is the highest-value item remaining.

**Paper implication:** the join key's direction is a modelling choice that has
been load-bearing without being stated. Any claim about federated retrieval
should say that a declared join is directional and that the system answers along
it one way.

**Resolved, and the diagnosis above was incomplete.** The third part was never
reached, because two larger faults sat in front of it and the second one also
explains the two-step tier.

1. **Routing ignored what each store can express.** A sub-question's source came
   from the plan; nothing checked it against the card. The first hop named
   `MAPS_TO` and `AttackPattern` and went to ATT&CK, which models neither.
   `reroute_source` now sends a sub-question to the card that models the most of
   its entities, and `rerouted` drops the entities that card does not model when
   a declared join reaches them — `Technique` on a CAPEC hop is the other end of
   `attack-technique-id`, not a boundary. The test is comparative because a
   cross-catalogue hop names entities from both sides and **no** card models all
   of them.

2. **`dependency_map` is keyed by SOURCE, so two hops in one store could never
   chain.** `by_source` maps source name to sub-question, so the second CAPEC
   hop overwrote the first and the join's endpoints collapsed onto a single
   sub-question. **Every** federated question's second hop returned zero records
   for this reason, including the three that scored well — they scored on their
   first hop alone. Plan order now supplies the edge for a sub-question that says
   in its own words that it depends on the one before it (`refers_back`),
   guarded against closing a cycle with a key-declared edge.

3. **The declared direction is flipped when one side is self-anchored and the
   other is not.** A hop with nothing to start from cannot feed a hop that is
   already anchored.

4. **A same-store consumer takes the producer's own ids, not its join values** —
   and takes the ids whose LABEL it anchors on. A category hop leaves one record
   whose primary id is the category and whose 52 related entries are the
   patterns; seeding the next hop with the category sends it back where it
   started.

5. **The bridge ran whenever a join key was declared.** A plan puts its join key
   on every sub-question, so "and which CWE weaknesses do those exploit" was
   answered with the patterns' ATT&CK mappings — a different question, answered
   confidently. It is now gated on `_has_mapping_intent`, the test the CAPEC
   ladder already used.

The third part is moot: once the first hop is routed to CAPEC it enters through
`_generic_bridge`'s existing reverse branch, which was already correct.

## I-12 — The answer named identifiers the catalogue does not publish, and dropped the content that was the answer

**Impact:** the two-step tier retrieved everything it needed and still lost half
its marks; the adversarial tier's abstentions named the wrong entity.

**Cause, three parts.**

1. A CAPEC prerequisite, consequence, execution step, example, indicator or
   mitigation has no name. The normalizer fills `name` from the node's id, so a
   prerequisite arrived named `capec:attack-pattern:94:prerequisite:1` and the
   composer listed that. The answer to "what prerequisites does each of those
   require" was six opaque strings and not one prerequisite. `_related_display`
   now renders the text for a neighbour whose identifier is a synthetic path,
   and keeps the identifier for a published one (`CAPEC-94`, `T1555`, `CWE-89`).

2. Categories and views share CAPEC's published numbering — `CAPEC-513` is a
   category and `CAPEC-1000` a view — but only `capec:attack-pattern:N` was
   canonicalised. A category surfaced as `capec:category:172`, which no gold
   assertion and no analyst can match. Both id rules now cover categories and
   views; composite children are deliberately excluded, since collapsing them to
   their parent's number would make each one claim to be the pattern.

3. The taxonomy neighbour on the mapping templates carried no edge type, so the
   composer read the relation off the related entries, found none, and wrote
   "CAPEC-150 has no MAPS_TO relationships in this catalogue" one sentence before
   listing its ATT&CK mapping. 26 answers carried that contradiction.

**Paper implication:** an identifier scheme is part of the interface. A record
that is correct and cites an identifier the catalogue does not publish is not
auditable, and a node whose content is its text cannot be cited by identifier at
all.

**Resolved, in four more steps than the diagnosis above records.**

4. A **published identifier always wins** over prose. The first cut of
   `_related_display` used "has a colon" to mean synthetic, which is true of
   `capec:attack-pattern:94:prerequisite:1` and false of `WASC:27` — six
   questions asking for a WASC mapping got prose instead of the key. The test is
   the identifier's DEPTH: CAPEC composes a child as `<parent>:<kind>:<index>`,
   four segments, while everything the catalogue publishes is shallower.

5. A **cross-taxonomy entry is published as `<taxonomy>:<entry>`** —
   `WASC:27`, `OWASP Attacks:<name>` — and as `T1555` for ATT&CK, which is the
   form the join key already uses. Three normalizer paths built that neighbour
   and all three emitted the internal vertex path.

6. A node with **no description carries its content in its own properties**: a
   CAPEC consequence has only `scopes` and `impacts`, both JSON lists, so there
   was nothing for the composer to say. Identity keys are dropped and the rest
   joined — no label table, so an unfamiliar node kind still reads.

7. The **merged build shares the rule**. `promote_public_id` excluded categories,
   views and non-ATT&CK taxonomy entries on the stated grounds that the
   federated path reported them raw. Both paths were wrong together; they now
   share one helper. **The merged store must be rebuilt before the merged-arm
   counterfactual is re-run** — its committed figures predate this.

### Result

Gold recall over the ANSWER TEXT, model-free, against the concurrent control at
`46652efc` (`data/gold_text_recall.py`, `data/gold_text_recall.json`):

| tier | n | before | after |
|---|---:|---:|---:|
| D0 adversarial | 36 | 0.8056 | 1.0000 |
| D1 attribute | 35 | 0.9129 | 1.0000 |
| D2 | 40 | 0.8018 | 0.9479 |
| D3 | 44 | 0.9205 | 1.0000 |
| D4 two-step | 55 | 0.5471 | 0.9301 |
| D5 requested property | 47 | 0.9674 | 1.0000 |
| D6 cross-catalogue | 27 | 0.3773 | 1.0000 |
| **all** | **284** | **0.7721** | **0.9791** |

98 questions improved and none regressed. The deterministic control moves 59 up
and 2 down, both of which are a 558-record catalogue dump being removed that
happened to contain the gold identifier.

The holdout bank reads **0.9788** on the same measure. It was run only after the
fixes, nothing was tuned against it, and it is not a judged number.

The two tiers still short of 1.0000 are short on ORDER rather than on content.
The answer states an execution step's phase, its number and its text, and a
consequence's scopes and impacts — in property-name order rather than the
catalogue's print order. Encoding the print order would mean a per-label table of
MITRE conventions inside a composer that is deliberately schema-driven, and a
reader or a grader sees the same facts either way. A grader reading both sees
the same facts.

## I-13 — A falsy value is a value, and a list-valued property is an answer

**Impact:** every question asking what a group is also called, who contributed
to a campaign, or whether a technique is a sub-technique.

**Cause.** `_attribute_pairs` skipped list-valued properties outright, on the
recorded reasoning that "a generic listing of every list a record carries is
noise". A group's ``aliases`` is not noise; it is the answer to "what else is
this group called", and the answer instead stated the group's ``revoked`` flag
and not one of its names. Flattening then introduced the mirror defect:
``value or ""`` turns ``False`` into the empty string and an empty attribute is
dropped, so "is T1052 a sub-technique" lost the literal ``False`` that answered
it. Lists are now listed after the scalars, so nothing that fitted under the
per-record cap before is displaced by one added after it.

**What this is not.** This is retrieval and composition measured against the
gold assertions, model-free. It says the evidence reaches the answer and the
answer states it in identifiers an analyst can look up. It does not say what the
grader will score, and the Step 6 re-judge is still the decision.

## I-14 — Two presentation faults the grader read as invented content

Found by judging the 82 two-step and cross-catalogue questions on the repaired
LLM arm rather than by inspection. Correctness on that slice moved **0.5104 →
0.8623** (position 1), but flagged hallucinations rose 64 → 72, and every one of
the new flags was one of these two.

**A false abstention beside a true answer.** The iterative loop re-runs a hop
that first came back empty — before its producer seeded it, or before the facet
expansion widened it — and BOTH attempts reach the composer. The empty one
abstained, so one answer said "the executed query ran cleanly and returned
CAPEC-150 with no linked records" four sentences after listing CAPEC-150's seven
CWE weaknesses. An abstention is a statement about a SUB-QUESTION, so a
sub-question another result answered no longer produces one.

**Text listed as though it were an identifier.** A two-leg walk returns the
intermediate patterns and the leaf consequences in ONE flat related set. A
single enumeration over both could only call them "related item(s)" and had to
print `CAPEC-182` beside `Other Confidentiality` in the same comma list. The
grader read it literally and recorded the consequence text as an invented
identifier in three answers. The enumeration is now split by neighbour label —
so each claim gets the noun its edge earns, "1 attack pattern" and "6
Consequences" — and a list whose items contain spaces is separated by semicolons
so a multi-word item stays legible as one item.

Neither changes what is retrieved: gold recall is 0.9791 on the development bank
and 0.9788 on the holdout before and after, with no question moving either way.

**Paper implication:** a faithfulness metric counts what the reader can
misread, not only what the system invented. Both defects here were true
statements arranged so that a careful reader would draw a false one.
