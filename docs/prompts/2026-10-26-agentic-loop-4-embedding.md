# Deep-research prompt — Ariadne as a component other systems call (2026-10-26)

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

## Your task: Ariadne as a component other systems call

The goal is that any other agent or application can call Ariadne to get correct, cited
information out of knowledge graphs, quickly. Find how knowledge-graph retrieval is
exposed to other agents today, what works, and what Ariadne's interface should be.

Questions:

1. **What exists.** How do existing products and open-source projects expose graph
   retrieval to agents? Start from: Neo4j's MCP servers and GraphRAG Python package,
   Amazon Neptune's MCP server, AWS GraphRAG Toolkit and BYOKG-RAG, Microsoft GraphRAG
   (local and global search), LlamaIndex property-graph retrievers, LangChain's graph
   QA chains, Graphiti/Zep, Cognee, TigerGraph and Memgraph offerings. For each: the
   tools exposed, what a call returns, whether an LLM writes the query, latency, and
   any published accuracy evidence.
2. **Protocol.** MCP (tools, resources, structured output, progress notifications,
   elicitation), Google's A2A, and plain OpenAPI or function-calling. Which suits a
   retrieval agent that may take from milliseconds to tens of seconds, streams progress,
   and sometimes needs to ask a clarifying question?
3. **Granularity.** Should a caller get one high-level "ask" tool (Ariadne runs its own
   loop) or the low-level tools (search entities, describe, expand, path) so the
   caller's own LLM drives? What evidence on tool granularity and agent accuracy bears
   on this? Is offering both levels common, and does it confuse callers?
4. **Response contract.** What should come back so a calling agent can trust and use it:
   answer, evidence records with provenance, the executed queries as a witness,
   completeness and truncation flags, confidence, explicit abstention with reason. Are
   there standards or conventions (W3C PROV, MCP structured content, citation formats)?
   How do callers' LLMs actually use citations and abstentions they receive?
5. **Speed.** Plan and query caching, semantic caches, a deterministic fast path with
   the LLM loop only on failure, latency budgets per call. Published latency figures
   for graph retrieval agents.
6. **Safety of an embedded agent.** Graph content (node descriptions written by others
   or by an LLM extraction pipeline) is untrusted text that reaches the controller's
   context: prompt-injection risk and published defences. Read-only enforcement and
   tenant isolation when several callers share one deployment.
7. **Testing a component.** How to evaluate a retrieval agent as a component: tool-use
   benchmarks, repeated-run consistency (pass^k), contract tests, and graph-QA
   benchmarks with unseen schemas (CypherBench, Text2Cypher datasets, GrailQA zero-shot,
   others) that Ariadne could report on.

## Deliverables

1. TL;DR and a comparison table of existing offerings (tools, LLM writes query or not,
   return format, latency, evidence, read status).
2. Findings for each question above.
3. A recommended interface for Ariadne: protocol, the tool list at each level with
   inputs and outputs, the response schema, streaming and clarification behaviour, and
   caching.
4. Where Ariadne's design (deterministic executors, source cards, federation, claim
   verification with abstention) is unusual compared with these offerings, and where it
   is behind them.
5. Three to five experiments or integration tests, with the measurement that decides each.
6. Bibliography with links and read status.

Keep it under about 6,000 words. Say plainly where no evidence exists.
```
