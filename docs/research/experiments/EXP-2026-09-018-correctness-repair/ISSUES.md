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
LLM arm rather than by inspection. Correctness on that slice moved **0.5125 →
0.8505** counterbalanced over both grading positions (`data/judged_hard_slice.json`)
— two-step 0.5405 → 0.8404, cross-catalogue 0.4556 → 0.8711, 66 improved and 10
down, every one of the ten a 1.00 falling to 0.90-0.95 where the answer now
carries more than the deliberately rolled-up gold. The two positions agree to
0.024, which is inside the grader's own spread.

Flagged hallucinations nonetheless rose 141 → 149 across both positions, and
every new flag was one of the two faults below rather than an invention.

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
The judged slice above was generated BEFORE both fixes, so its correctness is a
floor for the current tree.

### What the whole development half should read

The judged slice calibrates the cheap measure against the grader once: gold-text
recall gained 0.4373 there and judged correctness gained 0.3380, a **transfer of
0.773**. Applying that to how each untouched tier's recall moved, capped at 0.97:

| | n | repaired commit | low | high |
|---|---:|---:|---:|---:|
| D4 two-step | 55 | 0.5405 | **0.8404** | **0.8404** |
| D6 cross-catalogue | 27 | 0.4556 | **0.8711** | **0.8711** |
| the other five tiers | 202 | — | unchanged | up to 0.97 |
| **all** | **284** | **0.7845** | **0.8820** | **0.9253** |

The two hard tiers are measured; the rest is projection. The low end credits the
other five with NO gain at all, which is certainly too pessimistic — every one of
them improved on the cheap measure. The high end applies a transfer ratio
calibrated on a slice starting at 0.51, where there was far more headroom than a
tier already at 0.93 has, so it should be read as an upper bound.

**This is a projection, not a result.** The full judged run over the development
half costs about an hour and is what the ship gate needs.

**Paper implication:** a faithfulness metric counts what the reader can
misread, not only what the system invented. Both defects here were true
statements arranged so that a careful reader would draw a false one.

## The full judged development half

`data/dev_half_judged.json`, `scripts/dev_half_judged.py`. Three arms over all
284 development questions, each answer graded in both positions — 1,704
judgments — against the Step 6 cells at `46652efc`.

| arm | reference | Step 6 | now | improved | regressed |
|---|---:|---:|---:|---:|---:|
| `generic` (LLM) | 0.7188 | 0.7845 | **0.9211** | 123 | 26 |
| `generic_composed` (model-free) | 0.6547 | 0.7537 | **0.9210** | 146 | 14 |
| `deterministic` (template control) | 0.5018 | 0.5732 | 0.6060 | 95 | 97 |

Every tier of the LLM arm rose, and the two the repairs targeted rose most:

| tier | Step 6 | now |
|---|---:|---:|
| D0 adversarial | 0.7767 | 0.9264 |
| D1 attribute | 0.9407 | 0.9557 |
| D2 two-hop attribute | 0.9000 | 0.9600 |
| D3 filtered | 0.9278 | 0.9455 |
| D4 two-step | 0.5405 | 0.8603 |
| D5 requested property | 0.9160 | 0.9319 |
| D6 cross-catalogue | 0.4556 | 0.8767 |

The two grading positions agree to 0.005 (0.9187 / 0.9234). **The kill gate's
metric is clear**: fabricated cross-catalogue mappings go 1 → 0 on `generic` and
2 → 0 on `generic_composed`. It rises 2 → 4 on the template control, which was
not repaired and is not shipped.

**The template control is a wash** — 95 up, 97 down — which is what a control
should do, and it rules out the grader simply having a good day.

**The two real arms have converged.** The language model was worth 0.064 at the
reference and 0.031 at Step 6; it is now worth 0.0001. Every fault repaired here
was in routing, retrieval and identifiers, which both arms share, and there is no
headroom left for a narrator to recover. The model-free arm is byte-reproducible
and free to run.

### This is one-sided, and the protocol asks for a pair

The reference and Step 6 columns were graded in an earlier sitting; this one was
graded today. `Q46` records a metric moving 0.0503 between sessions. The gap here
is 0.1366 and is concentrated in exactly the two tiers the repairs targeted, so
drift does not explain it — but a true paired control re-runs the pre-repair code
in the same sitting, and that has not been done.

### The hallucination count rose, and none of the rise is invention

254 → 291 on `generic`. Classifying every flag:

| category | Step 6 | now |
|---|---:|---:|
| our own id-example help text | 176 | 54 |
| a real identifier the rolled-up gold omits | 62 | 106 |
| node text read as an identifier | 14 | 114 |
| a false absence claim | 2 | 15 |

The first falls because fewer answers abstain. The second is an answer being
**more** complete scoring worse, since the gold is deliberately rolled up
(`_top_level`). The last two are genuine and are recorded below.

## I-15 — Node text in an enumeration reads as an invented identifier (RESOLVED 2026-09-12)

114 flags. A CAPEC consequence, execution step or prerequisite has no published
identifier and its content is text, so the enumeration lists the text. The grader
reads a list item as an identifier the answer asserted. Splitting the enumeration
by neighbour label and separating multi-word items with semicolons (I-14) cut it
but did not remove it. It costs faithfulness, not correctness — the C0029 case
scores 1.0 with 24 flags.

**The diagnosis in that paragraph was wrong, and the experiment is what showed
it.** The plan pre-registered a 12-case judged slice precisely because "does the
grader stop flagging text once it is quoted and labelled" is empirical. It was
run, and the answer was **no**: rendering each text item as a labelled quotation
in its own clause — "has 6 Consequences, named only as text: “Other
Confidentiality”; …" — moved the class not at all. 18 flags before, 18 after.

Reading what the grader actually wrote settled it:

> "it states the consequence as “Other Confidentiality” … and **the evidence only
> shows the consequence id/name, not that text**"

The grader was not misparsing a list. It was being handed evidence that did not
contain the string the claim quoted, and calling the claim ungrounded — which,
from where it sat, was the correct verdict. `utils/evaluation/generate_e2e.py`
built the judging view of a related neighbour from an **allow-list** of keys —
the nine identity fields plus `description`. That is right for a mitigation and
wrong for every CAPEC node whose prose is stored elsewhere: a Consequence carries
`scopes` and `impacts` and nothing else, an ExecutionStep its `phase`. The
composer renders a neighbour from *every* non-identity key it carries, so the two
views disagreed, and the answer was judged against evidence its own text had been
stripped out of.

So this was never a grader artefact. It was a **real provenance gap** in the
evaluation harness, and a class this experiment had twice written off as the
metric's fault.

**Resolution.** The rule is inverted: identity keys are named, everything else is
content, bounded by the same helper every other property already used. A node
kind nobody has seen yet now arrives checkable rather than blank. The quoting
change is kept — it is right on its own terms, since a quotation cannot be read
as an asserted identifier by a human either — but it is not what fixed this.

The other half of the step was self-inflicted and did work as expected:
`_ID_EXAMPLES` ("e.g. T1566, M1017, or CAPEC-98") put three real catalogue
identifiers into abstaining answers, and the grader flagged them exactly as it
would flag an invention. The advice survives, the examples are gone, and a test
asserts no module constant and no answer surface names one.

**Verification** — the 12 most-flagged development answers, `generic_composed`,
graded in one position against the same cells in `dev-half-2026-09-12`:

| | mean correctness | own id-example | node text as identifier | all flags |
|---|---|---|---|---|
| `dev-half-2026-09-12` | 0.9000 | 21 | 18 | 49 |
| quoting only | 0.8615 | **0** | 18 | 23 |
| quoting + provenance | 0.8846 | **0** | **0** | 5 |

The two target classes go from 39 to **0** against the plan's bar of ≤ 2, and
total flags fall from 49 to 5. All five that remain are
`gold_omits_identifier` — a real identifier the rolled-up gold does not list —
which is the gold's narrowness and not ours, and the one class this repair was
never going to touch. Gold-text recall is unmoved on all
four model-free cells (dev 0.9791 / 0.6814, holdout 0.9788 / 0.6402, zero
questions regressing). The recorded-answer diff is 50, 37, 45 and 36 answers per
cell, every change one of the two intended sentences.

**Correctness on the slice is 0.0154 below the baseline, and the plan's bar said
"not lower".** Reporting it as a miss: ten of the thirteen cases are unchanged,
one rises 0.2 and two fall 0.2, on a thirteen-case slice whose grader has a
recorded between-session spread of 0.0503 (`Q46`). The two that fall are worth
more than the number, because both fall for a reason the fix *created the
conditions to see*:

* `D2-HAS_CONSEQUENCE-CAPEC-295` — **faithfulness 0.8 → 1.0**, the provenance gap
  closed exactly as intended and the "evidence does not contain that name"
  complaint gone. Correctness 0.6 → 0.4, because the grader can now compare our
  "Other Confidentiality" against the catalogue's "Confidentiality Other" and say
  precisely which is wrong. That is **I-17**, and it was previously hidden behind
  the provenance gap.
* `D4-ChildOf-HAS_EXECUTION_STEP-CAPEC-635` — a pre-existing complaint, that the
  steps are attributed to the anchor rather than to the pattern they were reached
  through, scored 0.9 → 0.7 on the same evidence.

So the step met its flag bar and missed its correctness bar by less than a third
of the instrument's own drift, and what it exchanged was an unattributable flag
class for a named, recorded defect. That is the better position to be in, but it
is a miss and the paired control is where it gets a real reading.

**The intermediate row is worth keeping.** Quoting alone *cost* 0.0458 while
removing nothing — invisible had the step gone straight to a full run, and the
reason the plan grades a named slice before anything larger.

See also [I-17](#i-17), found while fixing this and deliberately left open.

## I-16 — A false absence claim names the question's edge, not the store's (RESOLVED 2026-09-12)

15 flags. A View's members hang off `IN_VIEW`; a Category's hang off `MEMBER_OF`.
The builder resolves that and retrieves the members; the composer's absence check
looks for related entries **of the named relation**, finds none of type
`MEMBER_OF`, and writes "CAPEC-703 has no MEMBER_OF relationships in this
catalogue" in an answer that has just enumerated them. This costs correctness as
well as faithfulness and is the more urgent of the two.

**Two shapes, not one.** Scanning both banks for self-contradiction — an absence
claim the same answer refutes — found the containment case and a second one the
original write-up missed:

| Shape | Example | Why the old check could not see it |
|---|---|---|
| `resolved-edge` | "CAPEC-703 has no MEMBER_OF relationships" beside its 15 `IN_VIEW` members | the store's edge name differs from the question's |
| `enumerated-noun` | "T1518 has no tactics" beside "T1518 has 1 tactic: TA0007" | `Tactic -[HAS_TECHNIQUE]-> Technique` is the same relation read from the other end, so **no** edge-name folding reconciles it |

**Resolution.** Two one-way suppressions in `_relation_is_empty`, neither of
which can manufacture an absence:

1. Relation names fold across the containment class. `MEMBER_OF`, `HAS_MEMBER`
   and `IN_VIEW` denote one relation; that list already existed in
   `utils/specialists/gremlin/builder.py`, so it was made public
   (`MEMBERSHIP_ALIASES`) and imported rather than restated — a test asserts the
   two views of it stay equal. The fold is applied to the related-entry scan, to
   the facet-count scan, and to `_schema_denies`, which was the warrant actually
   firing: a View declares `IN_VIEW` and no `MEMBER_OF`, and reading that as
   "the schema has no such edge" is what licensed the claim.
2. An absence is refused when the enumeration the same result is about to emit
   calls those neighbours by the noun the absence would deny. The nouns are
   derived by walking exactly the groups `_enumeration_claims` walks, so the two
   cannot drift.

**What was deliberately left alone.** Six of the ten flagged development cases
were fixed; four keep their absence claim because it is **true** — a Campaign
has no `MITIGATES` edge, Software and Groups have no `DETECTS` edge, and
Software has no sub-techniques. Those are the `empty` mechanism working as
designed (the slice still states 8 empty sets, down only by the one
contradiction), and suppressing them would trade a false statement for a silent
one.

**Verification** (`scripts/mechanism_check.py`, new `contradictions()` property,
asserted on every slice and over each capture as a whole):

| Capture | before | after |
|---|---|---|
| dev · `generic_composed` (284) | 7 (6 resolved-edge, 1 enumerated-noun) | **0** |
| dev · `deterministic` (284) | 6 | **0** |
| holdout · `generic_composed` (288) | 5 | **0** |
| holdout · `deterministic` (288) | 6 | **0** |

Gold-text recall is unmoved on all four cells — dev 0.9791, holdout 0.9788 on
`generic_composed`; dev 0.6814, holdout 0.6402 on `deterministic` — with
**0 questions regressing** in any of them, against a baseline generated in a
worktree at `c5cb2906` so the comparison is same-data and same-sitting. The
recorded-answer diff is exactly 6 answers per bank on the deterministic arm,
each differing by the one removed claim and nothing else; provenance goes 4/4 to
3/3, so the ratio holds. Every other mechanism property is unchanged.

Neither capture's answer files are committed — `.gitignore` keeps every
`experiments/**/answers/*` that is not a judgment sidecar, and neither capture
was graded. Both arms are model-free and regenerate byte-for-byte from the
commit and the data; `data/i16_contradictions.json` is the committed evidence
and `i16-baseline-c5cb2906/README.md` carries the two commands. The holdout is
**not** spent by any of this.

**A note for whoever runs the paired control.** A `git worktree` of this
repository has a **tracked** `data/versions.json`, so `ln -s … data` silently
creates the link *inside* the checked-out directory and the schema registry
discovers no datasets: the run completes and reports 33/288 with "no specialist
for source 'attack'" on the rest. Symlink the *subdirectories* of `data/`
instead, and check `ok == count` before believing any reference number.

## I-17 — Our answers state the catalogue's text in an order the catalogue does not use (OPEN)

**Found while fixing I-15; not fixed here, because the fix is a build change.**

A CAPEC Consequence is `<Scope>…</Scope><Impact>…</Impact>` in the XML, and the
gold set records the element's own text in document order — "Confidentiality
Other", "Authorization Execute Unauthorized Commands Run Arbitrary Code". The
loader splits that into two list properties, `scopes` and `impacts`, and the
composer flattens a neighbour's content by iterating its keys **alphabetically**,
so `impacts` leads and the answer says "Other Confidentiality". Same content,
inverted order, on every consequence in the bank.

The grader notices: "it states the consequence as “Other Confidentiality” rather
than the expected “Confidentiality Other”". The cheap gold-text proxy does not,
because it matches long items by word recall — which is exactly the kind of
tolerance that hides a real difference, and is worth remembering when reading
that proxy anywhere else.

**Why it is not fixed in the close-out.** Ordering `scopes` before `impacts` in
`utils/synthesis/composer.py` would put CAPEC-specific knowledge in the generic
renderer, which is the thing that renderer exists to avoid. The principled fix is
in the builder: have a derived node carry the catalogue's own composed `text`
property, as `utils/specialists/evalset/raw_graph.py` already does for the gold,
and let the composer's existing generic flattening pick it up — after which our
string and the gold's are the same string by construction. That is a build-policy
change and needs a wipe-and-reload of both live stores before anything is
measured against it (see the live-fixture note), so it does not belong between
two arms of a paired control.

**What it costs.** Now partly measured, because fixing I-15's provenance gap is
what made it visible. On `D2-HAS_CONSEQUENCE-CAPEC-295` the grader's verdict
moved from "the evidence does not contain that name" (faithfulness 0.8) to "it
does not state the expected consequence 'Confidentiality Other'" (faithfulness
1.0, correctness 0.6 → 0.4). The gold's `must_include_related` for every CAPEC
consequence, execution step and skill is composed this way, so the exposure is
every `text_set` question in both banks — 6 of the 12 cases on the I-15 slice
carry at least one.

**Why it is still not fixed.** The change is in the graph build, and a build
change needs a wipe-and-reload of both live stores before anything is measured
against it. Doing that between the two arms of a paired control would mean the
reference side and the repaired side saw different data, which is the one thing
a paired control exists to prevent. It is a decision for the operator: fix it
before Step 3 and reload both stores so both sides see it, or ship the close-out
with it recorded and measure it separately afterwards.

## I-18 — A CAPEC mapping to OWASP or WASC was stated as an ATT&CK mapping (RESOLVED 2026-09-13)

**Found by the paired control's kill gate, which is what that gate is for.**

The Step 3 control read `fabricated_mapping` 1 → 3 and so FAILED its
pre-registered gate. Taking the three apart:

* two are the same template-arm case counted in both grading positions
  (`D6-MAPS_TO[ATTACK]-MAPS_TO[WASC]-T1110`, the `deterministic` control arm);
* the third is on the LLM arm, and is the **same answer graded twice** —
  position 1 records `fabricated_mapping: false` at correctness 1.0, position 2
  records `true` at 0.9. Three of its four flagged items
  (`CAPEC-648 -> T1513`, `CAPEC-268 -> T1562.002/003/008`) were checked against
  the evidence and are all **retrieved**: they are the `gold_omits_identifier`
  class, not inventions.

The fourth was real:

> `CAPEC-126 (Path Traversal) has 2 ATT&CK mappings: OWASP Attacks:Path
> Traversal; WASC:33.`

Neither is an ATT&CK mapping. `_REL_NOUNS["MAPS_TO"]` was hard-coded to "ATT&CK
mapping", and `_NOUN_EXPECTS` — which exists to stop a noun asserting a kind the
neighbours are not — could not see it, because it checks the neighbour's
**label** and ATT&CK, OWASP and WASC entries all arrive as `TaxonomyEntry`. The
distinguishing field is `taxonomy_name`, which every entry carries
(ATTACK 159, OWASP Attacks 20, WASC 16 on one capture).

**Why it matters more than its size.** Nine answers per arm is small; stating a
cross-catalogue mapping that does not exist is not, because federated
cross-catalogue routing is the capability this system is claimed for. On
`CAPEC-126` *neither* of the two listed mappings is ATT&CK, so the sentence is
false outright rather than imprecise.

**Resolution.** The noun is taken from the data: ATT&CK only when every entry
says `ATTACK`, the catalogue's own name when they all agree on another, and
"catalogue mapping" when they are mixed or when any entry does not say. One-way,
like every other noun guard here — an unknown taxonomy can never earn the ATT&CK
noun.

**Verification.** Answers calling a non-ATT&CK entry an ATT&CK mapping: **9 → 0**
on the development half. Gold-text recall unmoved at 0.9791 with zero questions
regressing; absence contradictions still 0. Four unit tests cover the mixed,
single-non-ATT&CK, all-ATT&CK and unknown-taxonomy cases.

**Cost to the schedule, recorded because it was a judgement call.** The fix
changes the tree the Step 3 control measured, so the control's repaired side is
being re-run against it. The reference side is not: it is a different commit,
unaffected, and its re-run had already reproduced the committed Step 6 reference
to within 0.0016 (0.7195 against 0.71875) — which is also the best evidence yet
that the between-session grader drift `Q46` records is not moving these figures.

## I-20 — A noun taken from the neighbour's label asserted a hierarchy that does not exist (RESOLVED 2026-09-13)

**And the I-16 scanner could not see the contradiction it caused.** Both halves
matter; the second more than the first.

"Which ATT&CK techniques is AN0749 a sub-technique of?" is a D0 question whose
gold answer is *none*. The system said:

> AN0749 (Analytic 0749) has 1 sub-technique: T1560.002.
> AN0749 has no subtechniques in this catalogue.

The retrieved edge is `AN0749 -[DETECTS]-> T1560.002`. `_REL_NOUNS` had no entry
for `DETECTS`, so `_related_noun` fell through to the neighbour's **label** —
`SubTechnique` — and asserted a parent/child relationship the edge does not
support. The two claims also contradict each other outright.

**Why I-16's scanner reported zero on it.** `_LABEL_NOUNS` spells the noun
`"sub-technique"`; `_relation_noun("HAS_SUBTECHNIQUE")` spells the same noun
`"subtechniques"`. The emission guard and the contradiction scanner both
compared *spellings*, so both passed. **The "contradictions: 0" recorded against
I-16 was therefore true only of what that scanner could detect** — two existed
in the same captures that it could not. With the scanner made noun-aware, the
committed control answers read **2**, and the fixed tree reads **0**.

**Resolution.** `_noun_key` normalises a noun to its shape — alphanumerics only,
one trailing "s" removed — and both the guard and the scanner compare through
it. `DETECTS` gains its own entry (`"detected technique"`, expecting
`Technique`/`SubTechnique`) so the noun names the edge rather than whatever
happens to sit at the other end of it.

The fix contains a lesson about itself: the first version of `_noun_key` stripped
a trailing `"es"`, turning `"subtechniques"` into `"subtechnic"`, which matched
nothing — the exact bug it was written to fix, reintroduced one line lower down
and caught only because the scanner still reported a clean 0 on answers known to
contain the defect. A normaliser that reports "no problems" is indistinguishable
from a normaliser that does nothing, which is why the check was run against a
capture whose answer was already known.

**Verification.** The two cases now read "has 1 detected technique: T1560.002"
with a true and uncontradicted absence claim. Gold-text recall unmoved at 0.9791
with zero questions regressing. Contradictions: control answers 2, fixed tree 0,
on both model-free arms.

**Scope note.** The paired control's answers predate this fix, so its cells carry
these 2 contradictions in 284 — recorded here rather than re-run, since the fix
changes 2 answers of 852 and the control is otherwise complete.
