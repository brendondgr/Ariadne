# Goals

## Primary Objective (by October 2026)

Deliver a working demonstration that:

- Queries ATT&CK and CAPEC as **distinct graph-database sources**
- Correlates attack patterns with ATT&CK techniques and mitigations
- Evaluates routing, query translation, answer grounding, and provenance correctness
- Documents guidelines for migrating the same agent framework to other query languages

## Five-Phase Timeline

**Award period:** June 8, 2026 – October 23, 2026

| Phase | Focus | Difficulty | Milestone |
|-------|-------|------------|-----------|
| 1 | Data and schema layer — STIX/CAPEC fixtures, source cards, Neo4j + Gremlin graph schemas | Medium | Foundation before agents |
| 2 | Federated planning agent — intent classification, sub-questions, source routing | High | ITS check-in |
| 3 | Source query agents — Cypher (Neo4j) and Gremlin specialists with validation and safety | High | Midpoint review |
| 4 | Synthesis agent — cross-source joins on ATT&CK/CAPEC IDs, provenance-linked answers | High | Pitch workshop prep |
| 5 | End-to-end evaluation and October demonstration | Medium–High | ReliaQuest pitch (Oct 2026) |

Phase 5 deliberately overlaps with late agent development so component evaluation findings can inform fixes before the pitch workshop.

## Research Risk Notes

- **Planning, Cypher, and Gremlin agents (Phases 2–3)** carry the highest research risk: prompt engineering, query validation, safety constraint enforcement, and inter-agent format alignment. Budget extra buffer time here.
- **Data layer (Phase 1)** is medium difficulty — parsing STIX 2.1 and CAPEC into property graphs is straightforward in principle, but vertex/edge label decisions cascade into the Gremlin agent. Getting schema wrong early breaks downstream specialists.
- **Synthesis agent (Phase 4)** is high difficulty — cross-source join failures surface here first. If ATT&CK technique IDs are not normalized consistently between specialists, provenance-linked answers break at synthesis.

## Evaluation Criteria

### Planning Agent

- Source-selection accuracy
- Sub-question quality
- Unnecessary source calls
- Schema adherence

### Cypher and Gremlin Agents

- Query validity
- Result correctness
- Safety-constraint adherence
- Latency

### Synthesis Agent

- Faithfulness
- Groundedness
- Evidence sufficiency
- Unsupported-claim rate

### End-to-End

- Cross-source answer accuracy
- CAPEC-to-ATT&CK mapping recall
- Provenance correctness
- Analyst inspectability

## Ground Truth

- MITRE ATT&CK Enterprise STIX 2.1 JSON
- MITRE CAPEC downloads
- Published CAPEC-to-ATT&CK mappings
- ATT&CK relationship objects
- Benchmark Cypher and Gremlin traversals
- Manually reviewed analyst questions

## Deliverables

1. Reproducible ATT&CK (Neo4j) and CAPEC (Gremlin) graph-database fixtures
2. Source registry with schema cards and safety limits
3. Federated agent workflow (planner, Cypher specialist, Gremlin specialist, synthesis)
4. Analyst-facing demonstration (web UI + grounded answers with provenance)
5. Component and end-to-end evaluation results
6. Migration guidelines for additional query languages (openCypher, GQL)
