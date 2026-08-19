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

---

## Methodological

### Q6 — How well does the LLM judge agree with a human?

Cross-model and evidence-grounded, but still an LLM, and its verdicts are not
perfectly stable across runs. It occasionally penalised correct answers over
citation metadata. **What resolves it:** human κ on a 40-answer sample. A
reviewer will ask. **From:** D-002.

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
§5, §7.

**Known limitation to record with it:** a machine-authored bank is as *blind* as
v1 (same prompt, author never sees the code) but its phrasing will be less
varied than a human's. It is a regression and comparison instrument. A published
headline figure still wants human-authored questions.


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
  weak evidence of a strong property. (C-008)
- ~~**There is no LICENSE file and no MITRE attribution notice.**~~ **Closed
  2026-08-18.** The repository is licensed Apache-2.0 (`LICENSE`, copyright
  Florida State University) with attribution in `NOTICE`, and `pyproject.toml`
  declares both. The remaining release blocker is archival identity (a DOI),
  not licensing.
