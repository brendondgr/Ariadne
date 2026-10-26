# Deep-research prompt — novelty audit of the candidate research claims (2026-10-26)

Second-round prompt on the agentic retrieval loop, written from the first round's
synthesis ([SYNTHESIS.md](../research/reports/2026-10-26-agentic-loop/SYNTHESIS.md)); the
full set is listed in [2026-10-26-agentic-loop-README.md](2026-10-26-agentic-loop-README.md).
Paste everything inside the block into a deep-research tool and bring the report back to
the Ariadne session.

```text
You are a research analyst. Today is 2026-10-26. Prefer evidence over claims. For every
figure you cite, tag how you read it: [READ] full text read, [ABSTRACT] abstract only,
[SNIPPET] search excerpt only. A figure tagged [ABSTRACT] or [SNIPPET] is a lead, not
evidence, and must not be presented as what a paper measured. Classify every method:
P = plug-and-play with an off-the-shelf model; B = needs only an automatic one-time build
step per graph; T = needs training or fine-tuning on the target graph or task. Say which.
Peer-reviewed or preprint: say which.

## The system: Ariadne

Ariadne answers natural-language questions over live knowledge graphs held in graph
databases: Neo4j (Cypher) and Gremlin/TinkerPop today, Amazon Neptune planned. Current
graphs are MITRE ATT&CK, CAPEC and CWE (about 10,000 nodes, 34 edge types), plus graphs
built by an LLM extraction pipeline from documents. Target graphs reach millions of
nodes, with high-degree hub nodes. Graphs stay in their own stores (federated, never
merged) and are joined on shared identifiers.

Each graph is described by a "source card": node labels, relationship types, the allowed
(source label, relation, target label) patterns, node properties, the identifier property
and its scheme, safety limits (max traversal depth 3, max rows 1000, timeout), connection
endpoint and backend, and a one-line description per label.

Specialists: one per store. Each builds a bounded, read-only, schema-validated query from
a small set of primitives (describe a node, expand along a relation, join projection
across sources, chained composition, two-anchor intersection) and runs it. This path is
deterministic and fast: 120 questions in 1.6 s end to end. LLM-written queries cost about
3,000x more wall-clock time, and on Gremlin in particular LLM-written traversals are
usually wrong even with instructions (a 2B model produced 0 working drafts of 17; free
text-to-Cypher by gpt-4o reaches about 60% execution accuracy on CypherBench's unseen
graphs). The design decision is fixed: the specialists stay deterministic and no
language model writes query text.

Current interface defect: the planner hands each specialist a natural-language
sub-question (text plus entity names, seed identifiers, limits, a join key), and the
deterministic builder re-reads that text with keyword rules to find names and to detect
request types. So any wording outside the vocabulary the rules expect breaks retrieval.

## What the system's own measurements show

- Given a correct plan, answers are accurate: judged correctness 0.9005 on 282 sealed
  questions, with no language model in the answer path.
- When the system plans for itself, gold coverage falls from 0.8611 to 0.4797 (-0.3814,
  n=284). On 77 of 284 the planner retrieved nothing where the correct plan retrieved
  records; never the reverse. Worst on chained and cross-source questions (about -0.50
  and -0.55).
- Wording sensitivity, records-exact by paraphrase tier: original 1.0000; synonym verb
  ("How do I defend against T1176?") 0.4667; entity named instead of given by
  identifier 0.0990 (0.3762 after deterministic fixes); paraphrased name 0.0000;
  description only 0.0000.
- Already tried and failed or mixed: an LLM-written relation lexicon from glosses (mixed;
  the synonym tier got worse); an LLM choosing an entity from a reranked candidate list
  (picked the wrong entity 35% of the time); a gated LLM rewrite stage before planning
  (lifted the hardest tiers to 0.088 and 0.164 but doubled confident-wrong answers).
- Not yet tried: an iterative agent loop in which an LLM controller calls the
  deterministic specialists as tools and reads their results; typed plan enumeration;
  edit-on-failure (Readi-style); a schema-compatibility filter on entity candidates.
- An earlier research pass already covered single-shot plug-and-play KGQA: plan
  enumeration and ranking (Pangu), Readi's edit-on-failure (1.55 edit calls on
  average), build-time relation lexicons, failure-gated cascades, and entity selection
  behind a compatibility filter with a "none" option. Do not re-survey those as
  stand-alone methods; cite them only where they fit inside the loop described below.

## The target design (what this research is for)

One LLM controller in a single tool-calling loop, modelled on Claude Code: call the
model, run its tool calls, append the results, repeat until it answers. It reads the
source cards of the graphs that are online, plans, calls the deterministic specialists
as tools, reads shaped results, decides whether it needs more or must adjust, and
iterates. When it has enough it drafts an answer, a validation step checks every claim
against the retrieved records (abstaining with the executed query as proof when nothing
holds), and the answer is returned. The whole thing must be embeddable: other systems
call Ariadne as an agent or tool and get correct, cited information back.

Priorities, in order: accuracy, then speed, then robustness. Plug-and-play: add a graph
by building its source card automatically; no per-graph training, no hand-written rules
or templates, no hand-labelled data. The controller runs on a local reasoning model in
the 27-35B class on one GPU (per-call times are measured below); hosted frontier models are a
comparison point, not the default.

## What a first research round settled (2026-10-26)

Four earlier deep-research reports (controller loop, observations, vocabulary boundary,
embedding) converged on a design; do not re-argue it, build on it:
- The controller never sends natural language to a specialist. It sends typed requests
  whose fields are the property-graph model (source, anchor id and label, relation,
  direction, target label, property filters, join key) and whose allowed values are
  computed per step from whichever source card is loaded. The design must be
  graph-universal: only the source card and the per-backend compiler change per graph.
- Choosing from a short list of valid options beats free generation, especially for small
  models (Middleware, EMNLP 2024). Executor-produced diagnostics beat self-critique
  (QueryAgent/ERASER, ACL 2024). The validator, not the model, decides when to stop.
- Answers must be exact. The controller reads bounded "envelopes" (exact totals, exact
  facet counts, a labelled sample, a completeness flag, a handle); the database computes
  the full set and a deterministic composer lists it. Nothing that belongs in the answer
  may be dropped by any shaping step.
- A wrong entity passes Ariadne's claim verifier, because the records genuinely support
  claims about the wrong node. Grounding must be defended when it happens.
- Speed comes from a cascade: deterministic fast path first, LLM loop only on failure.

Measured on the local stack on 2026-10-26 (one question, warm, single user):
- one typed tool call from the local controller model: 0.66-0.74 s with thinking off,
  1.16-2.38 s with thinking on; a pick from a four-option menu: 0.30-0.41 s;
- a decision model (d3-lite, 0.85B, returns a probability per answer to yes/no, choice or
  score questions, no generated text): about 80 ms per call; it picked the right relation
  with p = 0.614 and the right entity with p = 0.791;
- the deterministic path: 0.006 s median per question.

## Your task: refute these candidate research claims

Your job is not to help this project look new. It is to find the work that scoops it.
Treat every claim below as a hypothesis to refute first. A verdict of "clear" is only
credible if you show what you searched to try to kill it. An earlier audit of this project
found that a citation everyone relied on did not say what it was cited for, and that four
of eight prior-art rows were wrong because nobody had read past the abstract. So: read the
paper before you cite it for what it measured, and tag every citation [READ], [ABSTRACT]
or [SNIPPET].

### Candidate claims

C-A. **Exact answers under a bounded controller.** An LLM controller that reads only
bounded result envelopes (exact totals, exact facet counts, a labelled sample, a
completeness flag), while the database computes the full answer set and a deterministic
composer lists it, returns complete enumerations over million-node property graphs; and
"confident-incomplete" answers (asserting or implying completeness over a truncated view)
are a measurable failure mode of current graph agents that this design removes.

C-B. **Typed algebra vs text-to-query on unseen property graphs.** A controller that emits
typed, schema-constrained requests compiled by deterministic per-backend compilers is more
accurate than LLM-written query text on property graphs it has never seen, and the gap is
larger on Gremlin than on Cypher. No published work compares the two on unseen property
graphs, and no published work reports modern-model Gremlin generation accuracy.

C-C. **Calibrated cross-graph grounding.** A small decision model, trained once across many
knowledge graphs on questions synthesised from their schemas and reused unchanged, grounds
entity mentions and relation phrases on unseen graphs with calibrated probabilities, so
that accept / ask / abstain thresholds hold a stated wrong-entity rate.

C-D. **Interpretation verification.** Claim-level verification against retrieved records
cannot detect a wrong-entity or wrong-relation binding, because the records support claims
about the wrong node; a separate check of the binding against the question is needed and
measurably reduces confident-wrong answers.

C-E. **Federated agents across engines at hub scale.** An agent that answers across
independently administered graph stores on different engines (Neo4j/Cypher and
TinkerPop/Gremlin), unmerged and joined on shared identifiers, has not been evaluated in
published work, nor has hub-specific latency for KGQA on multi-million-node property graphs.

### What would close each claim

Search for these specifically. Any one of them, published (preprints count), closes or
narrows the claim:

- **C-A** is closed by a graph or database question-answering system that keeps the model's
  view bounded while the database computes the full answer set, and reports how complete its
  enumerations are; or by a measurement of answers that assert completeness over truncated
  tool output in a graph or database setting. Jeffries (2026) did this for document search,
  which narrows C-A to graphs but does not close it.
- **C-B** is closed by a comparison, on the same unseen property graphs and the same models,
  of requests compiled from a typed intermediate form against LLM-written query text; or, for
  its Gremlin half, by any 2025-2026 measurement of LLM Gremlin generation accuracy.
- **C-C** is closed by a grounding or linking model trained across several knowledge graphs
  and evaluated on held-out graphs for question answering, with calibration or selective
  prediction reported; its "none" half is closed by a measurement of how often LLMs correctly
  choose "none of these" in knowledge-graph entity linking.
- **C-D** is closed by a system that verifies the entity or relation binding against the
  question, separately from checking that claims are supported, and measures the effect.
- **C-E** is closed by a published evaluation of one agent answering across two or more
  independently run graph stores on different engines, without merging them; its latency half
  by hub-specific question-answering latency on a multi-million-node property graph.

### Prior art already found: go past it, and check it is described accurately

- Middleware for LLMs (Gu et al., EMNLP 2024): typed KB tools; decoupled generation from
  a list of valid actions.
- QueryAgent / ERASER (ACL 2024): typed PyQL calls compiled to SPARQL; executor diagnostics.
- SAGA (arXiv 2607.14494): schema-aware grounding for agentic text-to-SPARQL.
- GRASP (ISWC 2025): search tools vs execute-only for SPARQL agents.
- CypherBench (ACL 2025) and CYGNET (arXiv 2606.04645): text-to-Cypher on unseen graphs.
- CypherTurn (arXiv 2609.36987): autonomy divergence in text-to-Cypher agents.
- BYOKG-RAG (EMNLP 2025): multi-strategy retrieval on arbitrary KGs.
- Wikidata Search Traces (Chenene et al., arXiv 2610.06650): agent harness on a 48M-entity
  graph that keeps results out of context.
- Canedo (arXiv 2609.10237): answer path vs subgraph size; Jeffries (arXiv 2610.32110):
  truncation labelling in tool output; MoNaCo, KG-Guard, QO-Bench: under-enumeration.
- CLEAR-KGQA (arXiv 2504.09665): entropy-triggered clarification; CES-PK (arXiv 2608.24824):
  constrained entity selection.
- ULTRA, KG-ICL and other KG foundation models; zero-shot entity linking (ZESHEL, BLINK).
- AgCyRAG (RAGE-KG @ ISWC 2025) and Ozsoy (2026): federated security KG agents; the earlier
  audit conceded the architecture to them.

## Deliverables

1. A verdict per claim: killed, scooped (the mechanism exists), narrowed (state the
   surviving version exactly), or clear. Give the strongest piece of prior art against each,
   with read status. Explain each verdict first in two or three plain sentences a reader
   outside the field can follow, then in detail.
2. For every claim that survives, the exact sentence that can be defended, and the
   experiment whose result would make it a contribution rather than a description.
3. A search log: the queries run per claim, across at least three vocabularies (KGQA,
   text-to-SQL and databases, agents and tool use).
4. Which venues and workshops each surviving claim fits, and any competing group that has
   announced the same work as future work.
5. Bibliography with links and read status.

Keep it under about 6,000 words.
```
