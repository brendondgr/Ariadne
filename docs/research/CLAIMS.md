# Claims Ledger

Every claim the paper will make, and the evidence that supports it.

**Status:** `unsupported` | `partial` | `supported` | `refuted` | `cut`

This table is the highest-value file in this directory. It says, at a glance,
which claims can actually be made and which are currently vapour. Claims are
written **before** they are supported and marked `unsupported` on purpose — the
unsupported rows are the experiment backlog, and they are the honest answer to
"what is left to do".

A claim with no experiment ID is a claim that gets cut from the paper.

---

## Supported and partial

| ID | Claim (as it will appear in the paper) | Evidence | Artifact | Status | Notes |
|----|-------|----------|----------|--------|-------|
| C-001 | On an anchored, in-distribution question set, a fully deterministic pipeline — template routing, deterministic extraction, deterministic composition — answers at near-ceiling correctness with zero hallucinations. | EXP-2026-07-001 | fig-arm-comparison | `partial` | 0.9972, 120/120, 0 hallucinations. **Partial, not supported:** the catalogue was co-authored with the templates that answer it and there is no holdout, so this cannot yet be distinguished from a coverage artifact. Gated on C-013. |
| C-002 | Substituting LLM query planning for an authored plan is the dominant single source of correctness loss in the pipeline, with extraction and synthesis held constant. | EXP-2026-07-002, EXP-2026-07-003, EXP-2026-07-005 | fig-arm-comparison | `partial` | B − C = **−0.1185** within the post-fix run. **Do not quote −0.196** — that figure came from an earlier judge run and is not reproducible from the standing table. Recompute within one judge run before publication. See EXP-2026-07-003/ISSUES.md. |
| C-003 | The hand-written query templates, not the planner, are where the system's accuracy lives: disabling them costs roughly three times what substituting LLM planning costs. | EXP-2026-07-007, EXP-2026-07-002 | fig-arm-comparison | `supported` | G − F = **−0.3568** against B − C = **−0.1185**, a 3.0× ratio. Both deltas treated-minus-reference. The strongest result in the study. |
| C-004 | The deterministic path is not merely competitive with the LLM-planned path but orders of magnitude cheaper: the full 120-question catalogue completes in seconds rather than minutes. | EXP-2026-07-001, EXP-2026-07-006 | fig-arm-comparison | `supported` | 1.6 s (Arm A) against 1,019.7 s (Arm B) — a 637× ratio — and 533.4 s for Arm F. Wall clock, one machine, one run. |
| C-005 | Binding an LLM narrator to the *verified claim set* rather than to raw retrieved evidence removes the accuracy-versus-readability trade-off. | EXP-2026-07-003, EXP-2026-07-004, EXP-2026-07-006 | fig-arm-comparison | `supported` | Arm C (evidence-bound) 0.9690 with 8 PARTIAL → Arm D (claims-bound) 0.9917 with 0 PARTIAL → Arm F 0.9957 with 0 INCORRECT and full gold coverage, 0.0015 off the deterministic ceiling. |
| C-006 | The value of an iterative retrieval loop is a function of plan quality: it compensates for weak planning at substantial cost and does not substitute for good planning. | EXP-2026-07-005, EXP-2026-07-006 | fig-arm-comparison | `supported` | On an LLM plan the loop is ~neutral (0.8505 → 0.8560) while retrieving 3,449 records; on an authored plan it is part of the best result (0.9957) while retrieving 1,080. |
| C-007 | Constructing queries by filling validated read-only templates places query validity and safety adherence at a ceiling by construction, rather than achieving them by tuning. | EXP-2026-07-008, EXP-2026-07-009 | tab-component | `supported` | Validity 1.0 (78/78), execution exact-set-match 1.0 (80/80), provenance 120/120. Stated as a design property, **not** as a performance result — the repository's own report is explicit that this is a ceiling, and the claim must be phrased that way or it overclaims. |
| C-008 | A deterministic safety gate over templated queries blocks adversarial probes without leakage. | EXP-2026-07-008 | tab-component | `partial` | 17/17 probes blocked, 0 leaks, 0 breaches across 78 audited queries. **Partial:** the probe suite is small and was itself the thing that found the one bypass that has been fixed. A 100% block rate over 17 probes is weak evidence of a strong property. |
| C-009 | Self-judged evaluation materially overstates answer quality relative to independent cross-model judging, which is why the primary evaluation must be cross-model. | EXP-2026-07-009, EXP-2026-07-010 | — | `supported` | Four self-judged end-to-end metrics all read 1.0 while an independent Sonnet 5 panel scored the same pipeline at 0.8946 correctness with hallucinations in 11 of 120 answers. |
| C-010 | The system's dataset-specific surface is bounded and countable rather than pervasive: the schema-agnostic machinery transfers, and re-authoring cost is a known number of templates. | EXP-2026-07-011, EXP-2026-07-007 | — | `supported` | 19 of 25 distinct templates are MITRE-specific; orchestration, synthesis, provenance, and the whole evaluation apparatus are schema-agnostic. Arm G prices the generic path at 0.6388. |

## Unsupported — the experiment backlog

These are the claims the paper needs and currently cannot make. Each one is an
experiment that has not been run.

| ID | Claim (as it will appear in the paper) | Evidence | Artifact | Status | Notes |
|----|-------|----------|----------|--------|-------|
| C-011 | Federated question answering across cybersecurity knowledge graphs held in *separate engines with different query languages* is a contribution not made by prior work. | — | — | `unsupported` | A seven-formulation search found no paper whose contribution is this, and the one survey naming the idea cites nothing for it. But **AgCyRAG (Kurniawan et al., RAGE-KG @ ISWC 2025) partially scoops the architecture** — it runs Cypher and SPARQL agents over two stores in one security-domain loop. The differentiator must be the *result*, not the architecture. See [`RELATED_WORK.md`](RELATED_WORK.md). |
| C-012 | Routing to a fixed library of validated parameterised templates outperforms letting an LLM plan and generate the queries, in correctness and in cost. | — | — | `unsupported` | **This is the paper's intended headline and no experiment supports it.** Arm G is a *generic-primitives* control, not free-form generation: no LLM writes Cypher or Gremlin in any arm of the study. The free-form text-to-Cypher/Gremlin baseline has never been built. Highest-priority gap. |
| C-013 | The near-ceiling correctness of the deterministic path is a genuine capability rather than an artifact of a question set co-authored with the templates that answer it. | — | — | `unsupported` | Requires 30 blind-authored held-out questions against a frozen template set, sampling anchors uniformly rather than by mapping richness. **Gates C-001 and the value of every other result.** Cheapest high-value experiment available; see [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) Q1. |
| C-014 | The coverage cliff of template routing is measurable: the design's *price* on open-ended, non-anchored questions is bounded and reportable, not unknown. | — | — | `unsupported` | All 120 catalogue questions are anchored. Nothing measures the regime where a template router is weakest. A paper that reports only the benefit and not the trade will not survive review. |
| C-015 | Federating across two engines outperforms merging both sources into a single graph and querying that. | — | — | `unsupported` | The merged-single-graph baseline has never been built. Without it the federation claim — the part the funder cares about — has never been contrasted with a counterfactual. |
| C-016 | Mechanically localising the last pipeline stage at which the gold answer was still recoverable contradicts the assumption that LLM pipeline failures are predominantly hallucination failures. | EXP-2026-07-002 | — | `partial` | 26 of Arm B's 36 failures were planning or retrieval; only 2 were faithfulness. **Partial:** the classifier has been applied to exactly one system, so the finding is real for Ariadne and unproven as a generality. |
| C-017 | Claim-level verification with enforced abstention carrying executed-query proof eliminates unsupported claims without reducing answer coverage. | EXP-2026-07-009 | — | `unsupported` | Provenance and inspectability at 1.0 are self-consistency checks, not evidence for this claim. Needs the verifier ablation (gates disabled individually) and a proper answerable/unanswerable split — the current 10 negatives are far too few. |

## Refuted / cut claims

Kept deliberately. They document what was tried and stop settled questions being
re-litigated.

| ID | Claim | Why it went | Date |
|----|-------|-------------|------|
| C-018 | "LLM planning costs −0.196 correctness." | **Cut — not refuted.** The effect is real; this *figure* is not reproducible from the post-fix table. It was computed against an earlier judge run where Arm C scored 0.9620. Superseded by C-002 at −0.1185. Both numbers are faithfully recorded in the repository and neither was wrong at the time. | 2026-08-04 |
| C-019 | "The system is an agentic federated pipeline whose plan → retrieve → assess → re-plan loop drives retrieval." | **Refuted by its own record.** The loop had never executed: the live `.env` pins `ORCH_MAX_HOPS=1`, sufficiency was decided purely by join closure so single-source questions were complete by construction after one hop, and `expandable_facets()` was defined and never called. The loop now works and is measured (C-006), but the framing that preceded the measurement was false. | 2026-07-26 |
| C-020 | "There is an accuracy-versus-readability trade-off: readable LLM prose costs correctness." | **Refuted.** Arm F scores 0.9957 against the deterministic ceiling's 0.9972 — a 0.0015 gap — with zero INCORRECT and full gold coverage. The trade disappears once the narrator is bound to verified claims. Superseded by C-005. | 2026-07-26 |

---

## How to use this file

- **Adding a claim:** write it as it will appear in the paper, mark it
  `unsupported`, and leave evidence empty. That row is now a backlog item.
- **Adding evidence:** put the experiment ID in the evidence column. The
  validator enforces the reverse direction — a `supports_claims` entry in any
  manifest that has no row here is a hard failure.
- **Never delete a row.** Move it to *Refuted / cut* with the reason and the
  date. A deleted claim is one somebody re-proposes in month nine.
- **`partial` is the honest default.** A claim is `supported` only when the
  evidence would survive a reviewer who read the threats-to-validity section.
