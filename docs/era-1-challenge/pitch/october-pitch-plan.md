# Ariadne — October Pitch Plan

**Event:** ReliaQuest Innovation Challenge pitch, FSU Discovery Days, October 19, 2026 (5–7 min slot; we target < 5:00).
**Goal:** every rubric category at 4 minimum, most at 5, and a credible case for the follow-on award.
**Audience:** mixed — ReliaQuest engineers and leadership, FSU faculty, students. Every slide opens in plain English.

---

## 1. What the August scores actually say

Read off the assessment chart (filled marker = our score, hollow = that reviewer's average across all teams):

| Category | R1 | R2 | R3 | Total vs. avg | Diagnosis |
|---|---|---|---|---|---|
| Problem and use case are clear | 4 | 5 | 4 | −0.5 | Fine, but R1/R3 gave us *below* their average. The "two encyclopedias" opener landed; the *why now / why ReliaQuest* did not. |
| Proposed approach is technically credible | 4 | 4 | 4 | +1.2 | Our strongest relative category. Keep the plan-first / no-LLM-writes-queries story. |
| Data or evidence supports the claims | 3 | 4 | 3 | +0.5 | Two 3s. The August evidence was one table of 0.99s on questions we wrote ourselves. Judges sensed it. |
| Practical impact is clear and compelling | 4 | 4 | **2** | **−1.3** | Worst category. R3: "show a tangible output… put real examples in." |
| Clear case for further investment | 4 | 4 | **2** | **−1.0** | Second worst. R3 again. The August ask was a research roadmap, not an outcome ReliaQuest gets. |
| Relevant to the challenge area | 4 | 5 | 4 | +0.2 | R3 gave 4 against a 4.7 average — they didn't see Spanner/Neptune/"disparate graphs" connected to us. |

Three reviewers, three fixes, and the interview feedback maps onto the same three:

| Source | Ask | What we now have that answers it |
|---|---|---|
| R1 | Explain the "arms"; emphasize scalability and interoperability across diverse graph DBs | Drop the word "arms" entirely → "three ways of answering the same question." EXP-013: **three live sources, two query languages, one process**, zero questions change when a third DB is added. EXP-017: federation edited **0** records vs. **1,083** for merging. |
| R2 | Show how this benefits ReliaQuest | EXP-011/013: we pointed Ariadne at **ReliaQuest's own 72-type identity schema** (AD, Entra, Okta, AWS, GCP) with **zero customer records** — schema-only is the native input. It works (recall 0.66 vs 0.13), and it bridges to ATT&CK (a `DC_SYNC` edge *is* T1003.006). |
| R3 | Tangible output, real examples | A real answer card from the repo (question → plan → both queries → cited answer) and a real honest-abstention card. |
| Interview | Scalability; multiple systems; drop "arms"; **define hallucination**; the ReliaQuest-schema integration work; the "disparate → unified" hook; show example outputs | All of the above, plus one plain-English hallucination definition on the slide where it first matters. |

## 2. The strategic problem nobody flagged: the August story is no longer true

The August deck's headline was *0.9957 correctness, and the templates are where the accuracy lives.* The project's own ledger has since **refuted** that (C-003, C-013): the 0.99 was a property of questions co-authored with the code; on blind questions the same system scored 0.69. Presenting the August numbers again to a ReliaQuest engineer who reads the repo would end the pitch.

The honest story is *better* for a funder, not worse:

1. **The system that reads the database's own structure beats both the hand-written approach and "let the AI write the query"** — on 288 questions it had never seen, graded by two different models: **0.65 vs 0.49 vs 0.40**. And on the same questions, same machine, wall clock on both sides, the hand-written path finishes in 8 s where the AI-writes-the-query approach takes 3.2 h — **1,400×** (EXP-2026-09-016).
2. **Zero fabricated claims, by construction.** On the shipped path no language model can *propose* a claim; every claim is built from a retrieved record and carries the record and the query. 240 of 240 adversarial probes blocked (after finding and fixing 15 bypasses ourselves).
3. **It generalized to ReliaQuest's real schema** — retrieval recall 0.66 vs 0.13 for the hand-written approach (EXP-011 amendment A-10; the earlier 0.7877 vs 0.3177 is superseded) — which is exactly the property the challenge asked for.
4. **We know the next gap precisely**: ask by identifier or exact name → works; paraphrase the name → 0.00. That is the funding ask, and it is a measured target.

Numbers in the 0.6–0.8 range on blind questions look worse than 0.99 until you say out loud that they are blind, that the 0.99 was not, and that the *comparison* (which approach wins, by how much, under two graders) is the finding. That framing is what turns "Data or evidence" from a 3 into a 4–5.

## 3. Slide map (9 slides, 4:45 target)

| # | Slide | Rubric it targets | Time |
|---|---|---|---|
| 1 | **Hook** — "Security knowledge is scattered across databases that don't speak the same language. Ariadne asks one question across all of them — and shows the receipt for every sentence." | Problem · Relevance | 0:25 |
| 2 | **The problem** — Neo4j / Neptune / Spanner / identity graphs; the three options today (do it by hand, copy everything into one warehouse, ask a chatbot) and why each fails. **Hallucination defined here in one line.** | Problem · Relevance | 0:40 |
| 3 | **How it works** — four plain-English parts (spec sheet → planner → one translator per database → verifier). Rule: no AI ever writes a query; no claim without a record behind it. | Technically credible | 0:40 |
| 4 | **What it actually outputs** — a real answer card: the credential-theft question, the two queries it ran, the cited answer. Beside it, a real "the database has nothing — here is the query I ran" card. | **Practical impact** · Evidence | 0:40 |
| 5 | **The evidence** — 288 held-back questions (never graded before the final run), three ways of answering, two independent graders. Schema-read 0.65 · hand-written 0.49 · AI writes the query 0.40. 4 s vs ~2 days. Zero fabricated claims. 240/240 safety. | **Evidence** · Credible | 0:45 |
| 6 | **It scales across databases** — 3 live sources, 2 query languages, 1 process; adding a database = one spec sheet; 0 records edited vs 1,083 for merging; Spanner/Neptune on the roadmap. | Relevance (R1) · Impact | 0:30 |
| 7 | **It already runs on ReliaQuest's schema** — 72 node types, 5 identity planes, zero customer records needed; retrieval 0.66 vs 0.13; bridges `DC_SYNC` → T1003.006 → mitigations; 12/12 refusals with no false claims. Example question an analyst would ask. | **Relevance (R2)** · **Impact** | 0:40 |
| 8 | **What the next dollar buys** — the measured gap (paraphrase → 0.00) and four funded outcomes with a number attached to each: name resolution, human-checked validation, pilot on ReliaQuest data with real records, Neptune/Spanner. | **Further investment** | 0:35 |
| 9 | **Close** — one sentence, team, ask. | — | 0:10 |

Backup slides (not in the 5 min): full comparison table; July study (as history); how a source card looks; safety audit; open questions.

## 4. Vocabulary rules for the room

| Never say | Say instead |
|---|---|
| arm, Arm A–H, `generic`, `deterministic`, `llm_query` | "three ways of answering the same question": *read the database's own structure* / *hand-written queries* / *let the AI write the query* |
| hallucination (undefined) | "a hallucination is when the AI states something as a fact that is not in the data" — then use "made-up claim" |
| federated, orchestration, provenance, template cascade, schema-derived primitives | "one question across many databases", "the plan", "the receipt", "hand-written queries", "reads the database's own structure" |
| source card | "a one-page spec sheet per database" (say "source card" once, in parentheses) |
| holdout / blind bank | "questions the system had never seen" |
| Cypher / Gremlin | say once on the how-it-works slide as "two different query languages", then "each database's own language" |

## 5. Numbers policy (so nothing on a slide can be challenged)

- Every number on a slide is traceable to a file in `docs/research/experiments/` or `docs/research/reports/`; the script cites the file per slide.
- Blind holdout figures (EXP-2026-09-007): quote the qwen38-27B-v2 grader as primary; say "two graders agree on the ordering."
- The cost figure is `EXP-2026-09-016`: 284 development questions, 24 workers, one machine, **wall clock on both sides** — 8 s vs 3.2 h, **1,400×**. Not the holdout; the script says "the same 284 questions." **Never say 40,000× or "4 s vs 2 days"** — that divided one path's wall clock by another's summed machine time and is withdrawn (A-2).
- The schema-read path is **not model-free**: 159 model calls over 284 questions, because it keeps LLM planning, a specialist seam and the narrator. Say "no model writes a query", never "no model".
- "Two graders agree on the ordering" is a statement about the **288 held-out** questions only. On the 284 development half one gemma configuration reverses it (`EXP-2026-09-009`); the prepared answer is in the script's Q&A appendix.
- Identity figures (EXP-2026-08-011, amendment A-10): retrieval recall 0.657 vs 0.127 (precision 0.136 vs 0.057) on 117 blind questions, **synthetic records conforming to ReliaQuest's real schema** — say "synthetic records" and "retrieval" out loud. Do not quote the superseded 0.7877 vs 0.3177.
- Federation vs merging: say "no measurable accuracy difference; the difference is structural" — never "federation is more accurate."
- July 0.9957: only in backup, labeled "development questions, July; does not transfer."
- The "1,400×" and "1,083 nodes" are the two numbers to land; "0.65 vs 0.49 vs 0.40" is the one to explain.

## 6. Deliverables

1. `Ariadne_October_Pitch.pptx` — 9 main slides + divider + 4 backup, speaker notes on every slide (`Ariadne_October_Pitch_preview.pdf` is a render for quick viewing).
2. `Ariadne_October_Pitch_Script.docx` — word-for-word script with timings, per-slide "if you're running long, cut…" lines, and a Q&A appendix.
3. This plan.

## 7. Verification log (2026-09-06)

A second pass checked every number on the deck against the repository. Ten corrections were applied before delivery: co-authorship bias quoted as +0.03–0.05 (the ledger forbids 0.1472); the July "model no longer exists" line now names the pipeline model, not the grader; slide 4 says 11 citations, not 6; `llm_query` uses the completed two-family figure (0.4039 / +0.2507 / +0.0822); identity figures use A-10 retrieval recall (0.66 vs 0.13); the federate-vs-merge readings say "0.00 to +0.06, at or above in all six"; the swap-points line no longer claims the planner and harness are untouched; the ReliaQuest example question is the committed one; the test count is the reproducible 1,746 functions / 182 files; "never seen" became "held back, never graded".

Two things the deck deliberately does not claim: that federation is more accurate than merging (it isn't measurably), and that the schema-read path is the shipped default (it runs behind a flag; see Q&A).

## 8. Verification log (2026-09-10)

A third pass re-checked every slide number against the research record as it
stands after `EXP-2026-09-009` through `-016` and the 2026-09-09 record cleanup.
Full findings in [`numbers-audit-2026-09-10.md`](numbers-audit-2026-09-10.md).
Six corrections were applied to the deck, the script and this plan:

1. **40,000x is withdrawn.** It divided one path's wall clock by another's
   summed machine time. Held to one quantity the ratio is **1,400x**
   (`EXP-2026-09-016` A-2). Slide 5's stat, its spoken line, the Q&A answers and
   backup B1 all now carry the corrected figure with the concurrency named.
2. **"No model" became "no model writes a query."** The schema-read path makes
   159 model calls over 284 questions; backup B1's row label said otherwise.
3. **The seeded-repeat answer was stale** — six seeds give SD 0.0074 and three
   give 0.0089, so the "no repeat runs" admission is retired.
4. **A grader reversal on the development half** (`EXP-2026-09-009`) now has a
   prepared Q&A answer instead of an improvised one. No slide changed: the
   claim on slide 5 is about the held-out set, where both families agree.
5. **A superseded 0.79** survived in slide 7's cut instruction. Corrected to
   0.66.
6. **`docs/reports/` paths** were repaired to `docs/research/reports/` after the
   2026-09-09 cleanup moved them.

Three things were checked and deliberately left alone: `Q47` (audited clear, no
figure affected), `Q48` (no deck figure comes from that judge), and `Q45`, which
needs a graded re-run on the LLM server and would *raise* the margin slide 5
quotes. Until it runs, every figure stands as measured.
