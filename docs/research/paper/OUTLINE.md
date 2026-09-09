# Paper Outline

**Working title:** *When do hand-written query templates beat schema-derived
construction? A controlled study over three graph schemas and two query
languages*

> **Rewritten 2026-08-31.** The previous outline was written on 2026-08-06 against
> [`../audit-2026-08-03.md`](../audit-2026-08-03.md) §7 Path 1, and it led with
> **C-003 — "the hand-written templates are where the accuracy lives" — which is
> now `refuted` in [`../CLAIMS.md`](../CLAIMS.md)**. It also listed C-012's
> baseline and C-014's coverage cliff as not run; both have since been run. This
> file was planning a paper built on a claim the project's own experiments
> overturned, and that is the defect this rewrite exists to fix. See
> [`../audit-2026-08-31.md`](../audit-2026-08-31.md) §9 item 7.

**Framing** (`D-027`, and the 2026-08-26 novelty audit Part 4): *the architecture
is the method section, not the contribution.* Mediator-wrapper federation is
twenty-five years old; "templates rather than free generation" is a named family
in KBQA since 2015; earliest-failing-stage attribution is published prior art
(Leung et al., EACL 2026); read-only enforcement on generated graph queries is
published prior art (Szlobodnyik, *Analytics*, July 2026). **What is unoccupied
is the measurement.** A system that generates no queries with a language model is
a different *instrument*, not merely a different implementation — it is what
makes the comparisons below isolable at all, because there is no stochastic
query-writing step to confound them.

---

## The contribution, in one sentence

Four controlled measurements a generation-based architecture cannot make, three
of which are null or negative results, over three graph schemas and two query
languages — plus the question-set resource, conditional on `Q26`.

## Section plan

| § | Section | Claims | Status |
|---|---|---|---|
| 1 | Introduction — cross-language federation as a measurement instrument, not as a system claim | C-024 | ✅ Framing decided (`D-027`). Prose unwritten |
| 2 | Related work — federation, text-to-graph-query, template families, error attribution, benchmark authorship | C-024 | 🟢 **Unblocked 2026-09-06: `Q25` is closed.** CEUR-WS enumerated (12,764 rows), all four template systems opened in full, arXiv field sweep with a validated control, ten nearest neighbours in [`../RELATED_WORK.md`](../RELATED_WORK.md). **Still no prose — this is now the first thing to write.** Must cite Emonet et al. ourselves and carry a defensive sentence separating federated *learning* from federated query execution |
| 3 | System — plan → route → retrieve → verify → compose, and where the LLM seams are | C-007 | ✅ Documented. Say plainly that the shipped system is deterministic |
| 4 | Experimental design — the arm matrix, nine question populations, the grading protocol and its limits | C-009, C-021 | ✅ One `PROTOCOL.md` per experiment |
| 5 | **Templates versus schema-derived construction, across schemas** — the primary result | **C-023**, C-010 | ✅ `EXP-2026-08-007`, `-008`, `-011`, `-015` |
| 6 | **Templates versus an LLM writing the queries** | **C-012** | 🟡 **Evidence complete and the claim is now the weakest of the three.** Four measurements: dev/qwen **+0.1147** [+0.0653,+0.1645], dev/gemma **+0.0696** [−0.0024,+0.1450], holdout/qwen **+0.0822** [+0.0362,+0.1308], holdout/gemma **+0.0643** [−0.0080,+0.1333]. **Positive under both grader families on both halves; statistically solid under one of two.** Write it that way, and do **not** lead the paper with it |
| 7 | **Federated versus merged** — the architectural null, and the structural cost that survives it | **C-022** (rewritten `D-030`), C-015 (refuted) | 🟡 **Claim rewritten 2026-09-06 — its null was false.** SPLIT-RAG and FedV-KGQA both build merged and split conditions and report accuracy, and disagree about the sign. The strict reading (heterogeneous live stores, separate engines) survives. **This section must answer why our result is neutral when SPLIT-RAG's is 17.6 Hit points** |
| 8 | **Co-authored benchmarks overstate their systems** — priced, and localised | **C-021** | ✅ `EXP-2026-08-007`, `-008`, `-010`, `-020` |
| 9 | Failure localisation | C-016 | 🟡 **Mechanism scooped; finding contradicts the only comparable distribution.** Blocked on `Q24`, which is one day of writing and has been open since 2026-08-26 |
| 10 | The coverage cliff — what the design costs off its own vocabulary | C-014, C-001 | ✅ `EXP-2026-08-002`, `-020`. Record identity falls to **0.0000** on 104 paraphrased questions |
| 11 | Limitations | — | ✅ [`../OPEN_QUESTIONS.md`](../OPEN_QUESTIONS.md) |
| **12?** | **Grader calibration — measuring the instrument before trusting it** | new | 🆕 **Has no home yet, and needs one.** `EXP-2026-09-008`: two of three local models cannot express a 0.03 difference near the ceiling, and one *inverts* the mid/low ordering. Three claim-level near-misses trace to it, including a tie-break one commit from publication as four arm-order reversals. **Decide: own section, subsection of §4, or separate short paper** |

## The argument, in order

1. **The instrument.** A federated QA system that dispatches native queries in
   two graph query languages to two live, unmerged stores, and that generates no
   query with a model. Cite Ozsoy (2026) for the problem statement — the project
   does not own it — EICopilot for NL-to-Gremlin, and AgCyRAG for the closest
   architecture. Claim priority on *implementing and measuring*, nothing more.
2. **Templates hold precision and provable abstention on the schema they were
   written for, and that advantage reverses.** Level with a schema-derived path
   on ATT&CK/CAPEC (retrieval gap exactly **0.0000** after the one defective template was repaired, `EXP-2026-08-015` A-1; judged indistinguishable); **−0.61**
   retrieval on a schema nobody wrote them for, where the template arm asserts
   unsupported content in **82%** of blind answers rather than declining.
   **This is the primary result and it replaces the refuted C-003.**
3. **But do not therefore generate your queries.** An LLM given the real schema,
   resolved seeds, the gate's constraints and a repair loop scores **0.5000**
   against the cascade's **0.9467** on the same unseen questions. The choice is
   not templates-versus-models; it is *authored* versus *derived* structure,
   with generation losing to both.
4. **Federating buys no accuracy over merging** — merged minus federated
   **−0.0587** and **−0.0520** over eight named grading passes (`EXP-2026-08-009`
   A-1; the first pass's −0.0334 / +0.0000 is withdrawn, the exact zero was a
   grader artifact), **−0.0500 / −0.0400** under a second family
   (`EXP-2026-09-006`), every reading inside the ±0.06 sampling floor at n=30 —
   two blind sets, one variable, no model in either arm. What survives is
   structural and countable: merging required editing **1,083 of 9,138 nodes**;
   federation edited none, and a third graph that could not be copied at all was
   loaded unmodified beside both catalogues.
5. **And every number above is inflated when the questions are yours.**
   **0.0483**, same system, same grader, same night — and the bias's dominant
   form is not a wrong answer but *a question the bank does not contain*.
6. **Here is the price of the whole design.** Record identity **1.0000 → 0.4667
   → 0.0990 → 0.0000** across five paraphrase tiers, and four of thirty
   questions about entities that do not exist answered with up to 558
   genuinely-retrieved, genuinely-cited records. *Reporting the trade rather
   than a victory is what inoculates the paper against its own honest finding.*

## What blocks each venue tier

**Workshop / demo:** nothing. [`../audit-2026-08-31.md`](../audit-2026-08-31.md)
§8.3 scores every axis at or above the threshold.

**Applied conference:** one axis — novelty defensibility — and it is closed by
writing rather than by measuring.

* **`Q24`** — why our failure distribution runs opposite to Leung et al. One day.
  Blocks §9 entirely, and §9 is one of the four legs of the contribution.
* **Cross-model re-grade** — `EXP-2026-08-007`, `-008` and `-009` were graded by
  the local relay, whose weights are not determinable for that window
  (`Q12`). C-012, C-021 and C-022 all rest on it. See
  [`../../plans/2026-08-31-model-migration-qwen38.md`](../../plans/2026-08-31-model-migration-qwen38.md).
* **`Q26`** — whether the banks emit executable gold queries. Decides whether
  C-025 is a gap we documented or a gap we filled, and the novelty audit calls
  the resource *"may be the stronger paper"*.
* **`Q25`** — close the five coverage gaps the novelty audit disclosed about
  itself, RAGE-KG 2026 first.

**Archival:** add ≥3 runs per judged arm (`D-010` currently pins `n_runs: 1`),
the contamination control that has never been run, a published *external system*
baseline, and a second foreign schema. Not recommended on the current evidence,
and the reason is now novelty rather than evidence.

## The paper that may be stronger, and is not this one

The 2026-08-26 novelty audit's alternative: **the resource**. No existing
artifact pairs security-taxonomy questions with executable gold graph queries
scored by execution, and the most active competing group has twice declared
comprehensive evaluation to be future work. Blocked on `Q26`, and `Q26` carries a
circularity trap that must be answered rather than waved through — gold queries
emitted by the system under test, in its own templates' shape, are co-authored
gold in exactly the sense `C-021` measures.

## Rules for this outline

- Every number in the paper cites an `EXP-` ID. No orphan numbers.
  **Checked by `scripts/verify_paper_numbers.py`, on demand — not by CI.**
  It reported 0 untraced of 86 figures on 2026-09-07. It reads only
  `docs/research/experiments/*/manifest.yaml`, so a number living under
  `docs/evaluation/` is invisible to it (see `EXP-2026-09-007` A-2).
- Every claim appears in [`../CLAIMS.md`](../CLAIMS.md) with its status. A claim
  that is `unsupported` at writing time either gets an experiment or gets cut.
  **A claim that is `refuted` does not get argued around.**
- Every figure is generated by a committed script and promoted from an experiment
  into [`../figures/`](../figures/). Nothing hand-placed.
- Every model-dependent number states model, quantisation and date — never the
  relay alias. `skynet` has served three different models.
