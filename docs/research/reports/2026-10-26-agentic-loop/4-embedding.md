# Exposing Ariadne as a Callable Knowledge-Graph Agent: Interface, Contract, Speed, Safety and Tests

**Bottom line:** Expose Ariadne as an MCP server (specification revision 2026-07-28). Offer one high-level `ariadne_ask` tool that returns a verified, cited answer envelope, plus a small set of typed, deterministic low-level tools. Both levels should share one typed plan schema, so that the planner-to-specialist interface stops passing natural-language sub-questions. Nothing on the market combines deterministic executors, federation and per-claim verification. The trade-off is that Ariadne is currently far behind existing offerings on paraphrase robustness and entity resolution, and that gap, not the protocol, decides whether callers can trust it.

## TL;DR

- **What exists:** Almost every graph offering exposes either (a) "get schema + run arbitrary query" tools, where the *caller's* LLM writes Cypher/Gremlin (Neo4j, Neptune, Memgraph, TigerGraph MCP servers), or (b) one opaque "search/ask" call with an LLM inside (Microsoft GraphRAG, Cognee, Graphiti/Zep, AWS GraphRAG Toolkit). None returns a machine-checkable witness of what was executed together with claim-level verification and explicit abstention; LangChain's `return_intermediate_steps` and Neo4j GraphRAG's `metadata['cypher']` come closest.
- **What Ariadne should be:** An MCP 2026-07-28 server with `outputSchema`/`structuredContent` for a typed answer envelope, `notifications/progress` for streaming, the Tasks extension for runs beyond a few seconds, and Multi Round-Trip Requests (`input_required`) for clarification. Expose source cards as resources. Offer both `ariadne_ask` and roughly six deterministic primitives (resolve, describe, expand, join, paths, execute_plan). A2A and plain OpenAPI should be thin adapters, not the primary surface.
- **What decides success:** The protocol is the easy part. The hard part is the typed interface and entity resolution: Ariadne's records-exact drops from 1.0000 to 0.0000 on paraphrased names, while public text-to-Cypher accuracy has been rising (CypherBench, ACL 2025: claude3.5-sonnet 61.58% zero-shot execution accuracy, gpt-4o "slightly worse"; the CYGNET preprint, arXiv 2606.04645, Table 10, reports Gemma 4 31B at 77.6% single-attempt zero-shot execution accuracy on 2,348 CypherBench test questions). Run the five decision experiments in the final section before freezing the interface.

## Conventions used in this report

- Read status: **[READ]** full text (or the relevant full section) was read in this pass; **[READ-sub]** read in full by the delegated sub-agent; **[ABSTRACT]** abstract only; **[SNIPPET]** search excerpt only. Figures tagged [ABSTRACT] or [SNIPPET] are leads, not established measurements.
- Method class: **P** = plug-and-play with an off-the-shelf model; **B** = needs an automatic one-time build step per graph; **T** = needs training/fine-tuning on the target graph or task.
- Publication status is stated per paper (peer-reviewed venue vs. arXiv preprint vs. vendor documentation/blog).

## 1. Comparison of existing offerings

| Offering | Tools / entry points exposed | Who writes the query | What a call returns | Latency evidence | Accuracy evidence | Class | Read status |
|---|---|---|---|---|---|---|---|
| Neo4j official MCP server (`neo4j/mcp`) | `get-schema`, `read-cypher`, `write-cypher` (disabled with read-only env flag), `list-gds-procedures` | Caller's LLM writes Cypher | Raw query rows | None published | None published | P | [SNIPPET]\[1\] |
| Neo4j Labs `mcp-neo4j-cypher` (+ memory, data-modeling, Aura servers) | `get_neo4j_schema`, `read_neo4j_cypher`, `write_neo4j_cypher` | Caller's LLM | Raw rows | None | None | P | [SNIPPET]\[2\]\[3\] |
| Neo4j GraphRAG Python package | `VectorRetriever`, `VectorCypherRetriever`, `HybridRetriever`, `HybridCypherRetriever`, `Text2CypherRetriever`, `ToolsRetriever` (wraps retrievers as LLM tools) | Text2Cypher: package's LLM; Vector-Cypher: developer-written template | `RetrieverResultItem`s; metadata includes the generated Cypher | None | None | Text2Cypher P; vector retrievers B (index + embeddings) | [SNIPPET]\[4\]\[5\] |
| Amazon Neptune MCP server (awslabs) | Run openCypher/Gremlin query, get schema "as a text string", get status | Caller's LLM | Raw results | None | None | P | [READ]\[6\] |
| AWS GraphRAG Toolkit, lexical graph | Traversal-based and semantic-guided search; `create_mcp_server()` exposes graph tools; `tenant_id` multi-tenancy | Toolkit's LLM builds graph; retrieval is vector entry + 1–2-hop traversal, then LLM answer | Answer plus structured sources (sources → topics → statements → facts) | None | None | B (LLM extraction build) | [SNIPPET]\[7\]\[8\]\[9\] |
| AWS BYOKG-RAG (in same toolkit) | LLM "KG-Linker" emits entities, relation paths, openCypher, draft answer; tools do entity linking, follow-paths, shortest-paths, query execution, agentic/scoring triplet retrieval; iterative refinement | LLM writes openCypher *and* proposes paths; deterministic tools execute | Retrieved graph context for final LLM answer | Relative cost only: agentic retrieval 1.6×, BYOKG-RAG 2.4× of LLM+graph-query [SNIPPET] | +4.5 points over second-best graph retrieval method across benchmarks [ABSTRACT]; Hit 80.1/65.5/65.0 on Wiki/Temp/Med KGs [SNIPPET] | P (string/embedding linking; no training) | [READ] method §1–3.5; results [ABSTRACT]/[SNIPPET]. EMNLP 2025 (peer-reviewed)\[10\] |
| Microsoft GraphRAG (local, global, DRIFT) / LazyGraphRAG | CLI/library query methods `local`, `global`, `drift`; no first-party MCP surface found in this pass | LLM summarises communities at index time; LLM map-reduce at query time | Generated answer with context data | Global search "20–24 s" end-to-end in a secondary blog [SNIPPET] | LazyGraphRAG: global-query quality comparable to GraphRAG global search at ">700× lower query cost"; at 4% of C2 cost "significantly outperforms" all conditions (vendor blog) [SNIPPET] | B (expensive LLM index; LazyGraphRAG cheap NLP index) | [SNIPPET]\[11\]\[12\] |
| LlamaIndex PropertyGraphIndex retrievers | `LLMSynonymRetriever`, `VectorContextRetriever`, `TextToCypherRetriever`, `CypherTemplateRetriever` (LLM fills parameters of a fixed template) | LLM (free Cypher or template slots) | Nodes/paths, optional source text | None | None | P (text2cypher) / B (vector) | [SNIPPET]\[13\]\[14\] |
| LangChain `GraphCypherQAChain` | One chain: LLM → Cypher → execute → LLM answer; `validate_cypher` corrects relationship directions; `return_intermediate_steps` returns generated query and context; requires `allow_dangerous_requests=True` | LLM | Answer + optional intermediate steps (query, rows) | None | None | P | [SNIPPET]\[15\]\[16\] |
| Graphiti MCP server / Zep | `add_memory`, `search_nodes`, `search_memory_facts`, `get_entity_edge`, `get_episodes`, `delete_*`, `clear_graph`, `build_communities`, `get_status` (server marked "experimental") | No query language; hybrid vector + BM25 + traversal search | Node summaries / facts (edges) with validity windows | Graphiti README: "typically sub-second"; Zep site: 155 ms retrieval on LoCoMo (vendor marketing) [SNIPPET] | Zep site: LoCoMo 94.7%, LongMemEval 90.2% (vendor marketing, memory not KGQA) [SNIPPET] | B (LLM ingestion builds graph) | [SNIPPET]\[17\]\[18\]\[19\] |
| Cognee (library, REST, MCP) | MCP: `cognify`, `codify`, `search`, `list_data`, `delete` [SNIPPET]; `search` takes a `SearchType` (≈20 modes incl. `CYPHER`, `NATURAL_LANGUAGE`, `GRAPH_COMPLETION`, `AGENTIC_COMPLETION`, `FEELING_LUCKY`) | Depends on mode: `CYPHER` caller-written; `NATURAL_LANGUAGE` LLM-written; completion modes LLM answers | Answer or raw rows/chunks | Measured on a 99-node graph: `CHUNKS` ~0.3 s, `GRAPH_COMPLETION` ~3.9 s, `NATURAL_LANGUAGE` ~50 s, `GRAPH_COMPLETION_COT` ~200 s; `CYPHER` ~1 ms *estimated* | None for accuracy in docs | B | [READ] (SearchType docs)\[20\]\[21\]\[22\] |
| TigerGraph MCP (`tigergraph-mcp`) | Many tools (a directory lists 69), incl. `get_graph_schema`, `get_neighbors`, `run_query`, `run_installed_query`, optional LLM `generate_gsql`/`generate_cypher`, plus admin tools (create/drop/clear graph) | Caller's LLM, or server-side LLM generation | Raw results | None | None | P | [SNIPPET]\[23\]\[24\] |
| Memgraph MCP (`mcp-memgraph`) | Default: `run_cypher_query`, `search_schema`, `get_node_schema`, `get_relationship_schema`, `get_enum_schema`, `list_databases`, `use_database`; read-only by default; experimental server with "autonomous GraphRAG" via sampling and elicitation | Caller's LLM | Type-tagged nodes/relationships/paths | None | None | P | [SNIPPET]\[25\]\[26\]\[27\]\[28\] |

**What the table means:**

1. The industry default is "schema + free query" for database vendors and "one opaque search call" for GraphRAG/memory vendors. **Nobody publishes accuracy for their MCP servers.** The only accuracy numbers come from research papers (BYOKG-RAG, CypherBench) and from vendor blogs or marketing (Microsoft, Zep) measured on their own tasks.
2. Read-only enforcement is mostly weak:
   - Neptune's server "will run any query sent to it, which could include both mutating and read-only actions", and safety is left to IAM [READ].\[6\]
   - Neo4j enforces read-only via EXPLAIN and query-type classification, but notes that misclassified custom procedures "may bypass this check" [SNIPPET].\[29\]
   - Memgraph blocks write keywords [SNIPPET].\[28\]
   
   Ariadne's fixed primitive set is structurally stronger than all of these.
3. Only LangChain (`return_intermediate_steps`) and Neo4j GraphRAG (`metadata['cypher']`) return the executed query, and only as an optional debug field, not as a contract.\[15\]

## 2. Findings by question

### Q1. What exists: patterns and lessons

Three exposure patterns recur:

- **Pattern A: thin database tools** (Neo4j, Neptune, Memgraph, TigerGraph). The calling agent's LLM must write the query. Latency equals database latency plus caller LLM time. Accuracy is whatever the caller's model achieves on text-to-Cypher. This is exactly the approach Ariadne has rejected for itself.
  - The external evidence partly supports the rejection and partly erodes it. CypherBench (ACL 2025, peer-reviewed) reports that "claude3.5-sonnet achieves an execution accuracy of 61.58% and a PSJS of 80.85%", with gpt-4o "performing slightly worse" (60.18%); "the highest-performing open-source model reaches only 41.87%" (qwen2.5-72b), and "smaller models in the <10B parameter range achieve less than 20% execution accuracy" (§6.2; llama3.1-8b 18.82%) [SNIPPET]. The CYGNET preprint (Nikodem Tomczak, Thulge Labs, arXiv 2606.04645, June 2026, Table 10), using CypherBench's own zero-shot prompt template on 2,348 questions over 7 test-split schemas, reports single-attempt zero-shot execution accuracy of 85.3% for Gemini 3.1 Pro, 83.8% for Gemini 3 Flash and 77.6% for Gemma 4 31B [SNIPPET].
  - If that snippet holds, a 31B open model, inside Ariadne's local-model class, now writes Cypher correctly about three times in four. The brief's "about 60%" premise is therefore dated for Cypher.
  - The external record has no comparable figure for Gremlin. Ariadne's own 0/17 result is the only Gremlin evidence found, and it comes from a 2B model.
- **Pattern B: one opaque call** (Microsoft GraphRAG, Cognee completion modes, Graphiti search, AWS lexical graph). These offerings are easy for callers, but provenance is weak (text chunks or summaries, not executable witnesses), and latency spans milliseconds to minutes depending on mode. Cognee's own measurements are the most honest public latency data found: the jump from a single-LLM-call mode (~3.9 s) to iterative modes (~50–200 s) on a tiny graph [READ] shows what an iterative loop costs.\[20\]
- **Pattern C: LLM proposes artifacts, deterministic tools link and execute** (BYOKG-RAG). This is the closest published analogue to Ariadne's target design. Its KG-Linker emits entities, relation paths, a query and a draft answer in one LLM call. Fuzzy-string and embedding linkers ground the entities, follow-paths and shortest-path tools execute, and the loop refines [READ].\[10\]
  - Its lesson is that **multiple linking and retrieval strategies beat a single agentic traversal**: the abstract claims +4.5 points over the second-best method [ABSTRACT]; the snippet shows agentic retrieval at 69.3 versus BYOKG-RAG at 73.6 at 1.6× versus 2.4× cost [SNIPPET].\[30\]\[31\]
  - It differs from Ariadne in that it still lets the LLM write openCypher as one of its strategies.

### Q2. Protocol

**MCP, current revision 2026-07-28 [READ].** This is the largest revision since launch. The changes relevant to Ariadne:

- **Stateless core.** The `initialize` handshake and `Mcp-Session-Id` header are removed. Each request carries protocol version and client capabilities in `_meta`, and a new `server/discover` call is optional. Cross-call state must be "explicit, server-minted handles passed as ordinary tool arguments." The maintainers write that this "works better than session state hidden in the transport - the model can see the handle and thread it between tools."\[32\] For Ariadne, a `run_id`/`cursor` handle is the right way to support follow-ups and pagination.
- **Multi Round-Trip Requests (MRTR).** Server-initiated elicitation is replaced: "the server returns `resultType: "input_required"` along with the requests it needs answered, and the client retries the original call with the answers attached in `inputResponses`." Elicitation (a server asking the user for structured input mid-call) has a form mode, restricted to flat objects with primitive fields and enums, and a URL mode for sensitive flows [READ].\[32\]\[33\] An enum of candidate entities fits form mode directly.
- **Tasks** move out of the experimental core into the `io.modelcontextprotocol/tasks` extension, with poll-based `tasks/get` and a new `tasks/update`. Servers may return task handles unsolicited [READ].\[34\] Tasks first appeared as experimental in 2025-11-25 [SNIPPET].\[35\]
- **Progress.** `notifications/progress` keyed by a client-supplied `progressToken` continues to flow on the request's response stream. Progress "MUST increase with each notification", and servers may send none at all [READ-sub].\[34\]\[36\]
- **Structured output.** Tools may declare `outputSchema`. "Servers MUST provide structured results that conform to this schema. Clients SHOULD validate structured results against this schema." Tools that return `structuredContent` "SHOULD also return the serialized JSON in a TextContent block" for backward compatibility. Tool execution errors use `isError: true` and "Clients SHOULD provide tool execution errors to language models to enable self-correction." `resource_link` content lets a tool point to fetchable resources [READ-sub].\[37\]
- **Caching.** List results carry `ttlMs` and `cacheScope` (`public`/`private`), and servers SHOULD return tools in deterministic order "to improve LLM prompt cache hit rates" [READ].\[34\]
- **Deprecations.** Sampling, Roots and Logging are deprecated, with a twelve-month minimum window [READ].\[32\] Ariadne should not design its controller around MCP Sampling (borrowing the caller's model). Memgraph's experimental "autonomous GraphRAG" server is built on exactly that feature [SNIPPET],\[28\] which is a warning sign.\[25\]
- **Trust.** "Clients MUST consider tool annotations to be untrusted unless they come from trusted servers" [READ-sub].\[37\] A `readOnlyHint` is therefore documentation, not a guarantee.

**Google's A2A [SNIPPET].** A2A models work as a Task with states including `TASK_STATE_WORKING`, `TASK_STATE_INPUT_REQUIRED`, `TASK_STATE_AUTH_REQUIRED` and terminal states. It offers blocking or `returnImmediately` sends, SSE streaming of status and artifact updates, push notifications, and an Agent Card for discovery. A 1.0 version with renamed enum values exists [SNIPPET].\[38\]\[39\] A2A's model (opaque agent, task lifecycle, artifacts) fits "Ariadne as a peer agent" well. Its weakness for this use is that most agent hosts today attach tools through MCP, and A2A has no equivalent of typed per-tool `outputSchema` for low-level primitives.

**Plain OpenAPI or function-calling.** This works for single synchronous calls and is the lowest common denominator. It has no standard progress, clarification or long-running-task semantics, so each would have to be reinvented.

**Verdict (judgment, not measured).** MCP 2026-07-28 now covers every requirement in the brief:

| Requirement | MCP mechanism |
|---|---|
| Millisecond calls | Plain `tools/call` |
| Tens-of-seconds calls | Tasks extension + progress |
| Clarification | MRTR `input_required` |
| Typed contracts | `outputSchema` |
| Horizontal scaling | Stateless core |

Use MCP as the primary surface. Generate an A2A Agent Card and an OpenAPI description as thin adapters over the same handlers. Two caveats: Tasks is an *extension* and client support is uneven, so callers that ignore it must still get a bounded synchronous answer; and no evidence was found comparing protocols on retrieval-agent accuracy or latency.

### Q3. Granularity: one "ask" tool, low-level tools, or both?

The evidence is indirect but consistent:

- **Fewer, consolidated tools help agents.** Anthropic's tool-design guidance [READ]:
  - "More tools don't always lead to better outcomes." The guidance recommends tools that "consolidate functionality" and "handle frequently chained, multi-step tasks in a single tool call", and warns that "too many tools or overlapping tools can also distract agents."\[40\]
  - It recommends namespacing (e.g., `asana_search`), notes that prefix versus suffix naming had "non-trivial effects" on evaluations, and recommends a `response_format` parameter (concise/detailed).\[40\]\[41\]
  - This is a vendor engineering blog with internal evaluations, not a peer-reviewed study.
- **Selection accuracy falls as tool count grows:**
  - RAG-MCP (Gan & Sun, arXiv 2505.03275, May 2025): retrieval-filtered tool selection "more than triples tool selection accuracy (43.13% vs 13.62% baseline)" and "cuts prompt tokens (e.g., by over 50%)" on large tool sets [SNIPPET].
  - OSWorld-MCP (arXiv preprint): removing RAG filtering over 158 tools cut accuracy on tool-beneficial tasks from 24.9 to 18.0 [SNIPPET].\[42\]
  - A 2026 cloud-scale study (arXiv preprint): naive selection fell from 92.4% at 15 tools to 78.2% at 640 [SNIPPET].\[43\]
  
  These concern tool counts far above Ariadne's 6–8, so they argue against a 69-tool TigerGraph-style surface, not against a small primitive set.
- **Strong callers benefit from primitives; weak callers do not.** BYOKG-RAG's multi-strategy result [ABSTRACT] and Ariadne's own data (the planner is the failure point, −0.3814 coverage) suggest that delegating planning to a *stronger* caller LLM could help, while a weaker caller would replicate Ariadne's planner failure. No study was found that directly compares "high-level ask" with "low-level primitives" for KGQA callers.
- **Is offering both common? Yes:**
  - Cognee exposes a high-level `search` with completion modes and a raw `CYPHER` mode [READ].\[20\]
  - Neo4j's `ToolsRetriever` turns retrievers into tools for an LLM router [SNIPPET].\[44\]
  - Memgraph ships a low-level default server and a separate experimental autonomous server [SNIPPET].\[28\]
  - TigerGraph mixes raw `run_query` with LLM `generate_gsql` [SNIPPET].\[24\]
  
  **No evidence was found on whether offering both levels confuses callers.** Memgraph's separate-server approach is one way to avoid the question.

**Recommendation (judgment).** Offer both, but under a strict namespace and in two MCP "profiles". The default profile exposes `ariadne_ask` plus `ariadne_resolve_entity` and the read-only resources. An expert profile, enabled by configuration, adds the primitives. Every primitive takes typed arguments, never natural-language sub-questions. The first experiment below decides whether the default should change.

### Q4. Response contract

**Standards found:**

- MCP `outputSchema` + `structuredContent` is the operative standard for machine-checkable tool results [READ-sub]. Content annotations (`audience`, `priority`, `lastModified`) can mark which blocks the caller's LLM should see versus which are for the host application [READ-sub].\[37\]
- W3C PROV (the W3C provenance data model: entities, activities and agents linked by relations such as "was generated by" and "used") is a natural vocabulary for the witness. It was not retrieved in this pass, and no graph-retrieval product found here emits PROV.
- No graph product found emits a standard citation format. The de facto conventions are LangChain's intermediate steps (query + rows) and the AWS toolkit's sources → statements → facts tree [SNIPPET].\[7\]\[15\]

**How caller LLMs use citations and abstentions:**

- **Callers over-trust retrieved content.** ClashEval (arXiv preprint) [READ-sub]: across six models and 1,294 questions, models adopted incorrect retrieved content despite a correct prior in 31.3% (Claude Opus) to 62.6% (GPT-3.5) of cases, with GPT-4o at 60.8%. Adoption fell as perturbations became more implausible.\[45\] Implication: whatever Ariadne returns will usually be believed, so wrong-but-confident Ariadne answers propagate. Ariadne's gated LLM rewrite stage, which *doubled confident-wrong answers*, is therefore the most dangerous failure mode for an embedded component.
- **Citations are often post-hoc.** "Correctness is not Faithfulness in RAG Attributions" (arXiv preprint) [READ-sub]: with Command-R+ on NaturalQuestions, up to 57% of citations lacked faithfulness; planting a statement in a relevant-but-uncited document made the model cite it 57% of the time. The authors call their analysis "limited" (one model, one dataset).\[46\] ALCE (EMNLP 2023, peer-reviewed) reports that "even the best models lack complete citation support 50% of the time" on ELI5 [ABSTRACT].\[47\] Implication: Ariadne must *bind* claims to record IDs itself and verify them deterministically. It should not ask the caller's LLM to cite.
- **No study was found on how caller LLMs treat an explicit, structured abstention from a tool.** This is an evidence gap, and the fifth experiment addresses it.

**Recommended envelope.** This follows from the evidence above; the field set itself is a design judgment:

```
AnswerEnvelope {
  status: "answered" | "partial" | "abstained" | "needs_clarification" | "error"
  answer: string                      // short, only verified claims
  claims: [{ id, text, record_ids[], verified: bool, check: "exact"|"entailed"|"aggregate" }]
  records: [{ record_id, source_id, graph_version, kind: "node"|"edge"|"path",
              identifier: {scheme, value},           // e.g. ATT&CK T1176
              label, properties{...},                // shaped, size-bounded
              provenance: { origin: "curated"|"llm_extracted",
                            extraction?: {pipeline, model, document_uri, span} } }]
  witness: [{ source_id, backend: "cypher"|"gremlin", query_text, params,
              executed_at, rows_returned, truncated: bool, elapsed_ms }]
  completeness: { truncated: bool, limits_hit: ["max_rows"|"max_depth"|"timeout"],
                  sources_unavailable: [source_id], unresolved_mentions: [string] }
  confidence: "verified" | "partially_verified" | "unverified"   // derived, not self-reported
  abstention?: { reason: "no_entity_match"|"ambiguous_entity"|"no_records"|
                         "claims_unsupported"|"source_offline"|"out_of_scope",
                 detail, candidates? }
  plan: TypedPlan                     // re-executable via ariadne_execute_plan
  run_id, timings{total_ms, llm_ms, db_ms}, cache: {hit: bool, layer}
}
```

Three design points:

1. `confidence` is categorical and derived from verification, because ClashEval shows callers act on whatever arrives.
2. The text content block should carry a one-paragraph human/LLM summary that *states the status and abstention reason in words*. The MCP backward-compatibility text block may be a summary rather than the exact JSON [READ-sub], and many hosts pass only text to the model.
3. `plan` plus `witness` makes every answer re-executable, which no surveyed offering provides.

### Q5. Speed

**Published latency figures found:**

| System | Mode | Latency | Status |
|---|---|---|---|
| Cognee | `CHUNKS` | ~0.3 s | measured, tiny graph [READ]\[20\] |
| Cognee | `GRAPH_COMPLETION` | ~3.9 s | measured, tiny graph [READ]\[20\] |
| Cognee | `NATURAL_LANGUAGE` (text-to-Cypher, up to 3 attempts) | ~50 s | measured, tiny graph [READ]\[20\] |
| Cognee | `GRAPH_COMPLETION_COT` | ~200 s | measured, tiny graph [READ]\[20\] |
| Cognee | `AGENTIC_COMPLETION` | 60–200 s | estimated [READ]\[20\] |
| Microsoft GraphRAG | global search | 20–24 s | secondary source [SNIPPET]\[12\] |
| Graphiti/Zep | search | sub-second / 155 ms | vendor claim [SNIPPET]\[17\]\[18\] |
| Ariadne | deterministic path | 120 questions in 1.6 s | internal |

Cognee also documents a 60-second snapshot cache for its deterministic `CODE` mode, so only the first call scales with graph size [READ].\[20\] No peer-reviewed latency study of graph-retrieval agents was found.

**What this implies for Ariadne:** With a local 27–32B controller at several seconds per call, a 4–6-step loop lands at roughly 20–40 s, which is Cognee-iterative territory. The deterministic path is about 13 ms per question. The latency case for a cascade is therefore overwhelming. The open question is whether the deterministic first pass can be made *safe*: it must never return a confident wrong answer that the loop would have fixed.

**Recommended caching layers** (judgment; none is evidence-backed for KGQA specifically):

1. **Catalog cache.** Source cards and tool lists are served with MCP `ttlMs`/`cacheScope` [READ]; this is free.\[34\]
2. **Execution cache.** Key: (source_id, graph_version, canonical query text, params). It is exact and safe because executors are deterministic. Invalidate on graph version change.
3. **Plan cache.** Key: normalized *typed* plan with resolved identifiers. It is safe because it is keyed on identifiers, not wording.
4. **Semantic question→plan cache.** A semantic cache answers a new question with a stored result for a similar earlier question. Allow it only as a *candidate generator* whose plan is re-validated (types, entity resolution) and re-executed. Never return a cached answer on similarity alone. Ariadne's paraphrase data show that near-identical wording can need different entities, and an LLM picking from candidates chose wrongly 35% of the time.

**Latency budget per call.** Let callers pass `budget_ms` and `mode`:

- `fast`: deterministic only, ~100 ms target, returns `partial`/`abstained` rather than escalating.
- `auto`: deterministic first, loop on failure, Task + progress if the budget exceeds about 5 s.
- `thorough`: always loop.

### Q6. Safety of an embedded agent

**Prompt injection via graph content.** Node descriptions from other authors or from the LLM extraction pipeline reach the controller's context. "Design Patterns for Securing LLM Agents against Prompt Injections" (arXiv preprint, authors across Google, Microsoft, IBM, ETH Zurich, EPFL) [SNIPPET] states the principle that once an agent "has ingested untrusted input, it must be constrained so that it is impossible for that input to trigger any consequential actions". It proposes six patterns: Action-Selector, Plan-Then-Execute, LLM Map-Reduce, Dual LLM, Code-Then-Execute and Context-Minimization.\[48\]\[49\]\[50\] A secondary analysis notes residual risks remain in every pattern [SNIPPET].\[48\] CaMeL (Debenedetti et al., Google, Google DeepMind and ETH Zurich, arXiv 2503.18813) enforces control and data flow with a custom interpreter and reports "solving 77% of tasks with provable security (compared to 84% with an undefended system) in AgentDojo" [SNIPPET].

**Application to Ariadne:**

- Ariadne's tools are read-only and bounded, so injection cannot cause writes. The real risks are three: (a) steering the loop into irrelevant expansions (cost/denial of service); (b) altering the drafted answer; (c) in multi-tenant deployments, coaxing the controller to query sources the caller is not entitled to.
- (c) must be blocked outside the LLM, through per-caller source allowlists enforced in the specialists.
- (b) is mitigated by Ariadne's deterministic claim validator, the strongest defence in the design, since a claim must match records regardless of what the text said.
- (a) is mitigated by **context minimization**: the controller sees identifiers, labels, relation types and short shaped fields by default. Free-text descriptions are fetched only when needed, delimited as data (spotlighting), and tagged `origin: llm_extracted`.

**Read-only enforcement.** Use three layers: (1) primitives that cannot express writes; (2) read-only database credentials and, for Neo4j, read transactions; (3) per-source limits (depth 3, rows 1000, timeout). This is stricter than the Neo4j, Neptune and Memgraph MCP servers [READ]/[SNIPPET].

**Tenant isolation.** The AWS GraphRAG toolkit isolates logical graphs by `tenant_id` label scoping [SNIPPET].\[9\]\[51\] MCP 2026-07-28 binds client credentials to the issuing authorization server and adds `cacheScope: "private"` [READ].\[32\] For Ariadne:

- Map OAuth subject → tenant → allowed source cards.
- Partition all caches by tenant.
- Never let a `run_id` handle from one tenant resolve for another.

### Q7. Testing a component

- **pass^k.** pass^k is the probability that *all* k independent runs of a task succeed, not just one. It comes from τ-bench (Yao, Shinn, Razavi & Narasimhan, arXiv 2406.12045), whose abstract reports that "even state-of-the-art function calling agents (like gpt-4o) succeed on <50% of the tasks, and are quite inconsistent (pass^8 <25% in retail)"; the body notes gpt-4o's retail average success above 60% [SNIPPET]. Ariadne's deterministic path should score pass^k = pass^1 by construction. The LLM loop will not, so report both, with k ≥ 5.
- **Contract tests.** Run against every response:
  - JSON Schema validation of `structuredContent` against `outputSchema` (MCP says clients SHOULD validate) [READ-sub].\[37\]
  - Every `claims[].record_ids` exists in `records`.
  - Every record traces to a `witness` entry.
  - Every `abstained` response carries a reason and a witness.
  - Re-executing `plan` reproduces `records` when `graph_version` is unchanged.
- **Graph-QA benchmarks with unseen schemas:**
  - **CypherBench** (ACL 2025, peer-reviewed): 11 Wikidata-derived property graphs, 7.8M entities, >10,000 questions [SNIPPET].\[52\]\[53\]\[54\] Its provenance subgraph Jaccard similarity (PSJS) metric compares the subgraph a query touched with the gold subgraph, which matches Ariadne's witness design. Ariadne can report execution accuracy (result-set match) and PSJS without writing Cypher, by comparing its records to gold results.
  - **Neo4j Text2Cypher datasets and GrailQA zero-shot.** These were not retrieved in this pass. GrailQA is Freebase/SPARQL-based, so it would need a property-graph port. Treat both as candidates, not verified recommendations.
  - **Tool-use benchmarks** (τ-bench, τ²-bench) test the *caller* side. They are useful for the granularity experiment's methodology, not as Ariadne scores.

## 3. Recommended interface for Ariadne

**Protocol:** MCP 2026-07-28 over Streamable HTTP (stateless), plus stdio for local use. Thin A2A (Agent Card + task lifecycle mapped onto Tasks) and OpenAPI adapters share handlers. Use the namespace prefix `ariadne_`.

**Resources** (read-only, cacheable): `ariadne://sources` (online source cards with status), `ariadne://sources/{id}/card`, `ariadne://runs/{run_id}` (full envelope and trace).

**Level 1: high-level tool**

| Tool | Inputs | Output |
|---|---|---|
| `ariadne_ask` | `question` (string); optional `sources[]`, `seed_identifiers[]`, `mode` (fast/auto/thorough), `budget_ms`, `max_records`, `allow_clarification` (bool), `response_format` (concise/detailed) | `AnswerEnvelope` (Q4) |

**Level 2: deterministic primitives** (no LLM; millisecond-scale; all typed)

| Tool | Inputs | Output |
|---|---|---|
| `ariadne_resolve_entity` | `text`, optional `source_id`, `expected_labels[]`, `limit` | Ranked candidates `{identifier, label, name, source_id, score, match_type}` plus explicit `none_above_threshold` flag |
| `ariadne_describe` | `source_id`, `identifier`, `fields?` | One record + witness |
| `ariadne_expand` | `source_id`, `identifier`, `relation`, `direction`, `target_label?`, `limit`, `cursor?` | Records page + witness + `truncated` |
| `ariadne_join` | `from_source`, `identifiers[]`, `to_source`, `join_key` | Matched records + unmatched list + witness |
| `ariadne_paths` | `source_id`, `from`, `to`, `max_depth ≤ 3`, `relations?` | Paths + witness |
| `ariadne_execute_plan` | `TypedPlan` (chained composition, two-anchor intersection) | `AnswerEnvelope` without LLM answer text |

All primitives reject relations or labels not in the source card's allowed patterns, returning `isError: true` with the allowed alternatives, which is the self-correction channel MCP recommends [READ-sub].\[37\]

**The same `TypedPlan` should replace the natural-language sub-question inside Ariadne.** The current defect, where the builder re-parses text with keyword rules, is an *interface* bug. External exposure forces fixing it. This is the single most consequential recommendation.

**Streaming:** If the caller sent a `progressToken`, emit `notifications/progress` at plan, each tool call, verification and drafting, with human-readable `message`s. If `budget_ms` exceeds about 5 s, or the loop starts, return a Task handle; `tasks/get` returns the envelope.

**Clarification:** Use MRTR `input_required` with a form-mode enum of candidate entities, but only when `allow_clarification=true` and the caller declared elicitation support. Otherwise return `status: "needs_clarification"` with `abstention.candidates`, so agent callers with no human can choose and re-call. This is a judgment call: most callers will be agents, and MCP elicitation is designed for users.

**Caching:** The four layers in Q5, all tenant-partitioned, with `cache` reported in the envelope.

## 4. Where Ariadne is unusual, and where it is behind

**Unusual (no surveyed offering does this):**

- **Deterministic, typed executors as the only query path.** Every database MCP server hands query authorship to the caller's LLM. Every GraphRAG product puts an LLM in the answer path. BYOKG-RAG is closest but still executes LLM-written openCypher.
- **Source cards as the plug-and-play unit.** These are allowed patterns, identifier schemes and safety limits built automatically per graph. Vendors expose raw schema text (Neptune "as a text string"), not allowed-pattern contracts.\[6\]
- **Federation without merging, joined on identifiers.** No surveyed offering federates across separate stores; the AWS toolkit and Graphiti assume one store per deployment.
- **Claim-level verification with abstention plus executed-query witness.** No surveyed offering verifies claims or returns a re-executable plan as a contract.

**Behind:**

- **Paraphrase and entity robustness.** Records-exact is 0.0000 on paraphrased names and description-only questions. BYOKG-RAG-style multi-strategy linking (fuzzy string + embeddings, top-m candidates) and Graphiti's hybrid vector + BM25 + graph search are standard elsewhere.\[10\]\[18\] Ariadne's own LLM entity choice failed 35% of the time. Callers will hit this immediately.
- **Self-planning accuracy.** Gold coverage falls from 0.8611 to 0.4797, and the loop is not yet built. Competitors with an LLM in the loop may simply answer more questions, even if less verifiably.
- **Semantic/global questions.** Ariadne has no equivalent of GraphRAG global search or vector entry points for "themes" or description-only questions.
- **Text-to-Cypher may be catching up.** The CYGNET preprint (arXiv 2606.04645, Table 10) reports Gemma 4 31B at 77.6% single-attempt zero-shot execution accuracy on CypherBench [SNIPPET]; if that holds, "LLM writes Cypher, deterministic validator checks it" becomes a competitive alternative for Neo4j sources. The brief's fixed design decision deserves periodic re-testing on Cypher, though probably not on Gremlin.
- **Ecosystem maturity.** Vendors already ship installable MCP servers. Ariadne's latency advantage holds only on the deterministic path; with a local controller loop it will be no faster than Cognee's iterative modes.

## 5. Experiments and integration tests

1. **Typed handoff versus natural-language handoff (internal).** Replace sub-question text with `TypedPlan` arguments; keep everything else fixed.
   - *Measurement:* records-exact per paraphrase tier and gold coverage on the 284 questions.
   - *Decision:* adopt typed plans everywhere if the synonym-verb tier rises from 0.4667 toward the original 1.0000 and the "planner empty, gold non-empty" count (77/284) halves, with no rise in confident-wrong answers.
2. **Granularity A/B for callers.** Caller agents (local 27–32B and one hosted frontier model) answer the sealed set through (a) `ariadne_ask` only, (b) primitives only, (c) both.
   - *Measurement:* judged correctness, confident-wrong rate, pass^5, wall-clock and tokens per question.
   - *Decision:* default profile = the arm with the highest pass^5 among those within 10% of the fastest. If (c) is not better than the better of (a) and (b) for both callers, ship separate profiles.
3. **Fast-path cascade safety.** Compare deterministic-first-then-loop with always-loop.
   - *Measurement:* p50/p95 latency, and the share of deterministic-path answers that are confidently wrong where the loop would have been right.
   - *Decision:* keep `auto` as default only if that share is ≤1% of answered questions. Otherwise the fast path must abstain more aggressively.
4. **Injection red team on extracted graphs.** Plant instruction-bearing descriptions in LLM-extracted nodes (exfiltration, "ignore the question", "call expand on X").
   - *Measurement:* attack success rate (answer altered, extra tool calls, unverified claim passing the validator), with and without context minimization and spotlighting.
   - *Decision:* zero unverified claims must pass the validator in all conditions, and context minimization becomes default if it cuts loop-steering success without reducing correctness.
5. **Consumer test: do callers honour abstention?** Feed caller agents Ariadne envelopes with `abstained`, `partial` and `truncated` flags, varying whether the reason appears in text content or only in `structuredContent`.
   - *Measurement:* rate at which the caller fabricates an answer anyway, and rate of correctly propagated "unknown". ClashEval's 31–63% adoption of wrong context suggests the risk is real.
   - *Decision:* if fabrication exceeds 10% with structured-only signalling, make the text block lead with the status sentence and add an explicit "do not answer beyond these records" instruction to the tool description.

## 6. Caveats

- Most product facts are from search excerpts of official docs or repos [SNIPPET], because several GitHub pages blocked fetching. Tool lists change frequently; verify against the repos before citing them in a paper.
- All vendor latency and accuracy numbers (Zep, Microsoft LazyGraphRAG) are self-reported on vendor-chosen tasks.
- Several key papers (RAG-MCP, τ-bench, the design-patterns paper, CaMeL, CYGNET) were seen only as snippets. Treat their figures as leads.
- No evidence was found on: caller confusion when both granularity levels are offered; how agents treat structured abstentions; semantic caching for KGQA; protocol-level latency comparisons; or Gremlin generation accuracy by modern models.

## 7. Bibliography with read status

| Source | Type | Read status | Link |
|---|---|---|---|
| MCP 2026-07-28 release post (Soria Parra, Delimarsky) | Official spec blog | [READ] | https://blog.modelcontextprotocol.io/posts/2026-07-28/ |
| MCP 2026-07-28 changelog | Specification | [READ] | https://modelcontextprotocol.io/specification/2026-07-28/changelog |
| MCP 2026-07-28 Elicitation | Specification | [READ] | https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation |
| MCP 2026-07-28 Tools (repo source) | Specification | [READ-sub] | https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx |
| MCP 2026-07-28 Progress | Specification | [READ-sub] | https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/progress |
| MCP 2025-11-25 Tasks | Specification | [SNIPPET] | https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks |
| A2A specification | Specification | [SNIPPET] | https://a2a-protocol.org/latest/specification/ |
| Neo4j official MCP server | Repo/docs | [SNIPPET] | https://github.com/neo4j/mcp |
| Neo4j MCP integrations guide | Docs | [SNIPPET] | https://neo4j.com/developer/genai-ecosystem/model-context-protocol-mcp/ |
| Neo4j GraphRAG Python user guide | Docs | [SNIPPET] | https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html |
| Amazon Neptune MCP server | Docs | [READ] | https://awslabs.github.io/mcp/servers/amazon-neptune-mcp-server |
| AWS GraphRAG Toolkit (lexical graph, multi-tenancy, MCP) | Repo/wiki | [SNIPPET] | https://deepwiki.com/awslabs/graphrag-toolkit/8-examples-and-getting-started |
| Mavromatis et al., BYOKG-RAG | EMNLP 2025, peer-reviewed | [READ] §1–3.5; results [ABSTRACT]/[SNIPPET] | https://arxiv.org/abs/2507.04127 |
| Microsoft Research, LazyGraphRAG | Vendor research blog | [SNIPPET] | https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/ |
| LlamaIndex Property Graph Index guide | Docs | [SNIPPET] | https://developers.llamaindex.ai/python/framework/module_guides/indexing/lpg_index_guide/ |
| LangChain Neo4j / GraphCypherQAChain | Docs | [SNIPPET] | https://docs.langchain.com/oss/python/integrations/graphs/neo4j_cypher |
| Graphiti MCP server | Docs | [SNIPPET] | https://help.getzep.com/graphiti/getting-started/mcp-server |
| Graphiti/Zep product page | Vendor marketing | [SNIPPET] | https://www.getzep.com/product/knowledge-graph-mcp/ |
| Cognee SearchType (latency tables) | Docs | [READ] | https://docs.cognee.ai/python-api/search-type |
| TigerGraph MCP | Repo | [SNIPPET] | https://github.com/tigergraph/tigergraph-mcp/blob/main/README.md |
| Memgraph MCP | Package page | [SNIPPET] | https://pypi.org/project/mcp-memgraph/0.4.1/ |
| Anthropic, Writing effective tools for agents | Vendor engineering blog | [READ] | https://www.anthropic.com/engineering/writing-tools-for-agents |
| RAG-MCP | arXiv preprint | [SNIPPET] | https://www.alphaxiv.org/abs/2505.03275 |
| OSWorld-MCP | arXiv preprint | [SNIPPET] | https://arxiv.org/pdf/2510.24563 |
| Scalable LLM Agent Tool Access in the Cloud | arXiv preprint | [SNIPPET] | https://arxiv.org/pdf/2607.15593 |
| Yao et al., τ-bench | arXiv preprint | [SNIPPET] | https://arxiv.org/html/2406.12045v1 |
| Feng et al., CypherBench | ACL 2025, peer-reviewed | [SNIPPET] | https://aclanthology.org/2025.acl-long.438/ |
| CYGNET (CypherBench re-evaluation) | arXiv preprint | [SNIPPET] | https://arxiv.org/html/2606.04645 |
| Design Patterns for Securing LLM Agents against Prompt Injections | arXiv preprint | [SNIPPET] | https://arxiv.org/pdf/2506.08837 |
| Debenedetti et al., CaMeL | arXiv preprint | [SNIPPET] | https://arxiv.org/pdf/2503.18813 |
| Wu, Wu & Zou, ClashEval | arXiv preprint | [READ-sub] (through Table 2) | https://arxiv.org/abs/2404.10198 |
| Wallat et al., Correctness is not Faithfulness in RAG Attributions | arXiv preprint | [READ-sub] | https://arxiv.org/abs/2412.18004 |
| Gao et al., ALCE | EMNLP 2023, peer-reviewed | [ABSTRACT] | https://arxiv.org/abs/2305.14627 |

## Sources

1. [Neo4j MCP Server](https://hub.docker.com/mcp/server/neo4j/overview)
2. [Model Context Protocol (MCP) Integrations for the Neo4j Graph Database - Developer Guides](https://neo4j.com/developer/genai-ecosystem/model-context-protocol-mcp/)
3. [Neo4j in Coding Tools & Editors - Neo4j Labs](https://neo4j.com/labs/genai-ecosystem/agent-skills/coding-skills/)
4. [Effortless RAG with Text2CypherRetriever - Neo4j Graph Intelligence Platform](https://neo4j.com/blog/developer/effortless-rag-text2cypherretriever/)
5. [neo4j/neo4j-graphrag-python](https://deepwiki.com/neo4j/neo4j-graphrag-python)
6. [Amazon Neptune MCP Server | Welcome to Open Source MCP Servers for AWS](https://awslabs.github.io/mcp/servers/amazon-neptune-mcp-server)
7. [GitHub - aws-samples/sample-rag-explorer-graphragtoolkit · GitHub](https://github.com/aws-samples/sample-rag-explorer-graphragtoolkit)
8. [Introducing the GraphRAG Toolkit](https://aws-news.com/article/2025-01-27-introducing-the-graphrag-toolkit)
9. [Examples and Getting Started](https://deepwiki.com/awslabs/graphrag-toolkit/8-examples-and-getting-started)
10. <https://arxiv.org/pdf/2507.04127>
11. [LazyGraphRAG: Setting a new standard for quality and cost - Microsoft Research](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/)
12. [GraphRAG — When Knowledge Graphs Pay Off](https://it-blue.one/blog/graphrag-when-knowledge-graphs-pay-off)
13. [Using a Property Graph Index](https://developers.llamaindex.ai/python/framework/module_guides/indexing/lpg_index_guide/)
14. [Customizing property graph index in LlamaIndex - Neo4j Graph Intelligence Platform](https://neo4j.com/blog/developer/property-graph-index-llamaindex/)
15. [Neo4j integration - Docs by LangChain](https://docs.langchain.com/oss/python/integrations/graphs/neo4j_cypher)
16. [langchain.chains.graph\_qa.cypher.GraphCypherQAChain — 🦜🔗 LangChain 0.0.249](https://sj-langchain.readthedocs.io/en/latest/chains/langchain.chains.graph_qa.cypher.GraphCypherQAChain.html)
17. [Graphiti](https://www.getzep.com/product/knowledge-graph-mcp/)
18. [GitHub - getzep/graphiti: Build Real-Time Knowledge Graphs for AI Agents · GitHub](https://github.com/getzep/graphiti)
19. [Graphiti MCP Server](https://help.getzep.com/graphiti/getting-started/mcp-server)
20. [SearchType - Cognee Documentation](https://docs.cognee.ai/python-api/search-type)
21. [Search (low level): run one SearchType over the caller's datasets - Cognee Documentation](https://docs.cognee.ai/api-reference/search/search-low-level:-run-one-searchtype-over-the-callers-datasets)
22. [cognee-mcp MCP Server](https://archestra.ai/mcp-catalog/topoteretes__cognee__cognee-mcp)
23. [tigergraph-mcp by tigergraph](https://glama.ai/mcp/servers/tigergraph/tigergraph-mcp)
24. [tigergraph-mcp/README.md at main · tigergraph/tigergraph-mcp · GitHub](https://github.com/tigergraph/tigergraph-mcp/blob/main/README.md)
25. [Memgraph MCP Server - DXT Services](https://dxt.services/mcp/mcp-memgraph/)
26. [mcp-memgraph - MCP Server](https://www.codelibrary.ai/mcp/mcp-memgraph)
27. [mcp-memgraph · PyPI](https://pypi.org/project/mcp-memgraph/0.4.1/)
28. [Memgraph](https://llmbase.ai/mcp-servers/memgraph/)
29. [GitHub - neo4j/mcp: Neo4j official MCP Server · GitHub](https://github.com/neo4j/mcp)
30. [\[2507.04127\] BYOKG-RAG: Multi-Strategy Graph Retrieval for Knowledge Graph Question Answering](https://arxiv.org/abs/2507.04127)
31. [(PDF) BYOKG-RAG: Multi-Strategy Graph Retrieval for Knowledge Graph Question Answering](https://www.researchgate.net/publication/393478633_BYOKG-RAG_Multi-Strategy_Graph_Retrieval_for_Knowledge_Graph_Question_Answering)
32. [The 2026-07-28 Specification](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
33. <https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation>
34. <https://modelcontextprotocol.io/specification/2026-07-28/changelog>
35. [Tasks - Model Context Protocol](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks)
36. <https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/progress>
37. [modelcontextprotocol/docs/specification/2026-07-28/server/tools.mdx at main · modelcontextprotocol/modelcontextprotocol](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx)
38. [Agent2Agent (A2A) Protocol Specification](https://a2a-protocol.org/latest/specification/)
39. [A2A/docs/specification.md at main · a2aproject/A2A · GitHub](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)
40. [Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
41. [Writing Effective Tools for AI Agents: Production Lessons from Anthropic](https://blog.agentailor.com/posts/writing-tools-for-ai-agents)
42. [OSWorld-MCP: Benchmarking MCP Tool Invocation In Computer-Use Agents](https://arxiv.org/pdf/2510.24563)
43. [Scalable LLM Agent Tool Access in the Cloud](https://arxiv.org/pdf/2607.15593)
44. [introducing toolsretriever in the neo4j graphrag python package 04d0c3773f62](https://medium.com/neo4j/introducing-toolsretriever-in-the-neo4j-graphrag-python-package-04d0c3773f62)
45. [ClashEval: Quantifying the tug-of-war between an LLM’s internal prior and external evidence](https://arxiv.org/html/2404.10198v3)
46. <https://arxiv.org/pdf/2412.18004>
47. [Enabling Large Language Models to Generate Text with Citations](https://arxiv.org/abs/2305.14627)
48. [Design Patterns for Securing LLM Agents Against Prompt Injection: What Every Pattern Leaves Open - ARMO](https://www.armosec.io/blog/design-patterns-for-securing-llm-agents/)
49. [Design Patterns for Securing LLM Agents against Prompt Injections](https://arxiv.org/pdf/2506.08837)
50. [Design Patterns for Securing LLM Agents against Prompt Injections — The Agent Atlas](https://agent-atlas.blackarcindustrial.com/papers/design-patterns-for-securing-llm-agents/)
51. [Feature: Document-Graph — Structured Data ETL Complement to Lexical-Graph · Issue #356 · awslabs/graphrag-toolkit · GitHub](https://github.com/awslabs/graphrag-toolkit/issues/356)
52. [CypherBench: Towards Precise Retrieval over Full-scale ...](https://arxiv.org/pdf/2412.18702)
53. [GitHub - megagonlabs/cypherbench: CypherBench: Towards Precise Retrieval over Full-scale Modern Knowledge Graphs in the LLM Era · GitHub](https://github.com/megagonlabs/cypherbench)
54. [CypherBench: Towards Precise Retrieval over Full-scale Modern Knowledge Graphs in the LLM Era - ACL Anthology](https://aclanthology.org/2025.acl-long.438/)
