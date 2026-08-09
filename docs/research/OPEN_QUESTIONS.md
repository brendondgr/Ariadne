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
**Status: ANSWERED — coverage artifact, substantially.** EXP-2026-08-001 ran on
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

### Q2 — What is the variance on any of these numbers?

**Why it matters:** Every arm is `n_runs: 1` with seeds unrecorded. The two
headline deltas (−0.3568 and −0.1185) are differences of point estimates with no
confidence interval, and `statistical_test` is null in all eleven manifests.

**What resolves it:** Re-run the arms with recorded seeds — at minimum Arms A, B,
C, F, G — and compute a paired bootstrap on the two deltas.
**Cost:** ~1 hour wall clock plus ~600 judge agents. Operator's call.
**Blocks:** any claim stated with a p-value. **From:** D-010, every arm's §5.

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
- **There is no LICENSE file and no MITRE attribution notice.** The artifact
  cannot legally be released without them. Half a day of work; see
  [`paper/venue-targets.md`](paper/venue-targets.md).
