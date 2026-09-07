# Open Questions

Every follow-up from every `RESULTS.md`, plus the known weaknesses. This becomes
the future-work section and pre-empts the reviewer objections that are coming
either way.

Ordered by what blocks the most: **Q1 gates the value of everything else.**

**A question can now come from the literature, not just from a run.** Q23–Q26
were filed on 2026-08-26 from an external adversarial novelty audit
([`reports/2026-08-26-novelty-audit/`](reports/2026-08-26-novelty-audit/)). They
behave differently from the rest of this file: **none of them is answered by
measuring our own system.** Two are answered by reading somebody else's paper
(Q23, Q25), one by writing a paragraph we have all the materials for (Q24), and
one by a design decision with a circularity trap in it (Q26). They are here
rather than in a separate file because they block publication exactly the way a
missing experiment does — and because the audit's single most damaging finding
was a citation *we* had never opened.

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

**ANSWERED for the deterministic arms, and the question's premise was wrong
(EXP-2026-08-015, 2026-08-23).** "Re-run the arms" measures nothing on an
LLM-free path: both arms are byte-reproducible, so ten runs give ten identical
numbers. **Pipeline variance there is zero by construction** — a property to
state, not a quantity to estimate. The variance that exists is in *which anchors
were drawn*, and it is now measured over ten anchor-disjoint banks per
population, retrieval only, paired bootstrap (2000 resamples, seed 1729):

| population | templates | generic | difference | 95% CI |
|---|---|---|---|---|
| catalogue | 0.9900 (sd 0.0225) | **1.0000 (sd 0.0000)** | **−0.0100** | [−0.0233, **+0.0000**] |
| identity | 0.2392 (sd 0.0674) | 0.8514 (sd 0.0890) | **−0.6121** | [−0.6720, −0.5530] |

The first non-null `statistical_test` on an *arm comparison* in the record.

**Three things it settles.** (1) A single 30-question draw is a noisy instrument
on a foreign schema — ±0.07 is ordinary — and **not noisy at all** on the
catalogue, where the generic arm is 1.0000 on all ten banks. (2) The catalogue
retrieval metric is **saturated** and cannot price that gap; a judged metric is
required. (3) Resampling found a live template defect two fixed banks had hidden
through six experiments (Q22).

**What remains open, and it is now the whole of Q2:** the **LLM-in-the-loop arms**
(B, E, F, `llm_query`). They have genuine run variance, none has been run twice,
and nothing here touches them. Every figure quoting those arms is still n=1.

**The synthesis seam is now measured, and both levers failed (EXP-2026-08-019,
2026-08-24).** Three conditions × three repeats × 120 questions:

| condition | gold sd | fallbacks | per-question |
|---|---:|---:|---:|
| unseeded, 16 workers | 0.0207 | 21.3 | 65.1 s |
| **seeded**, 16 workers | 0.0212 | 14.0 | 53.0 s |
| **seeded**, 32 workers | 0.0373 | 28.3 | 85.5 s |

**H1 refuted: seeding does not reduce spread** (0.0212 against 0.0207). It was
never going to — temperature was already 0 everywhere graded, so there was no
sampling to remove, and the variance comes from **timeout and fallback**, which
is upstream of any sampling parameter. The seed stays because it costs nothing
and removes a real degree of freedom, but **must never be reported as a variance
reduction.**

**H3 refuted, and the actual finding is worse than the hypothesis.** Raising
workers 16 → 32 buys **19% wall clock** and costs a **61% rise in per-request
latency** and a **doubling of timeouts**. And because a timeout falls back to the
deterministic composer — which scores **0.8184** against the LLM's ~0.68 —
**failing more makes the arm score better**: r(fallbacks, gold) = **+0.62** over
all nine runs.

**At 32 workers roughly a fifth of the "LLM arm" is not the LLM arm.** That
generalises past concurrency: *any harness with a fallback to a stronger path
reports improvement when the primary path degrades.* Every LLM-arm figure in this
record should carry its engagement rate beside it.

**Practical answer to "is 32 safe":** yes for ungraded bulk work, no for a graded
arm. **And the binding constraint is not the concurrency ceiling — it is the
120 s read timeout**, which is the knob worth revisiting first.

**Still untouched:** the planner and specialist LLM seams. Q2 closes one of
three, and condition C (single worker) was deferred on cost, so how much a fully
serialised run would recover is unmeasured.

### Q22 — `capec_hierarchy_chain` returns nothing when the parent is already Meta

**Why it matters:** it is a live retrieval defect on the *catalogue*, found by
EXP-2026-08-015 and missed by every prior experiment.

The template emits a fixed two-hop chain —
`.out("CHILD_OF").as("parent").out("CHILD_OF").as("grandparent").select("ap","parent","grandparent")`
— and that `select` is an inner join over three positions. For a **Standard**
abstraction anchor whose parent is already **Meta**, there is no grandparent, the
select matches nothing, and the query returns **not even the parent the gold
asked for**. Three questions across two banks retrieved zero records
(CAPEC-466 → CAPEC-94, CAPEC-207 → CAPEC-22, CAPEC-182 → CAPEC-137).

**This is the outer-join class fixed in EXP-2026-08-004 and EXP-2026-08-006**, in
a template those fixes did not reach. holdout-v1's `H-ABS` anchors happened to
sit at Detailed level, three below Meta, so the chain resolved and the defect
stayed invisible — a sampling artifact, not a code change.

**What resolves it:** make the chain an outer join, exactly as the earlier fix
did, so a parent is returned whether or not a grandparent exists. **Cost:** hours
for the change; the real cost is the recorded-answer regression diff over both
banks that any builder change requires. **Blocks:** the catalogue half of C-023's
interval means "one defective template", and that should be a past-tense
statement. **From:** EXP-2026-08-015 RESULTS.

**Status: FIXED (2026-08-24).** Both ancestor hops are now `optional()`, and the
normalizer skips an "ancestor" equal to the anchor — `optional()` re-labels the
anchor into the parent slot when there is no parent, and without the guard a
top-level pattern would have been reported as its own ancestor.

**The regression diff is the part worth keeping.** Re-running all ten banks:
**15 of 300 answers changed and every one is `H-ABS-*`**, the kind this template
serves. Three went from empty to correct; the other twelve already scored 1.0000
and returned **identical ancestors**, differing only in record ordering.

`gold_in_evidence` for the template arm: **0.9900 → 1.0000, sd 0.0225 → 0.0000**.
The catalogue gap between the arms is now **exactly 0.0000** — it was entirely
this defect. Recorded in EXP-2026-08-015 §AMENDMENTS A-1.

**One methodological note.** The first diff reported all 300 answers as changed,
which was the differ, not the fix: `wall_s` and `timing_ms` are clock keys and
were not in the exclusion set. A regression check that flags everything is
indistinguishable from one that flags nothing — **strip timings before
comparing**, and treat a 100% diff as a bug in the comparison until proven
otherwise.

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

### Q23 — Does the paper that scooped C-008 actually contain the access-control layer?

**Why it matters:** it decides whether C-008 is **narrowed or cut**, and it is
the cheapest open question in this file — one PDF download.

Szlobodnyik, *Analytics* (MDPI) 5(3):25, DOI 10.3390/analytics5030025,
**published 28 July 2026**, peer-reviewed, open access, CC-BY. The 2026-08-26
novelty audit read it in full and reports that it contains, in one paper: a
six-category text-to-Cypher prompt-injection dataset from sixteen parameterised
templates; **Unsafe Operation Rate** and **Attack Success Rate**; a validator
that intercepts unsafe Cypher and recovers a read-only schema-consistent query;
a jury-of-models faithful/malicious/diverged classifier; five foundation models
against six training-free defence baselines; **and an identity-provider-driven
access-control layer limiting execution to the authorised portion of the graph
schema, both role-based and attribute-based.**

**Independently re-checked on 2026-08-26, and one row did not confirm.**

| element | status |
|---|---|
| Citation, date, single author, venue, DOI, CC-BY | **confirmed** (DOI resolution, Semantic Scholar) |
| Six injection categories | **confirmed verbatim** — instruction override, role confusion, output-format manipulation, misleading prompts, chained instructions, obfuscation |
| Unsafe Operation Rate + Attack Success Rate | **confirmed** |
| Validator flagging malicious/unsafe/divergent Cypher with corrective feedback | **confirmed** |
| GPT-4o, DeepSeek R1, Claude 3.5 Sonnet, Qwen 2.5 Coder 32B | **confirmed** |
| **Role/attribute-based access control over the schema** | **NOT CONFIRMED — mdpi.com and SSRN both 403 our fetcher** |

The unconfirmed row is the one that matters. It is the mechanism that maps onto
**our own schema-boundary refusal** — the part of the safety gate that rejects a
query touching a label the source card does not declare. If it is in the paper,
C-008's territory is occupied as thoroughly as the audit says and the claim
drops to a paragraph. If it is not, we have a real surviving mechanism rather
than four narrow slivers.

**What resolves it:** download the PDF and search it.

```bash
curl -L -o /tmp/szlobodnyik-2026.pdf "https://www.mdpi.com/2813-2203/5/3/25/pdf"
```

Then grep for `access control`, `role-based`, `attribute-based`, `authorized`,
`schema`. Answer three further things while it is open, all of which change the
size of what survives: **what schema does it evaluate against** (the audit says
the Neo4j text2cypher corpus with a movie-domain example — if so, no security
taxonomy, and that delta holds); **is enforcement at the database privilege
level or only prompt-and-validator level**; and **are the injection probes
model-authored** (if so, our analyst-authored 240-probe suite is a real delta
and it dovetails with C-021).

**One more thing to settle:** an SSRN version exists
(`papers.ssrn.com/sol3/papers.cfm?abstract_id=5669662`) whose **posting date is
unknown**. If it predates 28 July 2026, the "four weeks before the audit"
framing is wrong and this work was findable earlier — which matters, because it
turns "unlucky timing" into "our literature watch was not running".

**Cost:** under an hour. **Blocks:** C-008's novelty status, and the security
section of any submission. **From:** 2026-08-26 novelty audit, Part 2 Q8.

---

### Q24 — Why does our failure distribution run opposite to the only comparable published one?

**Status: ANSWERED (2026-08-31). It does not run opposite — the comparison was
invalid, and our own figure did not reproduce.**

Two corrections and two survivors, drafted in
[`paper/sections/09-failure-localisation.md`](paper/sections/09-failure-localisation.md).

**Correction 1.** Re-running the classifier over EXP-2026-07-002's committed
artifacts gives **28** non-CORRECT of 120 and **4** unfaithful — not 26-of-36
and 2. The 28 matches that experiment's own verdict counts; the 36 is most
likely an earlier judge run, the same species as `C-018`.

**Correction 2, and the real answer.** Our `unfaithful` class was being compared
against Leung et al.'s entire `Generation` stage — our narrowest category
against their broadest. Their Generation covers both *stating what you did not
retrieve* and *failing to state what you did*; we split those into `unfaithful`
and `projection_gap`. Mapped like-for-like, Arm B's generation share is
**42.3%**, **between** their DragonBall-EN 32.7% and CLAPnq 76.4%. There is no
contradiction to explain.

**Survivor 1.** Within the generation stage, under-statement outnumbers
fabrication **7 to 4**, and the two have **opposite fixes**. Their taxonomy
cannot draw that line.

**Survivor 2, and it needs no appeal to their pipeline.** Across three arms of
our own study: Arm A **0** failures, Arm F **10**, Arm B **28** — and **15 of
the 18 failures added by substituting an LLM planner are retrieval-side**, a
class empty under an authored plan.

**What is still unrun:** Leung et al. validate attribution by intervening on the
blamed stage and re-running. We do not. That is the cheapest experiment that
would raise this from a plausible localisation to a validated one.

**Why it matters:** this is the **highest-value piece of writing left before any
submission**, and it is writing, not an experiment. C-016 is either the paper's
best finding or its worst liability, and which one depends entirely on whether
this paragraph exists.

C-016 says failures concentrate in **planning**, and that faithfulness failures
are a small minority — 26 of Arm B's 36 failures were planning or retrieval,
only **2** were faithfulness. The 2026-08-26 audit found the comparable
published measurement, and it disagrees.

Leung, Belbahri, Sui, Labach, Zhang, Rose & Cresswell, *Classifying and
Addressing the Diversity of Errors in Retrieval-Augmented Generation Systems*,
**EACL 2026 Long Papers, pp. 3185–3207, peer-reviewed.** They walk pipeline
stages in order and stop at the earliest error — the same mechanism — over 832
and 1,222 erroneous responses, and validate it by intervening on the weak stages
and re-running.

| stage | DragonBall-EN | CLAPnq |
|---|---|---|
| Chunking | 29.7% | — |
| Retrieval | 31.5% | 21.7% |
| Reranking | 7.1% | 2.0% |
| **Generation** | **32.7%** | **76.4%** |

Generation — their faithfulness stage — is the plurality in one setting and the
overwhelming majority in the other. **Our claim does not merely lack a
comparison; it contradicts the only one that exists.**

**What resolves it:** a written structural argument, not more data. The
materials are already in hand and there are at least three distinct threads:

1. **Their pipeline has no planning stage.** A pipeline that cannot fail at
   planning cannot attribute failures to it, so the comparison is not
   like-for-like and the two distributions are over different partitions of the
   same total. State this first and state it precisely — it is the strongest
   thread and the easiest to get sloppy about.
2. **Their retrieval is over text chunks; ours is over a structured store with
   a safety gate and a claim verifier.** A generation stage that receives
   verified claims rather than retrieved passages has far less room to be
   unfaithful — which is C-005, already measured, and it predicts exactly the
   direction of the difference.
3. **Ours is measured on an arm where a language model plans.** Arm B is the
   condition; the deterministic path has no planning failures to find. Be
   explicit about which arm the 26-of-36 comes from, because a reader who
   assumes it is the shipped system will read the whole claim wrong.

**Do not stop at "different pipelines".** That sentence is what a reviewer
expects and it concedes the point. The finding is that *adding a planning stage
moves the failure mass into it*, which is a stronger and more interesting claim
than the one C-016 currently makes — and it is testable against their own
numbers rather than merely asserted beside them.

**Cost:** a day of writing, plus re-reading their appendix. **Blocks:** C-016,
and the framing of D-027's primary contribution. **From:** 2026-08-26 novelty
audit, Part 2 Q3.

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

**Status: RESOLVED BY RELABELLING (2026-08-24), not by re-scoring.** The
operator's call, and it is the right one: these are not performance results that
happen to be perfect, they are **properties true by construction**, and the
honest fix is to say so rather than to manufacture a number below 1.0.

Both now carry the treatment C-007 already uses for query validity: **stated as a
design guarantee, never quoted as a score.** Source recall is 1.0 because the
planner matches sources against declared card labels and the corpus contains only
questions it can route; schema adherence is 1.0 because a plan that fails the
deterministic self-eval gate is not emitted. Neither can fall below 1.0 without a
*defect*, which makes them **regression detectors, not measurements** — and that
is genuinely useful, just not as evidence of quality.

**The exclusion is still a real scope limit and stays disclosed:** the corpus
omits bare id lookups, so neither figure covers them. What changes is that the
1.0 is no longer offered as though it were earned.

### Q8 — Three of the four `goals.md` end-to-end metrics are self-consistency checks

Provenance correctness, analyst inspectability, and no-fabrication all measure
whether the system's outputs cohere with its own retrieved records. A confidently
wrong pipeline passes all three. **From:** EXP-2026-07-009 §5, D-001.

**Status: RESOLVED BY RELABELLING (2026-08-24)**, the operator's call, and the
same treatment as Q7 and C-007.

All three are **design guarantees, not performance results**, and reading 1.0 is
what they are *supposed* to do:

| metric | why it cannot be below 1.0 without a defect |
|---|---|
| provenance correctness | every record is emitted through `emit_record`, which requires the executed query and a record id — an unprovenanced record cannot be constructed |
| analyst inspectability | the executed query, the plan and the per-claim verdicts are attached to every answer unconditionally |
| no-fabrication | claims are composed *from* retrieved records, so an unsupported claim is unconstructible — proved directly by EXP-2026-08-014, where all four verifier gates cut **zero** claims from 888 |

**The objection this question raised stands and is now the headline rather than a
footnote: a confidently wrong pipeline passes all three.** They say the answer is
traceable, not that it is right. Only the fourth metric —
`cross_source_answer_accuracy`, graded against gold — speaks to correctness, and
it is the only one of the four that may be quoted as a result.

**What changes:** the three are reported as guarantees with the defect they would
catch named beside them, and are **never summed or averaged with the fourth**.
What does not change: they remain genuinely useful as regression detectors, since
any of them dropping below 1.0 is a real bug.

### Q9 — Is the failure-terminus classifier general, or shaped by this one pipeline?

Its finding — 26 of 36 failures were planning/retrieval, only 2 faithfulness —
contradicts the widespread assumption that LLM pipeline failures are
hallucination failures. But it has been applied to exactly one system and its
class ladder mirrors that system's stage boundaries. **What resolves it:** apply
it to a GraphRAG pipeline, a text-to-Cypher pipeline, and an agentic traversal
system; report what fraction falls through to `other`. **Blocks:** C-016.

### Q25 — Close the five coverage gaps the novelty audit disclosed about itself

**Why it matters:** the audit's negative findings are load-bearing — C-022,
C-024 and half of C-025 rest on "not found". It disclosed exactly where its own
search was thin, and **the thin spot is the one that already caught us once**.

Five gaps, in descending order of what they could cost:

1. **CEUR-WS workshop volumes were never enumerated directly.** General web
   search indexes them poorly, and **our closest known competitor is a CEUR
   workshop paper**. Sweep ESWC 2026 and ISWC 2026 workshop proceedings by hand.
   **Watch RAGE-KG 2026 specifically** — the Kurniawan/Kiesling/Ekelhart group
   has now stated in *two consecutive papers* that comprehensive evaluation is
   future work, which is C-025's artifact, promised publicly, by an active
   group.
2. **Four primary template-QA systems were never opened** — QUINT, TeBaQA,
   QAnswer/WDAqua, and SG-KBQA's results section (EMNLP 2025, currently 📄
   abstract-only). **TeBaQA claims portability "to a new domain… partially
   proven by evaluation over different KGs."** If that evaluation contains a
   precision-versus-coverage table across knowledge graphs, **C-023 narrows
   further** — and C-023 is one of the four measurements D-027 puts the paper on.
3. **The arXiv full-text API returned empty bodies throughout**, so no
   systematic field search (`abs:Gremlin` and similar) was possible. This is the
   main structural gap under C-024's negative.
4. **Two circulating statistics could not be traced** to any retrievable
   document — "planning… 33% of total errors" and "29% planning / 47% reasoning
   / 10% retrieval". Probable search-engine synthesis. **Recorded so nobody
   re-finds them and cites them**; same class as the phantom GraphRAG 13.4%
   number already in `RELATED_WORK.md`.
5. **Several arXiv PDFs had no machine-readable text.** Workaround that worked:
   `arxiv.org/html/<id>v1`.

**What resolves it:** items 1 and 2 are manual reading and are the only ones
that can change a claim. Items 3–5 are tooling notes; record them and move on.

**Status: ANSWERED (2026-09-06, overnight positioning sweep).** All five gaps
closed or declared. **Nothing killed a claim outright, and one claim had to be
rewritten anyway.**

1. **CEUR-WS enumerated directly** — the full master index loaded and scanned
   client-side, **12,764 rows**. Highest published volume Vol-4255 (3 Sep 2026).
   Only RAGE-KG volumes present are **Vol-3950** (2024) and **Vol-4079** (2025).
   ESWC 2026's seven workshop volumes contain no security-KGQA venue; ISWC 2026
   has **zero** volumes because the conference is still future.
2. **All four systems opened in full.** The TeBaQA cross-KG table we feared
   **does not exist** — one row and two sentences of prose. C-023 does not narrow.
3. **arXiv field sweep completed**, with quoting validated against a control so
   the zeros are real. `federation AND Cypher AND SPARQL` = **0**.
4. **Both circulating statistics resolved** — see below and `RELATED_WORK.md`.
5. Tooling notes recorded. The `arxiv.org/html/<id>v1` workaround held.

**What changed as a result:** C-022's loose reading is **dead** (`D-030`), C-024
narrows to foreground the two-query-language axis and must cite Emonet et al.
itself, C-025 gains a named near-miss and a **dated re-check**, and two
inherited citation errors are corrected.

**Where the negative is still thin, declared:** ACM DL and ResearchGate served
bot walls (WDAqua-core1 and TKDD 10.1145/3789506 unread); DBLP throttled after
~6 calls; IEEE Xplore and ScienceDirect paywalls not opened; no non-English
venues; industry systems (metaphactory, Stardog, Neptune tooling) could not be
checked from primary sources and **no claim is made about them**. One CEUR
series is flagged for a later pass: **Vol-4175, STIDS 2024** — the one venue
where a security-KGQA benchmark would plausibly land.

---

### Q27 — Re-check RAGE-KG 2026 in November, before camera-ready

**Why it matters:** this is the single dated, named, live risk to **C-025**, and
the sweep found it rather than closed it.

RAGE-KG 2026 runs **25-26 October 2026** at ISWC Bari. Notification was
21 August 2026 and camera-ready 1 September 2026, so **the acceptance decisions
already exist and the proceedings volume does not**. The accepted-paper list is
not public. The Kurniawan/Kiesling/Ekelhart group has now written in **two
consecutive papers** that comprehensive evaluation is future work — that is
C-025's artifact, promised publicly, by an active group, with a plausible third
instalment sitting in an invisible accepted set.

⚠️ **A trap to avoid when re-checking.** The RAGE-KG 2026 site already shows a
"Programme" for 25 Oct 2026 with 14 talks and `Paper` links — **every link points
at `ceur-ws.org/Vol-4079/`, the 2025 proceedings**, and diffing against that ToC
shows it is the 2025 paper set verbatim. **Stale carry-over. Do not read it as
2026 content.**

**What resolves it:** load the CEUR master index again once the volume appears
(historical lag: 2024 workshop -> published Apr 2025; 2025 workshop -> published
Oct 2025) and diff the ToC against Vol-4079.
**Cost:** ten minutes. **Blocks:** whether C-025 can be claimed at all.
**From:** 2026-09-06 positioning sweep, §2.

**Cost:** a day for the CEUR sweep, half a day for the four papers.
**Blocks:** the confidence level on C-022, C-024, C-025; possibly C-023's
narrowness. **From:** 2026-08-26 novelty audit, Part 8.

---

### Q26 — Should the banks emit the executable gold query?

**Why it matters:** it is the difference between C-025 being a gap we
*documented* and a gap we *fill* — and D-027 keeps a benchmark-first framing
live specifically pending this answer.

The audit's recommended novelty sentence claims we contribute *"the first
question set over MITRE ATT&CK and CAPEC that pairs natural-language questions
with executable gold queries scored by execution-based correctness."* **We do
not have gold queries.** A bank entry carries:

```
question, expected_template (a template NAME), task.seed_ids,
assertions.must_include_related, ex_gold.expected   # computed ANSWERS
```

Gold **answers**, computed independently from raw STIX and CAPEC XML rather than
through the ingest pipeline — which is a genuinely good property and the right
answer to benchmark rot — but **no executable Cypher or Gremlin string
anywhere**.

**The gold query is constructible.** Template name plus seed identifiers
determines the emitted query exactly; that is what makes the deterministic arms
byte-reproducible in the first place. Emitting it is close to mechanical.

**What resolves it:** decide, then do or don't.

- **In favour:** it converts C-025 from `unsupported` to a fillable claim; it is
  the cleanest gap the audit found; execution-based scoring against a live store
  is what every text-to-Cypher benchmark has and no security question set does;
  and it makes the resource usable by people who do not run our pipeline, which
  is the difference between a benchmark and an artifact.
- **Against, and this must be answered honestly rather than waved through:** a
  gold query emitted *by the system under test* is co-authored gold in exactly
  the sense C-021 measures. **Publishing our own queries as gold and then
  scoring ourselves against them would be the most circular thing in the
  project.** Any gold-query release needs the query validated against the
  computed answer independently — the query is gold only if executing it
  reproduces gold that was derived from the raw files, which we can check
  mechanically and which is the whole defence.
- **Also against:** it deepens the coupling C-023 says is conditional. A gold
  query in *our* template's shape is not neutral between the template arm and
  the schema-derived arm, and a benchmark that quietly favours one of our own
  arms is worse than no benchmark.

**Cost:** days for the emission; the real cost is the independent validation and
the framing. **Blocks:** C-025, and whether D-027's alternative framing becomes
primary. **From:** 2026-08-26 novelty audit Part 4, and
`reports/2026-08-26-novelty-audit/POINTERS.md`.

**Update 2026-09-01 (EXP-2026-09-001).** The schema census removes the "against"
argument's sharpest edge and adds a new argument in favour.

*Against, weakened.* The objection was that a gold query in **our template's
shape** is not neutral between the template arm and the schema-derived arm. The
census supplies an alternative shape that is neither: a
`(subject, predicate, object)` triple derived from the raw sources, with no
knowledge that Ariadne has templates at all. A query serialized from a census
path and validated against gold computed independently from the raw files is
co-authored by neither arm. The circularity trap is avoidable; it was not
obvious before that it was.

*In favour, strengthened.* The census shows the resource would cover **33 edge
types where the current banks reach 12**, plus 12 unused facet properties. A
released benchmark at 36% shape coverage would have been a thin contribution.

*Still open, and unchanged:* whether we do it. **What the census does NOT
settle** is whether Ariadne can answer the 21 never-asked shapes — coverage of
the question space is not coverage of system capability, and conflating them is
the single easiest mistake to make with this number.

---

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

**Status: FIXED (2026-08-24).** And the diagnosis above was half wrong in a way
worth recording: it was **not** a weighting problem. Both sources matched exactly
**one** token — `group` — and `max()` broke the tie **alphabetically**, so
`identity` beat `attack` on the letter *i*. The identifier `t1059` was in the
request and counted for nobody, because the concept index is built from label and
relationship *names* and never from instance identifiers.

The fix is the one this question proposed, implemented schema-agnostically: a
request token whose **shape** matches a learned identifier scheme of a source
counts as an id-hit for it. Shapes are learned from each dataset's canonical
snapshot by `utils/specialists/schema/idscheme.py` (`T1059.001` → `t#.#`), so
**no MITRE string enters the router**, and a source with no learned schemes
scores nothing extra rather than wrongly.

| | before | after |
|---|---|---|
| *"Which group uses T1059.001?"* | routed `identity` alone, **0 records** | routed **`attack`**, 1 record |
| leak totals | 1/14 probes, 5 records | **unchanged** |
| catalogue regression | — | **0 of 300 answers changed** |

Inert where it should be, active only where two sources compete for a generic
word. **Nothing was traded.**

**What is NOT fixed, and it is a different question.** `attack_tactic` — *"Which
techniques belong to the credential access tactic?"* — still routes to both and
pulls 5 identity records. It carries **no identifier**, so there is no
identifier-strength evidence to weigh; the tenant's 72 labels of ordinary IT
English match `credential`, `access` and `belong` on their own merits. That is
C-010's known limit: the planner is card-driven but not schema-*scale*-
independent.

**A second defect surfaced on the same probe and should not be confused with the
leak:** ATT&CK *is* routed there and returns **0 records** of its own. So the
answer is bad twice over, and only one half is a routing property. Filed nowhere
yet — it needs a look at what that question shape does on the ATT&CK side.

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

**Status: RESOLVED — reconnected, measured, KEPT AS AN INSTRUMENT
(EXP-2026-08-018, 2026-08-24).** The operator's instruction was to measure before
deleting and to run a series of tests rather than one check. Five ran, and the
decision rule was written into the protocol **before** any number was seen.

**The finding that justifies keeping it:** with a model proposing claims the
verifier cuts **32–36 per run** against **0** in every deterministic
configuration ever measured. `correlated` does almost all the work (92 against
`grounded` 19, `resolvable` 1, `cited` 0) — the model rarely emits an uncited
claim but does invent *relationships between* correctly-cited things.

**Why it is never a default:**

| | deterministic | LLM claims |
|---|---:|---:|
| gold-in-claims | **0.8184** | 0.6817 (sd 0.0207) |
| claims | 730 | 565 (−23%) |
| wall clock | **116 s** | 7,816 s (**67×**) |
| engaged | 120/120 | 96–104/120, the rest **120 s timeouts** |

`SYNTHESIS_LLM_CLAIMS` stays **default-false**. It is reconnected so that C-017's
central property is *falsifiable* — deleting it would have made that property
permanently untestable, which is the trap C-017 has been in since it was written.

**A caveat worth keeping:** the engagement rate is a property of the **timeout**,
not the model. 87–96% of fallbacks are 120 s read timeouts; a longer timeout
raises engagement and worsens cost. The two cannot be improved together.

---

## Environment and provenance

### Q11 — What is the served context window of `skynet`?

The repository has given three different answers and none is authoritative:
"unknown from the client side" (the honest one), "~64k" (an estimate never
verified against the server), and `48000` (a *client request* in `.env`, which
the server may cap lower). A client-side `num_ctx` request and a served
`max_model_len` are different numbers, and only the second is the context window.
**What resolves it:** read `max_model_len` off the model server.

**Status: ANSWERED (2026-08-24), by the operator, from the serving side.**

| | |
|---|---|
| Served context window | **96,000 tokens** |
| Served model | **MIRALABS/Ornith-1.5-35B-A3B-W4A16-SYM** |
| Concurrency at full context | **16** requests |
| Precision | **W4A16-SYM**, not FP8 (see Q12 — the model changed too) |

**All three earlier figures were wrong**, including the `48000` in `.env` — that
is a client request, and the server serves twice it. The two questions that
overflowed under the un-truncation profile (C-SCN-01, F-CWE-05) therefore
overflowed a 96k window, not a 48k one, which makes them a genuinely large
retrieval rather than a client misconfiguration.

**Provenance caveat the operator attached, and it matters more than the number:**
figures from the **test phase are unreliable**, because those runs used differing
parameters. Only recent runs are consistent. So the window is authoritative *now*
and must not be back-applied to any earlier recorded run — quote it for work
dated 2026-08-24 onward, and leave earlier runs recorded as unknown.

**Operational consequence.** 16 concurrent requests is the ceiling *at full
context*; short prompts (bank authoring, judging) run higher — the operator
authorised ~32 on 2026-08-24. A job whose prompts approach 96k must stay at or
under 16 or it will queue rather than parallelise.

**REOPENED 2026-08-31 — the model changed again and none of the above transfers.**
`skynet` now serves **`qwen38-27B-v2`** (see Q12). The 96,000-token window, the
16-way concurrency and the W4A16 precision were all properties of
`Ornith-1.5-35B-A3B` and **must not be carried over**. Still needed from the
serving side, in order of how much they break if wrong:

| | Why it is load-bearing |
|---|---|
| `max_model_len` | Two evaluation questions (`C-SCN-01`, `F-CWE-05`) already overflow at 96k. A smaller window silently changes which questions are answerable under the un-truncation profile |
| Concurrency at full context | Sets the worker ceiling for every judged run |
| Quantisation and shape (dense / MoE, active params) | Determines per-token latency, which determines whether the standing 120 s read timeout bites — and `EXP-2026-08-019` showed timeouts *inflate* measured quality (r = +0.62) |
| Is it a reasoning model, and its thinking budget | `.env` sets `SYNTHESIS_LLM_THINKING_BUDGET=4096`; a reasoning model truncates to empty below roughly 2048 and the failure presents as "LLM unavailable" |

Plan: [`../plans/2026-08-31-model-migration-qwen38.md`](../plans/2026-08-31-model-migration-qwen38.md) Step 0.

### Q12 — What quantisation is `skynet` serving?

Recorded as **unknown** rather than guessed. The model is Gemma 4 31B via vLLM.
Nothing in the study generalises to another model without re-running.

**Status: ANSWERED (2026-08-24) — and the answer is not the one this question
assumed, because the model itself changed.**

The operator's first answer was "FP8", corrected minutes later to the served
build:

> `MIRALABS/Ornith-1.5-35B-A3B-W4A16-SYM`

| | recorded in July | serving 2026-08-24 |
|---|---|---|
| Model | Gemma 4 31B | **Ornith-1.5-35B-A3B** |
| Quantisation | unknown | **W4A16-SYM** (4-bit weights, 16-bit activations, symmetric) |
| Architecture | dense | **MoE** (`A3B` ≈ 3B active of 35B) |

**Not FP8.** `W4A16` is 4-bit weight quantisation — substantially more lossy than
FP8, and a different kind of lossy: it degrades the weights while keeping
activations at 16-bit.

### The finding this actually produced, which is larger than the question

**The relay alias `skynet` has been repointed at a different model, and nothing
in the record noticed.** Seven July manifests record
`model: "vllm/gemma-4-31b@unknown"  # the relay alias 'skynet'`. That alias now
resolves to a different architecture, a different parameter count and a different
quantisation scheme.

So **an alias is not a model**, and every figure produced through `skynet` is
dated evidence about whatever was behind the alias that day:

* **July arm figures (B, C, D, E, F, G) are Gemma 4 31B** and must keep saying so.
* **Anything run from ~2026-08 onward is Ornith-1.5-35B-A3B-W4A16-SYM**, including
  every bank authored for EXP-2026-08-015 (`make_bank --model skynet`) and the
  identity banks.
* **The two are not comparable**, and no figure may be carried across the boundary
  without saying which model produced it.

This does not invalidate anything — the Author is never scored, and the arm
figures were self-consistent within their own runs — but it does mean the study's
"one model, one day" limitation is **stronger than recorded**: it is now *two*
models, and the record dated 2026-08-24 is the first place that is written down.

**ITS CONSEQUENCE IS NOW DISCHARGED (2026-09-05, `EXP-2026-09-006`).** The
damage this question did was not the quantisation itself — it was that
C-012, C-021 and C-022 rested on judgments from a model nobody could name.
Those 510 answers have now been re-graded under **two named families**,
`qwen38-27B-v2` and `gemma4-31B-mtp`, both identified by probe: zero contrast
sign flips, one arm-ordering reversal in 23 pairs on a pair neither grader
resolves. The rule below is unchanged and still binding; what changes is that
no current claim depends on breaking it.

**What to do with it:** state model, quantisation and date together, always.
Never write `skynet`. And the generalisation warning tightens rather than
loosens — a 4-bit weight quantisation is a long way from full precision, so a
result reproduced against the same weights at BF16 could legitimately differ.

**Still unknown, and now worth asking:** which model served the runs between the
July arms and 2026-08-24. The operator's "test-phase runs used differing
parameters" caveat (Q11) may in fact be describing a model change rather than a
parameter change.

---

## AMENDMENT, 2026-08-31 — a third model, and this time it was detected rather than disclosed

`skynet` now serves **`qwen38-27B-v2`**. It was found by probing rather than by
being told, which is the difference this amendment is really about.

| Era | Served model | How it was established |
|---|---|---|
| July 2026 | Gemma 4 31B | Operator, after the fact |
| ~August, start **still unknown** | **undetermined** | — |
| 2026-08-24 | `MIRALABS/Ornith-1.5-35B-A3B-W4A16-SYM` | Operator, after the fact |
| **2026-08-31** | **`qwen38-27B-v2`** | **`scripts/model_identity.py`**, from the response envelope |

**The question is now answerable without asking**, and that is the durable part:

```bash
uv run python scripts/model_identity.py
```

`GET /v1/models` is **not** enough — the relay answers `skynet` with
`upstream_model: "auto"` because it hot-swaps, and that is exactly how two swaps
went unnoticed. The only reliable identification is the `model` field on a
completion *response*, which names the weights that served it. The script also
reports when the relay's advertisement and its behaviour disagree, which they
currently do.

**The middle row is still the expensive one and it is now more expensive.**
`EXP-2026-08-007`, `-008` and `-009` — which carry **C-012, C-021 and C-022** —
were graded in the undetermined window. Those three claims are graded by a model
nobody can name. The cheapest repair is Step 2 of the migration plan: re-grade
the *saved* answers with the now-identified model, which changes one variable
and costs no pipeline run.

**What does not change:** the July and Sonnet-panel figures. The blind holdout
(`EXP-2026-08-002`) and the identity panels (`EXP-2026-08-011` A-7/A-9/A-10) were
graded by provider-hosted Sonnet agents and are untouched by any local swap.
That is now a practical argument for the cross-model panel, not only a
methodological one.

**Filed as a discipline change (`D-028`), not just a fact:** record the served
model automatically in `run_meta`, fail a judged run on a mismatch against the
manifest, and never write `skynet` in a result. Pinning is unavailable —
`qwen38-27B-v2` is not separately addressable on the relay — so detection is the
only defence.

### Q27 — The definitional rescue path declares a liveness-probe label as the record's type

**Status: still open, and now reproduced at scale.** EXP-2026-08-020's variant
bank reaches this path constantly — it is the same fall-through that produced
the catalogue dumps — and Arm 2's unanchored-abstention fix changes *what the
path does* without fixing *the label it declares*. The mislabelling stands.

**Why it matters:** it is a live mislabelling defect on the *catalogue*, and it
fires on exactly the questions C-021 says our banks never contain — the ones
that do not use the schema's own vocabulary.

**Found 2026-08-28 by asking what happens to a synonym.** Every one of these
returns an evidence record whose label is **`Analytic`**:

```
"How do I defend against T1176?"   primary=T1176  LABEL=Analytic
"Tell me about T1176"              primary=T1176  LABEL=Analytic
"What is T1176?"                   primary=T1176  LABEL=Analytic
```

**T1176 is a `Technique`.** Its own returned properties say so
(`stix_type: attack-pattern`), and the query that fetched it matched
`(n:Technique)`.

**The chain, all four steps individually reasonable:**

1. No request token matches a label or relationship name, so the keyword router
   builds nothing (`drafter.py::_match_card`).
2. The **definitional rescue** fires, because the request mentions an entity id
   (`drafter.py`, "no schema term matched; routed a name lookup").
3. It sets the sub-question's entities to `card.expected_probe_labels()[:1]`.
4. `expected_probe_labels()` is `sorted(self.node_labels)[:2]`
   (`cards.py:74`) — **a liveness-check helper**, whose docstring says
   *"a couple of labels the content probe expects to exist when loaded."* For
   ATT&CK, `sorted(...)[0]` is **`Analytic`**, alphabetically.

That arbitrary label becomes `resolved.primary_label()`, which
`normalizer.py::_label_for` prefers over **both** the id-prefix table below it
and the fallback. The id-prefix table would have got this right: `T\d{4}` →
`Technique` is already in `_DOSSIER_ID_LABELS`.

**It is the same species as I-9**, and `_label_for`'s own docstring is the
warning: *"the label is carried into the evidence record and read back out by
synthesis, so a DEVICE named `srv000` was being asserted to the judge as an
ATT&CK Technique."* The constant was fixed; the rescue path re-introduces the
defect by a different route.

**What resolves it:** the rescue path is asking "which labels prove this
database is loaded" when it means "what kind of thing might this be". Options:
**(a)** pass **no** entities and let `_label_for` fall through to the id-prefix
table — the smallest change and it makes the right answer reachable; **(b)** have
the rescue path resolve the label from the learned identifier scheme
(`idscheme.scheme_of`), which is the schema-agnostic version and works on a
source with no prefix table; **(c)** leave the label empty rather than guess,
which is the honest answer and the one consistent with `admits()` returning
`undetermined`. **(b) then (c) as a fallback** is probably right, but this needs
a decision rather than a patch — see D-025's reasoning about what a record is
allowed to assert.

**Cost:** hours for the change; the real cost is the recorded-answer regression
over both banks that any normalizer change requires
([[ariadne-recorded-answer-regression]]). **Expect zero diffs**, and that is
itself the finding — the banks cannot reach this path.

**Blocks:** nothing measured today, which is the uncomfortable part. **It
strengthens C-021 rather than threatening it:** the defect is unreachable from
120 catalogue questions and 30 blind ones because all 150 were written by people
who knew the vocabulary. A question set that avoided the schema's own words
would have found it immediately. **From:** conversational probe, 2026-08-28.

---

### Q29 — The `groups` category licenses a question in a direction too wide to grade

**Status: ANSWERED, negatively (2026-09-01), the same day it was filed.** The
worry does not reproduce. **Gold-set width does not predict judged score.**

Measured over **3,479 judgments** joined to the width the committed banks
declare, across 126 distinct questions and 32 runs:

| contrast | value | sign-stable? |
|---|---:|---|
| pooled r(width, correctness) | −0.0272 | — |
| within-cell r, 38 (run, arm) cells | **−0.0068** (sd 0.208) | negative in 16/38 |
| wide − narrow at width > 10 | **+0.0020** ± 0.0284 se | negative in 12/31 |
| wide − narrow at width > 20 | −0.0136 ± 0.0353 se | negative in 8/17 |

Every contrast is a coin flip. By width bin, correctness is flat and slightly
*rising*: 0.8994 (width 1), 0.8851, 0.8980, 0.9156, 0.9053, and **0.9680** for
the 21–50 bin — the widest bin but one scores highest of all. The widest ATT&CK
categories are at or near ceiling: `A-SW` at median width 55 scores 0.9356,
`A-GRP` at 25.5 scores 0.9820, `A-TAC` at 17 scores 0.9956.

**The one bin that looks like the worry is a different defect.** The 51+ bin
sits at 0.8417, and all of it is `H-SW-02` (169 gold items) in `holdout-v1` —
the *pre-fix* blind run. The same question on the current builder
(`outerjoin-holdout`, `composerfix-holdout`) scores **1.000**. That is the
binding/direction regression from EXP-2026-08-005, not width.

**Two things follow, and the second matters more.**

1. **No fan-out cap at generation time.** The census's askable threshold
   (p90 ≤ 50) is not where the score moves, because the score does not move.
   Capping would remove questions for a reason the data does not support.
2. **The existing banks cannot settle it, and the reason is the census's own
   finding.** There are **6 questions above width 20 in the entire corpus, and
   3 above 50.** The banks are too narrow to test width because nobody ever
   wrote a wide question. So width becomes a **designed, stratified variable in
   the new bank** rather than a constraint on it — the new bank should span the
   width range deliberately, and answer this properly at n where it can.

**The incidental finding is the one to remember.** The obvious way to run this
analysis is to read `gold_expected` off each judgment, where it sits next to the
score. That field is a **grader output** — `judge_answers.py` asks the model how
many gold identifiers the question expected — so correlating it with the same
model's score from the same call measures the grader, not the question. It is
also unstable: **140 of 1,679 (run, case) pairs disagree with themselves across
passes.** The first version of this analysis used it and reported
r = −0.0352 with a −0.0466 narrow-vs-wide contrast at threshold 10, both of
which vanish against real gold. `verify_grader_field_unused` now walks the AST
of any module claiming to compute width, and a test proves the guard fires.

Sixth instance of the project's recurring pattern: a procedural artifact that
moves a number in a consistent direction and is invisible until something is
checked against an independent source.

Reproduce: `uv run python scripts/gold_width_effect.py`.

---

<details>
<summary>Original filing, kept for the record</summary>

**Filed 2026-09-01 from EXP-2026-09-001 (I-2).** The schema census measures
fan-out in both directions for every edge type. `Group -[uses]-> Technique` has
a **p90 forward fan-out of 63** — the 90th-percentile group uses 63 or more
techniques.

`ATTACK_CATEGORIES["groups"]` reads *"The techniques a named group uses, **or**
the groups using a technique"*. It licenses both directions, and the first has
answers too large for a grader to score meaningfully. `Mitigation -mitigates->
Technique` (p90 79) is the mirror case and is safe only because the category
happens to ask it in reverse; `Technique -kill_chain_phase-> Tactic` (reverse
p90 113) is safe only because the category says "the tactics a technique belongs
to" and not the reverse.

**Two of the three widest edges in the graph are asked safely by accident.**

**Why it matters — it is an attribution problem, not a scoring problem.** A
question whose gold set has 63 members will score badly. That badness reads as a
*system* failure in every arm comparison we have run, when it is a *question*
defect. We cannot currently say how many such questions are in the committed
banks, because no bank records the gold-set size distribution against the
grader's score.

**What resolves it:** cheap, and it should be done before any expansion.
1. Compute gold-set size for every question in every committed bank; correlate
   with judged score. If the correlation is flat, this is a non-issue and the
   question closes. If it is negative, some of what we have called system
   failure is question width.
2. Then decide the policy: cap gold-set size at generation time, or grade
   wide-answer questions with a set-overlap metric instead of a judged one.

**What it does NOT license:** editing the category text in
`holdout_protocol.py`. Frozen banks were drawn from it; changing it silently
would break the provenance of every bank that cites it. Any change is an
amendment with a new protocol version, not an edit.

**Blocks:** the interpretation of every judged arm comparison that used a
`groups` question. **From:** EXP-2026-09-001 ISSUES I-2.

</details>

---

### Q28 — The name index's accept thresholds are unfitted, and must be tuned on a held-out split

**Status: ANSWERED, negatively (2026-08-31).** The protocol was executed exactly
as specified below — split by gold question via `sha256(case_id)` parity, drawn
before any fitting, 63 tune / 57 report, with the harness filtering the frozen
half out so a sweep cannot reach it.

**The score threshold turned out not to be the lever.** Correct and incorrect
resolutions overlap heavily on absolute score (medians 27.1 against 14.8, ranges
crossing) and barely overlap on **margin** — how far the leader is ahead of the
runner-up — at 1.72 against 1.08. The shipped default of 1.25 sat inside the
wrong-answer distribution. On the tuning half, margin ≥ 1.4 with **no score
floor** gave **12 right, 0 wrong**.

**It did not generalise.** Scored once on the frozen half: **17 right, 8 wrong**
— 68% precision, against 67% for the unfitted default. The margin medians that
separated cleanly when fitted (1.72 / 1.08) overlap when not (1.39 / 1.12).

So `ARIADNE_NAMESEARCH` stays off, and the reason is now measured rather than
suspected. **The wider result is the more useful one: had the threshold been
fitted against the whole bank, the reported figure would have been 12 right and
0 wrong, and it would have been an artifact.** That is the clearest evidence
this project has that the held-out discipline earns its cost.

The frozen half is now spent. Further threshold work needs a fresh split.
See EXP-2026-08-020 RESULTS §Step 6.

**Why it matters:** it is the difference between a component that works and a
router that helps. EXP-2026-08-020 Arm 3 measured the name index resolving **7
of 9** direct probes correctly — `SQL Injection`→CAPEC-66 over *Blind* SQL
Injection, `Software Extensions`→T1176 — and then, wired into routing, **gaining
3 questions at T3 while buying 11 wrong answers** across T3/T4/T5/T6.

`MIN_SCORE = 4.0` and `MIN_MARGIN = 1.25` in
`utils/specialists/schema/namesearch.py` were chosen **before any variant was
scored** and have never been fitted to anything.

**What resolves it, and what must not.** The obvious move is to raise both until
the wrong answers stop. **Doing that against the existing 579-variant bank would
convert the bank into a training set** and retrospectively turn every figure in
EXP-2026-08-020 into a training figure — committing, deliberately, the exact
co-authorship failure C-021 exists to measure, a week after measuring it.

So: **split the bank before touching a threshold.** Draw a tuning half and a
reporting half by case id with a committed seed, fit on the first, and report
only from the second. Cheap, and it is the only way a tuned threshold means
anything.

**Worth checking in the same pass:** whether the accept rule should differ by
tier of evidence rather than by score — an exact full-name match (which already
gets a boost) is a categorically different signal from a high BM25 sum, and
gating them on one scalar may be the actual mistake.

**Cost:** a day. **Blocks:** whether `ARIADNE_NAMESEARCH` can ever default on,
and therefore whether the T4/T5 retrieval gap is closable deterministically.
**From:** EXP-2026-08-020 Arm 3.

---

### Q13 — Two query templates are unreachable

`node_lookup` (Cypher) and `capec_lookup` (Gremlin) are not reachable from
`build()` or `expand()`. They are dead code and must not be counted as
capability. **From:** EXP-2026-07-011 ISSUES.md.

**Status: CLOSED (2026-08-23).** Both deleted. Plan 03 §3.3 had deferred this
behind the holdout freeze and called it a five-minute cleanup once the freeze
lifted; the freeze was discharged on 2026-08-09.

**Recounting mechanically caught a second error the audit had not.** The census
was wrong in *both* directions at once: inflated by these two dead templates and
deflated by four live ones, because the five generic primitives were added and
the README sentence never followed. It said "25 distinct, 17 Cypher, 11 Gremlin"
against a tree holding 29. It now reads **27 / 18 / 12**, derived by AST via
`derive_templates.py` rather than asserted in prose. The "19 exercised by the
120-question bank" half was correct and is unchanged.

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

**Status: ANSWERED, affirmatively — and the register simply never recorded it
(noted 2026-08-24).** EXP-2026-08-013 phase 2 built exactly the artifact this
question specifies: a **declared** identity-edge → ATT&CK-technique correspondence
(13 edge types carry a technique, 8 explicitly do not), versioned as its own
declaration rather than inferred, so crosswalk error and federation error stay
separable — the condition this question set.

Measured on 64 blind questions authored from a five-field view of one anchor,
audited before the run to contain **0 gold identifiers**, and half negative on
purpose:

| kind | n | schema-derived | templates |
|---|---:|---|---|
| bridge-technique | 24 | **0.8333** | 0.0000 |
| bridge-refusal | 12 | **1.0000** | 0.4167 |
| identity-control | 12 | 1.0000 | 1.0000 |
| bridge-mitigation | 16 | 0.3398 | 0.2081 |
| **overall** | 64 | **0.7724** | 0.3176 |

**Two graphs with no shared identifier were federated on declared meaning, and
the join does not over-fire:** on the twelve anchors no mapped edge touches, the
schema-derived arm names **no technique at all**, 12 of 12. The template cascade
scores **zero** on the technique questions and falsely names a technique on 7 of
those 12 negatives — the same "no template, so answer anyway" failure C-023
prices elsewhere.

**What is genuinely left, and it is narrower than the original question.**
`bridge-mitigation` at **0.3398** is the weak cell: naming the technique is one
hop, and carrying that technique across the engine boundary into ATT&CK to fetch
its mitigations is the second. The first hop works; the second is where two
thirds of the value is still missing. That is the three-hop case this question
described, half-answered.

**Also unclaimed:** the bridge is a *capability* argument for federation, and
C-022 currently rests only on non-modification. Whether the bridge strengthens
C-022 or deserves a claim of its own has not been decided.


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

---

## AMENDMENT, 2026-09-06 — five record defects surfaced by the venue readiness scoring

Filed from [`paper/venue-readiness-2026-09.md`](paper/venue-readiness-2026-09.md),
which scored the record against the tier checklists in
[`paper/venue-report-2026-09.md`](paper/venue-report-2026-09.md). **None of these
needs a run.** All five are record-integrity defects: the measurements exist and
the record misstates them. They are filed here rather than fixed silently because
three of them were quoted into an external brief before anyone noticed.

`make validate-research` is green through all five, which is itself the finding of
Q32.

### Q30 — `EXP-2026-09-008` is `planned` and holds a finished result

**Why it matters:** Its manifest still carries the scaffold title `<one line, the
question this answers>`, `status: planned`, empty `metrics.values`,
`supports_claims: []`, and a template `RESULTS.md`. `INDEX.md` renders it as a
placeholder row. Meanwhile `data/ceiling-resolution.json` carries the
pre-registered verdict — `gemma4-31B-mtp` emits **one** distinct value on the
ceiling band, `gemma-4-26B-it` emits **two** (`{0.5, 1.0}`) and additionally
**inverts** the mid/low ordering (0.6435 low against 0.6239 mid), `qwen38-27B-v2`
is the only usable one. `OUTLINE.md` §12 already depends on this and says it "has
no home yet". The most transferable finding in the project is, to anyone reading
the record properly, invisible.

**What resolves it:** Fill the manifest from `data/`, write `RESULTS.md`, hash the
`data/POINTERS.md` rows, link `supports_claims`, regenerate `INDEX.md`.
**Blocks:** `OUTLINE.md` §12; the journal-tier item J7. **From:** venue readiness
scoring, journal tier. **Cost:** one day.

### Q31 — ~~`EXP-2026-09-007`'s manifest and RESULTS are stale against their own `data/`~~ **ANSWERED 2026-09-07**

**Why it matters:** The manifest records `llm_query_holdout: 0.4031`,
`generic_minus_llm_query_holdout: 0.2515`,
`deterministic_minus_llm_query_holdout: 0.0831`, and `RESULTS.md` §4 states
"gemma never graded `llm_query`'s holdout answers". `data/judged-two-family-final.json`,
written 2026-09-06 03:27 under `EXP-2026-09-008`'s phases B/B2/B3, completes the
instrument: **3 arms × 288 questions × 2 grading positions × 2 grader families =
3,456 judgments**, with qwen at 0.6546 / 0.4862 / **0.4039** and gemma at 0.6464 /
0.4320 / 0.3678. Two files in the same folder disagree about whether the second
family graded a third of the experiment.

**ANSWERED 2026-09-07, and the answer was larger than the question.** Adjudicated
by recomputing from all **3,456 raw judgment sidecars** rather than by choosing
between two summary files. The recomputation reproduces
`judged-two-family-final.json` exactly, so **four** manifest metrics were wrong,
not three: `llm_query_holdout` 0.4031→**0.4039**,
`deterministic_minus_llm_query_holdout` 0.0831→**0.0822**,
`generic_minus_llm_query_holdout` 0.2515→**0.2507**, and — unlisted in this
question — `second_family_generic_minus_deterministic` 0.2053→**0.2143**, a
third-decimal error of 0.009.

**Ownership resolved against the guess above.** The figures belong to
`EXP-2026-09-007`, not `-008`: they are that experiment's own holdout instrument
and `judged-final.json` carries the dev half in a field named `dev`. Corrected in
place with `AMENDMENT A-1`; `-008` is untouched.

**Cause, which the question did not anticipate.** The manifest was populated from
`judged-final.json`, whose own fields declare it incomplete —
`grader_second: "position 1 only, deterministic+generic"` and
`not_measured: ["gemma on llm_query holdout answers", …]`. **Every wrong value lay
inside what that file said it had not measured.** The error was disclosed when it
was made and survived anyway, which puts the defect in the reading rather than
the writing.

**Two further defects surfaced while resolving it**, both recorded as amendments:
the entire dev-half row of the paper's §6 table lived outside the research record
in `docs/evaluation/composition/bank/two-grader-judged.json` (A-2), and contrasts
must be computed from unrounded means rather than by subtracting published
four-decimal figures (A-3).

**No conclusion moved.** Every corrected value keeps its sign and significance
verdict. **Cost:** four hours, not one day.

### Q32 — ~~"enforced by CI" is false, in four places~~ **ANSWERED 2026-09-07**

**Why it matters:** `AGENT_INSTRUCTIONS.md` principle 3, `OUTLINE.md:121`,
`paper/checklists/conference-full-paper.md:169` and
`paper/checklists/eacl-2027-demo.md:59` all assert that every number in the paper
traces to an `EXP-` ID. `.github/` **does not exist**;
`utils/research_record/validate.py` checks eight structural conditions, opens no
paper prose, and contains no numeric scan. `install_hooks.sh` calls CI "the real
gate" and CI was never built; the hook is opt-in and `--no-verify`-bypassable.
The live violation is `OUTLINE.md:44` — `+0.0822` and `+0.0643` carry no `EXP-`
ID and match no manifest's `metrics.values` (see Q31). `EXP-2026-09-002`'s
`ISSUES.md` already records one uncaught instance of the same failure.

**What resolves it:** Either build the check (paper-prose float scan against the
union of `metrics.values`, plus a `.github` workflow), or delete the claim from
all four files. **Deleting it is honest; leaving it is not.**
**Blocks:** journal item J4; the reproducibility statement at every tier.
**From:** venue readiness scoring. **Cost:** half a day either way.


**PARTLY ANSWERED 2026-09-07.** `scripts/verify_paper_numbers.py` now exists and
does what the four assertions claimed was already happening: it extracts every
numeric literal from the paper and checks each against the metric values in every
`manifest.yaml`. On first run it reported **17 untraced numbers**; after tracing
them it reports **0 across 86 figures**.

It is **not** CI and the assertions are still false as written. It runs on
demand, not on push, and it is deliberately a **review list rather than a gate** —
a number it cannot trace is a question, not a verdict, because years, counts in
prose and figures quoted from other papers legitimately do not trace.

**What it found, which is the argument for keeping it:** four wrong recorded
metrics (`Q31`), an entire table row living outside the research record, and a
rounding-convention error introduced while fixing those. None changed a
conclusion; all were findable by a reviewer.

**CLOSED 2026-09-07 by taking the honest option.** All four assertions now
describe the check that exists rather than one that does not:
`OUTLINE.md:121`, `AGENT_INSTRUCTIONS.md` principle 3,
`checklists/eacl-2027-demo.md:59` and `checklists/conference-full-paper.md`
(both places, one struck through with the correction beside it). A
`make verify-paper-numbers` target was added so the check is discoverable rather
than folklore.

**The stronger option was not taken and is not pretended to be.** There is still
no CI. Building it costs a day and is worth more than the hour this took;
`AGENT_INSTRUCTIONS.md:384` still carries the unticked box for it. What changed
is that the repository no longer claims to have it.
**Also unaddressed:** the checker reads only `docs/research/experiments/*/manifest.yaml`.
Numbers living under `docs/evaluation/` are invisible to it, which is exactly how
the dev-half row went unnoticed — see `EXP-2026-09-007` A-2.

### Q33 — retracted federation figures are still in circulation

**Why it matters:** `EXP-2026-08-009` `RESULTS.md` amendment A-1 (2026-08-31)
withdraws `−0.0334` and `+0.0000` — "the specific numbers should not be quoted",
the exact zero being an artifact of one pass by an unidentifiable model — and
replaces them with `−0.0587` (bank 19) and `−0.0520` (bank 20) over eight named
`qwen38-27B-v2` passes. The withdrawn pair was nonetheless the pair quoted into
the Part A venue brief on 2026-09-06 and it appears in the resulting report's
reasoning.

**What resolves it:** A single sentence in `CLAIMS.md` under C-022 and in
`OUTLINE.md` §7 naming the re-graded pair as the quotable one, so the next
person copying a number copies the right one.
**Blocks:** `OUTLINE.md` §7. **From:** venue readiness scoring. **Cost:** half a day.

### Q34 — `n_runs` undercounts on two manifests, and the field means two things

**Why it matters:** `EXP-2026-08-018` and `EXP-2026-08-019` both ran
`--repeats 3` and report metrics at `n: 3` with non-zero sd; both manifests
record `n_runs: 1`. Separately, every manifest with `n_runs ≥ 2` —
`EXP-2026-08-021` (5), `EXP-2026-08-022` (4), `EXP-2026-09-006` (2),
`EXP-2026-09-007` (2) — is counting **grading** sessions or positions, not system
runs. A reviewer auditing the field will conclude that **no experiment in the
record runs the system three times with seeds recorded**, and on the field's
current definition they are right. The defensible half is that the model-free
arms are byte-reproducible (`EXP-2026-08-015`: re-running "would have produced
ten byte-identical numbers"). The undefended half is `llm_query`, the one arm
with real variance and the one arm never repeated.

**What resolves it:** (a) correct the two manifests and note why in their
`ISSUES.md`; (b) state in the schema docs whether `n_runs` counts system runs or
grading passes, and add a separate field if it must count both; (c) three seeded
`llm_query` runs, which is the only *experiment* on this list.
**Blocks:** A-tier item A5; B-tier item B4 — the single thing separating the
project from a B-tier full paper. **From:** venue readiness scoring.
**Cost:** (a) and (b) one day; (c) days of machine time.
