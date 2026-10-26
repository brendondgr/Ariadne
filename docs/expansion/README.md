# Post-pitch expansion — where Ariadne goes next (from 2026-10-26)

**Status: discussion.** Nothing on this page is scheduled. Tests are listed so they can be
chosen later; none of them runs until the operator says so.

## The line between the two halves of the project

- **Before the pitch (July to mid-October 2026):** the research programme. That covered the
  arm comparisons, the question banks, judging, the experiments `EXP-2026-07-001` through
  `EXP-2026-09-029`, and the October pitch and showcase. Its record is
  [`docs/research/`](../research/), and its figures are quoted only from
  [`CURRENT.md`](../research/CURRENT.md).
- **After the pitch (from the ReliaQuest year-two award):** this section. It records the new
  direction, why it was chosen, and what it starts from.

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

## The direction

An LLM controller in one tool-calling loop, modelled on GAIFA's agent mod. It sends **typed,
card-derived requests** to deterministic specialists, which never read natural language. The
full design, the evidence behind it and a proposed test order are in the first-round
synthesis: [`SYNTHESIS.md`](../research/reports/2026-10-26-agentic-loop/SYNTHESIS.md).

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
   steps they can handle reliably is a question to test, step by step:
   [`decision-model-tests.md`](decision-model-tests.md).
5. **Errors that teach.** Every rejected request comes back with what to fix and the valid
   options, like GAIFA's `fix` field. An empty result comes back with a diagnosis.

## Research trail

| What | Where |
|---|---|
| Round 1 prompts (controller, observations, vocabulary, embedding) | [`docs/prompts/2026-10-26-agentic-loop-README.md`](../prompts/2026-10-26-agentic-loop-README.md) |
| Round 1 reports, filed unchanged | [`docs/research/reports/2026-10-26-agentic-loop/`](../research/reports/2026-10-26-agentic-loop/POINTERS.md) |
| Synthesis: revised design, proposed tests, open research areas | [`SYNTHESIS.md`](../research/reports/2026-10-26-agentic-loop/SYNTHESIS.md) |
| Per-call latency of the local model and d3-lite, measured 2026-10-26 | [`probe/RESULTS.md`](../research/reports/2026-10-26-agentic-loop/probe/RESULTS.md) |
| Round 2 prompts (decision models, universal coverage, novelty audit), awaiting reports | prompts 5–7 in the same README |
| Earlier post-pitch prompt: plug-and-play retrieval (2026-10-20) | [`docs/prompts/2026-10-20-plug-and-play-retrieval.md`](../prompts/2026-10-20-plug-and-play-retrieval.md) |
| ARA Fall 2026 proposal drafts | [`docs/proposal/`](../proposal/) |

## Open research candidates

Three candidates, explained in the synthesis §7. None is claimed until the novelty audit
(prompt 7) comes back.

1. Exact answers with a bounded controller.
2. Typed requests against LLM-written queries on unseen property graphs, in Cypher and Gremlin.
3. A grounding decision model trained once across many graphs.
