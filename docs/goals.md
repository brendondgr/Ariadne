# Goals

## Primary Objective (by October 2026)

Deliver a working demonstration that:

- Queries ATT&CK and CAPEC as **distinct graph-database sources**
- Correlates attack patterns with ATT&CK techniques and mitigations
- Evaluates routing, query translation, answer grounding, and provenance correctness
- Documents guidelines for migrating the same agent framework to other query languages

**Award period:** June 8, 2026 – October 23, 2026

## Roadmap

| Status | Weeks | Phase | Task | Difficulty | Why it's needed |
| :---: |-------|-------|------|------------|-----------------|
| [x] | Wk 1–2 | Setup | Environment and tooling setup — configure dev environment, install Neo4j, Gremlin Server, and LLM tooling; establish repo structure and coding conventions | Low | All subsequent components depend on a stable local environment. Early setup prevents integration surprises later. |
| [x] | Wk 2–3 | Setup | Download and validate public data sources — obtain ATT&CK Enterprise STIX 2.1 JSON and CAPEC attack-pattern slice; validate schema completeness and CAPEC-to-ATT&CK mapping coverage | Low | Ground truth for evaluation comes from these public sources. Early validation surfaces any gaps in the published mappings before agents are built. |
| [x] | Wk 3–4 | Data layer | Build portable ATT&CK graph artifacts — normalize STIX 2.1 JSON into a backend-neutral canonical graph model (`data/graphs/attack/canonical/`) and generate Neo4j and Gremlin export projections under `data/graphs/attack/exports/`; retain `data/processed/pairs/enterprise-attack.json` as the preprocessing checkpoint | Medium | Produces a reproducible, inspectable canonical truth set before any live graph-database load. Specialist query agents can consume backend-specific exports and live projections through the runtime loader. |
| [x] | Wk 4 | Data layer | Runtime ATT&CK graph loader — load built canonical artifacts into Neo4j and Gremlin via `utils/graph_loader/` with semantic validation, preflight, idempotent upserts, runtime manifests, and no-load `health` / `verify` commands | Medium | Turns portable artifacts into verified live graph-database fixtures for Cypher and Gremlin specialist development without coupling load to download or build. |
| [x] | Wk 4–5 | Data layer | Build Gremlin CAPEC fixture — parse the pinned CAPEC XML catalog, model vertices and edges, load into a local Gremlin Server with labeled traversal paths | Medium | The Gremlin query agent requires a correctly structured property graph. Proper vertex/edge labeling is critical for bounded traversal validation later. |
| [x] | Wk 5 | Data layer | Author source cards — write structured source-card documents for each database: connection details, schema elements, provenance fields, entity types, and safety/traversal limits (auto-generated base per source merged under hand-authored overlays in `data/source_cards/overlays/` carrying the connection block, provenance fields, and safety limits `max_result_rows`/`max_traversal_depth`/`query_timeout_ms`; overlay limits pinned == specialist env defaults by `test_card_enrichment.py`, and `--plan` shows both sources routed with card-sourced limits) | Low | The planning agent reads source cards to make routing decisions. Well-authored cards directly determine how accurately the planner selects and constrains queries. |

**ITS check-in:** Both graph fixtures live, source cards complete, environment reproducible.

| Status | Weeks | Phase | Task | Difficulty | Why it's needed |
| :---: |-------|-------|------|------------|-----------------|
| [x] | Wk 6–7 | Agents | Federated planning agent — reads source cards, classifies analyst intent, identifies required entities/relationships, emits a machine-readable plan with target sources, sub-questions, join keys, and traversal limits (`utils/planner/`; live-source content probe, deterministic self-eval gate, hybrid deterministic/OpenAI-compatible drafters, bounded ReAct loop, plan-level evaluation) | High | Architectural core of the system. Its accuracy directly controls whether downstream query agents receive correct, scoped tasks and whether unnecessary database calls are avoided. |
| [x] | Wk 7–8 | Agents | Cypher specialist agent — parameterize read-only Cypher templates, validate against source card, enforce bounded execution, normalize evidence into shared format, emit grounded summaries with evaluator traces (`utils/specialists/`; shared scaffold + four swap points, deterministic MATCH-template builder, pre-run gate, `READ_ACCESS` connector, evidence normalizer) | High | ATT&CK technique and mitigation data lives in Neo4j. Must generate safe, correct queries and produce structured evidence the synthesis agent can consume reliably. |
| [x] | Wk 8–9 | Agents | Gremlin specialist agent — map plan items to bounded traversals, validate vertex/edge labels and direction, shape results into shared evidence format, emit grounded summaries with evaluator traces (`utils/specialists/gremlin/`; label + edge-direction + depth gate, `MAPS_TO` ATT&CK join filtered to taxonomy ATTACK, federation router + `--query` CLI + `notebooks/planning-schematic-agents.ipynb`) | High | CAPEC attack-pattern data lives in Gremlin. Modular design: replacing only the query prompt, validator, connector, and normalizer if the back end changes. |

**Midpoint review:** All three agents functional end-to-end on the credential-theft example query flow.

| Status | Weeks | Phase | Task | Difficulty | Why it's needed |
| :---: |-------|-------|------|------------|-----------------|
| [x] | Wk 10 | Agents | Synthesis and reporting agent — align shared identifiers (ATT&CK IDs, CAPEC IDs), detect missing/conflicting evidence, assemble grounded answers, produce tables, figures, and network diagrams with full provenance (`utils/synthesis/`; claims-with-citations composer, always-deterministic claim verifier that cuts/flags unsupported claims, enforced abstention with executed-query proof; tables/figures/diagrams remain UI work) | High | Delivers analyst-facing output. Provenance retained here makes the system auditable and distinguishes it from a black-box answer. |
| [x] | Wk 10–11 | Agents | End-to-end integration and pipeline wiring — connect planner → specialist agents → synthesis; test full credential-theft flow; resolve inter-agent format mismatches (single `run_pipeline` orchestrator shared by CLI + API with per-stage timings and a total-pipeline deadline; dependent sub-question sequencing chosen on evidence — parallel failed the snapshot gold, the sequenced flow reproduces it 18/18 correlations and 64/64 technique→mitigation pairs; live federated acceptance suite) | Medium | Individual agents in isolation do not guarantee a correct pipeline. Integration surfaces join-key mismatches, timing issues, and edge cases not visible in unit testing. |
| [x] | Wk 11–13 | Evaluation | Component-level evaluation — score planning agent on source-selection accuracy, sub-question quality, and schema adherence; score Cypher/Gremlin agents on query validity, result correctness, safety constraints, and latency (deterministic `utils/evaluation/` + `utils/specialists/evalset/` scorers: planner corpus expanded 7→31 snapshot-derived with a sub-question-quality decomposition; query validity VA at ceiling; execution accuracy EX exact-set-match + precision/recall vs snapshot gold with an error taxonomy; a bounded-execution safety audit + adversarial gate probes at 100% block; latency p50/p95/p99 with bootstrap CIs, segmented and staged; one `--component-eval` report at `docs/evaluation/component-evaluation.{md,json}`) | Medium | Proposal commits to per-component metrics. Scores diagnose weaknesses before the pitch and demonstrate rigorous evaluation to ReliaQuest. |
| [ ] | Wk 12–13 | Evaluation | End-to-end evaluation and LLM evaluator — track cross-source answer accuracy, CAPEC-to-ATT&CK mapping recall, provenance correctness, and analyst inspectability; run LLM evaluator for faithfulness, groundedness, evidence sufficiency, and unsupported-claim rate | Medium | End-to-end metrics prove the system works holistically. LLM evaluator scales faithfulness assessment across many queries. |

**Pitch workshop:** Evaluation results compiled, demo stable, narrative prepared.

| Status | Weeks | Phase | Task | Difficulty | Why it's needed |
| :---: |-------|-------|------|------------|-----------------|
| [ ] | Wk 14–15 | Evaluation | Bug fixes, iteration, and documentation — address evaluation findings, harden edge cases, write technical docs covering source card format, agent interfaces, query safety constraints, and extending to a new query language | Low | Documentation makes the prototype extensible and demonstrates that replacing a query specialist requires only four targeted changes. |
| [ ] | Wk 15–16 | Pitch prep | Pitch preparation and final demo — build live demo script around credential-theft flow; prepare slides covering architecture, evaluation results, provenance output, and path to a ReliaQuest pilot; practice Q&A | Low | October ReliaQuest pitch is the primary deliverable. A polished end-to-end demo is the clearest proof the prototype meets the research goal. |

**October ReliaQuest pitch:** Live demo, evaluation results, and future development roadmap presented.

## Research Risk Notes

- **Planning, Cypher, and Gremlin agents (Wk 6–9)** carry the highest research risk: prompt engineering, query validation, safety constraint enforcement, and inter-agent format alignment.
- **Data layer (Wk 3–5)** — vertex/edge label decisions cascade into the Gremlin agent; schema errors break downstream specialists.
- **Synthesis agent (Wk 10)** — cross-source join failures surface here if ATT&CK technique IDs are not normalized consistently between specialists.
- **Evaluation (Wk 11–13)** overlaps late agent work so component findings can inform fixes before the pitch workshop.

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
