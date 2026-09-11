# Open Questions

Every follow-up from every `RESULTS.md`, plus the known weaknesses. This becomes
the future-work section and pre-empts the reviewer objections that are coming
either way.

**Only what is still open lives here.** On 2026-09-09 every answered question was
moved verbatim, with its amendments, to
[`OPEN_QUESTIONS-ANSWERED.md`](OPEN_QUESTIONS-ANSWERED.md); a question marked
*PARTLY ANSWERED* below carries one line saying which parts are closed and where.
Question numbers are never reused, so the gaps in the numbering are deliberate.

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
(Q24 and Q25 have since been answered and are in the archive; Q23 and Q26 remain
below.)

## Index — what is still open

| ID | Question | Section | Blocks |
|---|---|---|---|
| Q2 | What is the variance on any of these numbers? | Blocking | any p-value about the `llm` / `gold_llm` arms (D-010) *(partly)* |
| Q4 | Where is the coverage cliff? | Blocking | C-014 — the open-ended, non-anchored regime is still unmeasured *(open)* |
| Q23 | Does the paper that scooped C-008 actually contain the access-control layer? | Blocking | C-008's novelty status; the security section of any submission *(open)* |
| Q9 | Is the failure-terminus classifier general, or shaped by this one pipeline? | Methodological | C-016 *(open)* |
| Q27 | Re-check RAGE-KG 2026 in November, before camera-ready | Methodological | whether C-025 can be claimed at all (dated: November 2026) *(open)* |
| Q26 | Should the banks emit the executable gold query? | Methodological | C-025; whether D-027's alternative framing becomes primary *(open)* |
| Q11 | What is the served context window of `skynet`? | Environment and provenance | the worker ceiling and the un-truncation profile for every judged run on `qwen38-27B-v2` (reopened 2026-08-31) *(open)* |
| Q18 | Should the evidence reader accept column shapes the templates do not emit? | Environment and provenance | the free-form baseline's ceiling (C-012's phrasing itself is decided, D-025) *(partly)* |
| Q30 | `EXP-2026-09-008` is `planned` and holds a finished result | 2026-09-06 amendment (record defects) | `OUTLINE.md` §12; journal-tier item J7 *(partly)* |
| Q35 | The rewrite stage buys T4/T5 record identity by doubling confident-and-wrong at the same tiers | EXP-2026-09-014 follow-ups | any future attempt to ship the rewrite stage *(open)* |
| Q36 | The five-slot intent form cannot express a federated question, and the understanding-gold does not specify one | EXP-2026-09-014 follow-ups | any federated figure from the rewrite stage; plausibly the ship decision *(open)* |
| Q37 | A stage that adds latency inside a bounded pipeline cannot be measured without saying which budget it ran under | EXP-2026-09-014 follow-ups | shipping the rewrite stage; the honest reading of any future LLM-arm figure *(partly)* |
| Q44 | The understanding-gold names edges the graph does not have | EXP-2026-09-015 | `EXP-2026-09-014`'s reading of the relation slot; any future slot-accuracy figure *(open)* |
| Q45 | Five CAPEC relationships are declared but not allowlisted; the generic arm scores 0.0000 on the 34 dev questions that need them | diagnostic 2026-09-09 | `C-023`'s margin; any generic-arm figure on CAPEC *(open)* |
| Q46 | A metric moved 0.0503 between sessions while both sessions reported near-zero internal spread | EXP-2026-09-015 A-7 | every cross-session comparison; the error bars used throughout *(open)* |
| Q47 | The `generic` arm silently runs model-free at the default timeout | EXP-2026-09-016 I-4, A-8 | the 2026-09-10 audit was wrong by its denominator: dev fallback is 0.43, not 0.04 *(partly)* |
| Q48 | The judge counts the abstention template's example ids as fabricated claims, hardest on the arm that abstains most | EXP-2026-09-016 A-6 | any judge-derived hallucination figure *(open)* |
| Q49 | Which intervention converts development-score headroom into better answers? | EXP-2026-09-017 | the repair programme's ordering; `EXP-2026-09-018` *(open)* |
| Q50 | Category and View seeds are rewritten into the attack-pattern namespace by the generic walk | EXP-2026-09-017 A-2 | 12.6% of the dev loss; every CAPEC hierarchy question *(open)* |
| Q51 | Two-hop requests collapse to the shortest schema path from the anchor | EXP-2026-09-017 A-2 | 30.9% of the dev loss; every D4 and D6 figure *(open)* |
| Q52 | A declared property filter reaches neither the query nor the composer | EXP-2026-09-017 A-2 | 13.2% of the dev loss; every D5 figure *(open)* |
| Q53 | The composer drops list-valued requested properties and never states an empty set | EXP-2026-09-017 A-2 | 5.9% of the dev loss; `C-017`'s construction claim *(open)* |
| Q54 | Two CAPEC properties the questions filter on were never parsed from the source | EXP-2026-09-018 Step 4 | 10 dev and 16 holdout filtered questions; part of Q52's slice *(open)* |
| Q55 | The Neo4j loader packs every non-core property into a JSON string, so no Cypher filter can see it | EXP-2026-09-018 Step 4 | every ATT&CK-side filter push-down *(open)* |

---

## Blocking — these gate publication

### Q2 — What is the variance on any of these numbers?

**PARTLY ANSWERED.** Closed: grader variance (EXP-2026-08-007), the deterministic arms (EXP-2026-08-015), the synthesis seam (EXP-2026-08-019), the rewrite seam (EXP-2026-09-014) and — after the paragraph below was written — `llm_query` (EXP-2026-09-009, three seeds, balanced sd 0.0089) and `generic` (EXP-2026-09-011, sd 0.0039 three-seed, superseded by the six-seed 0.0074). Still open: the `llm` / `gold_llm` arms and the planner and specialist LLM seams.

**Status: the LLM-arm half is ANSWERED (2026-09-08, EXP-2026-09-014), and the
answer is that the variance is small and that the question was measuring the
wrong thing.** Two arms, two serving instances of the same checkpoint, three
seeded runs each with the model cache cleared between them, on 301 variants:
population sd across runs is **≤ 0.0160 on every tier of R2 and 0.0000 on all
but one tier of R3**, and the two instances differ by at most 0.0063 anywhere.
Seed 1729 is recorded; every graded call is temperature 0.

The finding underneath it matters more than the number. The *first* attempt at
the same arms swung 0.0755 ↔ 0.1509 at T5 between two runs, and none of that was
the model: `ARIADNE_LLM_TIMEOUT_S=240` was dropping 31–38% of calls at 32-way
concurrency, and `PIPELINE_TIMEOUT_S=120` was charging the rewrite's latency
against the budget retrieval needed. **An LLM arm's spread is uninterpretable
without its call-failure rate beside it**, and a spread measured against a bound
is a measurement of the bound. Both are now recorded per run by
`scripts/rewrite_aggregate.py`.

What remains open here is the *other* arms: `llm_query`, `llm`, `gold_llm` have
still never been run more than once, and this result does not transfer to them —
it says the rewrite seam is reproducible, not that every seam is.

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
| catalogue | 0.9900 (sd 0.0225) | **1.0000 (sd 0.0000)** | **−0.0100** | [−0.0233, **+0.0000**] | *(superseded by EXP-2026-08-015 A-1: gap exactly 0.0000 after the Q22 fix)*
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

### Q4 — Where is the coverage cliff?

**Why it matters:** All 120 questions are anchored — every one names an entity or
an id. Nothing measures the regime where a template router is *weakest*. A paper
that reports the benefit of the design without its price will not survive review.

**What resolves it:** ~40 open-ended, non-anchored questions on which the router
is expected to fail, reported as the design's cost rather than hidden.
**Blocks:** C-014. **From:** EXP-2026-07-011 §7, the 2026-07-26 limitations.

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

## Methodological

### Q9 — Is the failure-terminus classifier general, or shaped by this one pipeline?

Its finding — 26 of 36 failures were planning/retrieval, only 2 faithfulness —
contradicts the widespread assumption that LLM pipeline failures are
hallucination failures. But it has been applied to exactly one system and its
class ladder mirrors that system's stage boundaries. **What resolves it:** apply
it to a GraphRAG pipeline, a text-to-Cypher pipeline, and an agentic traversal
system; report what fraction falls through to `other`. **Blocks:** C-016.

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

## Environment and provenance

### Q11 — What is the served context window of `skynet`?

**OPEN — reopened 2026-08-31.** Q12 and the 2026-08-31 model amendment this text refers to are in the archive; only the `qwen38-27B-v2` serving facts in the table at the end are still wanted, and the migration plan's Step 0 has never been recorded.

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

### Q18 — Should the evidence reader accept column shapes the templates do not emit?

**PARTLY ANSWERED.** Closed: the framing decision, D-025 (2026-08-23), enforced by `utils/specialists/tests/test_evidence_contract.py`. Still open: what the free-form arm would score against a convention-keyed reader — deferred, see the last paragraph.

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

*Q31–Q34 have since been answered and are in the archive. Q30 remains below,
followed by Q35–Q37, filed 2026-09-08 from EXP-2026-09-014 (see D-031, D-032).*

### Q30 — `EXP-2026-09-008` is `planned` and holds a finished result

**PARTLY ANSWERED (2026-09-06, commit 4eb9b91).** Closed: the title, `status: complete`, `metrics.values` and a written `RESULTS.md`. Still open: `data/POINTERS.md` has no hashed rows, `supports_claims` is empty, the primary metric name (`ceiling_band_fraction_at_1`) matches no recorded value so `INDEX.md` renders it "not recorded", the purpose / hypothesis / data / llm fields are still scaffold text, and `OUTLINE.md` §12 still says it has no home.

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

### Q35 — The rewrite stage buys T4/T5 record identity by doubling confident-and-wrong at the same tiers

**Why it matters:** EXP-2026-09-014 is the first configuration in this record to
move T4/T5 `records_exact` off 0.0000 — to 0.0880 and 0.1635, reproducibly. It
does so by converting abstention into answers (T5 abstention 0.7736 → 0.4465),
and **roughly half of the converted silence is an answer about the wrong
entity**: T4 `wrong_entity` 0.1321 → 0.2516, T5 0.1132 → 0.2453. Catalogue dumps
fall everywhere, so these are *specific* wrong answers rather than the
catalogue — the worse failure for a system whose value proposition is not being
confidently wrong.

The pre-registered gate watched **T6 only**, where the stage is clean and
improving (0.1111 → 0.0556). It should have watched the tiers where the stage
does its work. That is a lesson about writing gates, not only about this stage.

**What resolves it:** (a) a per-tier negative-control gate in any future ship
rule, not a T6-only one; (b) whether the gate can be made to abstain on the
specific picks that go wrong — the anchor slot is right 0.18–0.25 of the time at
T4/T5 against a recall@5 ceiling of 0.45–0.57, so the chooser, not the list, is
the constraint; (c) a decision about whether 0.16 right for 0.13 wrong is ever
an acceptable trade here, which is a product question and not a measurement.
**Blocks:** any future attempt to ship the rewrite stage. **From:**
EXP-2026-09-014. **Cost:** (a) an hour; (b) days; (c) the operator's call.

### Q36 — The five-slot intent form cannot express a federated question, and the understanding-gold does not specify one

**Why it matters:** split by bank at the clean budget, every gain the rewrite
makes is on **single-source** questions — unchanged at T1/T6, +0.023 at T2,
+0.243 at T3, +0.143 at T4, +0.229 at T5 — and federated questions get **none**
of it (T4 and T5 stay at 0.0000) while paying −0.105 at T2. The form has one
relation slot and a federated question is a chain, so the rewrite delivers the
first hop and the second hop's records are gone. Compounding it,
`slot_gold.json` records only an anchor for all 40 federated questions, so the
failure could not be scored at the slot level even if the form could express it.

Restricted to the single-source half the stage reaches 0.2286 at T5, against a
pre-registered bar of 0.25 — close enough that the federated half is the
difference between a stage that ships and one that does not.

**What resolves it:** either (a) the form grows a second hop (`then: IntentForm`)
and the understanding-gold grows the slots to score it — the two must happen
together or the change is unmeasurable; or (b) the stage refuses to rewrite a
question it cannot express, which is a structural predicate (≥2 datasets, one
relation) rather than a fitted threshold, and federated questions pass through
untouched. (b) is cheap, recovers the −0.105 at T2, and recovers no gain.
**Blocks:** any federated figure from the rewrite stage; plausibly the ship
decision itself. **From:** EXP-2026-09-014 (the limitation was recorded at its
Step 1, before any arm ran). **Cost:** (b) an hour plus a re-run; (a) days, and
a gold-authoring pass.

### Q37 — A stage that adds latency inside a bounded pipeline cannot be measured without saying which budget it ran under

**PARTLY ANSWERED.** Closed: part (a) — `--llm-timeout-s` and `--pipeline-timeout-s` now record both budgets in the command (EXP-2026-09-014). Still open: (b) and (c); D-032 keeps the stage off partly on (c).

**Why it matters:** the same arm, same weights, same canonical questions, scores
T1 0.4180 under the shipped `PIPELINE_TIMEOUT_S=120` and 0.4921 at 900 s — and
0.4921 is exactly the no-rewrite baseline, so the "regression" attributed to the
rewrite was the clock. The proof is that **0 of 106 deterministic-rung rows
differ across three runs while 20 model-rung rows with a byte-identical
canonical question return different records**. This is the third distinct
appearance of a bound producing a plausible wrong number rather than an error
(after the import-time budget freeze and the ignored `.env` value in
`llm_query`), and the second time the total-pipeline deadline has done it
(EXP-2026-09-013).

**What resolves it:** (a) record the pipeline budget and the call timeout in
every manifest that has a model in the loop — `--llm-timeout-s` and
`--pipeline-timeout-s` now put them in the command; (b) decide whether the
rewrite's latency should be charged against the question's budget at all, or
whether the stage should have its own; (c) if the stage is ever to ship, its
cost must fit inside 120 s, and today it does not.
**Blocks:** shipping the rewrite stage; the honest reading of any future LLM-arm
figure. **From:** EXP-2026-09-014. **Cost:** (a) done; (b) a design decision;
(c) unknown.

## Residuals re-filed from answered questions (2026-09-09)

When the answered questions moved to
[`OPEN_QUESTIONS-ANSWERED.md`](OPEN_QUESTIONS-ANSWERED.md), six loose ends
were still open inside their text. They are re-filed here as their own
questions so that nothing open lives only in the archive.

### Q38 — C-012's cost half is unmeasured

**Why it matters:** C-012 claims templates beat a model writing the queries "in
correctness *and in cost*". Every measurement so far is correctness; no wall-clock
or token cost for the `llm_query` arm has been recorded against the cascade.
**What resolves it:** one run of both arms with `wall_clock_hours` and token
totals in the manifest. **From:** archived Q3. **Cost:** hours of machine time.

### Q39 — Merging with colliding identifier spaces

**Why it matters:** the federated-versus-merged null (`EXP-2026-08-009`,
`EXP-2026-09-006`) was measured on two catalogues whose identifier spaces do not
collide, so it says nothing about the case merging is usually argued against.
**What resolves it:** a third source whose ids overlap a catalogue's, merged and
federated. **From:** archived Q5. **Cost:** days.

### Q40 — Intervention validation of the failure localisation

**Why it matters:** Leung et al. validate earliest-failing-stage attribution by
intervening on the weak stage and re-running; ours is a mechanical walk with no
such check, which a reviewer of §9 will ask for.
**What resolves it:** repair the planner on the localised cases and show the
attribution moves. **From:** archived Q24. **Cost:** a day.

### Q41 — `attack_tactic` returns zero ATT&CK records

**Why it matters:** noted while fixing the comparative routing rule and "filed
nowhere yet"; a template that returns nothing on its own catalogue is a coverage
hole the arm comparison silently pays for.
**What resolves it:** a failing test and a fix, or a recorded decision that the
template is retired. **From:** archived Q21. **Cost:** an hour.

### Q42 — Does the declared bridge earn its own claim?

**Why it matters:** `EXP-2026-08-013` phase 2 measured the bridge-mitigation cell
at 0.3398 and nothing in `CLAIMS.md` says what the bridge is claimed to do.
**What resolves it:** either a claim row with that experiment as evidence, or a
sentence in the paper's federation section saying the bridge is demonstrated,
not evaluated. **From:** archived Q19. **Cost:** an hour of writing.

### Q43 — Which model served the July–August relay window

**Why it matters:** `EXP-2026-08-007`, `-008` and `-009` were graded by a model
the relay could not name. The claims they carry have since been re-graded under
named models (`EXP-2026-08-021`, `EXP-2026-09-006`), so nothing quotable rests
on it, but the record still cannot say what produced those first passes.
**What resolves it:** the serving side's logs for 19–21 August, if they exist;
otherwise the record says "undetermined" permanently. **From:** archived Q12.
**Cost:** an hour, or never.

### Q44 — The understanding-gold names edges the graph does not have

**Why it matters:** 11 of the 36 `slot_gold.json` records that carry a full
`(anchor_label, relation, target_label)` name a relation undeclared between
their own two labels — `Group -[HAS_TECHNIQUE]-> Technique` where the snapshot
has `USES`, and three more of the same shape. `variant_harness.score_slots`
compares against the raw gold, so a system answering the edge the graph
actually has is scored wrong. Pooled `slot_relation` reads 0.4286 strict and
0.7273 graph-consistent on the same rows (`EXP-2026-09-015`, A2 run 1), and
`EXP-2026-09-014`'s conclusion that relation was the model's worst slot rests
on the strict column.

**What resolves it:** either repair the 11 records from the snapshot and re-run
both experiments' slot scoring, or decide the gold stands and make
`score_slots` accept any relation the snapshot declares between gold's own
labels. The second is cheaper and the first is more honest; it is a decision,
not a fix, because repairing gold after seeing a score is exactly the move the
split discipline exists to prevent. **From:** `EXP-2026-09-015` I-1.
**Cost:** an hour either way, plus a re-run.

### Q45 — Five CAPEC relationships are declared but not allowlisted, and the generic arm pays for it

**Why it matters:** `data/source_cards/capec.json` declares 21 relationship
types and gives `safety.allowed_edge_patterns` for 16. The Gremlin validator
treats a relationship missing from a *non-empty* allowlist as forbidden and
rejects the query before it runs:

```
pre-run gate rejected all drafts:
relationship 'HAS_ALTERNATE_TERM' has no allowed_edge_patterns in card
```

The five are `HAS_ALTERNATE_TERM`, `HAS_EXAMPLE`, `HAS_INDICATOR`,
`HAS_PREREQUISITE` and `REQUIRES_RESOURCE`. Each has exactly one unambiguous
endpoint pair in the canonical snapshot (`AttackPattern` to `AlternateTerm`,
`Example`, `Indicator`, `Prerequisite`, `Resource`), so the allowlist entries
are derivable rather than authorable.

**The asymmetry is the point.** The rule lives only in
`utils/specialists/gremlin/validator.py`; the Cypher validator has no equivalent
(grep count 0). ATT&CK declares *zero* `allowed_edge_patterns` and is therefore
unconstrained. So a card that is 16/21 complete is punished where one that is
0/21 is not, and the punishment lands on the arm that builds its query from the
schema at run time.

**Measured**, on the 284-question dev half (`post-repair-2026-09-03` scores,
recomputed 2026-09-10):

| | on the 34 questions touching those five | on the other 250 |
|---|---|---|
| generic | **0.0000** | 0.6649 |
| deterministic | 0.2076 | 0.5452 |

An absolute zero, on the arm that leads everywhere else. Repairing it would move
pooled generic dev recall from 0.5853 to between 0.6102 and 0.6649 depending on
how many of the 34 then answer.

**What resolves it:** either fill the five patterns *from the snapshot* rather
than by hand, or — better — have the Gremlin validator fall back to the
registry's derived triples when a card lags its data, so a stale card cannot
silently forbid a real edge again. Both change shipped gate behaviour and so
need the recorded-answer regression over both banks first.

**Disclosure obligation.** `EXP-2026-09-005` repaired defects in the
*deterministic* arm before comparing. This is the symmetric defect in the other
direction, and fixing it widens a gap `C-023` already reports in the generic
arm's favour. It must be reported as such, not as an incidental bug fix.
**From:** diagnostic of 2026-09-09. **Cost:** an hour, plus the regression.

### Q46 — A metric moved 0.0503 between sessions with zero within-session spread

**Why it matters:** `wrong_entity` at T4 reads 0.2516 in `EXP-2026-09-014` and
0.3019 in `EXP-2026-09-015`, same arm, same model, same 301 questions. Both
experiments report **sd 0.0000 or 0.0089** across their own three runs, so
neither could have predicted the gap from its own variance. The ablation
(`EXP-2026-09-015` `A-7`) shows the intervention accounts for −0.0189, in the
opposite direction, so the gap is environmental.

The known difference is that the CAPEC Gremlin fixture was empty at the start of
the second session and was reloaded before its arms ran. Preflight verifies node
and edge counts against the pinned manifest and passed, so contents agree;
traversal ordering after a fresh load need not, and this system reads ordered
results.

**Why it is worth an entry rather than a shrug:** every cross-session comparison
in this repository inherits it. Within-session spread has been used as the error
bar throughout, and here it understates the true run-to-run difference by more
than fivefold.

**What resolves it:** re-run one arm of `EXP-2026-09-014` on tonight's tree with
tonight's fixture and see whether it reproduces 0.2516 or 0.3019. If the latter,
the fixture reload is the cause and every figure spanning a reload needs the
caveat. **From:** `EXP-2026-09-015` `A-7`. **Cost:** one 20-minute arm.

### Q47 — Which `generic` figures were measured with the model seams live?

**Why it matters:** the `generic` arm enables LLM planning, an LLM specialist
seam and the multi-hop loop. At the 30-second default read timeout every one of
those calls times out silently, the pipeline falls back to its deterministic
path, and the run completes 284 questions in 14 seconds with **zero** model
calls instead of 1,169 seconds with 159. No error surfaces. The only trace is
`fallback_reason`, set on 198 of 284 answers in the degraded run against 39 in
the healthy one (`EXP-2026-09-016` `I-4`).

`scripts/holdout_run.py` sets `SPECIALIST_LLM_TIMEOUT_S=4096` only inside
`if arm == "llm_query"`, so a `generic` run through the shared script inherits
whatever the environment holds. `EXP-2026-09-005`'s recorded entrypoint passes
no timeout at all.

**This does not say a published figure is wrong.** `EXP-2026-09-010` established
that this arm's narrator does call a model, so at least that run was configured.
It says the arm's identity turns on a variable nothing in the call path sets.

**PARTLY ANSWERED — and the 2026-09-10 answer was arithmetically wrong.**
Corrected 2026-09-11 as `EXP-2026-09-016` `A-8`.

The audit divided each run's fallback count by the number of **files** in its
answer directory. Those directories also hold two or more judgment sidecars per
answer, so the denominators were three to five times too large. Against answer
denominators:

| run | answers | carrying a fallback reason | rate | as published |
|---|---|---|---|---|
| `EXP-2026-09-005` post-repair dev | 284 | 122 | **0.43** | 0.04 |
| `EXP-2026-09-007` holdout | 288 | 86 | **0.30** | 0.06 |
| `EXP-2026-09-002` expansion | 284 | 19 | **0.07** | 0.02 |

The two references were always over answers and are unchanged: degraded 0.70,
healthy 0.14. Two of the three runs behind `C-023` are therefore *above* the
healthy reference, and the dev run the 0.6569 comes from is nearer the degraded
end. **"No published figure is affected" is withdrawn.**

**The seam that failed is not the one this question is about.** All 227
fallbacks across the three runs read *LLM narrator unavailable* — a read
time-out at the 120 s `SYNTHESIS_LLM_TIMEOUT_S` default. None is a planner or
specialist failure, so the arm-identity fragility of `I-4` is untouched by these
rates: the specialist seam was live. What fell over is the narrator, which
`EXP-2026-09-010` fixed independently by raising the budget to 600 s with a
`degraded()` health check.

**What it costs.** `EXP-2026-09-017` `A-2` prices it on the dev half: the 49
questions where a narrator fallback is the only defect average 0.6964, and the
fallback / no-fallback split across all 284 is 0.6268 against 0.6795 — real, and
about a fifth of the largest defect. See `Q51`.

**Still open:** the fragility, not a figure. Nothing in the CLI, the arm
definition or the shared runner sets the timeouts that decide which arm runs,
and getting either wrong is silent. The guard is to assert a fallback-rate
ceiling over *answers* in the runner and re-run any arm above 0.14 rather than
publish it; `EXP-2026-09-018` pre-registers exactly that and is where it lands.
Data in `EXP-2026-09-016/data/generic_fallback_audit.json`, regenerated by
`data/fallback_audit.py`.

### Q48 — The judge counts the abstention template's example ids as fabricated claims

**Why it matters:** the deterministic abstention narrative ends *"…name it or
give its id (e.g. T1566, M1017, or CAPEC-98)."* The LLM judge records those
three illustrative identifiers in its `hallucinations` field. On
`EXP-2026-09-016`'s `llm_query` dev run, 160 answers were flagged and **157 of
the flags are exactly that trio**; every one of the 160 also abstained. Read
literally, the arm "hallucinates on 57% of its answers" — it prints a help
string.

It is present in committed runs, and the share rises with how often an arm
abstains:

| run | judgments | flagged | of which the boilerplate ids |
|---|---|---|---|
| `EXP-2026-09-005` deterministic | 3,407 | 118 | 35 (30%) |
| `EXP-2026-09-005` generic | 3,123 | 255 | 137 (54%) |
| `EXP-2026-09-007` holdout generic | 1,152 | 186 | 128 (69%) |

**The bias has a direction:** it penalises abstention, so it falls hardest on
the generic arm, which wins `C-023`. Correcting it helps the winner, which is
why it must be a recorded decision rather than a quiet fix.

**Not affected:** `fabricated_mapping` is 0 across the run, and the "zero
fabricated claims" line comes from the deterministic verifier, not this judge.

**What resolves it:** either strip the example ids from the abstention narrative
so nothing downstream can mistake them for claims, or have the judge ignore
identifiers that appear inside a recognised abstention. The first is cleaner and
changes shipped output; both need the recorded-answer regression. Then recount
every judge-derived hallucination figure in the record. **From:**
`EXP-2026-09-016` `A-6`. **Cost:** an hour, plus a recount.

### Q49 — Which intervention converts development-score headroom into better answers?

EXP-2026-09-017 re-aggregates the original paired judgments by question type and supplies a reproducible figure and scenario explorer. Two-hop questions offer the largest category contribution to the score deficit; selected property questions also show evidence present but omitted from the answer. The D6 template advantage in earlier prose describes retrieval, not judged correctness.

Next candidates: Q45's CAPEC card repair, a frozen-evidence requested-field rendering comparison, typed multi-hop intent with execution feedback, and joint entity/label selection (Q35–Q36). Test each against a concurrent control before combining them; use unchanged answers to measure grader drift. Any scoring repair (Q44/Q48) must be reported separately from capability gains. The existing holdout has been spent, so confirm the selected configuration on a newly sealed set. See the experiment's RESULTS for provenance and threats to validity.

### Q50 — Category and View seeds are rewritten into the attack-pattern namespace

**Why it matters:** the generic Gremlin walk builds its seed vertex ids through
`_gremlin_vertex_id`, which maps every CAPEC identifier into
`capec:attack-pattern:<n>`. A CAPEC **Category** or **View** vertex does not
carry that id, so the anchor binds to nothing and the walk returns zero records
before any traversal runs. The template path was given
`_capec_candidate_ids` — which tries all three CAPEC namespaces — in July
(`EXP-2026-09-003`); the walk never adopted it, and the docstring on
`_capec_candidate_ids` already describes this exact failure.

On the dev half this costs **12.6% of the 97.45 judged points lost**: all 21
Category-anchored questions and 18 of the 20 View-anchored ones returned zero
records, and the 23 non-D0 cases the mechanism owns average **0.4674** against
0.9675 for cases with no known defect. The holdout carries 30 such anchors.

**What resolves it:** switch the two walk call sites that build `ids` to
`_capec_candidate_ids`, keeping the anchor identifier-only (no `hasLabel` on the
seed), with a Category-seeded and a View-seeded walk test. **From:**
`EXP-2026-09-017` `A-2`. **Cost:** an hour, plus the model-free regression.
**Where it lands:** `EXP-2026-09-018` Step 1.

### Q51 — Two-hop requests collapse to the shortest schema path from the anchor

**Why it matters:** both generic builders resolve the plan's ordered `entities`
to a set of wanted labels, compute the shortest declared path from the **anchor**
to each label independently, and union the results around the seed. A request
shaped `Campaign → Software → Technique` is therefore answered with the
campaign's own techniques over the direct `Campaign –USES→ Technique` edge, not
with the techniques used by the campaign's tools. The intermediate is never
bound, so the answer is well-formed, cited, and about a different question.

This is the largest single mechanism on the dev half: **30.9% of the points
lost**, 56 questions at a mean of **0.4625**. The holdout carries 95 two-hop
questions. The plan's `entities` list is already in path order, so the input
needed to fix it is present and unused.

**What resolves it:** a `chain_paths()` that resolves the shortest hop sequence
between each *consecutive* label pair, and builders that emit one leg per pair
from the previous leg's variable while keeping the existing per-label star as
the fallback when a chain returns nothing. This is the minimum form of the typed
multi-hop chain of Guo et al. (EMNLP 2023); the execution-feedback replanning
they describe is not attempted. **From:** `EXP-2026-09-017` `A-2`. **Cost:** a
day, plus judged confirmation. **Where it lands:** `EXP-2026-09-018` Step 3.

### Q52 — A declared property filter reaches neither the query nor the composer

**Why it matters:** 47 dev questions and 105 bank questions carry a `filters`
entry in their spec ("…with high typical severity", "…rated Medium
likelihood"). The gold plan does not carry it, no builder emits a `WHERE` or a
`has()` for it, and the composer enumerates every record it was handed. The
answer lists the unfiltered set and the judge marks it incomplete or wrong.

**39 questions, 13.2% of the points lost, mean 0.6699.** The mechanism is
cheaper than the chain and is the same defect as `Q53` viewed from the query
side: nothing downstream of the planner knows what was asked.

**What resolves it:** bind the filter from the sub-question text against the
card's declared property names and the registry's observed values — nothing
guessed, an unbound slot stays unbound — then push a bound `eq` filter into the
query *and* apply it in the composer's enumeration, so retrieval and composition
agree. The alternative is to extend the bank task and plan schema with a
`filters` slot, which is more general and is a protocol change affecting every
arm. **From:** `EXP-2026-09-017` `A-2`. **Cost:** a day. **Where it lands:**
`EXP-2026-09-018` Step 4.

### Q53 — The composer drops list-valued requested properties and never states an empty set

**Why it matters:** `C-017` rests on the deterministic composer being able to
answer without a model. It cannot currently say two things. First, a requested
property whose value is a **list** — `x_mitre_platforms`, `x_mitre_contributors`
— is skipped by `_attribute_pairs`, so the value sits in the evidence and never
reaches a claim; the narrator usually says it anyway, which is why this looked
fine until 43% of the dev run's narrators timed out (`Q47`). Second, when the
anchor resolves and the requested relation returns nothing, the composer lists
whatever else came back and never states that the requested set is **empty** —
16 dev questions, mean 0.6406, 5.9% of the points lost.

**Why it is a construction question, not a bug report:** "the narrator usually
says it" is not a property `C-017` can rest on. Projecting the requested value
and asserting the empty set as a *verified claim*, with the executed query as
its proof exactly as an abstention carries one, is what turns a habit into a
construction guarantee.

**What resolves it:** project the requested property even when its value is a
list (joined, capped) while the generic attribute listing keeps skipping lists;
add an `absence` claim kind that the verifier admits only when its query ran
clean and returned no rows for that relation. **From:** `EXP-2026-09-017` `A-2`.
**Cost:** a day. **Where it lands:** `EXP-2026-09-018` Steps 4 and 5.

### Q54 — Two CAPEC properties the questions filter on were never parsed

**Why it matters:** `Typical_Severity` and `Likelihood_Of_Attack` are published
by CAPEC on every attack pattern — the pinned v3.9 catalogue carries **490** and
**345** of them, counted by this project's own discovery report
(`data/processed/discovery/capec-inventory.json`). Neither reaches the graph.
`utils/kg_builder/preprocess/capec_parse.py` reads an attack pattern's XML
*attributes* (`Name`, `Abstraction`, `Status`) and its `Description` child, and
these two are child *elements*, so they are silently dropped. The node's whole
property set in the canonical snapshot is `Abstraction`, `Status`, `description`.

This is the same class as the five node labels added on 2026-09-01
(`EXP-2026-09-001` A-2): a field the source publishes and the load discards, so
no question can reach it. It is not a retrieval defect, a composer defect or a
gold defect — the data is simply not there.

**What it costs.** 10 development and 16 holdout questions filter on one of the
two, and they are unanswerable as loaded. Their share of `Q52`'s slice is exactly
the part `EXP-2026-09-018` Step 4 could not bind: 30 of the 37 *answerable*
development filters bind, and the 10 that do not are all these. The D1 property
questions "how severe is CAPEC-543 typically" and "how likely is an attack using
CAPEC-32" are in the same position.

**What resolves it:** read the two elements in `normalize_attack_pattern`, like
`Description`. The change is small; what is not small is that it **changes the
graph**, so every arm's retrieval moves and `EXP-2026-09-018`'s reference
captures must be re-taken. That makes it a decision with a re-baseline attached,
not a quiet fix. **From:** `EXP-2026-09-018` Step 4. **Cost:** an hour, plus a
full re-baseline of the experiment's model-free references.

### Q55 — The Neo4j loader packs every non-core property into a JSON string

**Why it matters:** `utils/graph_loader/stores/neo4j.py` `node_merge_cypher`
writes exactly four real node properties — `id`, `name`, `attack_id`,
`stix_type` — and serialises everything else into a single `properties_json`
string. So `x_mitre_platforms`, `x_mitre_contributors` and every other field are
invisible to a Cypher `WHERE` clause. The derived schema registry reads the
canonical node files and correctly reports them as real properties; what it
cannot know is that the loader flattened them.

**How it was found, and why it matters that it was found this way.** The Step 4
filter push-down emitted `$v IN coalesce(m.x_mitre_platforms, [])` against a
store with no such property. That matches **nothing**, silently, and it cost 23
development questions their entire gold coverage in the first measurement of the
step. Neo4j does warn ("property key does not exist"), but the warning is
attached to the driver's result summary and nothing reads it.

**Not a Gremlin problem.** The CAPEC store keeps real properties, so the filter
push-down works there and loses nothing: `Abstraction` and `Status` filter
correctly on both banks.

**What it costs.** Every ATT&CK-side filter — 27 development and 33 holdout
questions — cannot be applied at retrieval. Step 4 therefore gates the Cypher
push-down on the four native properties, all of which are non-filterable for
other reasons, so today it refuses every Cypher filter. Composition still states
what a filtered answer was restricted to, but the set itself is unfiltered on
that side.

**What resolves it:** store scalar and list-of-scalar properties natively and
keep the JSON blob only for nested structures, which Neo4j cannot hold. Neo4j
stores lists of strings directly, so nothing is lost. Like `Q54` this changes the
graph and needs a re-baseline. A cheaper partial alternative is to project the
neighbour's `properties_json` into the generic queries and filter in the
composer, but that ships a full description blob per neighbour row and was
rejected on payload size. **From:** `EXP-2026-09-018` Step 4. **Cost:** a day,
plus a re-baseline.
