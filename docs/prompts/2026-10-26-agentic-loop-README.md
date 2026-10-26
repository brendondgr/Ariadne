# Deep-research prompts — the agentic retrieval loop (2026-10-26)

Prompts for separate deep-research chats, in two rounds. Each one carries the same brief, so it
stands alone; only the task section differs. Run them in any order and bring every
report back to the Ariadne session.

| # | File | Question it answers |
|---|---|---|
| 1 | [controller](2026-10-26-agentic-loop-1-controller.md) | Which loop design (action space, control pattern, stopping and recovery rules) fits an LLM controller that drives deterministic specialists? |
| 2 | [observations](2026-10-26-agentic-loop-2-observations.md) | How should specialist results be shaped so hub nodes on million-node graphs don't flood the controller, while enumerations stay complete? |
| 3 | [vocabulary](2026-10-26-agentic-loop-3-vocabulary.md) | How does the user's wording get into the card's vocabulary, so the specialists receive typed requests and never read natural language? |
| 4 | [embedding](2026-10-26-agentic-loop-4-embedding.md) | What interface lets other agents and systems call Ariadne, and what must each response carry? |

The four reports came back on 2026-10-26 and are filed, with a synthesis, in
[`docs/research/reports/2026-10-26-agentic-loop/`](../research/reports/2026-10-26-agentic-loop/SYNTHESIS.md).
Second round, written from that synthesis:

| # | File | Question it answers |
|---|---|---|
| 5 | [decision models](2026-10-26-agentic-loop-5-decision-models.md) | Which decision models and calibrated classifiers can make the loop's grounding and control decisions, and can one be trained once across graphs? |
| 6 | [universal coverage](2026-10-26-agentic-loop-6-universal-coverage.md) | What operators a graph-universal request algebra needs, how to build complete source cards automatically, and how to test on unseen graphs |
| 7 | [novelty audit](2026-10-26-agentic-loop-7-novelty-audit.md) | A refutation brief against the five candidate research claims in the synthesis |

## The design the prompts assume

Taken from GAIFA's agent mod (`~/Agents/GAIFA/services/agent/agent/loop.py`,
`docs/agent-architecture.md` there):

| GAIFA agent | Ariadne equivalent |
|---|---|
| One hand-written loop: call the model, run its tools, append results, stop on a reply with no tool calls | The controller: plans, calls specialists, reads results, iterates, then drafts the answer |
| Tool schemas loaded on demand (`find_tools`, `load_tools`) | Source cards of the graphs that are online, read on demand rather than all in the prompt |
| Tool errors carry a `fix` field saying what to change | A specialist rejects an out-of-vocabulary request with the valid options |
| Results capped at 4,000 tokens, numbered `#n`, paged with `read_result` | **Does not transfer as is.** GAIFA can lose rows; Ariadne cannot. The controller reads a bounded view (exact totals, exact facet counts, a labelled sample), while the full set is fetched by pagination and listed by the composer, so nothing that belongs in the answer is dropped |
| Repeated-call guard, step cap, a forced wrap-up with no tools | The same guards, plus abstention with the executed query |
| Approvals enforced by the hub, not by the model | The claim verifier stays deterministic and outside the model |

The prompts cover retrieval only. Writing to graphs belongs to Synapse and is out of scope.
