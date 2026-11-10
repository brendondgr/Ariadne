# Era 2 — the expansion: where Ariadne goes next (from 2026-10-20)

*Written 2026-10-26 as the post-pitch expansion section; renamed from docs/expansion/ when the
docs were split into two eras.
What we started with is [era 1](../era-1-challenge/README.md).*

**Status: discussion.** Nothing on this page is scheduled.

## The line between the two halves of the project

- **Era 1, before the pitch (June 8 to October 19, 2026), finished:** the research
  programme. That covered the arm comparisons, the question banks, judging, the experiments
  `EXP-2026-07-001` through `EXP-2026-09-029`, and the October pitch and showcase. Its record is
  [`docs/research/`](../research/), and its figures are quoted only from
  [`CURRENT.md`](../research/CURRENT.md).
- **Era 2, after the pitch (from 2026-10-20, the ReliaQuest year-two award onward):** this
  section. It records the new direction, why it was chosen, and what it starts from.

## The goal, in the operator's words

Ariadne becomes **its own agent that other systems call** to read knowledge graphs and get
the correct information back, as fast and as accurately as possible. Priorities: accuracy,
then speed, then robustness.

It must work on **any** knowledge graph. Per graph, only two things change: the source card
(built automatically) and the specialist for that graph's backend. Nothing in the controller,
the request format or the tests may be specific to cybersecurity or to the current three
graphs.

## What it starts from (quoted from the record)

| Measurement | Figure | Where |
|---|---|---|
| Correctness given a correct plan, no model in the answer path | 0.9005 (n=282) | `EXP-2026-09-018` |
| Gold coverage, authored plan → the system's own planner | 0.8611 → 0.4797 (−0.3814, n=284) | `EXP-2026-09-019` |
| Questions where the planner retrieved nothing and the authored plan did | 77 of 284 | `EXP-2026-09-019` |
| Records-exact by wording tier: original, synonym verb, named entity, paraphrased name, description | 1.0000, 0.4667, 0.0990 (0.3762 after fixes), 0.0000, 0.0000 | `EXP-2026-08-020`, `EXP-2026-09-025` |
| Wrong entity when an LLM picked from a reranked list | 35% | `EXP-2026-09-028` |
| Deterministic path, median per question, single user | 0.006 s | `EXP-2026-09-016` |

## Requirements the operator set on 2026-10-26

1. **Exact results.** No shaping or truncation step may drop anything that belongs in the
   answer. The controller's *view* can be bounded: exact totals, exact facet counts, and a
   sample labelled as one. The *answer* is the complete set, fetched by pagination and listed
   by the composer, or an explicit `partial` status saying exactly what is missing. GAIFA's
   4,000-token cap does not transfer: GAIFA can lose rows, Ariadne cannot.
   - Known defect: `utils/specialists/cypher/connector.py` stops at 1,000 rows with no flag.
2. **Graph-universal.** The request's fields (source, anchor id and label, relation,
   direction, target label, property filters, join key) are the property-graph model itself.
   Their allowed values are computed at run time from whichever card is loaded.
3. **More than one model.** No result may depend on a single model. Every test must be
   runnable across a set of models, with the served model recorded on every call (the relay
   alias has already served four different models). The first model to study is
   `minicpmv47-35b`, which the alias serves as of 2026-10-26.
4. **Decision models on their own server.** Decision models (small models that return a
   probability per answer to a yes/no, choice or score question, with no generated text) will
   run on a separate vLLM server, so their calls can run concurrently and in batches. Which
   steps they can handle reliably is a question to test, step by step.
5. **Errors that teach.** Every rejected request comes back with what to fix and the valid
   options, like GAIFA's `fix` field. An empty result comes back with a diagnosis.

## Plans, research trail and proposals

Era 2's roadmap, its step-by-step research plan, the decision-model test list, the research
prompts and reports behind the design, and the proposal drafts are kept privately, outside
this repository. See [`../../AGENTS.md`](../../AGENTS.md) for where.
