# Federated Agentic Access for Cybersecurity Knowledge Graph Integration

**ReliaQuest Innovation Challenge Fund**

| Field | Value |
| --- | --- |
| Challenge area | Challenge Three — Knowledge Graph Integration |
| Principal investigator | Olmo S. Zavala Romero |
| Department | Department of Scientific Computing, Florida State University |
| Email | olmo.zavala@fsu.edu |
| Project personnel | Brendon DGR, graduate research assistant / technical lead for prototype implementation, evaluation, and documentation |
| Amount requested | $29,298 |
| Project period | June 8, 2026 – October 23, 2026 |

---

## Project Summary

Cybersecurity teams increasingly rely on knowledge graphs to represent adversary techniques, attack patterns, mitigations, and related threat intelligence, but these sources often use different schemas, metadata, and query languages. This project will implement a proof-of-concept federated agentic graph-database access prototype grounded in two public cybersecurity knowledge graphs: MITRE ATT&CK Enterprise STIX and MITRE CAPEC ATT&CK-related attack patterns. The objective is to establish the technical foundation for an agentic federated query system that can work across existing databases and query languages.

The first prototype will focus on property-graph systems because they are widely used in fraud detection, network analysis, and cyber analytics. It will simulate heterogeneous graph access with one source in Neo4j queried with Cypher and a second source in a Gremlin Server environment that approximates Amazon Neptune-style traversal. The agents will operate directly through native graph-query interfaces; no vector index or embedding store will be created from the graph databases. An orchestrator agent will route the relevant parts of an analyst's natural-language question to source-specific query agents, which will generate validated queries, convert database results into grounded text, and pass evidence to a synthesis agent.

By October 2026, the team will deliver a working demonstration that queries ATT&CK and CAPEC as distinct graph-database sources, correlates attack patterns with ATT&CK techniques and mitigations, evaluates routing, query translation, answer grounding, and provenance correctness, and documents guidelines for migrating the same agent framework to other query languages. A second grant stage could request cloud funds to instantiate managed graph databases, including Google Cloud Spanner/Spanner Graph and Amazon Neptune, and extend testing to candidate languages such as openCypher and GQL.

---

## Proposed Research

### 1. Relevance, Innovation, and Impact

This proposal addresses Challenge Three — Knowledge Graph Integration. Corporate security teams increasingly depend on graph databases and knowledge graphs to represent adversary techniques, attack patterns, mitigations, and operational relationships, but these sources often sit in different systems with different schemas, metadata, and query languages. Our objective is to build a proof-of-concept federated agentic graph-database access prototype that establishes the technical foundation for an agentic query system spanning multiple existing databases and query languages.

The agentic layer assumes the participating graph databases already exist and accesses them through native, read-only query interfaces. For a reproducible demonstration, we will expose two public cybersecurity knowledge graphs as separate graph-database sources: MITRE ATT&CK Enterprise STIX in Neo4j/Cypher and the CAPEC ATT&CK-related attack-pattern slice in a Gremlin Server environment approximating Amazon Neptune-style traversal.[^5][^6] This focuses the prototype on property-graph systems common in fraud detection, network analysis, and cyber analytics while covering Cypher/openCypher, Gremlin, and GQL as representative query families.[^1][^2][^3][^4] Grounding will come from schema descriptions, source metadata, and executed graph queries; no vector index or embedding store will be created from the graph databases.

The main contribution is a reusable design for an agentic federated access layer that uses database schema and metadata to plan, route, query, and synthesize analyst requests across sources. Outputs may include final text, tables, figures, or diagrams. The intended business impact is a deployable analyst-facing prototype that reduces manual correlation work while preserving source provenance, query constraints, and auditability.

### 2. Feasibility and Technical Merit

The prototype will have four components.

#### Data and schema layer

The data and schema layer will publish source cards for each existing graph database, including connection details, schema elements, provenance fields, and safety limits. For the public demonstration, it will also provide reproducible ATT&CK and CAPEC graph-database fixtures while testing the agentic layer as an access layer over already-available databases.

#### Federated planning agent

The federated planning agent will read the source cards, classify the analyst's intent, identify required entities and relationships, and emit a machine-readable plan describing target sources, sub-questions, join keys, and traversal limits. It will explain source-selection decisions, mark unsupported request parts, and avoid unnecessary database calls.

#### Source-specific query agents

The source-specific query agents will translate narrow plan items into validated graph queries.

- **Cypher specialist** — Parameterize read-only Neo4j templates, validate them against the source card, enforce bounded execution, and normalize returned evidence.
- **Gremlin specialist** — Map plan items into bounded traversals, validate vertex and edge labels, check edge direction, and shape results for the shared evidence format.

Each specialist receives source metadata and a filtered task, then returns a validated query, normalized records, a grounded summary, and evaluator traces. To migrate to another graph query language, a future developer would replace only the query prompt, validator, connector, and result normalizer.

#### Example flow

If a user asks, *"Which CAPEC patterns related to credential theft map to ATT&CK techniques, and what mitigations appear for those techniques?"*, the planner emits:

1. A **CAPEC task** — find credential-theft patterns and mapped ATT&CK IDs.
2. An **ATT&CK task** — retrieve technique names and mitigations for those IDs.

The Cypher specialist can execute a bounded pattern query such as:

```cypher
MATCH (pattern)-[:maps_to]->(technique) RETURN IDs
```

and summarize: *"CAPEC-560 and CAPEC-565 map to T1555."*

The Gremlin specialist can execute:

```gremlin
g.V(ids).out('mitigatedBy')
```

and summarize: *"T1555 is linked to credential-access mitigations M1026 and M1027."*

The synthesis agent then joins on ATT&CK IDs and returns a provenance-linked answer, table, and compact CAPEC–ATT&CK–mitigation network plot.

#### Synthesis and reporting agent

The synthesis and reporting agent will reconcile partial evidence across sources by aligning shared identifiers such as ATT&CK technique IDs and CAPEC IDs, detecting missing or conflicting evidence, assembling grounded answers, and producing concise tables, comparison figures, or simple diagrams for analyst review. It will retain source, query, timestamp, and record-level provenance behind every claim.

#### Data plan and evaluation

The data plan uses only public, reproducible sources: ATT&CK Enterprise STIX 2.1 JSON and CAPEC downloads.[^7][^8] Ground truth will come from published CAPEC-to-ATT&CK mappings, ATT&CK relationship objects, benchmark Cypher and Gremlin traversals, and manually reviewed questions.

Evaluation will occur at component and end-to-end levels:

| Component | Metrics |
| --- | --- |
| Planning agent | Source-selection accuracy, sub-question quality, unnecessary source calls, schema adherence |
| Cypher and Gremlin agents | Query validity, result correctness, safety-constraint adherence, latency |
| Synthesis | Deterministic checks and an LLM evaluator estimating faithfulness, groundedness, evidence sufficiency, and unsupported-claim rate |

We will also track cross-source answer accuracy, CAPEC-to-ATT&CK mapping recall, provenance correctness, and analyst inspectability. The work plan aligns with the required ITS check-in, midpoint review, pitch workshop, and October ReliaQuest pitch schedule.

### 3. Team and Resource Readiness

PI Olmo S. Zavala Romero is an Assistant Professor in FSU's Department of Scientific Computing with expertise in AI-enabled data exploration, scientific machine learning, high-performance computing, and geospatial systems. His group has developed AI models for ocean data assimilation and operational ozone forecasting,[^9][^10] leads the FSU Scientific Computing Artificial Intelligence Seminar on large language models, AI agents, fine tuning, and scientific machine learning,[^11] and participates in a collaboration building a microplastics and nanoplastics knowledge graph.

The team has access to existing compute for controlled LLM comparison, including four NVIDIA A100 GPUs and 20 classroom machines with NVIDIA RTX A5000 GPUs. Brendon DGR will serve as graduate RA and technical lead. He is an FSU Computational Science PhD student whose work includes agentic knowledge graph workflows, local LLM infrastructure, Django-based agent platforms, and AI systems for healthcare and biomedical data. He will prepare the graph-database fixtures, source registry, agent workflow, and prototype evaluation/demonstration. The requested laptop and AI-assisted coding tools support portable development, integration testing, documentation, and iteration during the four-month award period.

### 4. Future Development Potential

Follow-on funding would move the prototype from two public graph-database fixtures to a stronger ReliaQuest pilot. A second grant stage could request AWS and Google Cloud credits to instantiate Amazon Neptune and Google Cloud Spanner/Spanner Graph, so the prototype can be tested across production-grade graph back ends and query-language families including Gremlin, openCypher, and GQL.[^6][^12] This stage could also add vulnerability feeds, strengthen security-specific schemas, and add role-based access controls with query audit logs.

---

## References

[^1]: Neo4j. *Cypher Manual: Overview*. https://neo4j.com/docs/cypher-manual/current/introduction/cypher-overview/

[^2]: openCypher. *Cypher Query Language Reference, Version 9*. https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf

[^3]: Apache TinkerPop. *Gremlin Query Language*. https://tinkerpop.apache.org/gremlin.html

[^4]: ISO/IEC. *ISO/IEC 39075:2024 Information Technology – Database Languages – GQL*. https://www.iso.org/standard/76120.html

[^5]: Neo4j. *What Is Neo4j?* https://neo4j.com/docs/getting-started/whats-neo4j/

[^6]: Amazon Web Services. *Amazon Neptune Documentation*. https://docs.aws.amazon.com/neptune/

[^7]: MITRE ATT&CK. *ATT&CK STIX Data*. STIX 2.1 JSON collections for Enterprise, Mobile, and ICS ATT&CK. https://github.com/mitre-attack/attack-stix-data

[^8]: MITRE CAPEC. *CAPEC List Version 3.9 Downloads*. Includes CAPEC CSV/XML/HTML downloads and ATT&CK-related patterns. https://capec.mitre.org/data/downloads.html

[^9]: O. Zavala-Romero, A. Bozec, E. P. Chassignet, and J. R. Miranda. Convolutional Neural Networks for Sea Surface Data Assimilation in Operational Ocean Models: Test Case in the Gulf of Mexico. *Ocean Science*, 21, 113–132, 2025. https://doi.org/10.5194/os-21-113-2025

[^10]: O. Zavala-Romero, P. A. Segura-Chavez, P. Camacho-Gonzalez, J. Zavala-Hidalgo, A. R. Garcia, P. Oropeza-Alfaro, R. Romero-Centeno, and O. Gomez-Ramos. Operational Ozone Forecasting System in Mexico City: A Machine Learning Framework Integrating Forecasted Weather and Historical Ozone Data. *Atmospheric Environment*, 344, 121017, 2025. https://doi.org/10.1016/j.atmosenv.2024.121017

[^11]: FSU Scientific Computing Artificial Intelligence Seminar. https://sc-ai.net/

[^12]: Google Cloud. *Spanner Graph Documentation*. https://cloud.google.com/spanner/docs/graph
