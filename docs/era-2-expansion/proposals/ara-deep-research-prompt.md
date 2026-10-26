# Deep-research prompt — ARA Fall 2026 scope (2026-10-20)

Paste everything inside the block into a deep-research tool. Bring the report back to the
Ariadne session for discussion.

```text
You are a research analyst preparing the evidence base for a grant proposal. Today is
2026-10-20. Your job is to find what is already known, what is already claimed, and where
a real gap remains. Work adversarially: try to REFUTE the novelty claims below before you
accept any of them.

## Context

Two open-source research systems from Florida State University (Department of Scientific
Computing):

1. Ariadne (Apache 2.0). It answers natural-language security questions across live
   knowledge graphs held in different graph databases that do not share a query language
   (Neo4j/Cypher and a Gremlin/TinkerPop server). The current data is MITRE ATT&CK and
   MITRE CAPEC, which are federated rather than merged. Each graph is described by a
   "source card" (schema, provenance fields, safety limits). A planner splits the question,
   per-engine agents build bounded, read-only, schema-validated queries, results are joined
   on shared identifiers, and a deterministic verifier checks every claim against the
   retrieved records, abstaining with the executed query as proof. Its measured findings:
   - A schema-derived, template-free query engine transfers to a schema it was never
     written for: retrieval recall 0.6923 against 0.1140 for hand-written templates.
   - Given a correct retrieval plan, answers are accurate with no LLM in the answer path.
     The system's own planner is the bottleneck: it costs -0.3814 gold coverage.
   - Federation needed zero node rewrites. Merging the same two graphs rewrote 1,083 of
     9,138 nodes.
   - LLM-written queries cost about 3,000x the deterministic path in wall-clock time.
2. Synapse. It builds typed, evidence-anchored knowledge graphs from document corpora
   using an LLM pipeline (generated schema, per-file extraction, entity resolution, a
   verbatim source quote on every triple). It exports any graph it builds as an Ariadne
   source with a source card. Built so far: a micro/nanoplastics health graph (about 17,800
   nodes and 20,400 edges from 3,136 abstracts), a university-department graph, and a
   94,000-relationship full-text build.

The proposal targets the Amazon Research Awards Fall 2026 call "AI for Information
Security" (deadline 2026-11-04; about $80k unrestricted plus $40k AWS credits). It is a
one-time gift, with a 4-page proposal. The goals:
- Scale the system on AWS infrastructure, especially Amazon Neptune.
- Make it reusable by other organisations: a security company (ReliaQuest) funds the
  applied side; the Amazon award would fund open research.
- Accept ANY knowledge graph whose structure is described by a source card, from any
  domain, without per-graph engineering.
- Test learned components (graph ML, embeddings, ranking) that transfer across graphs
  instead of being trained for one graph.

The team's working thesis, which you must test: "Most graph ML models and KG systems are
fine-tuned for one graph and one graph only. A schema-agnostic layer that works on any
graph described by a source card is the unclaimed foundational capability."

## Questions to answer

A. Graph foundation models and cross-graph transfer
   1. What is the state of the art in models that transfer zero-shot or few-shot to
      knowledge graphs, or relation vocabularies, unseen in training? Cover at least
      ULTRA (Galkin et al., ICLR 2024), KG-ICL, TRIX and their successors through 2026,
      plus graph foundation models for node classification and text-attributed graphs
      (e.g. One-For-All, GraphAny, AnyGraph, OpenGraph). For each: tasks, number of
      graphs tested, zero-shot vs fine-tuned gap, largest graph size handled, code
      availability.
   2. Has any of these been applied to cybersecurity graphs (ATT&CK, CAPEC, CWE, CVE/NVD,
      D3FEND, threat-intel graphs)? With what results?
   3. Which parts of an agentic KG question-answering system could such a model replace
      or support: entity/anchor resolution, candidate ranking, predicting missing links
      (e.g. CAPEC-to-ATT&CK mappings), query planning, anomaly detection on graphs?
   4. How far does the thesis survive? State plainly which parts are already done by
      others.

B. Schema-agnostic and federated question answering over graphs
   1. Text-to-Cypher, Gremlin, SPARQL or GQL on schemas unseen in training (CypherBench,
      Text2Cypher, NL-to-Gremlin such as EICopilot, and others): accuracy on unseen
      schemas, failure modes.
   2. LLM agents that query several graph databases or query languages in one answer.
      Federated query in polystores and SPARQL federation. Check AgCyRAG, Ozsoy (2026),
      RAGE-KG 2026 and anything newer.
   3. Benchmarks that span MULTIPLE knowledge graphs or domains with executable gold
      queries scored by execution. Does one exist for security taxonomies?
   4. Planning: published evidence on LLM planners vs authored or deterministic plans
      for multi-hop graph retrieval.

C. Amazon's graph stack and research (the proposal's AWS fit)
   1. Amazon Neptune Database vs Neptune Analytics in 2026: supported query languages
      (Gremlin, openCypher, SPARQL), graph size limits, built-in algorithms, vector
      search, serverless options, and pricing. Estimate what $40k of credits buys for
      a year of research workloads.
   2. Neptune ML, GraphStorm and DGL-KE: does each train per graph? What scale do they
      reach? Is there any cross-graph or foundation-model direction?
   3. Amazon-authored or AWS-authored research on graph foundation models, KG question
      answering, and AI for security operations (2023-2026).
   4. Past Amazon Research Award recipients in AI for Information Security, and in
      graph or knowledge-graph topics. What scope and style got funded?

D. Scalable ML methods for cross-domain testing
   1. Which graph-learning and retrieval methods have a credible record at scale (tens of
      millions of edges or more) AND across domains? Cover inductive GNNs, KG embeddings,
      learned rerankers over graph neighbourhoods, entity resolution, and graph anomaly
      detection.
   2. Which public KGs would make a fair cross-domain test: several security graphs
      plus several non-security graphs of different shape (biomedical, scholarly,
      enterprise-like)? Give sizes and licences.
   3. How to evaluate LLM-BUILT graphs (noisy, like Synapse's) against curated ones
      (like MITRE's) inside the same system.

E. Multi-organisation deployment
   1. Published patterns for multi-tenant graph platforms with access control, query
      audit logs, and tenant isolation, especially for security data.
   2. Known risks of agents with graph database access (prompt injection through graph
      content, confused-deputy access, data leakage) and published defences.

## Output format

1. A one-page executive summary: the three to five strongest defensible framings for the
   proposal, each one sentence, ranked, each with the closest prior work that threatens
   it.
2. A section per question group (A-E), with tables where items are compared.
3. A table "Claims we cannot make", each with the paper that blocks it.
4. A table "Open gaps", each with why it is open and the evidence that it is.
5. A bibliography. For every citation give: authors, year, venue, link, and a read-status
   tag: [READ] (full text read), [ABSTRACT] (abstract only), [SNIPPET] (search result
   only). Never cite an [ABSTRACT] or [SNIPPET] source for what a paper measured; say
   what you could not verify.

Rules: date every product fact (AWS features and prices change). Distinguish peer-reviewed
papers from preprints and blog posts. Prefer 2024-2026 sources and flag anything older
that is still the reference point. If a question cannot be answered, say so; do not fill
the gap with a guess.
```
