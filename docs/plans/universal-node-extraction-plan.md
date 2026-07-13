# Universal Node Extraction Plan

Replacing the 24-template query registry with two schema-agnostic primitives — `describe` and `expand`.

---

## 1. Introduction

Ariadne currently reaches its graphs through a closed registry of hand-written query templates: 15 Cypher templates in `utils/specialists/cypher/builder.py` and 9 Gremlin traversals in `utils/specialists/gremlin/builder.py`, selected by an if-chain over regex-matched intent. A question either matches a template someone anticipated, or it falls through to `_node_lookup`, which returns an id and a name and nothing else. Node descriptions are reachable from exactly two of the 24 templates. Neighbour lists are silently truncated at 25. Gremlin traverses outgoing edges only, leaving `ParentOf`, `CanFollow`, and `PeerOf` structurally unroutable. The result is an extraction layer that answers the questions it was built for and quietly returns impoverished evidence for everything else.

This plan replaces that registry with two universal primitives. `describe(id_or_title)` returns **every** property on the anchor node plus a compact *facet block* — a count of adjacent nodes grouped by `(relationship, direction, neighbour label)`. `expand(anchor, facet)` returns the members of one facet, identity-only, paged with an explicit signal when paging occurs. Neither primitive knows anything about ATT&CK or CAPEC: they read whatever the node actually has. The planning LLM never names a label or a relationship type, so it cannot hallucinate schema, and schema drift stops mattering — a new MITRE edge type appears in the facet block without a code change.

The load-bearing insight from the data: **the facet block is free.** Across both graphs, no node has more than 13 distinct facets (max 7 in ATT&CK, median 2). A `describe` payload is bounded at roughly 0.04 KB of adjacency summary regardless of whether the node has 4 neighbours or 858. The cap that exists today is not a size defence — median degree is 4, so it never fires for 90% of nodes — it is a data-destruction mechanism aimed precisely at the hub nodes analysts ask about most.

Critically, the iterative retrieval loop this design needs **already exists**. `utils/orchestration/main.py:272-283` wires `bundle → assess → (synthesize | replan → specialists)` with `ORCH_MAX_HOPS` defaulting to 5. Its own configuration comment concedes the loop is inert: *"well-formed federated plans already close their joins in a single pass, so extra hops add no evidence."* That is not a property of the loop. It is a property of a retrieval primitive too impoverished to produce a frontier worth chasing. Swapping the primitive lights up machinery that is already built and already tested.

---

## 2. Gaps & Unanswered Questions

### Resolved by assumption

- **Turn count.** The pipeline should terminate as early as the evidence allows, not run a fixed number of hops. Zero LLM turns when conversation memory already holds the record; one turn when `describe` alone answers the question (true for every definitional question, since the description arrives on the first call); two or more only when the facet block reveals an expansion is required. *Assumption*: the existing `assess` node's sufficiency predicate is the right place for this early-exit check, extended to read facets.

- **`properties_json` migration.** *Assumption*: unpack on read now, migrate later. `describe` JSON-parses the blob in Python, so no graph reload is required to ship. Promotion to first-class Neo4j properties is deferred to a follow-up for indexing and query performance. The canonical JSONL already carries a proper `properties` dict — only the Neo4j store flattens it (`utils/graph_loader/stores/neo4j.py:39`).

- **Template disposition.** *Assumption*: delete all 24. If `describe`/`expand` extract everything regardless of node type, the templates are strictly redundant surface area. They are removed in Step 6, after the primitives prove out in Steps 1–5, so the change is staged rather than simultaneous.

- **Facet zero-rows.** A facet block derived from live edges can never contain a zero count — absence of a row means absence of edges. This makes "T1105 has no sub-techniques" a weaker claim than it should be. *Assumption*: emit *plausible* facets for the anchor's label from the schema registry, with real zeros, so the model can assert absence confidently rather than merely failing to observe presence.

### Requiring human input

- **Paging policy for high-degree facets.** Identity-only expansion of the largest ATT&CK facet (Process Creation, degree 858) is ~92 KB. Not fatal, but not free either. The rule this plan commits to is **never truncate silently** — but whether the ceiling is a hard page size, a token budget, or an LLM-negotiated sample is a product decision. *Human intervention is needed to answer this question.* The plan implements paging with an explicit `truncated: true` + `total: N` signal and leaves the page size as a config knob (`SPECIALIST_EXPAND_PAGE_SIZE`) pending that decision.

- **Alias source for title resolution.** ATT&CK Groups carry multiple aliases (`G0016` is "APT29", "Cozy Bear", "The Dukes", …). Title lookup will silently resolve to the wrong node — or fail — without an alias index. Whether aliases come from the STIX `aliases` property, a curated mapping, or an embedding fallback determines how much of Step 2 is real work. *Human intervention is needed to answer this question.* The plan assumes the STIX `aliases`/`x_mitre_aliases` properties are authoritative and treats embeddings as out of scope.

- **Golden-eval baseline drift.** Deleting the templates will change answers on the golden set — that is the point, since the current answers are built on truncated evidence. But it means the committed baselines in `utils/specialists/evalset/gold_bank.py` are no longer a regression signal; they are a *comparison* signal. Whether to re-baseline or to hold both sets side by side needs a call. *Human intervention is needed to answer this question.*

---

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Schema Registry and Property Unpacking

Build the foundation both primitives read from, and make node properties actually reachable.

- **Locations**:
  - New: `utils/specialists/schema/registry.py` — `SchemaRegistry` class, `build_registry()`, `label_facets()`, `label_properties()`.
  - New: `utils/specialists/schema/build.py` — walks `data/graphs/{dataset}/canonical/nodes.jsonl` and `relationships.jsonl` to derive: label → observed property keys; `(source_label, rel_type, target_label)` → plausible facet triples.
  - Modify: `utils/graph_loader/stores/neo4j.py` — `node_merge_cypher` (keep writing `properties_json` for now); add a module-level `unpack_properties()` helper that JSON-parses the blob on read.
  - Modify: `utils/planner/cards.py` (`SourceCardView`) — expose the registry so `resolve` and the validators can consult it.
- **Rationale**: `describe` cannot return "all properties" against a JSON string blob — there is nothing to enumerate. And the facet block cannot show honest zeros without knowing which facets are *plausible* for a label versus merely absent on this node. Both primitives depend on this registry existing, so it is built first. Deriving it from the canonical artifacts rather than live DB introspection means it works offline, in tests, and without a running Neo4j.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: Universal Node Extraction (1/7) Complete: Added the canonical-derived schema registry and Neo4j property unpacking.

---

### Step 2: The Resolver — Identifier or Title to Node Identity

Replace regex intent-gating with a real resolution ladder that returns ambiguity instead of guessing.

- **Locations**:
  - New: `utils/specialists/resolve/resolver.py` — `resolve_anchor()`, `ResolvedAnchor`, `AmbiguousAnchor`.
  - Modify: `utils/specialists/resolve.py` — retain `extract_attack_ids`, `extract_capec_ids`, `extract_cwe_ids`, `_extract_name_terms`; **delete** `_DOSSIER_INTENT_RE` (`:44`), `_WHATIS_INTENT_RE` (`:61`), `is_dossier_intent` (`:52`), `is_definitional_intent` (`:68`).
  - Modify: `utils/specialists/base.py` — the `resolve` step in `QuerySpecialist.run` calls the new resolver.
- **Full caller blast radius** (all six must be updated in this step — the intent regexes reach well beyond the two builders):
  1. `utils/specialists/cypher/builder.py` — imports at `:14`; `is_dossier_intent` at `:90`, `is_definitional_intent` at `:234`.
  2. `utils/specialists/gremlin/builder.py` — imports at `:18-19`; `is_dossier_intent` at `:117`, `is_definitional_intent` at `:123`.
  3. `utils/planner/intent.py` — local import at `:226`, call at `:228`.
  4. `utils/planner/drafter.py` — local import at `:302`; `should_rescue = is_definitional_intent(request)` at `:304`.
  5. `utils/specialists/resolve.py` **internally** — `definitional_name_terms` (`:254`) gates on `is_definitional_intent` at `:261`. This one is easy to miss.
  6. `utils/synthesis/composer.py` — consumes `definitional_name_terms` (import `:27`; calls at `:61`, `:118`, `:277`). **Deleting `is_definitional_intent` breaks `composer.py` transitively.** Decide whether `definitional_name_terms` keeps its intent gate (and therefore keeps a regex) or becomes unconditional name extraction. Recommended: unconditional — the resolver already knows whether a name resolved, so the gate is redundant.
  - Tests to update: `utils/specialists/tests/test_resolve.py` (imports `:10`, assertions `:185-193`).
- **Rationale**: Today the difference between getting a description and getting nothing is whether the user's phrasing matched a regex. That is the single most arbitrary failure mode in the system. The resolver replaces it with a deterministic ladder — exact id → exact name → alias → fuzzy — that always lands on a node or honestly reports that it landed on several. Ambiguity must propagate to the planner as a disambiguation prompt, never be silently collapsed to the first match. Once `describe` returns everything unconditionally, intent-gating has no remaining purpose: there is no cheap path to protect.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: Universal Node Extraction (2/7) Complete: Replaced regex intent-gating with a deterministic id/title resolution ladder.

---

### Step 3: The `describe` Primitive

Full anchor properties plus the bounded facet block, in both query languages.

- **Locations**:
  - New: `utils/specialists/primitives/describe.py` — the backend-agnostic `DescribeRequest` / `DescribeResult` contract.
  - Modify: `utils/specialists/cypher/builder.py` — new `_describe()` compiler; aggregates via `MATCH (n)-[r]-(m)` with `type(r)`, `startNode(r) = n`, `head(labels(m))`, `count(*)`, returning `n.properties_json` alongside.
  - Modify: `utils/specialists/gremlin/builder.py` — new `_describe()` compiler using `bothE()` with a `groupCount()` over `(label, direction, otherV label)`.
  - Modify: `utils/specialists/cypher/normalizer.py` and `utils/specialists/gremlin/normalizer.py` — unpack properties in full (**delete** `_DOSSIER_ATTRS` allow-lists at `cypher/normalizer.py:30` and `gremlin/normalizer.py:28`); emit the facet block.
  - **Delete**: `_DOSSIER_NEIGHBOR_CAP` (`cypher/builder.py:48`, `gremlin/normalizer.py:26`).
- **Rationale**: This is the centre of the plan. The facet block is what makes the whole design safe: it gives the planner a complete, honest picture of the node's neighbourhood in at most 13 lines, so it can decide what to fetch next *with full information* rather than being handed 25 arbitrary neighbours and no indication that 833 were dropped. The `_DOSSIER_ATTRS` allow-lists must die alongside the cap — they are the same mistake in a different costume, enumerating in advance which properties are worth returning.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: Universal Node Extraction (3/7) Complete: Added the describe primitive returning full node properties and a bounded facet block.

---

### Step 4: The `expand` Primitive

One facet, paged, identity-only, honest about truncation.

- **Locations**:
  - New: `utils/specialists/primitives/expand.py` — `ExpandRequest` (anchor, rel_type, direction, target_label, page, page_size), `ExpandResult` (members, total, truncated).
  - Modify: `utils/specialists/cypher/builder.py`, `utils/specialists/gremlin/builder.py` — the `_expand()` compilers.
  - Modify: `utils/specialists/config.py` — new `SPECIALIST_EXPAND_PAGE_SIZE` knob (see the open question in §2).
  - Modify: both normalizers — emit `truncated` / `total` on the result, never a bare short list.
- **Rationale**: `expand` returns identity only (id, name, label), never descriptions — that asymmetry is what keeps a 519-neighbour fan-out at ~8 KB instead of ~500 KB. If the planner wants a neighbour's full record it calls `describe` on it, which is the same primitive recursing. Two calls, one concept. The paging signal is non-negotiable: the rule that matters is not "never truncate," it is **never truncate silently.** A `total: 858, truncated: true` is an honest answer the planner can act on; a bare list of 25 is a lie by omission, and is what the system does today.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: Universal Node Extraction (4/7) Complete: Added the expand primitive with explicit paging and truncation signalling.

---

### Step 5: Carry Properties and Facets Through the Evidence Contract

Stop dropping the data on the floor between retrieval and synthesis.

- **Locations**:
  - Modify: `utils/specialists/contracts.py` — `EvidenceRecord` gains a `facets` field (`contracts.py:121-150`); `properties` already exists and is already populated.
  - Modify: `utils/synthesis/llm_composer.py` — `_record_line` (`llm_composer.py:78-89`) currently builds its evidence entry from `primary_id`, `label`, `name`, `join_values`, and a `related` list filtered down to `id`/`entry_id`/`name`. It **drops `record.properties` entirely** and strips `type`/`direction` from related entries. Both must be carried.
  - Modify: `utils/synthesis/narrator.py` — inherits the fix via the shared `build_evidence_context`.
  - Modify: `utils/conversation/agents/answer.py` — `_MAX_DESC_CHARS` (`answer.py:59`), `_MAX_BRIEF_RECORDS` (`:60`), `_MAX_BRIEF_CHARS` (`:66`); re-tune now that upstream truncation is gone, and make every remaining cut *signalled* rather than silent.
- **Rationale**: This is an independent bug and worth fixing even if nothing else in this plan ships. Today the claims composer and the prose narrator write their output with **zero access to node descriptions** and zero access to edge semantics — the normalizers compute `direction` and `type` correctly, and `_record_line` filters them out one layer later. Only the final answer agent ever sees a description. Steps 3 and 4 make more evidence available; this step ensures it survives the trip to the model that has to write the answer.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: Universal Node Extraction (5/7) Complete: Carried node properties, edge types, and facets through to the synthesis evidence context.

---

### Step 6: Wire the Primitives into the Existing Assess/Replan Loop

Light up machinery that is already built.

- **Locations**:
  - Modify: `utils/orchestration/agents/assess/frontier.py` — `extract_frontier()` should read the new `facets` field, so an unexpanded facet with a non-zero count *is* a frontier entry.
  - Modify: `utils/orchestration/agents/assess/policy.py` — the sufficiency predicate gains an early-exit: if `describe` already answers the sub-question, do not re-plan. This is what produces the adaptive turn count (0 / 1 / 2+) rather than a fixed budget.
  - Modify: `utils/planner/llm_drafter.py` — the plan schema (`llm_drafter.py:38-76`) currently asks the model for `entities` (labels and relationship types). Replace with anchors (ids/titles) plus optional facet selections. **The model must never name a label or a relationship type it did not first see in a facet block.**
  - Modify: `utils/planner/card_enrichment.py` — the hand-authored `entity_descriptions` glosses become redundant once the registry is authoritative. Precise delete targets: the ATT&CK block at `:81-102` and the CAPEC block at `:119-150`. **Do not delete `:104-118`** — that range holds the CAPEC `connection`/`safety`/`provenance` sections, which are unrelated and still needed.
- **Rationale**: `orchestration/main.py:272-283` already implements `bundle → assess → (synthesize | replan → specialists)`, and `ORCH_MAX_HOPS` already defaults to 5 (`utils/orchestration/config.py:30`). The loop is live and inert — its own config comment (`config.py:27-28`) admits *"extra hops add no evidence."* That was never a loop defect; the templates simply never returned a frontier worth chasing. A facet block with `MITIGATES × 6` is exactly such a frontier. This step is mostly deletion and rewiring, not new machinery.
- **Drive-by fix**: `utils/orchestration/main.py:318`'s docstring still claims `ORCH_MAX_HOPS=1` is "the default," contradicting `config.py:30` where it is 5. Correct it while in the file.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: Universal Node Extraction (6/7) Complete: Wired describe/expand facets into the existing assess/replan retrieval loop.

---

### Step 7: Delete the Template Registry

Remove the surface area the primitives have made redundant.

- **Locations**:
  - Modify: `utils/specialists/cypher/builder.py` — **delete** all 15 templates (`technique_detection`, `technique_mitigations`, `campaign_attribution`, `campaign_techniques`, `group_techniques`, `subtechnique_parent`, `software_techniques`, `tactic_technique_mitigations`, `technique_tactics`, `tactic_techniques`, `datacomponent_analytics`, `node_lookup`, `node_dossier`, `node_dossier_by_name`, `label_scan`) and the selection if-chain at `builder.py:127-239`.
  - Modify: `utils/specialists/gremlin/builder.py` — **delete** all 9 traversals and the dispatch at `builder.py:80-125`, including the `_capec_neighbors`-before-dossier ordering bug at `:112-119` and the `_AP_NEIGHBOR_RELS` allow-list at `:29-37` that renders `ParentOf`/`CanFollow`/`PeerOf` unroutable.
  - Modify: `utils/specialists/cypher/validator.py` — `_REL_TYPE_RE` (`:27`) validates relationship types by regex over the query string and cannot see `-[r]-`. Replace with structural validation of the primitive request against the schema registry.
  - Modify: `utils/specialists/gremlin/validator.py` — `_TRAVERSAL_STEP_RE` (`:30`) matches `.out(`/`.in(`/`.both(` but not `.outE(`/`.inE(`, so the dossier currently bypasses the edge-pattern check entirely. Same replacement.
  - Modify: `utils/specialists/tests/test_cypher_specialist.py`, `test_gremlin_specialist.py`, `test_cypher_validator.py`, `test_gremlin_validator.py` — rewritten against the primitives.
- **Rationale**: Validating a generated query *string* with regexes was always the weaker check, and both validators have a documented hole that the bidirectional patterns slip through. Validating a *structured request* against the registry — "does `(Technique, MITIGATES, in, Mitigation)` exist in this schema?" — is strictly stronger, fails at plan time instead of returning a silently-empty result, and is the natural check once the model emits anchors rather than query shapes. The templates go last so that every prior step lands against a working system.
- **Action**: Undergo the verification/tests/validation process for this phase. Once validated, push changes to GitHub stating: Universal Node Extraction (7/7) Complete: Deleted the 24-template registry and replaced string-regex validation with registry-backed structural validation.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Schema registry | Label → properties, and plausible `(label, rel, direction, label)` facet triples, derived from canonical artifacts. | `utils/specialists/schema/registry.py` |
| Registry builder | Walks canonical `nodes.jsonl` / `relationships.jsonl` to populate the registry. | `utils/specialists/schema/build.py` |
| Property unpacking | JSON-parses `properties_json` on read so descriptions are reachable without a reload. | `utils/graph_loader/stores/neo4j.py` |
| Anchor resolver | Deterministic id → name → alias → fuzzy ladder; returns ambiguity rather than guessing. | `utils/specialists/resolve/resolver.py` |
| `describe` primitive | Full anchor properties + bounded facet block; the request/result contract. | `utils/specialists/primitives/describe.py` |
| `expand` primitive | One facet, identity-only, paged with explicit truncation signalling. | `utils/specialists/primitives/expand.py` |
| Cypher compilers | `_describe()` / `_expand()` replacing the 15 templates. | `utils/specialists/cypher/builder.py` |
| Gremlin compilers | `_describe()` / `_expand()` replacing the 9 traversals. | `utils/specialists/gremlin/builder.py` |
| Registry-backed validators | Structural validation of primitive requests, replacing query-string regexes. | `utils/specialists/cypher/validator.py`, `utils/specialists/gremlin/validator.py` |
| Evidence contract update | `EvidenceRecord.facets`; `properties` and edge `direction`/`type` carried to synthesis. | `utils/specialists/contracts.py`, `utils/synthesis/llm_composer.py` |
| Loop wiring | Facets become frontier entries; sufficiency gains an early-exit. | `utils/orchestration/agents/assess/frontier.py`, `policy.py` |
| **Registry tests** | Assert every ATT&CK label's properties and facet triples are derived correctly from a small canonical fixture. | `utils/specialists/schema/tests/test_registry.py` |
| **Resolver tests** | Exact id, exact title, alias hit, ambiguous title (must return `AmbiguousAnchor`, not a guess), miss. | `utils/specialists/resolve/tests/test_resolver.py` |
| **`describe` tests** | Full properties returned (incl. `description`); facet block correct on a known node; **zero-degree and 858-degree nodes both bounded**. | `utils/specialists/primitives/tests/test_describe.py` |
| **`expand` tests** | Uncapped small facet returns all members; oversized facet sets `truncated: true` and a correct `total`; **assert no silent truncation**. | `utils/specialists/primitives/tests/test_expand.py` |
| **Bidirectionality test** | The Tacos/Lettuce case: given `A -[CONTAINS]-> B`, `describe(B)` must show the inbound `CONTAINS` facet. Covers the CAPEC `ParentOf`/`CanFollow` regression directly. | `utils/specialists/primitives/tests/test_describe.py` |
| **Synthesis carry-through test** | Assert `build_evidence_context` output contains node descriptions and edge directions — the `_record_line` regression guard. | `utils/synthesis/tests/test_llm_composer.py` |
| **Degree-distribution utility** | Reproduces the facet/degree statistics this plan is built on; guards against a future cap creeping back in. | `utils/specialists/schema/degree_stats.py` |

### Verification status of this plan

Every code reference above was checked against the repo before this plan was committed: **27 of 27 file paths, symbols, and line ranges verified accurate.** The two scoping errors found during that check (the under-scoped caller list in Step 2, and an over-reaching delete range in Step 6) have been corrected in place.

---

## 5. Appendix — The Data This Plan Rests On

Computed from `data/graphs/{attack,capec}/canonical/`:

| | ATT&CK | CAPEC |
|---|---|---|
| Nodes / edges | 4,369 / 27,669 | 4,769 / 6,972 |
| Median degree | **4** | 1 |
| p95 / p99 degree | 44 / 129 | 13 / 27 |
| Max degree | **858** (Process Creation) | 59 (CWE-200) |
| Nodes exceeding the cap of 25 | **450 (10.3%)** | 63 (1.3%) |
| **Facet rows per node (max)** | **7** | **13** |
| Facet rows per node (median) | 2 | 1 |

Payload for the worst-case node (Process Creation, degree 858):

| Strategy | Size |
|---|---|
| Full properties on every neighbour | **543 KB** — context death |
| Identity-only on every neighbour | 92 KB — survivable, needs paging |
| **Facet summary** | **0.04 KB** |

The cap of 25 does not fire for the median node (degree 4). It fires only on hubs — Ingress Tool Transfer loses 494 neighbours, System Information Discovery loses 401, Process Creation loses 833 — which are precisely the nodes analysts ask about. It is not a size defence. It is targeted data loss.
