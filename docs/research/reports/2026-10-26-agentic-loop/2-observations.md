# What Ariadne's Controller Should See: Shaping Graph-Query Results for Large Graphs and Hub Nodes

**Bottom line:** the controller should never see raw hub expansions. Every specialist result should be an envelope: exact totals computed by the database, facet counts, a small labelled sample with its ordering stated, an explicit truncation flag and a handle the controller can page through. The complete answer set should come from the database, by re-executing the query the controller chose, and be written out by a deterministic composer. The evidence supports each part of this design. It does not yet show that the parts work together on enumeration questions, and closing that gap is Ariadne's first experiment.

## TL;DR

- **Making observations smaller is cheap; losing the answer path is not.** In a controlled study with 30,841 trials (Canedo 2026, preprint, [READ]), keeping the answer chain fixed and swapping out the other triples changed answer F1 by only +0.003. Removing the chain dropped F1 to 0.231, and to 0.005 under a strict grounding prompt. Subgraph size from 0 to 200 triples and serialisation syntax also had no measurable effect at multi-hop depth.\[1\] So the controller needs counts plus enough sample to choose the next step, while the full set lives in the database and the composer.
- **Truncation that is not labelled causes confident-incomplete answers, and labelling it fixes much of the problem.** One directly relevant study exists, and it is weak: a single-author, non-archival workshop preprint, [ABSTRACT]. It reports that stating result caps and search limits in tool output cut unsupported agent claims "substantially for three of the four failure types". In one test, verifiers went from accepting incorrect answers 90 of 90 times to rejecting them 90 of 90 times.\[2\] Separately, LLMs systematically under-enumerate on list questions (MoNaCo, KG-Guard, [SNIPPET]/[ABSTRACT]).\[3\]\[4\] A deterministic composer is therefore needed for "list every X" questions, not optional.
- **Hubs are handled at the query level by probing degree first and expanding only along typed, directed relations, with per-source caps.** In Neo4j, a typed degree count reads a stored per-node degree instead of traversing relationships ([SNIPPET], Neo4j KB).\[5\] In Neptune, `in()`/`both()` without an edge label "will run unconstrained" ([SNIPPET], AWS re:Post).\[6\] The only end-to-end KG-agent evidence at hub scale comes from a 48-million-entity Wikidata snapshot (Chenene et al. 2026, preprint, [READ]). There, keeping graph results outside the model's context raised an open 27B model on one H100 from 60 to 74 of 100 correct. That is the closest published analogue to Ariadne's setup.

## Read-status and classification conventions

- **[READ]**: I read the full text, or the relevant section in full. **[ABSTRACT]**: abstract only. **[SNIPPET]**: search excerpt only. A figure tagged [ABSTRACT] or [SNIPPET] is a lead, not evidence of what a paper measured.
- **P** = plug-and-play with an off-the-shelf model. **B** = needs only an automatic one-time build step per graph. **T** = needs training or fine-tuning on the target graph or task.
- "Peer-reviewed" means a conference or workshop paper. "Preprint" means arXiv only. Vendor documentation and engineering blogs are labelled "practitioner".

## One-page technique table

| Technique | Where it applies | Class | Cost | Evidence (status) |
|---|---|---|---|---|
| Totals + facet counts by (relation, label) before any rows | DB (degree/count query), specialist (envelope) | P (B if degree is precomputed) | One extra count query; degree reads are cheap in Neo4j | Neo4j stored-degree read [SNIPPET]; agents miss completeness when caps are unstated (Jeffries 2026) [ABSTRACT] |
| Explicit truncation flag ("showing k of N, ordered by …") | Specialist | P | ~20 tokens | Jeffries 2026, 90/90→90/90 verifier flip [ABSTRACT]; Anthropic tool guidance (practitioner) [READ] |
| Small ranked sample (k ≈ 10–50) with stated ordering | Specialist | P | Bounded tokens | Size 0–200 triples no effect when chain present (Canedo 2026) [READ]; SubgraphRAG says K must fit the LLM [SNIPPET] |
| Handle + paging (result spilled to a store) | Specialist / store | P | One store per session | Manus "restorable compression" (practitioner) [SNIPPET]; RLM harness on Wikidata 60→74 (Chenene 2026) [READ] |
| Concise/detailed response modes | Specialist | P | None | Anthropic: 72 vs 206 tokens, ~⅓ [READ] |
| Observation masking of stale results in the loop | Controller loop | P | None | Halves cost, matches LLM summarisation (Lindenbauer et al. 2025, DL4C workshop) [ABSTRACT] |
| LLM beam pruning of relations/entities (ToG) | Controller | P | N LLM calls per hop; ToG ≈ 13 calls, 19 s per question | ToG ablation [SNIPPET]; RAPL efficiency table [SNIPPET] |
| Trained triple scorer, top-K (SubgraphRAG) | Retriever | T | Training per graph/task | ICLR 2025 [SNIPPET] |
| PPR / BM25 / embedding pruning of neighbours | Specialist | P (B for embeddings) | Index build + per-query scoring | FRAG uses them [SNIPPET]; **no head-to-head on hub neighbour ranking found** |
| Readable predicate names, labels instead of raw IDs | Specialist serialiser | B (labels from source card) | None | Predicate name is "the active ingredient" (Canedo) [READ]; UUID→names reduces hallucination (Anthropic) [READ] |
| Deterministic composer over full DB result | Composer | P | One extra DB query | No published KGQA system measured; IE→SQL over-generates, not under (QO-Bench) [SNIPPET] |
| Typed, directed expansion; degree probe; per-row caps | DB query (Cypher/Gremlin) | P | None | Neo4j KB, Neptune docs/re:Post, TinkerPop docs [SNIPPET] |
| Precomputed degree per (node, rel type) property | DB | B | Build-time job; must be refreshed | Needed where degree is not stored natively; Neptune behaviour **not verified** |

## Findings by question

### Q1. How KG agents keep observations small, and what each method costs

**Quick answer:** published KG agents shrink observations with hard caps and LLM pruning. Nobody has measured what these cost on enumeration or count questions, because the standard benchmarks (WebQSP, CWQ) are mostly lookups and short chains.

- **Beam pruning (Think-on-Graph, ToG; peer-reviewed, ICLR 2024; P).** *Beam search* keeps only the N best partial paths at each hop and discards the rest. ToG asks the LLM to score candidate relations and entities and keeps the top N, with default width N = 3 and depth 3. Its ablation reports that performance "improves with the search depth and width". The authors chose 3 because cost "increases linearly with the depth" ([SNIPPET]). Each iteration needs about N LLM calls for relation pruning, N for entity pruning and one reasoning call ([SNIPPET]).\[7\] A later efficiency table (RAPL, preprint) puts ToG on WebQSP at 75.1 Hit, 19.03 s, 13.2 LLM calls and 410 triples per question ([SNIPPET]).\[8\] A second paper measured ToG at 41,586 ms per question on WebQSP ([SNIPPET]).\[9\] **Cost by question type:** beam width 3 is fatal for enumerations by construction. A "list every X" question whose answer has 40 members cannot survive a beam that keeps 3 entities. No paper measures this, but it follows directly from the algorithm.
- **Top-K by a trained scorer (SubgraphRAG; peer-reviewed, ICLR 2025; T).** SubgraphRAG gives the reasoner the top 100 triples by default, which is "2.3% of total candidate triples on average". The authors state that "the size K needs to be properly selected per LLM" ([SNIPPET]).\[10\] In snippet tables, GPT-4o gains a few points going from 100 to 500 triples ([SNIPPET]).\[11\] The retriever is trained, so it is ruled out for Ariadne.
- **Hard caps in a SPARQL agent (SPINACH; peer-reviewed, EMNLP Findings 2024; P).** SPINACH caps search results at "at most 8 entities and 4 properties" and shows only "the first and last 5 rows" of large SPARQL results ([SNIPPET]).\[12\] This is the clearest published example of a fixed-sample observation. The paper reports no ablation of the cap.
- **Code-held state instead of context (Wikidata Search Traces RLM harness; preprint; P).** The authors name the failure Ariadne fears: "one navigation step on a hub entity can return thousands of neighbours and statements" ([READ]). Their harness keeps graph results in Python variables so that "its context holds only what it chooses to print", and truncates visible output at 10,000 characters. The same 13 graph functions were exposed either as direct tool calls or through the harness. With the harness, Qwen3.8-27B went from 60 to 74 of 100 and from 20 to 28 of 50 multi-hop questions, and gpt-6-luna went from 49 to 61 ([READ]).\[13\] The gain came from "carrying the search further". The target entity was reached in 39 of 50 multi-hop runs versus 27, while accuracy after reaching it stayed about the same ([READ]).\[13\] **Caveat:** graph-call budgets were not matched (620 versus 45 calls per run for Qwen), and the evaluation has 100 questions.\[13\]
- **Aggregation to counts.** I found no KG-agent paper that ablates "give the counts instead of the rows". The indirect evidence points one way: LLMs count poorly over long in-context lists ("performance decays rapidly with list length", [SNIPPET]).\[14\] So counts should be computed by the database, never inferred by the model from rows.
- **Summaries.** In coding agents, simple *observation masking* (hiding older tool outputs) "halves cost relative to the raw agent while matching, and sometimes slightly exceeding, the solve rate of LLM summarization" (peer-reviewed workshop, [ABSTRACT]).\[15\]\[16\] No KGQA study compares LLM summaries of graph results with deterministic facets. Summarising rows with an LLM would also put a model into the record path, which conflicts with Ariadne's design.

**Does flooding actually hurt? (The brief assumes so.)** The evidence is mixed. Canedo's controlled study found no effect of subgraph size from chain-only up to 200 triples ([READ]).\[1\] Chroma's "context rot" technical report (Hong, Troynikov and Huber, July 2025; practitioner) tested 18 LLMs including GPT-4.1, Claude 4, Gemini 2.5 and Qwen3 and found that "performance grows increasingly unreliable as input length grows", especially when distractors are present ([SNIPPET]). Du et al. (EMNLP Findings 2025) found that Llama-3.1-8B-Instruct's MMLU accuracy fell by 24.2% at 30k tokens even with perfect retrieval, and drops of at least 7.9% remained when the model attended only to the evidence ([SNIPPET]). The honest reading: a few hundred rows are probably harmless to accuracy but cost latency on a local 27–32B model. Tens of thousands of rows are harmful. Nobody has measured where in between the damage starts for a reasoning model reading graph rows.

### Q2. Ranking neighbours without training

**Quick answer:** no published experiment shows that BM25, off-the-shelf embeddings, personalised PageRank (PPR) or degree priors rank a hub's neighbours well enough to show only the top few *for KGQA*. Treat any such ranking as a convenience for the sample, never as a filter on the answer.

- *BM25* is a lexical score: it rewards rare query words that appear in a candidate's text, with saturation for repeated words. *PPR* scores nodes by a random walk that keeps jumping back to the seed: π = α·e_s + (1−α)·π·P. Here e_s is the seed indicator vector, P is the transition matrix and α is the restart probability. Nodes near the seed through many paths score high.
- FRAG (preprint) plugs in random walk with restart, PPR and PageRank-Nibble for node pruning, and BM25 or SentenceTransformer for edge pruning, all without training ([SNIPPET]).\[17\]\[18\] I found no isolated comparison of these rankers on hub neighbours.
- PPR has a structural problem on hubs. A one-hop neighbour set from a hub is, almost by definition, the set PPR scores near-uniformly from that seed. PPR helps rank *multi-hop* candidates, not siblings of one hub.
- Degree priors are cheap but answer the wrong question. "Most connected" is not "most relevant to the question", and in a security graph high degree often marks generic nodes. This is my inference; I found no evidence either way.
- **What matters for Ariadne:** most hub blow-ups in a schema-typed graph are already scoped by relation type and target label. Facet counts let the controller narrow by *type* (a deterministic, complete operation) before any ranking is needed. Ranking matters only for "most relevant/important" questions. For those, the ordering is part of the answer and should be stated, e.g. "ordered by embedding similarity to the question".

### Q3. Completeness: keeping enumerations complete when the controller sees a sample

**Quick answer:** nobody publishes a KGQA system with exactly the "controller sees counts and a sample, database computes the full set, deterministic composer lists it" split. Its components are each supported. There is direct evidence that LLMs under-enumerate and that unstated truncation produces false completeness.

**Evidence that LLMs under-enumerate:**
- MoNaCo (Wolfson et al., preprint; 1,315 time-consuming natural questions): frontier LLMs "achieve at most 61.2% F1, hampered by low recall and hallucinations" ([ABSTRACT]). GPT-4o's "recall sharply decreases with the number of expected answers" ([SNIPPET]).\[4\]
- KG-Guard (preprint): on WebQSP the LLM returns "3.0–3.3 nodes on average against 10+ gold answers" ([SNIPPET]).\[3\]
- QO-Bench (preprint): across retrieval-side paradigms "the dominant mode is under-enumeration and abstention". The pipeline in which a database computes the set (IE→SQL) is "the sole over-generator" ([SNIPPET]).\[19\] This is the same split Ariadne proposes, and it moves errors from recall to precision.

**Evidence on truncation and false completeness:**
- Jeffries (2026, non-archival NeurIPS workshop poster, preprint, [ABSTRACT]) ran an A/B test on a production RAG research system used by the Pilsudski Institute in New York. Tool output either omitted "search limits, result caps, or identifier namespaces" or stated them. Unsupported claims "dropped substantially for three of the four failure types". A snippet of the full text shows the failure: the output began "Found 20 document(s)" and "the truncated list read as the complete result set" ([SNIPPET]).\[20\] This is the only controlled test I found. It is new and has a single author.
- Anthropic's tool guidance (practitioner, [READ]) recommends "pagination, range selection, filtering, and/or truncation with sensible default parameter values". It says that "if you choose to truncate responses, be sure to steer agents with helpful instructions". Claude Code caps tool responses at 25,000 tokens by default.\[21\]

**Known weaknesses of the proposed split (be critical here):**
1. **Errors in the filter spread silently.** The database lists exactly what the controller's plan selects. If the controller picks the wrong relation, misses a second relation that also counts, or puts a filter in the wrong place, the composer produces a complete list of the wrong set. The controller cannot see the error, because it saw only 20 rows. QO-Bench's IE→SQL over-generation is this failure mode ([SNIPPET]). Mitigation: show facet counts for *all* candidate relations and labels at the anchor, so a missing facet is visible. Also have validation check the plan against the question, not only claims against records.
2. **Membership that needs judgment cannot be computed by the database.** "Which of these 300 techniques are relevant to cloud identity?" needs reading, not a query. The split works only when membership is expressible as a schema predicate. The controller must recognise when it is not and say so, or page through the set.
3. **Prose can still overclaim.** The composer can list correctly while the controller's prose says "the key ones are A, B, C" based on a ranking-by-accident. Ban unqualified "all"/"only"/"none" in controller prose unless the envelope says `complete: true`, and let validation enforce it.
4. **The re-executed query must be the same query.** On live graphs the full-set query can see different data than the sample did. Pin a snapshot or transaction timestamp in the handle, or report both counts.
5. **Enormous answers are not useful.** A 12,000-row correct answer is complete but unhelpful. The composer should group by facet and attach the full list as an artefact or handle. That is a presentation decision, not a completeness one.

**Canedo's two other results matter here** ([READ]). First, scoping each hop with an oracle *hurt*, Δ = −0.057 versus full context ("loses holistic view").\[1\] Do not show the controller only the current hop; keep a compact running ledger of all prior envelopes. Second, the strict grounding instruction suppresses answers when facts are missing (F1 0.035 vs 0.299 with no facts).\[1\] That is good for abstention, and abstention is what Ariadne wants when nothing holds.

### Q4. Serialisation

**Quick answer:** with frontier models at multi-hop depth, syntax barely matters. What matters is readable predicate and entity names, and incident-style (grouped-by-node) layout for degree and neighbour questions. Choose for tokens.

- Canedo (2026, preprint, [READ]) tested 7 formats over 6 models. The accuracy spread was 0.234 at one hop and 0.036 at three hops. "The active ingredient is the predicate name": the bottom formats (JSON-LD, RDF/XML) exposed only P-numbers. Mean length per 50 triples ranged from 644 tokens (prose) to 2,383 (N-Triples), and "length does not predict accuracy". Caveat: depth is completely aliased with benchmark (LC-QuAD vs QALD) in that study.\[1\]
- Yu et al. (2026, Oracle, preprint, [READ] abstract and introduction): 15 formats across nine frontier configurations. "Knowledge extraction is relatively insensitive", "structural reasoning" is sensitive, and a query-dependent format selector gained 9.52 pp over the best fixed format.\[22\] In the appendix, adjacency had the highest mean accuracy at 62.86% ([SNIPPET]).\[22\]
- Older, non-reasoning evidence shows larger effects. Talk Like a Graph (ICLR 2024) reports 4.8–61.8 pp spreads;\[22\] for connected-node questions, incident encoding scored 53.8% versus 19.8% for adjacency ([SNIPPET]).\[1\]\[23\] KG-LLM-Bench (NAACL 2025 workshop) reports 17.5 pp variation, with structured JSON and list-of-edges best overall ([SNIPPET]).\[24\]\[25\]
- Anthropic ([READ]): resolving opaque IDs to meaningful names "significantly improves Claude's precision in retrieval tasks by reducing hallucinations". Concise responses used ~⅓ the tokens of detailed ones (72 vs 206).\[21\]

**Implication for Ariadne:** use a JSON envelope for metadata, because it is machine-checkable, and a compact *entity-centric table* for the sample: one row per node with label, ID, name and the relation it was reached by. Always include human-readable names next to ATT&CK/CWE IDs. Test two formats on your 27–32B model rather than trusting frontier results.

### Q5. Handles, paging and progressive disclosure

**Quick answer:** the practitioner consensus is strong (cap, paginate, label truncation, keep restorable references), and one controlled study supports it. Controlled measurements that isolate a handle or paging scheme do not exist.

- Manus (practitioner, [SNIPPET]): "our compression strategies are always designed to be restorable", i.e. drop content but keep the URL or path.\[26\] Ji's July 2025 Manus post reports that "the average input-to-output token ratio is around 100:1" and that a typical task "requires around 50 tool calls on average".
- Anthropic ([READ]): `response_format` concise/detailed enum, default caps, and truncation messages that steer the agent toward narrower queries.\[21\]
- Lindenbauer et al. ([ABSTRACT]): masking stale observations matches summarisation at half the cost, and on SWE-bench Verified across five model configurations a hybrid cuts cost by a further 7% versus masking alone and 11% versus LLM summarisation.
- Chenene et al. ([READ]): persistent state outside the context plus selective printing is the best-measured form of a "handle". Note that its advantage comes partly from allowing far more graph calls.\[13\]
- **Progressive disclosure** (facets first, details on request) has no isolated measurement in KGQA. It is a design pattern, supported by the evidence above that unnecessary context costs latency and sometimes accuracy.

### Q6. Hubs in the database

**Quick answer:** always traverse by typed, directed relationships. Probe degree before expanding. Cap per source row, not just globally. Start intersections from the cheaper anchor. Profile everything.

- **Neo4j.** `size((n)-[:TYPE]->())` compiles to `GetDegree(n, Some(TYPE), OUT)`, which "consult[s] the degree value stored with the given node" rather than traversing (Neo4j KB, [SNIPPET]).\[5\] In Neo4j 5 Cypher, the `COUNT { }` subquery is the current form. Dense nodes keep "separate relationship chains for each relationship type", so typed expansion avoids scanning other types (Neo4j community answer, [SNIPPET]).\[27\] A dated 2012-era measurement showed that fetching the single IS_IN relationship of a node with 100,001 relationships took 1.6 s on first access ([SNIPPET]; old engine, treat as illustrative only).\[28\] The standard modelling fix, intermediate or partition nodes, changes the schema and is out of scope for read-only specialists.\[29\]\[30\]
- **Neptune / TinkerPop.** "Queries that use in(), inE(), both(), or bothE() will run unconstrained unless you also provide a edge label" (AWS re:Post, [SNIPPET]).\[6\] Neptune evaluates a Gremlin query on a single thread (re:Post, [SNIPPET]).\[31\] Its prescriptive guidance says Neptune is optimised for transactional queries "that start from a single node or set of nodes and fan out", not whole-graph analytics ([SNIPPET]).\[32\] Neptune docs recommend inserting `barrier()` after `order().by(...).limit(n)` to avoid a TinkerPop 3.4.11 regression ([SNIPPET]).\[33\] TinkerPop provides `limit(local, n)`, `sample(n)` and `local(...)` for per-traverser caps ([SNIPPET]).\[34\]\[35\]
- **Cost at million-node scale:** one synthetic benchmark with 1.02M nodes and 5.34M rows reports query geomeans in the low milliseconds across eight engines, and rank orders that change with scale (preprint, [SNIPPET]).\[36\] It does not isolate hubs. I found **no published measurement** of Neptune degree-probe cost, and I could not verify whether Neptune stores per-label degree. Assume it does not, and precompute a degree property as a build step (B).

### Q7. Scale evidence (≥1M nodes)

**Quick answer:** almost all KGQA agent work runs on Freebase subsets. Full-graph agent evidence exists for Wikidata, and it says context management, not the model, was the bottleneck.

- Chenene et al. (preprint, [READ]): 48M entities and 262M facts. The best configuration was Qwen3.8-27B in the harness at 74/100 and an estimated $0.04 per question on one H100. What broke under plain tool calling: runs ended without an answer (8/50 multi-hop for Qwen; 16 and 20 of 50 for two other models that hit turn or cost limits), and search did not reach the target. The authors also excluded seeds with more than 500 incoming links when building questions, so the evaluation partly avoids the worst hubs.\[13\]
- SPINACH (Wikidata, peer-reviewed): caps observations (see Q1). On its own dataset of 320 question–SPARQL pairs from Wikidata's "Request a Query" forum, it reports a ≥38.1% F1 gain over the best GPT-4 KBQA agent ([ABSTRACT]), and it also beats the previous best on QALD-7, QALD-9 Plus and QALD-10 by 31.0%, 27.0% and 10.0% F1 ([SNIPPET]). No latency figures were gathered.
- ToG on Freebase: 19–42 s per question with frontier APIs ([SNIPPET]).\[8\]\[9\] A local model at several seconds per call with 13 calls per question would be slower still.
- KG-R1 (preprint, T, RL-trained): 6.38 s mean latency per WebQSP query on one H100 ([SNIPPET]).\[37\] Excluded as T, but useful as a latency reference point.
- **Missing:** no published study reports enumeration accuracy, hub-specific latency or confident-incomplete rates for KGQA on a multi-million-node *property graph* (Neo4j/Neptune). Ariadne would be first.

## Recommended observation format for specialist results

Every specialist call returns one envelope. The controller sees the envelope; the record store keeps everything. Fields:

```json
{
  "call_id": "c7",
  "source": "attack-neo4j",
  "primitive": "expand",
  "plan": {"anchor": "T1176 (Browser Extensions)", "relation": "MITIGATED_BY",
           "direction": "out", "target_label": "Mitigation", "filters": []},
  "executed_query": "<parameterised Cypher/Gremlin text>",
  "snapshot": "tx-ts 2026-10-26T14:02:11Z",
  "anchor_degree": {"total": 41230,
      "by_relation": {"MITIGATED_BY/out": 3, "USES/in": 40880, "SUBTECHNIQUE_OF/in": 0}},
  "total": 3,
  "facets": {"by_target_label": {"Mitigation": 3}},
  "sample": {"k": 3, "ordering": "identifier ascending (deterministic)",
      "columns": ["id", "name", "via_relation"],
      "rows": [["M1047","Audit","MITIGATED_BY"], ["...","...","..."]]},
  "complete": true,
  "truncation_note": null,
  "handle": "h:c7",
  "next": ["page(h:c7, offset, limit)", "facet(h:c7, by)", "filter(h:c7, label|relation|property)", "count_only"],
  "limits_hit": {"rows": false, "timeout": false, "depth": false},
  "status": "ok"
}
```

**Rules:**
1. **Counts first, always exact, from the database.** `anchor_degree` and `facets` come from count queries, not from counting sampled rows. If a count would itself time out, return `"total": ">=1000 (capped)"` explicitly. Never return a silent number.
2. **Sample size ≤ 20 by default, ≤ 50 on request.** State the ordering in words. Default to a deterministic order (identifier). Use a question-conditioned order (BM25 or embedding) only if the controller asks for "most relevant", and then label it as such.
3. **Truncation is stated as a sentence and a flag:** `complete: false`, plus "Showing 20 of 40,880 USES/in neighbours, ordered by identifier. This is a sample; do not describe it as the full set. Use facet(...) or filter(...) to narrow, or let the composer list all." This wording follows the Jeffries and Anthropic evidence.
4. **Readable names next to every ID**, as in the source card's one-line label descriptions.
5. **The handle holds the executed query, parameters and snapshot, not cached rows.** Paging re-executes with SKIP/LIMIT, or `range()` in Gremlin, under the same snapshot where the backend allows it.
6. **The controller's context keeps all envelopes but masks stale samples.** Masking stale observations is supported by Lindenbauer et al.; keeping all envelopes is supported by Canedo's per-hop-scoping penalty. Totals, facets and the plan stay; sample rows older than the last two calls are replaced by their handle.

**How the composer stays complete:**
- When the controller decides to answer, it emits a structured answer plan rather than a list of members. The plan has the form "answer = members of h:c7 (all), grouped by facet X, plus the scalar from h:c9", together with any prose claims.
- The composer re-executes each referenced handle *without* the row cap but with a hard ceiling. The source card's 1,000-row limit becomes the composer's ceiling. Above it the composer reports "N results; first 1,000 listed; full set via handle". It then renders the list deterministically.
- Validation checks every prose claim against the records the composer actually retrieved. It also rejects "all/only/none/every" wording whenever any referenced envelope has `complete: false` and the composer did not enumerate it. When nothing holds, it abstains and shows the executed queries.
- **Residual risk:** the composer guarantees completeness *relative to the plan*. Plan correctness is still the controller's job. The facet view of all relations at the anchor is the main defence.

## Recommended hub handling at query level

**Cypher (Neo4j 5):**

```cypher
// 1. Degree probe (no traversal on dense nodes): one row per (type, direction)
MATCH (a {stix_id: $id})
RETURN COUNT { (a)-[:MITIGATED_BY]->() } AS mitigated_by_out,
       COUNT { (a)<-[:USES]-() }        AS uses_in;

// 2. Facet counts by target label for one typed relation
MATCH (a {stix_id: $id})<-[:USES]-(n)
RETURN labels(n)[0] AS label, count(*) AS c;

// 3. Capped sample with deterministic order
MATCH (a {stix_id: $id})<-[:USES]-(n:Group)
RETURN n.stix_id, n.name ORDER BY n.stix_id LIMIT $k;

// 4. Two-anchor intersection: expand from the lower-degree anchor, then check membership
MATCH (lo {stix_id: $lowDegId})<-[:USES]-(x)
WHERE EXISTS { (x)-[:USES]->(:Technique {stix_id: $highDegId}) }
RETURN x.stix_id, x.name ORDER BY x.stix_id LIMIT $k;

// 5. Per-row caps in chained expansions
MATCH (t:Technique {stix_id: $id})<-[:USES]-(g:Group)
CALL (g) { MATCH (g)-[:USES]->(s:Software) RETURN s ORDER BY s.stix_id LIMIT 5 }
RETURN g.stix_id, collect(s.stix_id);
```

Always specify the type and direction. Index the identifier property for every label in the source card (a B step). Run `PROFILE` in CI on the top 20 hubs. The intersection planner should take degrees from step 1, never guess them.

**Gremlin (TinkerPop / Neptune):**

```groovy
// Degree probe per label (traverses edges; cache as a property on Neptune if slow)
g.V().has('stix_id', id).project('uses_in','mitigated_by_out').
  by(inE('USES').count()).by(outE('MITIGATED_BY').count())

// Facets
g.V().has('stix_id', id).in('USES').groupCount().by(label)

// Capped deterministic sample (barrier() per Neptune guidance)
g.V().has('stix_id', id).in('USES').hasLabel('Group').
  order().by('stix_id').limit(k).barrier().valueMap('stix_id','name')

// Per-traverser cap in chains
g.V().has('stix_id', id).in('USES').hasLabel('Group').
  local(out('USES').hasLabel('Software').order().by('stix_id').limit(5)).path()
```

Never emit `in()`, `out()`, `both()` or `bothE()` without a label. Neptune's single-threaded Gremlin evaluation makes unlabelled fan-out on a hub the main timeout risk. Unlike Neo4j's stored degrees, `inE('USES').count()` here walks the edges, as far as I could verify. If the probe is slow on hubs, a build-time job writing `deg_USES_in` properties (class B) turns it into a property read. Refresh it when the graph changes.

**Avoid random sampling (`sample()`, `rand()`) in specialist samples.** It breaks reproducibility, caching and the "executed query as proof" requirement. Use deterministic orderings.

## Experiments to run on Ariadne

1. **Truncation labelling A/B (decides rule 3).** Take the enumeration subset of the 282 sealed questions and inflate answer sets with synthetic members, so that totals exceed k = 20. Arm A shows rows only; arm B shows rows plus `total`, `complete` and the truncation sentence. **Decisive measure:** the *confident-incomplete rate*, i.e. the share of answers asserting completeness or listing members while the envelope was truncated, and records-exact. The labelling is adopted if B cuts confident-incomplete by at least half without lowering records-exact.
2. **Composer split vs controller listing (decides the architecture).** On the same enumeration questions, compare (a) the controller writing the list from paged results with (b) the controller emitting a handle-based plan that the composer renders. **Decisive measure:** enumeration recall and precision against gold, the confident-wrong rate, and wall-clock time. Also log plan errors that the composer completed faithfully (weakness 1) and judgment-membership questions the split cannot express (weakness 2).
3. **Sample-size sweep (sets k).** k ∈ {0 (counts and facets only), 5, 20, 100, 500} on chained and cross-source questions, which are the worst tiers (about −0.50 and −0.55). **Decisive measure:** next-call correctness (did the controller choose the gold relation or anchor next?), gold coverage, tokens per call and seconds per call on the local 27–32B model. Choose the smallest k within 1 point of the best coverage.
4. **Hub stress test (decides query templates).** Attach synthetic indicator nodes to ATT&CK techniques until the top hubs reach 10⁵–10⁶ edges, with about 10⁶–10⁷ nodes in total. Run them in Neo4j and Gremlin Server, and in Neptune when available. Compare naive expand vs degree probe plus typed capped expand, and intersection from the high- vs the low-degree anchor. **Decisive measure:** p50/p95 latency, timeouts at the source card's limit, and identical result sets.
5. **Envelope history policy (decides rule 6).** Compare full history, masking of stale samples, and per-hop scoping only, on chained questions. **Decisive measure:** gold coverage and total controller tokens. Canedo predicts that per-hop scoping loses; Lindenbauer predicts that masking ties full history at lower cost.

## Caveats

- Much of the strongest evidence is from 2026 preprints (Canedo; Chenene et al.; Yu et al.; Jeffries) and has not been peer-reviewed. Jeffries is single-author and was read only at abstract level.
- No study measures confident-incomplete behaviour on graph-query results specifically. The truncation evidence comes from RAG document search.
- Format, size and precision results come from frontier models (Claude, GPT-5, Gemini). A local 27–32B reasoning model may be more sensitive. Experiment 3 exists to check this.
- The Neo4j and Neptune hub guidance is from vendor knowledge-base pages and forums, read as snippets. Version-specific behaviour (Neo4j 5 store format, Neptune DFE engine) should be confirmed with `PROFILE` on your own deployment.
- No evidence was found for training-free neighbour ranking at hub scale. The recommendation to rank only when asked follows from that absence.

## Bibliography and read status

- Canedo, "The Answer Path and the Grounding Instruction in LLM Question Answering over Knowledge Graphs", preprint 2026. https://arxiv.org/html/2609.10237 — [READ] (through §V)
- Chenene, Rosas-Hinostroza, Langlais, Stasenko, "Wikidata Search Traces: A Dataset for Training Knowledge Graph Search Agents", preprint 2026. https://arxiv.org/html/2610.06650v1 — [READ]
- Yu, Bornea, Sil, Kirchhoff, "Graph Serializations for Reasoning LLMs", preprint 2026. https://arxiv.org/html/2610.22734 — [READ] abstract–§3; appendix table [SNIPPET]
- Anthropic, "Writing effective tools for agents — with agents", engineering blog 2025 (practitioner). https://www.anthropic.com/engineering/writing-tools-for-agents — [READ]
- Jeffries, "Who Verifies the Tools? How Warped Formatters Mislead Agents and Their Verifiers", NeurIPS 2026 workshop poster (non-archival), preprint. https://arxiv.org/abs/2610.32110 — [ABSTRACT]; full-text quotes [SNIPPET]
- Lindenbauer et al., "The Complexity Trap: Simple Observation Masking Is as Efficient as LLM Summarization", DL4C @ NeurIPS 2025 (peer-reviewed workshop). https://arxiv.org/abs/2508.21433 — [ABSTRACT]
- Sun et al., "Think-on-Graph", ICLR 2024 (peer-reviewed). https://arxiv.org/html/2307.07697v6 — [READ] intro/method; ablation [SNIPPET]
- Li et al., "Simple is Effective: … SubgraphRAG", ICLR 2025 (peer-reviewed). https://arxiv.org/abs/2410.20724 — [SNIPPET]
- Liu et al., "SPINACH: SPARQL-Based Information Navigation", EMNLP Findings 2024 (peer-reviewed). https://arxiv.org/abs/2407.11417 — [ABSTRACT]; caps [SNIPPET]
- "Learning Efficient and Generalizable Graph Retriever for KGQA" (RAPL), preprint. https://arxiv.org/pdf/2506.09645 — [SNIPPET]
- "SPLIT-RAG: Question-Driven Graph Partitioning", preprint. https://arxiv.org/pdf/2505.13994 — [SNIPPET]
- Fatemi, Halcrow, Perozzi, "Talk like a Graph", ICLR 2024 (peer-reviewed). https://arxiv.org/pdf/2310.04560 — [SNIPPET]
- Markowitz et al., "KG-LLM-Bench", NAACL 2025 KnowledgeNLP workshop. https://arxiv.org/abs/2504.07087 — [SNIPPET]
- Wolfson et al., "MoNaCo", preprint. https://arxiv.org/abs/2508.11133 — [ABSTRACT]; §5.3 [SNIPPET]
- "KG-Guard: Graph-Based Hallucination Detection for KBQA", preprint. https://arxiv.org/pdf/2606.00328 — [SNIPPET]
- "QO-Bench: Query-Operator-Preserving Retrieval over Typed Event Tuples", preprint. https://arxiv.org/pdf/2606.04646 — [SNIPPET]
- Biswal et al., "Text2SQL is Not Enough: Unifying AI and Databases with TAG", preprint 2024. https://arxiv.org/abs/2408.14717 — [ABSTRACT]
- FRAG, "A Flexible Modular Framework for Retrieval-Augmented Generation based on KGs", ACL Findings 2025. https://arxiv.org/pdf/2501.09957 — [SNIPPET]
- Hong, Troynikov, Huber, "Context Rot", Chroma technical report 2025 (practitioner). https://www.trychroma.com/research/context-rot — [SNIPPET]
- "Context Length Alone Hurts LLM Performance Despite Perfect Retrieval", EMNLP Findings 2025. https://aclanthology.org/2025.findings-emnlp.1264.pdf — [SNIPPET]
- "Can We Count on LLMs? The Fixed-Effect Fallacy", preprint. https://arxiv.org/html/2409.07638v1 — [SNIPPET]
- Ji (Manus), "Context Engineering for AI Agents: Lessons from Building Manus", blog 2025 (practitioner). https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus — [SNIPPET]
- "KG-R1: Efficient and Transferable Agentic KG RAG via RL", preprint. https://arxiv.org/pdf/2509.26383 — [SNIPPET]
- "Graph Memory for LLM Agents: At What Cost?", preprint. https://arxiv.org/html/2609.23315v1 — [SNIPPET]
- Neo4j KB, "How do I improve the performance of counting number of relationships on a node". https://neo4j.com/developer/kb/how-do-i-improve-the-performance-of-counting-number-of-relationships-on-a-node/ — [SNIPPET]
- Neo4j Community, "Many relationship types or one with properties?". https://community.neo4j.com/t/is-it-better-to-have-many-different-relationship-types-or-one-relationship-with-properties/1669 — [SNIPPET]
- OpenCredo, "Neo4j: Super-Nodes and Indexed Relationships". https://opencredo.com/blogs/neo4j-super-nodes-and-indexed-relationships-part-i/ — [SNIPPET]
- AWS re:Post, "Expected performance / limitations of Neptune with millions of edges". https://repost.aws/questions/QUo5aORKo8Qm-HiKpEFaOa9Q — [SNIPPET]
- AWS re:Post, "Vertex filtering significant performance issues". https://repost.aws/questions/QUGBmGmpyETASRoht-xbWyRg — [SNIPPET]
- AWS, "General Best Practices for Using Gremlin with Neptune". https://docs.aws.amazon.com/neptune/latest/userguide/best-practices-gremlin.html — [SNIPPET]
- AWS Prescriptive Guidance, Neptune performance efficiency pillar. https://docs.aws.amazon.com/prescriptive-guidance/latest/neptune-well-architected-framework/performance-efficiency-pillar.html — [SNIPPET]
- Apache TinkerPop reference documentation. https://tinkerpop.apache.org/docs/current/reference/ — [SNIPPET]

## Sources

1. <https://arxiv.org/html/2609.10237>
2. [Who Verifies the Tools? How Warped Formatters Mislead Agents and Their Verifiers](https://arxiv.org/abs/2610.32110)
3. [KG-Guard: Graph-Based Hallucination Detection for Knowledge Base Question Answering](https://arxiv.org/pdf/2606.00328)
4. [MoNaCo: More Natural and Complex Questions for Reasoning Across Dozens of Documents](https://arxiv.org/pdf/2508.11133)
5. [How do I improve the performance of counting number of relationships on a node - Knowledge Base](https://neo4j.com/developer/kb/how-do-i-improve-the-performance-of-counting-number-of-relationships-on-a-node/)
6. [Expected performance / Limitations of AWS Neptune graph with millions of edges](https://repost.aws/questions/QUo5aORKo8Qm-HiKpEFaOa9Q/expected-performance-limitations-of-aws-neptune-graph-with-millions-of-edges)
7. [Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph](https://arxiv.org/html/2307.07697v6)
8. [Learning Efficient and Generalizable Graph Retriever for Knowledge-Graph Question Answering](https://arxiv.org/pdf/2506.09645)
9. [Divide by Question, Conquer by Agent: SPLIT-RAG with Question-Driven Graph Partitioning](https://arxiv.org/pdf/2505.13994)
10. [Simple is Effective: The Roles of Graphs and Large Language Models in Knowledge-Graph-Based Retrieval-Augmented Generation](https://arxiv.org/html/2410.20724v2)
11. [BASED RETRIEVAL-AUGMENTED GENERATION](https://proceedings.iclr.cc/paper_files/paper/2025/file/11e1900e680f5fe1893a8e27362dbe2c-Paper-Conference.pdf)
12. [Spinach: SPARQL-Based Information Navigation for Challenging Real-World Questions](https://arxiv.org/html/2407.11417v1)
13. <https://arxiv.org/html/2610.06650v1>
14. [Can We Count on LLMs? The Fixed-Effect Fallacy and Claims of GPT-4 Capabilities](https://arxiv.org/html/2409.07638v1)
15. [The Complexity Trap: Simple Observation Masking Is as Efficient as LLM Summarization for Agent Context Management](https://arxiv.org/abs/2508.21433)
16. [Paper page - The Complexity Trap: Simple Observation Masking Is as Efficient as LLM Summarization for Agent Context Management](https://huggingface.co/papers/2508.21433)
17. [FRAG: A Flexible Modular Framework for Retrieval-Augmented](https://arxiv.org/pdf/2501.09957)
18. [FRAG: A Flexible Modular Framework for Retrieval- ...](https://aclanthology.org/2025.findings-acl.321.pdf)
19. [QO-Bench: Diagnosing Query-Operator-Preserving Retrieval over Typed Event Tuples](https://arxiv.org/pdf/2606.04646)
20. [Who Verifies the Tools? How Warped Formatters Mislead Agents and Their Verifiers](https://arxiv.org/html/2610.32110)
21. [Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
22. [Graph Serializations for Reasoning LLMs:A Study Across Knowledge Extraction and Structural Reasoning](https://arxiv.org/html/2610.22734)
23. [\[2310.04560\] Talk like a Graph: Encoding Graphs for Large Language Models](https://ar5iv.labs.arxiv.org/html/2310.04560)
24. [KG-LLM-Bench: A Scalable Benchmark for Evaluating LLM Reasoning on Textualized](https://knowledge-nlp.github.io/naacl2025/papers/39.pdf)
25. [zenn-content/articles/kg-llm-bench.md at main · sea-turt1e/zenn-content · GitHub](https://github.com/sea-turt1e/zenn-content/blob/main/articles/kg-llm-bench.md)
26. [Context Engineering for AI Agents: Lessons from Building Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)
27. [Is it better to have many different relationship types or one relationship with properties? - Cypher - Neo4j Online Community](https://community.neo4j.com/t/is-it-better-to-have-many-different-relationship-types-or-one-relationship-with-properties/1669)
28. [Neo4j: Super-Nodes and Indexed Relationships, Part I](https://opencredo.com/blogs/neo4j-super-nodes-and-indexed-relationships-part-i/)
29. [Best Practices in Graph Data Modeling for Neo4j Professional Certification](https://medium.com/@firmanbrilian/best-practices-in-graph-data-modeling-for-neo4j-professional-certification-39b0bf1dfe9a)
30. [Neo4j Dense Nodes: Solve the Supernode Performance Problem (2026)](https://adhdecode.com/articles/neo4j/neo4j-dense-node-supernode-problem/)
31. [Vertex Filtering Significant Performance Issues](https://repost.aws/questions/QUGBmGmpyETASRoht-xbWyRg/vertex-filtering-significant-performance-issues)
32. [Pilastro dell'efficienza delle prestazioni - AWS Guida prescrittiva](https://docs.aws.amazon.com/it_it/prescriptive-guidance/latest/neptune-well-architected-framework/performance-efficiency-pillar.html)
33. [General Best Practices for Using Gremlin with Neptune - Amazon Neptune](https://docs.aws.amazon.com/neptune/latest/userguide/best-practices-gremlin.html)
34. [TinkerPop Documentation - Apache Software Foundation](https://tinkerpop.apache.org/docs/current/reference/)
35. [GraphTraversal (Apache TinkerPop 3.2.5 API)](https://tinkerpop.apache.org/javadocs/3.2.5/core/org/apache/tinkerpop/gremlin/process/traversal/dsl/graph/GraphTraversal.html)
36. [Graph Memory for LLM Agents: At What Cost? A Comparative Evaluation of Query, Ingest, and Update Performance Across Graph Database Engines](https://arxiv.org/html/2609.23315v1)
37. [Efficient and Transferable Agentic Knowledge Graph RAG via Reinforcement Learning](https://arxiv.org/pdf/2509.26383)
