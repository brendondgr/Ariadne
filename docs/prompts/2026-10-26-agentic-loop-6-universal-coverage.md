# Deep-research prompt — what a graph-universal system needs (2026-10-26)

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

## Your task: what a graph-universal system needs

Ariadne must work on any property graph given only an automatically built source card and
a compiler for the graph's backend. Two things decide whether that is true: whether the
typed request algebra can express the questions people ask of arbitrary graphs, and
whether the source card can be built completely and automatically. Today the algebra has
describe, expand, join across sources, chained composition and two-anchor intersection.
Known gaps: property filters in the question never reach the query; no aggregates; no
absence ("X with no Y"); no variable-length or shortest paths.

Questions:

1. **Question shapes.** Across KGQA and text-to-query benchmarks over many graphs
   (CypherBench, GrailQA, KQA Pro, LC-QuAD 2.0, MetaQA, Spider, BIRD, Spider 2.0, Text2Cypher
   datasets), what question categories exist and how often does each occur? Build one
   taxonomy (lookup, multi-hop chain, intersection, union, negation/absence, count,
   group-by, superlative/argmax, comparison, numeric and date ranges, temporal validity,
   path existence, shortest path, ...) and report frequencies per benchmark.
2. **Operator sets.** Which intermediate representations cover which shapes: KoPL
   (KQA Pro), S-expressions (GrailQA), lambda-DCS, SPARQL algebra, Cypher and Gremlin step
   sets, Middleware's KB tools, QueryAgent's PyQL. What minimal operator set covers, say,
   95% of questions in the benchmarks above? Which operators are hard to compile to
   Gremlin specifically?
3. **One algebra, many backends.** Systems that compile one intermediate representation to
   several graph query languages (Cypher, Gremlin, SPARQL, GQL): how complete and how
   correct are the translations, and where do the languages differ in ways that matter
   (null semantics, path semantics, set vs bag results, ordering)? GQL (ISO/IEC 39075) is
   relevant here.
4. **Automatic source cards.** Methods for building a complete schema description from a
   live graph with no hand work: label and relationship discovery, allowed (source, rel,
   target) patterns from data, property types and value statistics, identifier-property and
   identifier-scheme detection, name and alias property detection, LLM-written glosses for
   labels and relations (and how accurate they are), degree statistics for hub detection.
   Include schema summarisation for very large schemas (hundreds of relation types). What
   goes wrong on graphs built by LLM extraction (inconsistent labels, duplicate relations,
   opaque ids)?
5. **Testing universality.** Which public benchmarks give unseen graphs with gold answers
   that can be scored by comparing result sets rather than query text? Is there any Gremlin
   or Neptune benchmark? Has anyone tested the same content under two different schemas, to
   separate schema difficulty from content difficulty?

## Deliverables

1. TL;DR and a question-shape taxonomy with frequencies per benchmark.
2. Findings for each question above.
3. A recommended operator set for Ariadne's typed algebra, ranked by question coverage,
   with notes on compiling each operator to Cypher and Gremlin.
4. A recommended automatic card-building pipeline: each field, how it is derived, and how
   it fails on LLM-built graphs.
5. A recommended universality test suite (graphs, question sets, metrics), and a "zero
   code change" protocol for adding a graph.
6. Bibliography with links and read status.

Keep it under about 7,000 words. Say plainly where no evidence exists.
```
