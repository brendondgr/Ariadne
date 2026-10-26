# Deep-research prompt — observations from large graphs and hub nodes (2026-10-26)

One of four prompts on the agentic retrieval loop; the others are listed in
[2026-10-26-agentic-loop-README.md](2026-10-26-agentic-loop-README.md). Paste everything
inside the block into a deep-research tool and bring the report back to the Ariadne
session. Figures in the brief are quoted from `docs/research/CURRENT.md` and the
experiments it indexes.

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
the 27-32B class on one GPU (several seconds per call); hosted frontier models are a
comparison point, not the default.

## Your task: what the controller sees (large graphs and hub nodes)

The controller reads every specialist result. On a graph with millions of nodes, one
expansion from a hub can return tens of thousands of neighbours, which floods the
model's context, slows it down and makes it guess. Find what is known about shaping
graph-query results so an LLM can reason over them without being overwhelmed, while the
answer stays complete and correct.

Questions:

1. **How KG agents keep observations small.** Relation pruning and beam width
   (Think-on-Graph and successors), top-k by score, sampling, aggregation to counts,
   summaries. What does each cost in accuracy, and on which questions (lookups,
   enumerations "list every X that Y", counts, multi-hop chains)?
2. **Question-conditioned ranking without training.** BM25, off-the-shelf embeddings,
   personalised PageRank, degree or centrality priors, rerankers pre-trained elsewhere.
   Which ranks neighbours well enough to show only the top few?
3. **Completeness.** Many security questions are enumerations whose correct answer is
   every match. If the controller only sees a sample, how do published systems keep the
   final answer complete? (For example: the controller sees counts and a sample, the
   database computes the full set, and a deterministic composer lists it.) Is there
   evidence on LLMs claiming completeness they do not have when shown a truncated
   result, and on how to state truncation so they do not?
4. **Serialisation.** Triples, tables, JSON, nested adjacency, or prose: measured effects
   on accuracy and tokens when an LLM reads a subgraph.
5. **Handles and paging.** Tool-result caps, spilling large results to a store with a
   handle the model can page through, progressive disclosure (a facet summary first,
   details on request). What does the agent and context-engineering literature measure?
6. **Hubs in the database.** How Neo4j, Neptune and TinkerPop users handle supernodes:
   degree caps inside the traversal, precomputed degree properties, sampling steps,
   relationship-type indexes, query patterns that avoid fanning out. Costs at the
   million-node scale.
7. **Scale evidence.** KG question answering or graph RAG measured on graphs of a million
   nodes or more: latency, accuracy, and what broke.

## Deliverables

1. TL;DR and a one-page table: technique, where it applies (database side, specialist
   side, controller side), class (P/B/T), cost, evidence, read status.
2. Findings for each question above.
3. A recommended observation format for Ariadne's specialist results: what fields every
   result carries (for example totals, facet counts by relation and label, a ranked
   sample with its ordering stated, a truncation flag, a handle for paging), and how the
   composer stays complete when the controller only saw part of the result.
4. Recommended hub handling at the query level for Cypher and Gremlin.
5. Three to five experiments to run on Ariadne, with the measurement that decides each.
6. Bibliography with links and read status.

Keep it under about 6,000 words. Say plainly where no evidence exists.
```
