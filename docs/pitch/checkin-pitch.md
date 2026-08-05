# Ariadne — Five-Slide Check-In Pitch

**ReliaQuest Innovation Challenge Fund · Challenge Three: Knowledge Graph Integration**
Award period June 8 – October 23, 2026 · $29,298
PI: Olmo S. Zavala Romero (FSU Scientific Computing) · Graduate RA / technical lead: Brendon DGR

**Occasion:** August 6 check-in — practice pitch for feedback from the PI and FSU
cybersecurity faculty, as a proxy for the October Discovery Days pitch to ReliaQuest.

**Format:** 5 slides / 5 minutes. Every number is sourced to a committed artifact in this
repository; the "Source" line under each slide tells you where to point if challenged.

---

## Run sheet — read this before you rehearse

**The audience is mixed.** Students and campus leaders who have never heard of ATT&CK are
sitting next to cybersecurity faculty and, in October, ReliaQuest engineers. A pitch that
only lands for one of those groups fails. The rule used throughout this deck: **every slide
opens with a sentence a non-specialist fully understands, and only then earns the right to
a number.**

**Timing budget — 5:00 total, and it is tight.**

| Slide | Target | Hard cap | If you are running long |
|---|---|---|---|
| 1 — Problem | 0:50 | 1:00 | Drop the vector-index bullet |
| 2 — Approach | 0:55 | 1:05 | Drop the four-swap-points line |
| 3 — Evidence | 1:20 | 1:30 | **Never cut this one** — cut elsewhere |
| 4 — Impact | 0:55 | 1:05 | Drop the "evaluation is a deliverable" bullet |
| 5 — Funding | 1:00 | 1:10 | Drop asks 4–6, keep 1–3 |

**The one sentence that must land.** If they remember nothing else:

> *We built a system that answers a security question across two databases that don't speak
> the same language — without copying either one — and it shows you the receipt for every
> sentence it says.*

**The one number that must land.** 0.6388 → 0.9957. What the system scores without the
hand-written query templates, versus with them. It is the honest limitation *and* the
funding ask, and leading with your own weakness is what makes the rest of the deck
credible.

**Do not say, in the room:** "agentic," "orchestration layer," "normalizer," "provenance
completeness," "un-truncation profile." Every one of these has a plain-English substitute
used below.

---

## Slide 1 — The Problem

**Headline: Security knowledge lives in databases that can't talk to each other.**

*Plain-English opener (say this first, before any jargon):*

> Imagine two encyclopedias about the same subject. One is written in French, one in German.
> They reference each other constantly. But there is no way to ask a single question of both
> at once — so a person has to read both and do the cross-referencing in their head. That is
> the state of cybersecurity knowledge today.

On-slide:

- Security teams model attacker behavior as **knowledge graphs** — techniques, attack
  patterns, mitigations, weaknesses, and how they connect.
- Those graphs sit on **different database engines, with different structures and different
  query languages**. MITRE ATT&CK in one, speaking Cypher. MITRE CAPEC in another, speaking
  Gremlin. *Same field, explicitly cross-referenced, and still no way to ask one question
  across both.*
- So one analyst question — *"which credential-theft attack patterns map to ATT&CK
  techniques, and what mitigations exist for those?"* — becomes manual lookups in two
  consoles, by hand, every time.
- The standard fix is to **copy both into one database** (an "ETL merge"): expensive, stale
  the moment it lands, and it destroys the record of where each fact came from.
- The fashionable fix — feed everything to a chatbot — buys fluency and loses the audit
  trail. **In security, an answer you can't trace is an answer you can't act on.**

Visual: two disconnected graph icons (Neo4j/Cypher · Gremlin/Gremlin), an analyst in the
middle, a red X over an "ETL → one merged graph" arrow.

Speaker notes (≈50s):
> Security teams have gotten good at drawing attacker knowledge as graphs. What nobody has
> solved is that those graphs don't share a query language. MITRE ATT&CK and MITRE CAPEC are
> the textbook case — same domain, they cite each other by ID, and there's still no way to
> ask one question across both. So today an analyst does it by hand, or somebody builds a
> job that copies both into one database. That copy is stale the day it lands, and it
> flattens away which source each fact came from. The newer answer — embed everything, ask a
> chatbot — is worse here, because the thing a security analyst actually needs is the
> citation. Not a confident paragraph. The citation.

Source: [docs/purpose.md](../purpose.md) · [README.md](../../README.md) intro.

---

## Slide 2 — The Approach

**Headline: Don't merge the graphs. Federate the questions — and keep the receipts.**

*Plain-English opener:*

> Instead of copying both encyclopedias into one book, we built a translator that reads the
> table of contents of each, works out which parts of your question belong to which book,
> asks each one in its own language, and staples the page numbers to every sentence of the
> answer.

On-slide — four parts, each independently tested:

| # | Part | What it does |
|---|---|---|
| 1 | **Source card** | One machine-readable profile per database: how to connect, what's in it, what the safety limits are. The system reads *this*, never a hardcoded assumption about MITRE. |
| 2 | **Planner** | Reads the cards, works out what's being asked, and writes a **checkable plan** — which sources, which sub-questions, which shared IDs to join on — *before anything touches a database.* |
| 3 | **Two query specialists** | Cypher for ATT&CK, Gremlin for CAPEC. Each one drafts a query, **checks it against the card**, runs it read-only with hard limits, and converts the result into a common format. |
| 4 | **Verifier** | Joins the partial answers on shared IDs, then checks **every claim against the actual records retrieved**, deletes anything unsupported, and when the graph genuinely has nothing, says so *and shows the query it ran as proof.* |

Three commitments worth stating out loud:

- **Live, read-only, native to each engine.** No copy of the data exists.
- **No vector index, no embeddings.** Grounding comes from the schema, the source metadata,
  and the queries actually executed — not from statistical similarity.
- **No LLM ever writes a query.** Queries come from a checked template library. That is a
  deliberate constraint, and Slide 3 shows what it buys and Slide 5 what it costs.

Visual: the architecture SVG at [docs/assets/architecture.svg](../assets/architecture.svg).

Speaker notes (≈55s):
> The bet is that you don't need to move the data — you need a layer that knows what each
> source *is* and can plan across them. The planner never improvises in free text; it emits
> a structured plan we can check by machine, and all the engine-specific work is pushed down
> into specialists so the planner stays swappable. Every query is validated against the
> source's own declared schema before it touches a live database. And the last stage is a
> verifier, not a writer — it checks each claim against the records that came back, deletes
> what isn't supported, and when the graph has nothing, it says so and hands you the query.
> One design choice to flag now because it matters later: no language model ever writes a
> query in this system. Ever.

Source: [docs/purpose.md](../purpose.md), [docs/planner_agent.md](../planner_agent.md),
[docs/specialist_agents.md](../specialist_agents.md),
[docs/migration-guide.md](../migration-guide.md).

---

## Slide 3 — The Evidence

**Headline: It's built, it's measured — and it was graded by a model that didn't write the answers.**

*Plain-English opener:*

> We didn't grade our own homework. We had a different company's AI grade all 120 answers,
> question by question, against both the correct answer and the raw evidence.

**What's running** — live, against a version-pinned snapshot (ATT&CK 19.0 · CAPEC 3.9):

- ATT&CK / Neo4j: **4,369 nodes · 27,669 relationships**
- CAPEC / Gremlin: **4,769 nodes · 6,972 relationships**
- ~58,000 lines of Python · **142 test files / 1,525 tests** · a web workbench for analysts
  (chat · graph explorer · live evaluation view)

**The headline result** — 120 questions, each graded by a **separate, independent Sonnet 5
agent** (cross-model on purpose: the system never grades its own work):

| | Committed baseline | **Arm F — the product** | Arm A — no AI in the answer |
|---|---|---|---|
| Configuration | AI writes prose from raw evidence | AI writes prose from **verified claims only** | Deterministic, no AI at all |
| Correctness | 0.8946 | **0.9957** | **0.9972** |
| Correct / Partial / Incorrect | 91 / 27 / 2 | **119 / 1 / 0** | **120 / 0 / 0** |
| Answers with a hallucination | 11 | 3 | **0** |
| Time for all 120 questions | — | 533 s | **1.6 s** |

> **Read the middle column, not the right one.** Arm F is the honest like-for-like against
> the baseline: same product shape — readable analyst prose — and it goes from 0.89 to 0.996
> with **zero incorrect answers**. Arm A is the control that proves the retrieval and
> verification layers are sound on their own; it's 637× faster and hallucination-free, but
> it outputs a claim table, not prose.

**How we got there:** a controlled experiment across **seven configurations** (960
independent grading agents, one per question per arm), a classifier that identifies *which
stage of the pipeline lost the information*, and **eight concrete defects found and fixed**
— including a declared cross-source join that never reached its sub-questions, and evidence
silently doubling on every retrieval pass.

**What we are doing about the obvious objection.** Our 120 questions were written by the
same person who wrote the query templates. That is a real weakness and we are not waiting
to be asked about it: the codebase is **frozen at a tagged commit** (`freeze/holdout-v1`),
and a **blind holdout** — fresh questions, written by someone else, anchors sampled
uniformly rather than hand-picked — runs against that frozen tree. Whatever it says, it
gets reported.

Speaker notes (≈80s — go long here, this is the slide that wins or loses the room):
> Two things to take from this. First, it works. Both specialists are at ceiling on query
> validity, execution accuracy and safety. Second — and this is the part I'd want to see if I
> were you — I didn't trust our own scores. I had a model from a different vendor grade all
> 120 answers, one independent agent per question, against the gold answer *and* the raw
> evidence. It came back at 0.89 and flagged eleven hallucinations. That gap was the real
> finding. So I built a classifier that tells me which stage lost the information, ran seven
> full configurations, found eight defects, and fixed them. Re-graded: 0.996, with zero
> incorrect answers, on the configuration that produces readable prose. And the version with
> no AI in the answer path at all scores 0.997 with zero hallucinations, in one and a half
> seconds. Now — the obvious objection is that I wrote the test questions and I wrote the
> code that answers them. Correct. So the code is frozen at a tagged commit as of yesterday,
> and someone else is writing a fresh set of questions to run against it blind. I'll report
> that number whatever it is.

Source: [docs/evaluation/2026-07-26/README.md](../evaluation/2026-07-26/README.md) §1 ·
[docs/evaluation/component-evaluation.md](../evaluation/component-evaluation.md) ·
[docs/evaluation/e2e-evaluation.md](../evaluation/e2e-evaluation.md) ·
[docs/plans/robustness/02-holdout-question-generation.md](../plans/robustness/02-holdout-question-generation.md)
(holdout protocol) · recomputed figures in
[docs/plans/robustness/_overnight/numbers.json](../plans/robustness/_overnight/numbers.json).

---

## Slide 4 — Anticipated Impact

**Headline: An auditable answer layer — and a finding that says *precision beats volume*.**

*Plain-English opener:*

> The surprise wasn't that AI makes things up. It's that ours mostly didn't — it just looked
> in the wrong places, very energetically.

On-slide:

- **For an analyst:** one question, one answer spanning sources that don't share a query
  language, with the executed query attached to every claim. No pipeline to maintain, no
  stale copy, nothing to rebuild when MITRE ships a new version.
- **For a security organization:** the sources stay where they are, read-only. Adding a third
  graph is a source card plus four swap points — not a new data warehouse and not a new team.
- **The transferable research finding:** across every configuration we ran, *precision in
  planning beat volume in retrieval, every time.* The best AI configuration retrieved the
  **least** evidence of any (1,080 records) and scored the **highest**. The AI-planned
  configuration retrieved **2.6× more** and surfaced 20% **less** of the correct answer.
  **26 of 36 failures were planning or retrieval; only 2 were making things up.** That
  contradicts the standard assumption about how these systems fail, and it changes where you
  spend engineering effort.
- **The accuracy-versus-readability trade-off is not real.** Binding the writer to *verified
  claims* instead of raw evidence gets you readable prose at 0.9957 against a ceiling of
  0.9972 — a gap of 0.0015, with zero incorrect answers.
- **The measurement apparatus is itself a deliverable.** The experiment runner, the
  independent judge panel, and the stage-attribution classifier are dataset-independent.
  They found all eight defects, and they would run on ReliaQuest data unchanged.

Speaker notes (≈55s):
> The product impact is straightforward: an analyst asks one question, gets one answer
> spanning both graphs, with a citation on every claim, and nobody maintains a copy pipeline.
> The research impact is the part I didn't expect. Everyone assumes these systems fail by
> hallucinating. Ours didn't — only two of thirty-six failures were faithfulness. They failed
> by planning badly and then retrieving the wrong things very enthusiastically. The
> configuration that retrieved the least scored the highest. If that generalizes, it says the
> money in agentic systems goes into planning and verification, not into retrieving more
> context — which is where most of the field is currently spending it.

Source: [docs/evaluation/2026-07-26/README.md](../evaluation/2026-07-26/README.md) §1.

---

## Slide 5 — What Additional Funding Does

**Headline: We know what the next dollar buys, because we measured what's missing.**

*Plain-English opener:*

> Here's the weakness, before you ask. We hand-wrote the questions this system is good at.
> So we ran the experiment that measures exactly how much that's worth — and that number is
> the roadmap.

**The measured gap — state it before anyone asks:**

> The system knows **25 query templates**, 19 of them written specifically for MITRE.
> Everything else — planning, retrieval, verification, provenance, the whole measurement
> apparatus — is driven by the source card, not by MITRE. So we ran the control:
> **turn every MITRE-specific template off** and force the generic, schema-driven path.
>
> Correctness falls **0.9957 → 0.6388**. Faithfulness holds at 0.966 — *it doesn't start
> lying, it stops finding things.*

**Put the two numbers side by side, because this is the whole argument:**

| What we removed | Cost in correctness |
|---|---|
| The hand-written templates (G − F) | **−0.3568** |
| Deterministic planning, swapped for an LLM planner (B − C) | −0.1185 |

> Losing the templates costs **three times** what losing deterministic planning costs. So the
> templates are where the accuracy actually lives — and closing that gap is the highest-value
> thing anyone can fund on this project. It is now a *measured* target, not a guess.

Priorities for a second stage, in order:

1. **Close the generic path.** Make the schema-driven approach reach template-level accuracy
   with no hand-written templates. Highest leverage, and we can measure progress weekly
   against a number that already exists.
2. **Finish the blind holdout and add an external baseline.** Fresh questions from someone
   else against the frozen tree, plus a comparison against an existing system rather than
   only against ourselves. This is what turns an internal result into a publishable one.
3. **Entity resolution for schemas without clean IDs.** Every question is currently anchored
   by an identifier like `T1047` or `CAPEC-555`. A real customer schema may not have one.
   This is the identified breaking point on genuinely new data.
4. **More engines** — Amazon Neptune, Google Spanner Graph, openCypher and GQL — testing the
   portability claim against a third and fourth backend.
5. **More sources** — vulnerability feeds (CVE / CWE / KEV) and customer telemetry, joined by
   the same shared-identifier mechanism already proven on the CAPEC↔ATT&CK bridge.
6. **Enterprise controls** — role-based access and query audit logs, which the plan-first,
   gated-query design is already shaped to support.
7. **A pilot on ReliaQuest data**, measurable from week one, because the evaluation harness
   travels with the system.

Speaker notes (≈60s):
> I want to be direct about the limitation, because it's the most useful thing I can tell
> you. Our best scores lean on nineteen query templates we hand-wrote for MITRE. So I ran the
> experiment that answers "what happens on data we have no templates for" — I turned them all
> off. Correctness drops from 0.996 to 0.64. And notice: faithfulness stays at 0.97. It
> doesn't start hallucinating; it just stops finding things. That's a retrieval problem, and
> retrieval problems are tractable. Here's the number I'd put in front of you: losing the
> templates costs three times what losing deterministic planning costs. So the first thing
> more funding buys is closing that gap — making a new dataset a source card and a question
> set, not a month of hand-authoring. Then the blind holdout and a real external baseline,
> entity resolution for schemas without clean IDs, more engines, vulnerability feeds, access
> controls — and a pilot on your data. And because the measurement harness travels with the
> system, we can tell you how well it's working from week one instead of month six.

Source: [docs/evaluation/2026-07-26/portability.md](../evaluation/2026-07-26/portability.md) ·
[docs/evaluation/experiments/untruncated-generic/](../evaluation/experiments/untruncated-generic/)
(Arm G — 120 questions, independently judged, committed) ·
[docs/plans/robustness/03-deferred-work.md](../plans/robustness/03-deferred-work.md).

---

## Appendix — Backup numbers for Q&A

### The four questions most likely to come from a cybersecurity expert

**"Both your datasets are small, public, and already cross-referenced. Why not just merge
them?"** — *The strongest objection in the room; answer it without flinching.* For two public
catalogues, merging genuinely is cheap, and we have not run a merged-graph comparison — that
is an acknowledged gap and it is on the funding list. The argument for federation is about
what comes next: customer telemetry and licensed vendor feeds have different retention
rules, different access controls, and different owners. You cannot legally or practically
copy those into one warehouse, and a merge destroys the per-source provenance that makes an
answer defensible to an auditor. We are demonstrating the mechanism on the two graphs where
the ground truth is public and checkable.

**"Your questions were co-authored with your templates."** — Yes. That is why the tree is
frozen at `freeze/holdout-v1` and a blind holdout is being written by someone else, with
anchors sampled uniformly instead of picked for how well they map. The result gets reported
whatever it says.

**"Why is your own end-to-end report 1.0 but the independent judge 0.895?"** — They measure
different things. The deterministic metrics measure retrieval, join correctness and
provenance — those are genuinely at 1.0. The independent judge measures the *answer text*
against gold assertions, which is a stricter and different bar. Reporting both is the point.

**"How many runs? What are the error bars?"** — One run per configuration, 120 questions
each. No error bars, and I won't pretend otherwise. Repeat runs across seeds are on the
funding list. What makes the current result worth something is the *size of the effects* —
a 0.36 gap is not seed noise — and that every arm is byte-reproducible with the LLM off.

### Numbers

**Schedule.** Roadmap weeks 1–13 of 16 are complete as of August 1, 2026 (award began
June 8) — data layer, all four agents, end-to-end integration, component evaluation, and
end-to-end evaluation, plus the Wk 14–15 technical documentation set delivered early
(source card format, agent interface contracts, query safety model, openCypher/GQL migration
guide — proposal Deliverable #6). Remaining: bug-fix iteration, the blind holdout, pitch prep.

**Component-level scores** (deterministic — the model drafts, code grades):

| | ATT&CK (Cypher) | CAPEC (Gremlin) |
|---|---|---|
| Query validity, first-pass | 1.000 (44/44) | 1.000 (34/34) |
| Execution accuracy vs gold (exact-set) | 1.000 (46/46) | 1.000 (34/34) |
| Adversarial safety-probe block rate | 1.000 (10 probes, 0 leaks) | 1.000 (7 probes, 0 leaks) |
| Warm p50 latency | 1.1 ms | 2.6 ms |

Planner: source recall 1.000, schema adherence 1.000, source precision 0.919 — it
over-routes, and we say so.

**End-to-end deterministic metrics** — cross-source accuracy 1.000 (30/30 positives, 10/10
negatives with zero fabrication), CAPEC→ATT&CK mapping recall 1.000 (113/113), provenance
correctness 1.000 (120/120), analyst inspectability 1.000.

**Full arm table** (120 questions each, independently judged):

| Arm | Configuration | Correctness | C/P/I | Halluc. | Wall clock |
|---|---|---|---|---|---|
| A | Deterministic throughout | 0.9972 | 120/0/0 | 0 | **1.6 s** |
| F | **The product** — verified-claims narrator + retrieval loop | 0.9957 | 119/1/0 | 3 | 533 s |
| D | Verified-claims narrator | 0.9917 | 119/0/1 | 1 | 501 s |
| C | Narrator reads raw evidence | 0.9690 | 110/8/2 | 3 | 584 s |
| E | LLM-planned + retrieval loop | 0.8560 | 97/7/16 | 15 | 1,043 s |
| B | LLM-planned | 0.8505 | 92/14/14 | 12 | 1,020 s |
| G | **Templates disabled** (control) | 0.6388 | 64/14/42 | 7 | 915 s |

**"How fast is it?"** All 120 questions in **1.6 seconds** fully deterministic — **637×**
faster than the AI-planned configuration (1,019.7 / 1.6). The product configuration takes
533 s for 120 (≈4.4 s/question) and is the one that produces prose.

**"Did the retrieval loop ever actually run?"** No — and finding that was one of the eight
defects. The documented plan→retrieve→assess→re-plan loop ran a single pass, because
sufficiency was decided purely by cross-source join closure, so any single-source question
was "complete by construction" after one hop. Fixed, and the loop is part of the
best-scoring arm.

**"What breaks first on a new dataset?"** Entity resolution, not the templates. With no
stable ID convention there is nothing to extract as an anchor. The deterministic planner
already misreads *"what mitigations does ATT&CK list for T1047?"* as entities
`['Matrix', 'Mitigation']`; the LLM planner is what rescues that today.

**Attribution.** ATT&CK® and CAPEC™ are used under MITRE's terms; see
[`NOTICE`](../../NOTICE). Ariadne is not affiliated with or endorsed by The MITRE
Corporation.

**Reproduce anything on this deck:**

```bash
uv run main.py --component-eval && uv run main.py --e2e-eval
```

Every arm figure is recomputable from the committed judgment files:

```bash
uv run python docs/plans/robustness/_overnight/recompute.py
```
