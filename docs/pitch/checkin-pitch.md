# Ariadne — Five-Slide Check-In Pitch

**ReliaQuest Innovation Challenge Fund · Challenge Three: Knowledge Graph Integration**
Award period June 8 – October 23, 2026 · $29,298
PI: Olmo S. Zavala Romero (FSU Scientific Computing) · Graduate RA / technical lead: Brendon DGR

**Format:** 5 slides / 5 minutes. Budget ≈ 55–60 seconds per slide. Every number below is
sourced to a committed artifact in this repository; the "Source" line under each slide tells
you where to point if you are challenged.

---

## Slide 1 — The Problem

**Headline: Security knowledge lives in graphs that can't talk to each other.**

On-slide:

- Cyber teams increasingly model adversary behavior as knowledge graphs — techniques,
  attack patterns, mitigations, weaknesses.
- Those graphs sit on **different engines, with different schemas and different query
  languages**. ATT&CK in one store speaking Cypher; CAPEC in another speaking Gremlin.
- So a single analyst question — *"which credential-theft attack patterns map to ATT&CK
  techniques, and what mitigations exist for those techniques?"* — becomes manual lookups
  in two consoles, by hand, per question.
- The standard fix is an **offline ETL merge into one graph**: expensive, stale the moment
  it lands, and it destroys the provenance that makes an answer defensible.
- The alternative fix — dump the graph into a vector index and let an LLM talk about it —
  buys fluency and loses the audit trail. In security, an answer you can't trace is an
  answer you can't act on.

Visual: two disconnected graph icons (Neo4j / Cypher · Gremlin / Gremlin), an analyst in the
middle, and a red X over an "ETL → single merged graph" arrow.

Speaker notes (≈60s):
> Security teams have gotten good at representing adversary knowledge as graphs. What they
> haven't solved is that those graphs don't share a query language. MITRE ATT&CK and MITRE
> CAPEC are the canonical example — same domain, explicitly cross-referenced, and still no
> way to ask one question across both. Today an analyst either does it by hand, or somebody
> builds an ETL job that copies both into one database. The ETL answer is the one most
> teams pick and it has two costs: it's stale on arrival, and it flattens away where each
> fact came from. The newer answer — embed everything and ask a chatbot — is worse for this
> use case, because the thing a security analyst actually needs is the citation.

Source: [docs/purpose.md](../purpose.md) · [README.md](../../README.md) intro.

---

## Slide 2 — The Approach

**Headline: Don't merge the graphs. Federate the queries — and keep the receipts.**

On-slide — four components, each independently testable:

| # | Component | What it does |
|---|---|---|
| 1 | **Data & schema layer** | A *source card* per database: connection, schema, provenance fields, safety limits. Plus reproducible ATT&CK/CAPEC fixtures, sha256-pinned to the raw snapshot. |
| 2 | **Federated planning agent** | Reads the cards, classifies analyst intent, emits a *machine-checkable plan* — target sources, sub-questions, join keys, traversal limits — before any query runs. |
| 3 | **Source-specific query specialists** | Cypher over Neo4j; Gremlin over a Neptune-style server. Each drafts, **gates**, executes, and normalizes — no unbounded traversal reaches a live graph. |
| 4 | **Verifying synthesis agent** | Joins partial evidence on shared IDs (ATT&CK / CAPEC), verifies every claim against the evidence, cuts unsupported ones, and turns honest empties into **abstentions with the executed query as proof**. |

Key design commitments:

- **Live, read-only, native per engine.** No offline merge, no copy of the data.
- **No vector index, no embedding store** is built from the graph data. Grounding comes
  from schema descriptions, source metadata, and the queries actually executed.
- **A new backend is four swap points** — builder, validator, connector, normalizer — on one
  unchanged scaffold. That's the portability claim, and it's documented as a deliverable.

Visual: the architecture SVG at [docs/assets/architecture.svg](../assets/architecture.svg).

Speaker notes (≈60s):
> The bet is that you don't need to move the data. You need a layer that knows what each
> source *is* and can plan across them. The planner never guesses in free text — it emits a
> structured plan we can machine-check, and the engine-specific work is pushed down into
> specialists so the planner stays swappable. Every query passes a safety gate before it
> touches a live database. And the last agent is a verifier, not a writer: it checks each
> claim against the retrieved records, deletes what isn't supported, and when the graph
> genuinely has nothing, it says so and shows you the query it ran. That last part is what
> makes this usable by an analyst who has to justify a decision.

Source: [docs/purpose.md](../purpose.md), [docs/planner_agent.md](../planner_agent.md),
[docs/specialist_agents.md](../specialist_agents.md),
[docs/migration-guide.md](../migration-guide.md).

---

## Slide 3 — The Evidence

**Headline: It's built, it's measured, and it was measured by a model that didn't write the answers.**

**What's running** — live, on a pinned snapshot (ATT&CK v19.0 · CAPEC v3.9):

- ATT&CK / Neo4j: **4,369 nodes · 27,669 relationships** across 11 labels.
- CAPEC / Gremlin: **4,769 nodes · 6,972 relationships** across 10 labels.
- ~58k lines of Python, 142 test files / 1,176 tests, plus a Next.js analyst workbench
  (chat · graph explorer · live evaluation view).

**Component-level scores** (deterministic, reproducible — the model drafts, code grades):

| | ATT&CK (Cypher) | CAPEC (Gremlin) |
|---|---|---|
| Query validity, first-pass | 1.000 (44/44) | 1.000 (34/34) |
| Execution accuracy vs gold (exact-set) | 1.000 (46/46) | 1.000 (34/34) |
| Adversarial safety-probe block rate | 1.000 (10 probes, 0 leaks) | 1.000 (7 probes, 0 leaks) |
| Warm p50 latency | 1.1 ms | 2.6 ms |

Planner: source recall 1.000, schema adherence 1.000, source precision 0.919 — it
over-routes, and we say so.

**End-to-end, over a 120-question golden catalogue** — cross-source accuracy 1.000 (30/30
positives, 10/10 negatives with zero fabrication), CAPEC→ATT&CK mapping recall 1.000
(113/113), provenance correctness 1.000 (120/120), analyst inspectability 1.000.

**The honest part — we hired an outside grader.** Those four metrics measure retrieval and
provenance. To measure the *answers*, all 120 were re-graded by an independent Sonnet 5
agent per question — cross-model on purpose, so the pipeline never grades its own work.

| | Committed baseline | After the fixes below |
|---|---|---|
| Correctness | 0.895 | **0.997** |
| Verdicts (Correct / Partial / Incorrect) | 91 / 27 / 2 | **120 / 0 / 0** |
| Answers carrying a hallucination | 11 | **0** |

Getting there meant a seven-arm controlled experiment (840 independent grading agents), a
`failure_terminus` classifier that identifies *which pipeline stage lost the information*,
and **eight defects found and fixed** — including a declared join that never reached its
sub-questions (19 of 36 failures in the LLM-planned arm) and evidence silently doubling on
every retrieval hop.

Speaker notes (≈65s — this is the slide worth going long on):
> Two things I want you to take from this. First, the system works: both specialists are at
> ceiling on validity, execution accuracy and safety, and end-to-end we recover every
> cross-source correlation and every mapping in the gold set with complete provenance.
> Second — and this is the part I'd want to see if I were you — I didn't trust our own
> scores. I had a different model, from a different vendor, grade all 120 answers against
> the gold *and* the raw evidence. It came back at 0.895 and flagged eleven hallucinations.
> That gap is the real finding. So I built a classifier that tells me which *stage* lost the
> information, ran seven full configurations, found eight concrete defects, and fixed them.
> The re-graded result is 0.997 with zero hallucinations across all 120.

Source: [docs/evaluation/component-evaluation.md](../evaluation/component-evaluation.md),
[docs/evaluation/e2e-evaluation.md](../evaluation/e2e-evaluation.md),
[docs/evaluation/archive/independent-eval.md](../evaluation/archive/independent-eval.md),
[docs/evaluation/2026-07-26/README.md](../evaluation/2026-07-26/README.md).

---

## Slide 4 — Anticipated Impact

**Headline: A federated, auditable answer layer — and a result that says *precision beats volume*.**

On-slide:

- **For an analyst:** one question, one provenance-linked answer, spanning sources that
  don't share a query language — with the executed query attached to every claim. No ETL
  pipeline to maintain, no stale copy, nothing to re-index when MITRE ships a new version.
- **For a security org:** the sources stay where they are, read-only. Extending to a third
  graph is a source card plus four swap points, not a new data warehouse.
- **The transferable research finding:** across every arm we ran, *precision in planning
  beat volume in retrieval, every time.* The best-scoring LLM configuration retrieved the
  **least** evidence of any LLM arm (1,080 records) and scored highest (0.996). The
  LLM-planned arm retrieved **2.6× more** and surfaced 20% *less* of the gold. Bad planning,
  not fabrication, is what breaks agentic graph QA — 26 of 36 failures were planning or
  retrieval; only 2 were faithfulness.
- **The accuracy-vs-readability trade is not real.** Binding the narrator to *verified
  claims* instead of raw evidence gets readable analyst prose at 0.9957 against a
  deterministic ceiling of 0.9972 — a 0.0015 gap, zero incorrect answers, full gold coverage.
- **The evaluation apparatus is itself a deliverable.** The arm runner, the per-question
  independent judge panel, and the stage-attribution classifier are dataset-independent.
  They are what found all eight defects, and they'd work on ReliaQuest data unchanged.

Speaker notes (≈55s):
> The product impact is straightforward: an analyst asks one question and gets one answer
> that spans both graphs with a citation on every claim, and nobody has to build or babysit
> an ETL job. The research impact is the part I didn't expect. Everyone assumes LLM systems
> fail by making things up. Ours didn't — only two of thirty-six failures were faithfulness.
> They failed by planning badly and then retrieving the wrong things enthusiastically. The
> arm that retrieved the least scored the highest. That reframes where you spend engineering
> effort in any agentic graph system, and it's not on retrieving more.

Source: [docs/evaluation/2026-07-26/README.md](../evaluation/2026-07-26/README.md) §1.

---

## Slide 5 — What Additional Funding Does

**Headline: We know exactly what the next dollar buys, because we measured what's missing.**

The bounded, honest gap — stated before anyone asks:

> Today's 0.99 scores come partly from **19 hand-authored, MITRE-specific query templates**.
> Everything else — orchestration, the retrieval loop, synthesis, verification, provenance,
> and the whole evaluation apparatus — is driven by the source card, not by MITRE. So we ran
> the control: **disable every MITRE template and force the schema-driven generic path.**
> Correctness falls from 0.996 to **0.639** (64 correct / 14 partial / 42 incorrect), while
> faithfulness holds at 0.966 — it doesn't start lying, it stops finding things.
> *That number is the roadmap.*

Priorities for a second stage, in order:

1. **Close the generic path** — make schema-driven `describe`/`expand` plus the
   facet-chasing retrieval loop reach template-level accuracy with no bespoke templates.
   This is the single highest-leverage item and it is now a *measured* target, not a guess.
2. **Entity resolution for schemas without stable IDs.** The pipeline seeds every question
   by extracting an anchor (`T1047`, `CAPEC-555`). A real customer schema may not have one.
   This is the identified breaking point for a genuinely new dataset.
3. **Managed graph backends** — Amazon Neptune, Google Spanner Graph — plus **openCypher and
   GQL** specialists, exercising the four-swap-point claim against a third and fourth engine.
4. **More sources** — vulnerability feeds (CVE/CWE/KEV) and customer telemetry, joined on the
   same shared-identifier mechanism already proven on the CAPEC↔ATT&CK bridge.
5. **Enterprise controls** — role-based access control and query audit logs, which the
   plan-first, gated-query architecture is already shaped to support.
6. **A pilot on ReliaQuest data.** Everything above is measurable on day one, because the
   evaluation harness travels with the system.

Speaker notes (≈60s):
> I want to be direct about the limitation, because it's the most useful thing I can tell
> you. Our best scores lean on nineteen query templates we hand-wrote for MITRE. So I ran
> the experiment that answers "what happens on a schema we have no templates for" — I turned
> those templates off. Correctness drops to 0.64. Notably, faithfulness stays at 0.97: it
> doesn't start hallucinating, it just stops finding things. That's a retrieval problem, and
> retrieval problems are tractable. So the first thing more funding buys is closing that
> gap — making the schema-driven path good enough that a new dataset is a source card and a
> gold set, not a month of template authoring. After that: entity resolution for schemas
> without clean IDs, managed backends with openCypher and GQL, vulnerability feeds, access
> controls and audit logging, and a pilot on your data. And because the evaluation harness
> is dataset-independent, we can tell you exactly how well it's working from week one.

Source: [docs/evaluation/2026-07-26/portability.md](../evaluation/2026-07-26/portability.md),
[docs/evaluation/experiments/untruncated-generic/](../evaluation/experiments/untruncated-generic/)
(Arm G, 120 questions, independently judged — *run complete, summary not yet committed*),
[docs/purpose.md](../purpose.md) "Future Development".

---

## Appendix — Backup numbers for Q&A

**Schedule.** Roadmap weeks 1–13 of 16 are complete as of August 1, 2026 (award began
June 8) — data layer, all four agents, end-to-end integration, component evaluation, and
end-to-end evaluation, plus the Wk 14–15 technical documentation set delivered early
(source card format, agent interface contracts, query safety model, openCypher/GQL migration
guide — proposal Deliverable #6). Remaining: bug-fix iteration and pitch prep.

**"How fast is it?"** The fully deterministic arm answers all 120 questions in **2.6
seconds**. The best LLM-narrated arm takes 533 s for 120 (≈4.4 s/question) and is the one
that produces analyst prose. Specialist-level warm p50 is 1.1 ms (ATT&CK) / 2.6 ms (CAPEC).

**"Which arm is the product?"** Arm F — authored plan, deterministic extraction plus the
facet-chasing loop, LLM narrator bound to verified claims. 0.9957 correctness, 119/1/0,
coverage 1.0.

**"Why is your own e2e report 1.0 but the independent judge 0.895?"** They measure different
things. The four deterministic e2e metrics measure retrieval, join correctness, and
provenance — those are genuinely at 1.0. The independent judge measures the *answer text*
against gold assertions, which is a stricter and different bar. Reporting both is the point.

**"Did the retrieval loop ever actually run?"** No — and finding that was one of the eight
defects. The documented plan→retrieve→assess→re-plan loop executed a single pass because
sufficiency was decided purely by cross-source join closure, so any single-source question
was "complete by construction" after one hop, and `expandable_facets()` was defined and
never called. `ORCH_CHASE_FACETS` plus `assess/facets.py` fixes it; the loop is part of the
best-scoring arm.

**"What's the deterministic ceiling?"** 0.9972 correctness, 1.0000 completeness, 0.9993
faithfulness, 1.0000 groundedness, 120/0/0, zero hallucinations — no LLM in the answer path
at all. It's the control that proves the retrieval and verification layers are sound.

**"What breaks first on a new dataset?"** Entity resolution, not the templates. With no
stable ID convention there is nothing to extract as an anchor; the deterministic planner
already misreads *"what mitigations does ATT&CK list for T1047?"* as entities
`['Matrix', 'Mitigation']`. The LLM planner is what rescues that today.

**Reproduce anything on this deck:**

```bash
uv run main.py --component-eval && uv run main.py --e2e-eval
```
