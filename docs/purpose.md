# Purpose

## Challenge and Funding

**ReliaQuest Innovation Challenge Fund** — Challenge Three: Knowledge Graph Integration

**Project period:** June 8, 2026 – October 23, 2026  
**Amount requested:** $29,298

## Problem

Cybersecurity teams increasingly rely on knowledge graphs to represent adversary techniques, attack patterns, mitigations, and threat intelligence. These sources often use different schemas, metadata, and query languages, making cross-source correlation slow and error-prone for analysts.

## Solution

Ariadne implements a **federated agentic graph-database access prototype** — a reusable design for an agentic layer that uses database schema and metadata to plan, route, query, and synthesize analyst requests across existing graph databases through native, read-only query interfaces.

Grounding comes from schema descriptions, source metadata, and executed graph queries. **No vector index or embedding store** is created from the graph databases.

## Demonstration Sources

| Source | Backend | Query language |
|--------|---------|----------------|
| MITRE ATT&CK Enterprise STIX 2.1 | Neo4j | Cypher |
| MITRE CAPEC (ATT&CK-related attack patterns) | Gremlin Server (Neptune-style) | Gremlin |

Public, reproducible fixtures are built from ATT&CK STIX JSON and CAPEC downloads.

## Architecture

Four components:

1. **Data and schema layer** — Source cards per graph database (connection details, schema elements, provenance fields, safety limits) plus reproducible ATT&CK and CAPEC fixtures.
2. **Federated planning agent** — Reads source cards, classifies analyst intent, identifies entities and relationships, emits a machine-readable plan (target sources, sub-questions, join keys, traversal limits).
3. **Source-specific query agents** — Cypher specialist (Neo4j) and Gremlin specialist (bounded traversals). Each validates queries, enforces safety constraints, normalizes evidence, and returns grounded summaries with evaluator traces.
4. **Synthesis and reporting agent** — Reconciles partial evidence across sources by aligning shared identifiers (ATT&CK technique IDs, CAPEC IDs), detects conflicts, assembles provenance-linked answers, tables, and diagrams.

**As implemented**, components 2–4 run deterministically by default: the planner
matches schema labels from the source cards, the query agents compile
card-validated read-only templates (no LLM writes a query), and the synthesis
agent composes claims from evidence and verifies each one before rendering. Each
LLM seam is opt-in, individually backstopped, and off in `.env.example`. The
controlled seven-arm evaluation in `evaluation/2026-07-26/README.md` is why:
the deterministic path scores highest, and LLM planning is the single largest
source of loss. See the "What actually runs" table in the [README](../README.md).

## Example Analyst Flow

**Question:** "Which CAPEC patterns related to credential theft map to ATT&CK techniques, and what mitigations appear for those techniques?"

1. **Planner** emits a CAPEC task (find credential-theft patterns and mapped ATT&CK IDs) and a dependent ATT&CK task (retrieve technique names and mitigations for those IDs).
2. **Gremlin specialist** (CAPEC) executes a bounded traversal over the `MAPS_TO` edges, filtered to the `ATTACK` taxonomy, and summarizes: "CAPEC-560 and CAPEC-565 map to T1555."
3. **Cypher specialist** (ATT&CK) is seeded with the join values the Gremlin side produced, executes a bounded `MITIGATES` match, and summarizes: "T1555 is linked to credential-access mitigations M1026 and M1027."
4. **Synthesis agent** joins on ATT&CK IDs and returns a provenance-linked answer, table, and compact CAPEC–ATT&CK–mitigation network plot.

## Team

| Role | Person |
|------|--------|
| Principal Investigator | Olmo S. Zavala Romero — Assistant Professor, FSU Department of Scientific Computing |
| Graduate RA / technical lead | Brendon DGR — prototype implementation, evaluation, documentation |

**Compute:** Four NVIDIA A100 GPUs and 20 classroom machines with RTX A5000 GPUs for controlled LLM comparison.

## Future Development

A second grant stage could instantiate managed graph databases (Amazon Neptune, Google Cloud Spanner/Spanner Graph), extend testing to openCypher and GQL, add vulnerability feeds, strengthen security schemas, and add role-based access controls with query audit logs.
