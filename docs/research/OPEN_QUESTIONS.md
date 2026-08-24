# Open Questions

Every follow-up from every `RESULTS.md`, plus the known weaknesses. This becomes
the future-work section and pre-empts the reviewer objections that are coming
either way.

Ordered by what blocks the most: **Q1 gates the value of everything else.**

---

## Blocking — these gate publication

### Q1 — Is 0.9972 a capability or a coverage artifact?

**Why it matters:** All 120 catalogue questions were used during development and
were co-authored commit-for-commit with the templates that answer them; each
ships an `expected_template` field. There is no holdout. Until this is answered,
C-001 stays `partial` and every downstream number inherits the doubt.

**What resolves it:** Freeze the templates and the planner. Have someone other
than the author write **30 anchored questions** using the existing category
scheme but sampling anchors *uniformly* rather than by mapping richness. Run Arm
A and Arm F blind.

**Cost:** ~4 days. The cheapest high-value experiment available.
**Blocks:** C-001, C-013, and the interpretation of C-003 and C-005.
**From:** EXP-2026-07-001 §7, EXP-2026-07-006 §7, D-006.
**Status: ANSWERED — coverage artifact, substantially.** EXP-2026-08-002 ran on
2026-08-09 against `freeze/holdout-v1`. Arm A **0.689** (95% CI 0.550–0.817),
Arm F **0.708** (0.565–0.838), against 0.9972 and 0.9957. C-013 is `refuted`,
C-001 downgraded to hold only for the relation directions the templates serve.
The drop is concentrated: 1.00 on seven of sixteen categories, 0.00 on
`groups`. The Branch A §6 gate's `< 0.70` branch applies. See
[`docs/evaluation/holdout-v1/README.md`](../evaluation/holdout-v1/README.md).

**What Q1 leaves open:** the holdout was LLM-authored, so it controls
co-authorship bias but not distribution bias — a human-authored set of 15–20
questions remains the cheap secondary check. And n=30 puts the gate's 0.70
threshold 0.011 from the result with a CI spanning three of its four bands.

**Update (2026-08-18, EXP-2026-08-005).** The concentrated part of the loss has
a named cause and a schema-derived repair: blind retrieval for the default
cascade moves 0.7688 → 0.8952 with the development catalogue unmoved, and the
residue is five CAPEC identifiers belonging to the *join* defect rather than the
direction one. Two consequences for this question. First, **a re-run of holdout
v1 on the repaired system is no longer an independent measurement** — v1
diagnosed the defect, so its post-fix number is co-authored with its own test,
exactly the failure this question exists to catch. Second, that makes **holdout
v2 a prerequisite for any blind figure quoted after the fix**, not an optional
strengthening.


**ANSWERED — coverage artifact, and now located exactly (EXP-2026-08-010, 2026-08-21).**
Measured on two published external benchmarks, not on anything written here. Of
14 external question types the deterministic cascade matches an oracle graph
read on 8 and returns **nothing at all** on 4 — every Group↔Software and
Campaign↔Software ask. Two more lose ~70% to a single pinned label. Overall
recall against the ceiling is **−0.303**.

The decisive detail is that this is **not** a phrasing effect. Identical
questions in this project's wording and in AttackQA's produce byte-identical
queries. Across both generated banks, all eight `group_techniques` /
`campaign_techniques` / `software_techniques` questions are technique-anchored;
the reverse direction is never asked, and Group↔Software is never asked at all.
The banks were drawn from the shapes the templates serve. The artifact was in
**which questions exist**, not in how they are worded.

Still open within Q1: the external sets are enumerative and Enterprise-only, and
say nothing about CAPEC or open-ended asks.

### Q2 — What is the variance on any of these numbers?

**Why it matters:** Every arm is `n_runs: 1` with seeds unrecorded. The two
headline deltas (−0.3568 and −0.1185) are differences of point estimates with no
confidence interval, and `statistical_test` is null in all eleven manifests.

**What resolves it:** Re-run the arms with recorded seeds — at minimum Arms A, B,
C, F, G — and compute a paired bootstrap on the two deltas.
**Cost:** ~1 hour wall clock plus ~600 judge agents. Operator's call.
**Blocks:** any claim stated with a p-value. **From:** D-010, every arm's §5.
**Status: HALF ANSWERED — grader variance measured, pipeline variance still not.**
EXP-2026-08-007 graded one fixed set of *deterministic* answers three times, so
every point of the resulting spread is grader variance and none of it is
pipeline variance: **0.0050** (0.8367 / 0.8417 / 0.8400, sd 0.0021). That is
the noise floor every delta in that experiment is read against, and it is why
the arm comparison there is reported as *not* a separation while the repair
delta is. The first non-null `statistical_test` in the record also lands there —
a paired percentile bootstrap (2000 resamples, seed 1729) on the repair delta,
95% CI +0.0333 to +0.2167.
**What is still open:** the pipeline half. No arm has been run twice, seeds
remain unrecorded, and grader variance is *not* a substitute for run variance —
an LLM-in-the-loop arm like F or B would have its own, and it is likely larger
than the grader's. Any p-value about an *arm* still needs the re-run this
question originally asked for.

### Q3 — Does template routing actually beat free-form LLM query generation?

**Why it matters:** **This is the paper's intended headline claim (C-012) and no
experiment supports it.** Arm G disables templates but is a *generic-primitives*
control; no LLM writes Cypher or Gremlin in any arm. The literature contains no
controlled head-to-head of a template library against free-form generation —
that null result was verified explicitly — so the gap is both the opportunity and
the unfinished work.

**What resolves it:** Build an external free-form text-to-Cypher/Gremlin
baseline, tuned in good faith, and run it over the same catalogue.
**Cost:** weeks, not days. **Blocks:** C-012. **From:** D-004, EXP-2026-07-007 §7.

**Status: ANSWERED, affirmatively (EXP-2026-08-008, 2026-08-19).** The baseline
above was built and run. On 30 questions no arm had seen, the template cascade
scored **0.9467** and an arm in which a language model writes the Cypher/Gremlin
itself scored **0.5000**, with the plan held constant between them so query
generation is the only variable. It was built to be fair rather than to lose: the
model receives the real schema, the resolved seed identifiers, the constraints
the safety gate enforces, the harness's output-column convention, and a repair
loop that feeds gate rejections back for another attempt. It is denied only the
templates. Crediting every ambiguous failure to the baseline — 7 questions whose
correct query our own evidence reader could not parse, 2 empty replies from a
token budget — it reaches **0.5739**, still barely half the cascade, so the
conclusion does not rest on the ambiguous cases. C-012 moved to `supported` on
this evidence.

**What is genuinely left of this question, and it is not what the text above
says.** Two things, both narrower. (1) *The cost half of C-012 is unmeasured* —
no cost figure was taken in that run, so "outperforms … in correctness and in
cost" is half-evidenced. (2) *Scope* — EXP-2026-08-010 showed the comparison was
run on question shapes the templates serve; on 14 external question types the
cascade returns nothing at all on 4, so "outperforms" holds inside the template
library's coverage and is untested outside it. The evidence-reader ambiguity in
(1)'s first clause is now a decision rather than an open question: see D-019 and
Q18.

### Q4 — Where is the coverage cliff?

**Why it matters:** All 120 questions are anchored — every one names an entity or
an id. Nothing measures the regime where a template router is *weakest*. A paper
that reports the benefit of the design without its price will not survive review.

**What resolves it:** ~40 open-ended, non-anchored questions on which the router
is expected to fail, reported as the design's cost rather than hidden.
**Blocks:** C-014. **From:** EXP-2026-07-011 §7, the 2026-07-26 limitations.

### Q5 — Does federation beat merging both sources into one graph?

**Why it matters:** The federation claim is the part the funder cares about and it
has never been contrasted with a counterfactual.
**What resolves it:** Build the merged-single-graph baseline.
**Blocks:** C-015. **From:** D-005.

**Status: ANSWERED — no, not on correctness.** EXP-2026-08-009 ran on
2026-08-21. The merged store holds both catalogues (9138 nodes, 34641
relationships, all eight separation checks passing) and is answered by one
Cypher specialist. Against `generic_composed` — identical primitives, identical
deterministic composer, two stores instead of one, no language model on either
side so both are byte-reproducible — merging scores **−0.0334** on one blind set
and **+0.0000** on the other, n=30 each, intervals overlapping. C-015 is
`refuted` as written.

**What Q5 leaves open, and it is most of the question.** Correctness was never
the interesting part of the federation argument; it was just the only part
anyone had a number for. The reasons to federate that practitioners actually
give — provenance, licensing, staleness, and not re-running a merge every time a
catalogue updates — are untested, unclaimed, and now the only case left. Writing
them as a claim is the follow-up, and it is a different kind of work from this:
none of them is measured by asking questions and grading answers.

A second gap: both catalogues here have **disjoint identifier spaces and exactly
one colliding label**. That is the easy case for merging. A pair of sources
whose ids collide would put the merged design under a strain this experiment
never applied.

**Narrowed 2026-08-23 — two of the four surviving reasons are ruled out as
unmeasurable here, and the other two are restated as one structural claim.**

*Ruled out: merge cost and onboarding cost.* Both are functions of **which two
graphs are chosen**, not of the architecture. ATT&CK and CAPEC merge cheaply
precisely because they already share edge semantics and a taxonomy crosswalk;
two sources with unrelated schemas would not. Any wall-clock figure taken over
this pair is a statement about this pair, and a reviewer would say so. They are
not open questions — they are questions this study cannot answer without
confounding them, and that is recorded rather than attempted.

*Restated: the surviving case is non-modification, and it is dataset-independent.*
Merging **required editing both catalogues at load** — D-017 records exactly what
`utils/kg_builder/merge.py` had to write that upstream does not ship (CAPEC's
public identifier, which the federated system derives at read time, and the
`T`-prefixed form of CAPEC's ATT&CK taxonomy entries). That edit is permanent,
versioned separately from upstream, and must be redone on every catalogue
release. Federation ran the same catalogues as shipped, and EXP-2026-08-013
demonstrated it on a third: a customer identity graph loaded unmodified, with
three live sources retrieving **identically** to one. Licensing and provenance
are consequences of that property rather than separate arguments — a graph that
is never rewritten is one whose provenance and licence survive by construction.

That is the form the follow-up takes: **C-022**, recorded in
`EXP-2026-08-017-federation-isolation`, with what merging genuinely buys
(cheaper multi-hop across the seam — consumer sub-questions skipped for want of
a join value fell from 7 of 30 to 3 of 30) reported beside it rather than
omitted.

**Status: CLOSED (2026-08-23).** The count is in: the merged condition carries
`attack_id` on **1,083** nodes whose upstream record does not ship it — 22.7% of
CAPEC — against **0** federated. Merging relocates the reconciliation from code
into the stored records, and the edit is due again on every catalogue release.
C-022 states it, and keeps C-015's refutation as its premise rather than
route around it.

**What stays open is deliberately narrower than this question was.** Licensing
is a legal constraint and will never be evidence. Merge and onboarding cost are
**ruled out**, not deferred. And the identifier-collision case named above — two
sources whose ids collide — remains untested, which is the one gap here that a
new experiment could still close.

---

## Methodological

### Q6 — How well does the LLM judge agree with a human?

Cross-model and evidence-grounded, but still an LLM, and its verdicts are not
perfectly stable across runs. It occasionally penalised correct answers over
citation metadata. **What resolves it:** human κ on a 40-answer sample. A
reviewer will ask. **From:** D-002.

**Status: CLOSED as WILL NOT DO (2026-08-23), and it moves to the known-weakness
list rather than staying a backlog item.** The operator is the only available
annotator and does not have the domain background to adjudicate ATT&CK/CAPEC
answers at a standard worth citing. A κ computed from an under-qualified
annotator is worse than no κ: it would read as human validation while measuring
something else. Recording the refusal is the honest move, and the reviewer's
question gets answered with what *is* measured rather than with a number
manufactured to have one.

**What stands in its place, and it is not nothing.** Three measurements bound the
grader without a human in the loop: cross-model agreement at **r = 0.9275**
between the local grader and Sonnet on the same judgments; the demonstration that
self-judging overstates quality substantially — four self-judged metrics all read
1.0 while an independent Sonnet panel scored the same pipeline at 0.8946 with
hallucinations in 11 of 120 answers (C-009); and the grader's own re-run spread,
**0.0050** across three passes over one fixed set of deterministic answers
(sd 0.0021), which is the noise floor every delta in EXP-2026-08-007 is read
against. The limitation to state in the paper is that all three are
machine-to-machine.

### Q7 — Two of the planner's reported metrics are 1.0 by construction

The planner corpus excludes bare id lookups (`what is T1059.001?`) as
unroutable — it is filtered on the planner's own success. Source recall 1.0 and
schema adherence 1.0 partly reflect what the corpus omits.
**What resolves it:** add a lookup intent, then re-score without the exclusion.
**From:** EXP-2026-07-008 ISSUES.md.

### Q8 — Three of the four `goals.md` end-to-end metrics are self-consistency checks

Provenance correctness, analyst inspectability, and no-fabrication all measure
whether the system's outputs cohere with its own retrieved records. A confidently
wrong pipeline passes all three. **From:** EXP-2026-07-009 §5, D-001.

### Q9 — Is the failure-terminus classifier general, or shaped by this one pipeline?

Its finding — 26 of 36 failures were planning/retrieval, only 2 faithfulness —
contradicts the widespread assumption that LLM pipeline failures are
hallucination failures. But it has been applied to exactly one system and its
class ladder mirrors that system's stage boundaries. **What resolves it:** apply
it to a GraphRAG pipeline, a text-to-Cypher pipeline, and an agentic traversal
system; report what fraction falls through to `other`. **Blocks:** C-016.

### Q10 — Does the verifier actually do anything?

Provenance and inspectability at 1.0 are self-consistency checks, not evidence
that verification prevents unsupported claims. **What resolves it:** the verifier
ablation — each of the four gates (cited / resolvable / grounded / correlated)
disabled individually — plus a proper answerable/unanswerable split. The current
10 negatives are far too few. **Blocks:** C-017.

**Status: ANSWERED (EXP-2026-08-014, 2026-08-23). It does nothing, and that is
the right answer.** All four gates ablated over 888 claims from 137 answered
questions across four banks: each cuts **zero**, and the baseline carries zero
unsupported claims. Not because verification is broken but because
`factory.synthesize` always composes with `DeterministicComposer`, which builds
every claim *from* a retrieved record — the citation is that record and the
entity ids are its own. **An uncited, unresolvable or ungrounded claim cannot be
constructed on this path.**

So the question was mis-framed, and usefully so: the verifier is a **ceiling by
construction**, like C-007's safety property, not a filter with a hit rate.
C-017's first half has been restated accordingly. The evidence that survives is
the unit proof (13 assertions in
`utils/synthesis/tests/test_verifier_gates.py`) plus the structural argument —
never an ablation, which on this pipeline cannot tell a working verifier from a
disabled one.

**What is left of Q10 is a new question, recorded as Q20:** the only input that
could stress the verifier is an LLM-proposed claim, and no shipped path produces
one. The answerable/unanswerable half of the original question is unaffected and
still open — 10 negatives remains too few.

### Q21 — The comparative routing rule can lose the source a question is about

**Why it matters:** EXP-2026-08-016 measured what the 2026-08-22 source-selection
fix bought — cross-tenant leakage from **568 records to 5** — and, because the
protocol required reporting off-metric regressions, also what it cost.

*"Which group uses T1059.001?"* is an ATT&CK question. Under the comparative rule
the tenant identity graph is the leader on the token `group`, ATT&CK contributes
no token identity does not, and ATT&CK is dropped: the question routes to
`identity` alone and **returns nothing at all**. The leak metric scores this
*clean*, because the one source consulted returned no foreign records — a rule
routing everything to a single source would score a perfect zero while answering
nothing.

So the fix is a trade, and both halves must travel with the claim.

**What resolves it:** the leader rule breaks ties on *token count*, which treats
a generic word matched by a 72-label tenant schema as equal evidence to an
identifier matched by a catalogue. A weighting that prefers a source matching a
**resolved identifier** (`T1059.001`) over one matching only generic vocabulary
would keep both properties. That is a design change with its own regression risk
across all 120 catalogue entries, so it needs an experiment, not a patch.
**Cost:** ~1 day. **Blocks:** stating the routing fix without a caveat.
**From:** EXP-2026-08-016 RESULTS.

### Q20 — The LLM claims composer is unreachable. Delete it, or reconnect and measure it?

**Why it matters:** `utils/synthesis/llm_composer.py::OpenAICompatibleComposer`
builds claims from model JSON (`Claim.from_dict`), and
`factory.select_composer` would wire it in — but `factory.synthesize` never calls
`select_composer`; it constructs `DeterministicComposer` directly. The composer
is described capability with no caller, the same class of inflation as the two
unreachable query templates deleted on 2026-08-23.

It matters more than those did. It is the **only** thing in the codebase that
would let a language model propose a claim, so it is the only input against which
the verifier's four gates are load-bearing (Q10, EXP-2026-08-014). While it stays
unreachable, C-017 can only ever be a construction argument.

**What resolves it:** a decision. Either delete it and state that no path admits
model-proposed claims — which simplifies the system description and makes the
verifier's role honest — or reconnect it as a measured arm and re-run the
ablation against it, which would finally give C-017 a rate rather than a
guarantee. **Cost:** an afternoon to delete; ~2 days to reconnect and measure.
**Blocks:** whether C-017 can ever be more than a design claim.
**From:** EXP-2026-08-014 RESULTS.

---

## Environment and provenance

### Q11 — What is the served context window of `skynet`?

The repository has given three different answers and none is authoritative:
"unknown from the client side" (the honest one), "~64k" (an estimate never
verified against the server), and `48000` (a *client request* in `.env`, which
the server may cap lower). A client-side `num_ctx` request and a served
`max_model_len` are different numbers, and only the second is the context window.
**What resolves it:** read `max_model_len` off the model server.
**Until then:** quote none of the three. Say the window is unrecorded, and note
that two questions (C-SCN-01, F-CWE-05) overflowed it under the un-truncation
profile — an observation that does not depend on knowing its size.

### Q12 — What quantisation is `skynet` serving?

Recorded as **unknown** rather than guessed. The model is Gemma 4 31B via vLLM.
Nothing in the study generalises to another model without re-running.

### Q13 — Two query templates are unreachable

`node_lookup` (Cypher) and `capec_lookup` (Gremlin) are not reachable from
`build()` or `expand()`. They are dead code and must not be counted as
capability. **From:** EXP-2026-07-011 ISSUES.md.

---

### Q14 — What do the templates actually hold, if not accuracy?

**Why it matters:** C-003 — *"the templates are where the accuracy lives"* — is
described in the ledger as the strongest result in the study, and
EXP-2026-08-007 contradicts its plain reading. Arm H disables the templates and
judged level with the cascade (0.8483 vs 0.8367, 2.3× the grader's spread,
overlapping intervals). The original 3.0× ratio came from Arm G, a weaker
generic arm that predates the schema-derived capabilities.

**What resolves it:** rewrite the claim around the property that *did* separate
the arms — provable abstention, 95% vs 55% — and re-derive the ratio against Arm
H rather than Arm G. Then decide whether a claim about abstention integrity is
strong enough to carry the section C-003 currently carries.

**Cost:** ~half a day of analysis, no new runs. **Blocks:** C-003, and the
framing of the paper's central section. **From:** EXP-2026-08-007 §4, §6.

**Status: ANSWERED (2026-08-23).** C-003 is now marked `refuted` and superseded
by **C-023**, which states the surviving property: templates hold *precision on
the schemas they were written for* and *provable abstention*, not correctness,
and they cost coverage. The ratio was not re-derived against Arm H because there
is no ratio to derive — Arm H is level on the catalogue, ahead on the fresh
bank, and 0.278 ahead externally, so the quantity C-003 measured does not exist
in the direction it assumed.

**And the answer is weaker than Q14 expected on its own preferred ground.**
Q15's read found that 4 of the abstention cases separating the arms have
byte-identical abstention objects and were simply graded differently, so the
95%/55% pair Q14 proposed building the section on is inflated; the real gap is
~0.30. It is still the most robust of the three properties, and it is the only
one that holds across both the external benchmark and the foreign schema — but
the section should be written on **0.810 vs 0.500**, with the mechanism named.

### Q15 — Why is Arm H's abstention proof rate half the cascade's?

**Why it matters:** honest abstention carrying executed-query proof is the
property the project leads with (C-017), and it is the one thing that got
*worse* on the portable path. 11 of 20 against 20 of 21, reproduced
independently on the blind set (2 of 4 against 3 of 3). If generic primitives
are the route to new datasets, this defect travels with them.

**What resolves it:** the abstentions are on disk. Read the 9 Arm H catalogue
abstentions that carried no query and determine whether the query was never
executed, was executed and lost, or was executed and not attached — three
different defects with three different fixes.

**Cost:** ~2 hours, no new runs. **Blocks:** C-017 going beyond `partial`, and
any recommendation of the generic path. **From:** EXP-2026-08-007 §7.

**Status: ANSWERED (2026-08-23), and it was none of the three.** Full working in
`EXP-2026-08-007/RESULTS.md` §AMENDMENTS A-1. The nine unproved abstentions are
two mechanisms:

1. **A missing abstention, not a missing proof (6 of 9).** On `F-NEG-01`…`06`
   the cascade emits two abstentions — the CAPEC side carrying its executed
   query, and the ATT&CK side correctly carrying none because a dependency skip
   meant no query ran — while Arm H emits only the second. The source-side
   abstention is never produced. The cause is `_empty_ok_results` in
   `utils/synthesis/verifier.py`: the template path's narrow query returns the
   anchor with an empty fold and reads as "nothing joined", while the generic
   path returns the anchor *plus its real neighbours* and never reaches the
   branch. **The over-returning that costs the generic arm precision is the same
   property that costs it its abstention** — one defect, two prices.
2. **Grader noise (4 cases).** `F-PART-01`, `F-PART-02`, `A-AST-01` and
   `A-AST-02` have **byte-identical abstention objects in both arms** and were
   scored differently anyway, net +2 to the cascade.
   `abstention_carries_query` is LLM-assigned, not computed.

**Corrected: the gap is ~0.30, not 0.402** — 0.810 vs 0.500 strict, or 1.000 vs
0.700 lenient. **Stop quoting "95% against 55%."** The defect is real, localised
to one predicate, and deliberately left unfixed: fixing it moves recorded
numbers and needs its own experiment. A new threat also falls out of (2) — a
judged binary field that disagrees with itself on identical input is unbounded
by the 0.0050 spread in EXP-2026-08-007 §2, which was measured on correctness.

### Q16 — Can a fairly-drawn question bank be produced on demand?

**Why it matters:** every figure in the study is bounded by having exactly two
question sets — one co-authored with the code (120) and one that has been burned
by fixing the defects it found (30). Each clean read currently costs a
hand-commissioned holdout, which is why the blind bank was reused past the point
where it was still blind.

**What resolves it:** nothing in the pipeline requires this to be manual. Gold
is already computed mechanically end to end — `gold_bank.py` derives it from the
pinned raw STIX/XML, and `holdout_protocol.py` states outright *"gold is
computed, never authored"*. The sampler already takes `--seed` and already
records population hashes. `author_prompt()` already builds the blind prompt.
Three gaps remain: draws cannot exclude previously-used anchors, `compile_bank`
has no command-line entry, and nothing runs the author prompt.

**Cost:** ~1 day. **Blocks:** any measurement of work done after 2026-08-18,
including the composer fix and both missing baselines. **From:** EXP-2026-08-007

**PARTIALLY ANSWERED, and the remaining half is now known to be blocked
(EXP-2026-08-010, 2026-08-21).** A web search on 2026-08-21 found **no
human-authored question set over ATT&CK or CAPEC anywhere public.** Every
candidate checked is LLM-generated or template-generated with humans in a
validating role; AttackQA ships a `human_question` flag that means *a human
wrote the generator script*, and reading it as human authorship would be a
defensible-looking but substantively wrong citation.

What that search did supply is the other half of what this question wanted:
**externally authored** questions, which control co-authorship without
controlling phrasing. Two are now in use (CTIBench `cti-ate`, AttackQA), with
set-valued gold that needs no grader.

So the position is: external authorship — **available and used**. Human phrasing
— **does not exist to be had**, and constructing 15–20 questions is now a
build-or-accept decision rather than a search.

**Known limitation to record with it:** a machine-authored bank is as *blind* as
v1 (same prompt, author never sees the code) but its phrasing will be less
varied than a human's. It is a regression and comparison instrument. A published
headline figure still wants human-authored questions.

**Status: ANSWERED — the machinery shipped and the register did not notice
(recorded 2026-08-23).** All three gaps named above are closed, and have been
since before EXP-2026-08-008:

| Gap as written | Where it is closed |
|---|---|
| "draws cannot exclude previously-used anchors" | `utils/specialists/evalset/make_bank.py` keeps an exclusion registry in `drawn_anchors.json` and excludes by default; `--no-exclusion` opts out and the help text records why you should not (51% of reseeds collide). |
| "`compile_bank` has no command-line entry" | `make_bank` *is* the entry: `--seed`, `--scale`, `--out`, `--authored`, `--workers`, `--model`, `--dry-run`. |
| "nothing runs the author prompt" | `make_bank` runs it, at `--workers` concurrency, against a model the flag forces to differ from the pipeline's. |

It was also exercised in anger rather than merely written:
`scripts/night2_sweep.py::make_bank2` drew the first *second* bank and asserted
zero anchor overlap against every prior bank — the check that a fresh seed alone
would have failed. Bank 3 (117 questions, authored by a non-pipeline model) is
the largest artifact it has produced.

**The cost line above is therefore wrong and must not be planned against.** A
30-question bank costs ~8s per question of authoring, so minutes, not a day.
`EXP-2026-08-015-bank-variance` is the first work to depend on this, drawing ten
anchor-disjoint banks across two populations.


### Q17 — How much of the blind holdout's `software` failure was the question, not the system?

**Why it matters:** EXP-2026-08-002 reports the blind holdout at **0.06 on
`software`** and 0.00 on `groups`, and that pair is the evidence behind the
"reverse-direction asks the templates do not serve" reading in C-014. The
`software` half of that is now partly confounded.

The Author's category description for `software` was
*"The techniques a piece of software implements"* — written from the software's
point of view. But the anchor in that stratum is always a **Technique**, and the
gold is always the **software ids** that implement it. The description asked for
the opposite of what was scored. One of v1's two software questions came back
accordingly malformed — *"What techniques does T1555.005 (Password Managers)
implement?"* — which asks for techniques, names a technique as though it were
software, and was then graded against a list of software ids. It is not a
question the system could have answered correctly.

`groups` avoided the trap only by accident: its description names both
directions (*"…or the groups using a technique"*), so the Author could pick the
right one. Every other category description matches its gold direction; this was
the only one that did not.

**What resolves it:** the description is corrected as of 2026-08-19, so any bank
generated from here on is unaffected. For v1, re-read the two `H-SW-*` questions
and their judgments and determine how much of the 0.06 is a malformed question
rather than a retrieval failure. n = 2, so this cannot move much on its own —
but it bears directly on whether the `software` category belongs in the
evidence for the directional-cliff claim at all.

**Cost:** ~1 hour, no new runs — the questions and judgments are on disk.
**Blocks:** the `software` half of C-014's supporting evidence.
**From:** EXP-2026-08-007 follow-up work; found while automating the Author.

**Status: ANSWERED, negatively (2026-08-23).** Working in
`EXP-2026-08-002/RESULTS.md` §AMENDMENTS A-1. The malformation is confirmed and
**contributed none of the loss.** `H-SW-01`, the malformed one, scored **0.10**;
`H-SW-02`, which is well-formed ("Which software has been observed implementing
T1005?"), scored **0.02**, and Arm F scored it 0.00. Mean 0.06, reproducing the
recorded figure. The well-formed question scored *five times worse* — its
170-item gold is simply harder to partially hit than a 4-item one.

Both failed by the same directional mechanism: `describe` returned the anchor
and a facet **count** for the reverse `USES` edge and never expanded it. The
grader noted the count was visible in both cases. So the system could see the
relationship existed and could not follow it.

**`software` stays in C-014's evidence, and the reading is stronger than
before:** the directional cliff no longer rests on a question a reviewer can
dismiss as broken. It rests on `H-SW-02`.


### Q18 — Should the evidence reader accept column shapes the templates do not emit?

**Why it matters:** it is the one ambiguity in C-012, the study's headline. The
evidence reader dispatches on the column combinations the templates produce, so
a free-form query returning `group_id`+`group_name` and nothing else normalises
to nothing however correct the query and the rows it returned. Seven of the
LLM-query arm's thirty questions failed that way in EXP-2026-08-008.

**Two defensible readings, and they lead to different papers.** Either the
reader's coupling is an artifact of our harness and the baseline should be
measured without it; or guaranteeing that a query's output is consumable is a
genuine property templates provide, and the arm should wear it. The experiment
reports both (0.5000 raw, 0.5739 crediting every reader failure) so the
conclusion holds either way — but a paper has to pick one framing and defend it.

**What resolves it:** either a generic normaliser keyed on `<entity>_id` /
`<entity>_name` conventions rather than on template shapes, measured as a
secondary arm; or an explicit written decision in `DECISIONS.md` that the
coupling is part of what is being compared.

**Cost:** ~1 day for the generic reader, or an afternoon for the decision.
**Blocks:** how C-012 is phrased in the paper. **From:** EXP-2026-08-008 §7.

**Status: DECIDED, and narrowed rather than closed (2026-08-23).** **D-025**
takes the second reading: the coupling is part of what C-012 compares, because a
template library's value is not only that the query is correct but that its
output is consumable by the pipeline that has to read it. EXP-2026-08-008
reports both numbers permanently — **0.5000** raw and **0.5739** crediting every
reader failure — and the conclusion holds either way, which is the only reason
the decision is affordable. If a future result ever turns on which number is
quoted, D-025 must be revisited rather than leaned on.

The coupling is now enforced rather than asserted:
`utils/specialists/tests/test_evidence_contract.py` pins, in both directions,
that the `<entity>_id` columns the Cypher builder emits are exactly those the
normalizer dispatches on, and pins the branch ordering as well.

**What stays open, in a narrower form:** *what would the free-form arm score
against a convention-keyed reader?* That is a question about the baseline's
ceiling, not about whether C-012 holds, and it is worth running — it is deferred
because changing what the baseline *is* mid-study is worse than not knowing.


### Q19 — Can two graphs be federated on meaning when they share no identifier?

**Why it matters:** every federated result on record joins ATT&CK to CAPEC on a
*shared identifier* — the same ATT&CK ID appearing in both catalogues. C-015's
refutation is explicitly scoped to "two catalogues whose identifier spaces do not
collide". That is the easy case, and it is the only case measured. The
ReliaQuest identity catalog (EXP-2026-08-011) shares **no identifier at all**
with MITRE, yet the two are obviously related in meaning: a `DC_SYNC` edge *is*
T1003.006, `ADD_KEY_CREDENTIAL_LINK` is the shadow-credentials family under
T1556, `SAME_FOREST_TRUST` bears on T1482. The analyst question ReliaQuest
actually has — *which ATT&CK techniques do the privilege-escalation edges in this
tenant correspond to, and what mitigations apply* — is a three-hop federated
question across two engines with no join key.

**Why it is not folded into EXP-2026-08-011:** the join would have to come from a
hand-built edge → technique crosswalk, which is a third source with its own
authorship bias and its own error rate. Running it inside the schema-transfer
experiment would confound transfer with crosswalk quality, and neither number
would survive review.

**What resolves it:** a separate experiment in which the crosswalk is a declared,
versioned artifact with its own dataset card, and the measurement is of the
federated answer given the crosswalk — so crosswalk error and federation error
are separable.

**Cost:** ~2 days, most of it authoring and reviewing the crosswalk.
**Blocks:** whether the surviving federation case (C-015's remainder — provenance,
licensing, staleness) can be joined by a *capability* argument as well.
**From:** EXP-2026-08-011 planning.


## Known weaknesses to state in the paper, not resolve

These are limitations to disclose, not questions to answer.

- **No baseline of any kind exists.** Every comparison is Ariadne against
  Ariadne. (D-005)
- **The gold set is small and fixed.** 120 questions, categories of 1–10 members,
  so one case moves a category mean substantially.
- **One model, one day.** An earlier Arm B on the relay's other model ran ~6×
  slower and was discarded.
- **Arm A's 120/120 splices two judge runs** — 118 pre-scan-fix verdicts plus 2
  re-judged — justified only because the other 118 artifacts were verified
  materially identical.
- **Execution accuracy is agreement with a pinned snapshot**, not with ground
  truth. An ingest error present in both is invisible.
- **The safety probe suite is 17 probes.** A 100% block rate over 17 probes is
  weak evidence of a strong property, and the suite itself found the one bypass
  that was subsequently fixed, so it partly grades against its own answer key.
  (C-008) **ADDRESSED (EXP-2026-08-016):** the suite is now generated, 240
  probes, and it found **15 live bypasses** the 17 never reached. All closed;
  240/240 after. State the 15 alongside the clean rate — the defects are the
  evidence that 17 was too few, and the rate alone teaches the opposite lesson.
- **No human ever graded an answer.** Every correctness figure in the study is
  machine-graded, and judge–human agreement was closed as will-not-do rather
  than measured (Q6). What bounds the grader instead is cross-model agreement
  (r = 0.9275), the measured overstatement of self-judging (C-009), and the
  grader's own 0.0050 re-run spread. State this plainly; it is the study's
  largest methodological gap and it is not recoverable with the resources
  available.
- ~~**There is no LICENSE file and no MITRE attribution notice.**~~ **Closed
  2026-08-18.** The repository is licensed Apache-2.0 (`LICENSE`, copyright
  Florida State University) with attribution in `NOTICE`, and `pyproject.toml`
  declares both. The remaining release blocker is archival identity (a DOI),
  not licensing.
