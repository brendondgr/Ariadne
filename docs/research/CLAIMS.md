# Claims Ledger

One row per claim, holding only the **current** figure. Every number here is a
`metrics.values` entry in the named experiment's manifest; `make check-docs`
fails this file if it quotes a value the record has since withdrawn. How each
claim reached its status — every earlier row, every layered update, the model
provenance warnings — is in [`CLAIMS-HISTORY.md`](CLAIMS-HISTORY.md), verbatim
and append-only. Which figures are current across the whole record is
[`CURRENT.md`](CURRENT.md).

**Status:** `unsupported` | `partial` | `supported` | `refuted` | `cut`.
`partial` is the honest default; `supported` means the evidence would survive a
reviewer who read the threats-to-validity section.

**Grader provenance, in one line.** July arms were graded by Sonnet 5 (cross-model);
the August judged comparisons by a local model the relay could not name, since
re-graded under `qwen38-27B-v2` and `gemma4-31B-mtp` (`EXP-2026-08-021`,
`EXP-2026-09-006`); every September figure names its grader. Retrieval,
isolation, leakage and node-edit figures take no model in the metric. See
`D-028`. Never write the alias `skynet` beside a number.

---

## The primary result and the two comparisons beside it

| ID | Claim | Current figure | Evidence | Status |
|---|---|---|---|---|
| **C-023** | Hand-written query templates do not hold the system's correctness. A schema-derived, template-free path matches them on the schema they were written for and beats them off it; what templates hold is precision and provable abstention on their own vocabulary, and what they cost is coverage. | Dev (n=284, qwen): generic **0.6569** vs templates **0.4946**, gap **0.1623**; gemma 0.6659 vs 0.4175. Holdout (n=288): **0.6546** vs **0.4862**, gap **0.1684** [0.1340, 0.2049]; gemma gap 0.2143. Catalogue retrieval saturated at 1.0000 for both after one template was repaired; foreign schema −0.6121 [−0.6720, −0.5530] retrieval, generic 0.6923 vs 0.1140 recall after fixes. | EXP-2026-09-005, EXP-2026-09-007, EXP-2026-09-006, EXP-2026-08-015, EXP-2026-08-011, EXP-2026-08-010 | `partial` — the generic arm's narrator calls a model (EXP-2026-09-010); its across-seed spread is 0.0074 over six seeds (EXP-2026-09-011), forty times smaller than the gap |
| **C-012** | Routing to validated templates beats letting a model write the queries, in correctness. | Dev (n=284): templates − llm_query **+0.1147** [+0.0653, +0.1645] qwen, **+0.0696** [−0.0024, +0.1450] gemma. Holdout (n=288): **+0.0822** [+0.0362, +0.1308] qwen, +0.0643 [−0.0080, +0.1333] gemma. Positive under both grader families; significant under one. Seeded repeats of the arm: sd 0.0089, but the two families order the arms oppositely (+0.1012 vs −0.2885) because gemma emits two values on this population. | EXP-2026-09-007, EXP-2026-09-006, EXP-2026-09-009; precursor at n=30 EXP-2026-08-008 (0.9467 vs 0.5000) | `supported` for correctness; the cost half is unmeasured (Q38) |
| **C-022** | Within this system federated execution and materialised merging are accuracy-neutral; federation's advantage is structural. We are not aware of a head-to-head comparison across heterogeneous live stores (`D-030`, strict reading only). | Merged − federated, eight named passes, order-corrected: **−0.0587** (bank 19), **−0.0520** (bank 20); second family −0.0500 / −0.0400 (upper bounds, saturated). All inside the ±0.06 sampling floor at n=30. Merging rewrote **1,083 of 9,138** nodes (22.71 % of CAPEC); federation rewrote **0**. Three live sources retrieve identically to one. | EXP-2026-08-009 (A-1), EXP-2026-09-006, EXP-2026-08-017, EXP-2026-08-013 | `partial` |

## Supported

| ID | Claim | Current figure | Evidence | Status |
|---|---|---|---|---|
| C-004 | The deterministic path is orders of magnitude cheaper than the LLM-planned one. | 120 questions in **1.6 s** (Arm A) against **1,019.7 s** (Arm B) and 533.4 s (Arm F). | EXP-2026-07-001, EXP-2026-07-002, EXP-2026-07-006 | `supported` |
| C-005 | Binding an LLM narrator to the verified claim set removes the accuracy-versus-readability trade. | 0.9690 (evidence-bound) → 0.9917 (claims-bound) → 0.9957 (claims-bound + loop), 0.0016 off the deterministic 0.9972. | EXP-2026-07-003, EXP-2026-07-004, EXP-2026-07-006 | `supported` (July, Gemma 4 31B) |
| C-006 | An iterative retrieval loop compensates for weak planning at cost and does not substitute for good planning. | LLM plan: 0.8505 → 0.8560 while retrieving 3,449 records; authored plan: 0.9957 retrieving 1,080. | EXP-2026-07-005, EXP-2026-07-006 | `supported` (July) |
| C-007 | Filling validated read-only templates places query validity and safety adherence at a ceiling by construction. | Validity 78/78, execution exact-set-match 80/80, provenance 120/120 — stated as guarantees with the defect each would catch, not as scores (Q7/Q8 relabelling). | EXP-2026-07-008, EXP-2026-07-009 | `supported` as a design property |
| C-009 | Self-judged evaluation overstates answer quality; the primary evaluation must be cross-model, and the grader must be characterised first. | Self-judged metrics all 1.0 while an independent panel scored 0.8946 (EXP-2026-07-010). Of three local graders, one resolves near the ceiling; one emits a single value there and one inverts mid/low ordering (EXP-2026-09-008). Re-grading the same answers moves a mean by a median 0.0066, up to 0.0242 (EXP-2026-09-012). | EXP-2026-07-009, EXP-2026-07-010, EXP-2026-09-008, EXP-2026-09-006, EXP-2026-09-012 | `supported` |
| C-021 | Benchmarks co-authored with the system overstate it by a measurable margin. | **0.0483** — same cascade, same grader, same night, catalogue vs blind, after the composer fix (0.1472 before it, same night). Under a named grader 0.0322; the second family reads 0.0000 because it is saturated. Holdout drift ≤ 0.025 per arm. | EXP-2026-08-008, EXP-2026-08-007, EXP-2026-09-006, EXP-2026-09-007 | `supported` |

## Partial

| ID | Claim | Current figure | Evidence | Status |
|---|---|---|---|---|
| C-001 | On an anchored, in-vocabulary question set the fully deterministic pipeline answers near the ceiling with zero hallucinations. | Catalogue **0.9972**, 120/120, 0 hallucinations (co-authored). Blind after repairs **0.8367** (0 INCORRECT); fresh bank **0.9467**, 0 fabrications. Record identity falls to **0.0000** once the question leaves the schema's vocabulary (T4/T5), and a non-existent entity is answered with hundreds of genuinely retrieved records. | EXP-2026-07-001, EXP-2026-08-007, EXP-2026-08-008, EXP-2026-08-020 | `partial` — never quote 0.9972 or "zero hallucinations" without the vocabulary bound |
| C-002 | Substituting LLM planning for an authored plan is the dominant single source of correctness loss. | B − C = **−0.1185** within one judge run. | EXP-2026-07-002, EXP-2026-07-003, EXP-2026-07-005 | `partial` (July, Gemma 4 31B; the −0.196 figure is cut, C-018) |
| C-008 | A deterministic safety gate over templated queries blocks adversarial probes without leakage. | **240/240** blocked after **15** live bypasses found and closed (mergeV/mergeE, Groovy closure, unbounded repeat, literal hop chain, USE, backtick/multi-label). Cross-tenant leakage under the comparative routing rule: 5 records / 1 probe of 14 (was 568 / 3). | EXP-2026-08-016 | `partial` — true, and published prior art (Szlobodnyik 2026) means it is not a contribution |
| C-010 | The dataset-specific surface is bounded and countable; the schema-agnostic machinery transfers. | Identifier schemes are learned, not hard-coded (EXP-2026-08-005). On a 72-label identity schema both arms first retrieved **0.0000**; after five structural fixes generic recall **0.6923** vs templates **0.1140** (EXP-2026-08-011 A-10); replicated −0.6121 over ten banks (EXP-2026-08-015). The planner, not the templates, was the non-portable layer. | EXP-2026-08-005, EXP-2026-08-011, EXP-2026-08-015, EXP-2026-07-011 | `partial` — one foreign schema |
| C-014 | The coverage cliff of template routing is measurable and reportable. | Direction cliff closed by schema-resolved direction: blind retrieval 0.7688 → 1.0000. Vocabulary cliff: record identity **1.0000 → 0.4667 → 0.4250 → 0.0990 → 0.0000** across T0–T5. A gated rewrite stage lifts T4/T5 to 0.0880 / 0.1635 but doubles confident-wrong answers there and stays off (`D-032`). | EXP-2026-08-005, EXP-2026-08-006, EXP-2026-08-020, EXP-2026-09-014 | `partial` — open-ended, non-anchored questions unmeasured (Q4) |
| C-016 | Failure localisation contradicts the assumption that LLM pipeline failures are mostly hallucination. | Of Arm B's failures, planning-or-retrieval dominates and faithfulness is rare (4 of 28 on the amended count, EXP-2026-07-002 A-1). Mechanism is published prior art (Leung et al., EACL 2026) and their distribution runs the other way; the reconciliation is written in `paper/sections/09-failure-localisation.md`. | EXP-2026-07-002 | `partial` — intervention validation owed (Q40) |
| C-017 | Claim-level verification with enforced abstention-with-proof eliminates unsupported claims without reducing coverage. | On the deterministic path no gate cuts anything because a violating claim is unconstructible (0 of 888, EXP-2026-08-014); on LLM-proposed claims the gates cut 32–36 per run, dominated by the `correlated` gate (EXP-2026-08-018). Query-carrying abstention: cascade ahead of the generic arm by about 0.30 (EXP-2026-08-007 A-1). | EXP-2026-08-014, EXP-2026-08-018, EXP-2026-08-007 | `partial` |
| C-024 | First implemented and measured cross-language federation over live, unmerged, independently administered stores. Priority on the idea is conceded (Ozsoy 2026; AgCyRAG; EICopilot). | Three live sources on two engines answer identically to one (EXP-2026-08-013); federation edits 0 nodes (EXP-2026-08-017). | EXP-2026-08-013, EXP-2026-08-017, EXP-2026-07-001 | `partial` — a positioning claim, cite the priority explicitly |

## Unsupported

| ID | Claim | Current figure | Evidence | Status |
|---|---|---|---|---|
| C-025 | No benchmark pairs natural-language questions with executable gold graph queries, scored by execution, over the security taxonomies. | The negative half is evidenced by the novelty audit; the resource is not yet produced — a bank entry carries `expected_template`, not a gold query. The schema census found the sources support 34 edge types of which the old banks reached 12 (EXP-2026-09-001). | EXP-2026-09-001 | `unsupported` until Q26 is decided |

## Refuted and cut

Kept so that a settled question is not re-litigated. Full reasoning in [`CLAIMS-HISTORY.md`](CLAIMS-HISTORY.md).

| ID | Claim | Why it went | When |
|---|---|---|---|
| C-003 | The templates, not the planner, are where the accuracy lives; disabling them costs 3× what LLM planning costs. | Four measurements contradict it: level on the catalogue, behind on the fresh bank, 0.278 behind on external questions, behind on both axes off-schema. The 3× ratio was against Arm G, a weaker generic arm that also ran with the gold plan, not the LLM planner. Superseded by C-023. | 2026-08-23 |
| C-011 | Federated QA across cybersecurity KGs in separate engines is a contribution not made by prior work. | AgCyRAG built the architecture; Ozsoy posed the problem. Superseded by C-024. | 2026-08-26 |
| C-013 | The near-ceiling correctness is a capability, not a co-authorship artifact. | Blind holdout 0.689 against 0.9972; the drop sits on the reverse-direction categories the templates did not serve. Priced by C-021. | 2026-08-09 |
| C-015 | Federating across two engines outperforms merging. | Neutral on both blind sets under three graders. Successor is C-022. | 2026-08-21 |
| C-018 | "LLM planning costs −0.196." | Cut, not refuted: the figure came from an earlier judge run and is not reproducible from the standing table; C-002 holds −0.1185. | 2026-08-04 |
| C-019 | "The plan → retrieve → assess → re-plan loop drives retrieval." | The loop had never executed (`ORCH_MAX_HOPS=1` in `.env`). Now measured as C-006. | 2026-07-26 |
| C-020 | "Readable LLM prose costs correctness." | 0.9957 vs 0.9972 with zero INCORRECT once the narrator is claim-bound. Superseded by C-005. | 2026-07-26 |

---

## How to use this file

- **Adding a claim:** one row, `unsupported`, evidence empty. That row is the backlog.
- **Changing a row:** append the outgoing row to `CLAIMS-HISTORY.md` under the claim's ID with the date, then replace it here. The validator enforces that every `supports_claims` ID in a manifest exists here.
- **Quoting:** every figure above is a manifest value; if `CURRENT.md` lists it as withdrawn, this row is wrong and must be updated the same day.
- **Never delete a row.** Move it to *Refuted and cut* with the reason and the date.
