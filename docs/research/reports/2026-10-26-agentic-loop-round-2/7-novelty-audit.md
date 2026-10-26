# Ariadne prior-art audit: which of five novelty claims survive a "refute first" search (2026-10-26)

None of the five claims is fully clear. One sub-claim is killed outright: C-B's "no published work reports modern-model Gremlin generation accuracy" is false, because EICopilot (2025) measured LLM Gremlin generation on a production graph. The other four survive only in narrowed form. The defensible core is now a set of measurements on property graphs, not new mechanisms: confident-incomplete answers, typed-versus-free generation on Cypher and Gremlin, calibration of the grounding step under graph shift, the effect of binding verification, and cross-engine federation with latency broken out by hub nodes.

## TL;DR

- **Verdicts:** C-A narrowed. C-B narrowed, with its Gremlin "no measurement" half killed by EICopilot. C-C narrowed. C-D scooped on mechanism but narrowed-surviving on measurement. C-E narrowed. Nothing is "clear". Every surviving version is "first to *measure* X on property graphs under Y", not "first to *build* X".
- **Strongest prior art per claim:**
  - C-A: Jeffries (2026) for truncation misleading agents and verifiers, and Wikidata Search Traces (2026) for keeping results out of the model's context.
  - C-B: EICopilot (Gremlin), Text2GQL-Bench (dialect collapse), text2ql (typed IR vs LLM, SQL/GraphQL only).
  - C-C: KG-R1 (cross-KG transfer of a trained policy) plus classic selective QA under domain shift.
  - C-D: Alrashed, Sukoon, Karger & Noy (Google, PVLDB 19, 2026). Their round-trip critique and synthetic execution consistency methods together flag "64% of errors from a state-of-the-art generator". Also SAGA's type checks that catch wrong entities.
  - C-E: the Data Agent Benchmark (one agent, four DBMSs, not graphs), AgCyRAG (Cypher plus SPARQL agents, demonstration only) and Ozsoy's multi-database Text2Cypher roadmap.
- **What to do:** run the five experiments specified below on CypherBench-derived graphs loaded into both Neo4j and a TinkerPop engine, plus your security graphs. Treat Ozsoy (Neo4j) and the TuGraph/Ant Group Text2GQL team as the groups most likely to publish overlapping results first. Also fix two citation errors before anything is written up: "Ozsoy (2026)" is not a security/federation paper, and KG-Guard is not an under-enumeration paper.

## Key Findings

| Claim | Verdict | Strongest prior art (read status) | Survives as |
|---|---|---|---|
| C-A Exact answers under a bounded controller | **Narrowed** | Jeffries 2610.32110 [ABSTRACT]; Wikidata Search Traces 2610.06650 [ABSTRACT] | First measurement of confident-incomplete answers in *graph* QA, and of a design that bounds them, conditional on a correct binding |
| C-B Typed algebra vs text-to-query | **Narrowed; Gremlin-measurement half killed** | EICopilot 2501.13746 [READ]; Text2GQL-Bench 2602.11745 [READ intro/Table 1; figures ABSTRACT/SNIPPET]; text2ql 2609.02115 [ABSTRACT] | Same-graph, same-model comparison of typed compiled requests vs free Cypher *and* Gremlin on unseen property graphs |
| C-C Calibrated cross-graph grounding | **Narrowed** | KG-R1 2509.26383 [SNIPPET]; Kamath et al. ACL 2020 [SNIPPET]; BLINKout [SNIPPET] | Calibration and risk control of a grounding model under *graph* shift, with a measured "none" rate |
| C-D Interpretation verification | **Scooped (mechanism); narrowed (measurement)** | PVLDB text-to-SQL verification [ABSTRACT]; SAGA 2607.14494 [ABSTRACT + SNIPPET of appendix]; CES-PK 2608.24824 [ABSTRACT] | Measured reduction of confident-wrong answers when a binding check is added *on top of* a claim verifier in KG QA |
| C-E Federated cross-engine agents at hub scale | **Narrowed** | DAB 2603.20576 [ABSTRACT]; AgCyRAG CEUR 4079 [SNIPPET]; Ozsoy 2605.10373 [READ via subagent] | First quantitative evaluation across Cypher and Gremlin stores, unmerged, with hub-stratified latency |

## Details

Method classes used throughout: **P** means plug-and-play with an off-the-shelf model. **B** means it needs an automatic one-time build step per graph. **T** means it needs training or fine-tuning on the target graph or task.

### C-A. Exact answers under a bounded controller: NARROWED

**Plain language.** An agent can answer "list all X" while only having seen the first page of X, and say or imply that this is everything. Someone has already shown this happens with document-search tools, and that labelling the cut-off fixes much of it. Nobody I found has measured it for graph databases, or shown that letting the database compute the full list while the model sees only a summary removes it.

**Detail.** William Jeffries' "Who Verifies the Tools? How Warped Formatters Mislead Agents and Their Verifiers" (arXiv 2610.32110v1, 23 Oct 2026; preprint, poster at the non-archival "Who Verifies the Agents?" NeurIPS 2026 workshop) [ABSTRACT] studies "a production RAG research system used by the Pilsudski Institute in New York". It reports:
- tool formatters that "omitted search limits, result caps, or identifier namespaces" misled agents;
- repairing the wording reduced unsupported claims "substantially for three of the four failure types";
- verifiers went from accepting incorrect answers "90 out of 90 times to rejecting them 90 out of 90 times";
- its audit prompt "found warped formatters in both" OpenClaw and Hermes, and "the OpenClaw fix has already been merged".

This is the measurement for document search that the brief anticipated. The fix is P: formatter wording only.

Wikidata Search Traces (Chenene, Rosas-Hinostroza, Stasenko, Evenstein Sigalov & Langlais, 2610.06650v3; preprint) [ABSTRACT] builds the bounded-view mechanism for a knowledge graph and releases "10,235 solving traces". Its recursive-language-model harness keeps graph results "in persistent Python state" and lets the model read selected evidence through sub-calls. On 100 questions it raised gpt-6-luna "from 49 to 61 correct answers, doubling its multi-hop accuracy", and Qwen3.8-27B, "an open-weight model served on a single GPU", from 60 to 74. The harness itself is P. That model class matches your controller, so this is the nearest neighbour to your loop. Its abstract reports accuracy, however, not enumeration completeness or confident-incomplete rates. The abstract describes only "a frozen Wikidata snapshot", so the "48M-entity graph" figure in your brief remains unverified.

Practitioner evidence exists in the SQL world. A Metabase issue documents `execute_sql` silently truncating at a row limit while reporting `status: completed`, noting that an agent "will report the number without any hedge" [SNIPPET].\[1\] That is a bug report, not a measurement. Searches across the text-to-SQL and data-agent vocabularies (truncation, LIMIT, completeness of rows) found no paper measuring this rate.

**Why "removes" is too strong.** Your own premise (C-D) says a wrong entity yields records that genuinely support claims about the wrong node. An envelope design makes the enumeration complete *for the executed query*. It cannot make it complete for the question if the binding is wrong. The "million-node" part is also unsupported by your data: current graphs are about 10,000 nodes.

**Defensible sentence.** "On property-graph question answering, agents that read truncated tool output produce confident-incomplete answers at a measurable rate. A controller that reads only exact-total envelopes, while the database computes and a deterministic composer lists the full set, reduces that rate to near zero *conditional on a correct binding*, with no loss of accuracy."

**Experiment that makes it a contribution.**
1. Take enumeration questions whose gold answer sets exceed the row cap (1,000) on CypherBench graphs and on a scaled security graph.
2. Run three arms with the same local 27–35B controller:
   - (a) raw truncated rows;
   - (b) truncated rows plus a Jeffries-style truncation label;
   - (c) your envelope plus composer.
3. Report recall of the answer set and the confident-incomplete rate. Confident-incomplete means the answer asserts or implies completeness while recall is below 1, scored by a fixed rubric.
4. Stratify by answer-set size, including hubs.

Arm (b) is essential. Without it, a reviewer will say Jeffries already solved this.

### C-B. Typed algebra vs text-to-query on unseen property graphs: NARROWED; the Gremlin "no measurement" half is KILLED

**Plain language.** Someone has already measured how well LLMs write Gremlin: on a large real company graph, zero-shot accuracy was poor and rose sharply only with hand-made examples. Someone has also built a typed in-between representation that a deterministic compiler turns into queries, but only for SQL and GraphQL. Nobody I found has run your exact comparison, typed requests versus LLM-written queries on the same unseen property graphs with the same models, for both Cypher and Gremlin.

**Detail: Gremlin.** EICopilot (Yun et al., Baidu, arXiv 2501.13746, January 2025; preprint) [READ] generates Gremlin for a TinkerPop enterprise graph of "hundred millions of nodes, ten billions of edges". On 150 real user queries:
- zero-shot "execution correctness" ranged from **17.33% (ErnieBot-Speed) to 41.00% (ErnieBot)**, with Llama3-8b at 17.66%;
- the production setup, top-5 retrieved examples with entity masking, reached **82.14% (ErnieBot)** and **83.93% (fine-tuned ErnieBot-Speed)**.\[2\]

Read these carefully:
- "Execution correctness" is an *expert rating* with 0.5 partial credit, not result-set matching, so it is not comparable to CypherBench's execution accuracy.
- The "syntax error rate" formula as printed is inverted relative to its name.
- The deployment appendix describes NebulaGraph, contradicting the TinkerPop description in the main text.
- The method is **T**: hand-written Gremlin for representative queries, plus supervised fine-tuning on 418 annotated pairs.\[2\]

The direction matches your observation that a 2B model produced 0 working drafts of 17. It does kill the claim that no 2025–2026 Gremlin measurement exists.

Text2GQL-Bench (Lyu et al., Ant Group/CUHK-SZ/HKUST-GZ, 2602.11745; preprint) [READ intro and Table 1] covers Cypher and ISO-GQL, not Gremlin. Its v1 abstract [ABSTRACT] reported a "stark dialect gap":
- strong LLMs reach "≤4% execution accuracy" zero-shot on ISO-GQL;
- a fixed 3-shot prompt gives about 50%;
- a fine-tuned 8B model reaches 45.1%.

The current version (2602.11745v2, 5 Aug 2026) is retitled "Text2GraphQuery-Bench". It covers Cypher, GQL and SQL/PGQ, with "267,276 (Question, Graph Query) pairs across 34 databases and 13 domains" and 8 LLMs. It drops those figures and says only that "zero-shot GQL and SQL/PGQ Grammar is far below Cypher, yet few-shot prompting largely recovers it" and that "fine-tuning an 8B model reaches or exceeds zero-shot large models". Cite the version you use.

There is an internal inconsistency to flag. A results snippet [SNIPPET] gives Claude Opus 4.5 a zero-shot score of 44.5%, while Qwen3-Max scores 3.2% and GPT-5.2 1.7%.\[3\] That contradicts the abstract's "≤4%" for strong LLMs, so treat both figures as leads. Its companion framework, Awesome-Text2GQL, advertises an intermediate representation covering Gremlin [SNIPPET].\[4\] A Gremlin benchmark from this group is plausible next.

**Detail: typed intermediate representation (IR) vs LLM.** text2ql (Kumar, 2609.02115; preprint) [ABSTRACT + SNIPPET] proposes a "language-agnostic typed intermediate representation" with pluggable renderers.\[5\] It reports 84–91% execution accuracy for LLM mode and "100% execution accuracy with zero parse errors" for deterministic mode, on 50-query samples from Spider and BIRD.\[6\] Its own table shows deterministic structural accuracy of only 32–52% and exact match of 0%.\[7\] "Execution accuracy" there appears to mean executes without error, not returns the right rows. It targets SQL and GraphQL, not property graphs, and says "full-set evaluation is planned." Middleware (Gu et al., EMNLP 2024) and QueryAgent/ERASER (ACL 2024) make the typed-tool argument for SPARQL over Freebase-style knowledge bases. I did not re-read them this round.

On Cypher, CypherBench (Feng et al., ACL 2025; peer-reviewed) [SNIPPET, consistent across the ACL PDF, arXiv and CYGNET's summary] reports:
- gpt-4o at 60.18% and claude-3.5-sonnet at 61.58% zero-shot execution accuracy on its test graphs;
- no model under 10B parameters above 20%.\[8\]\[9\]

These baselines are P. SPOT (Findings of ACL 2025; peer-reviewed) [SNIPPET] does zero-shot semantic parsing over property graphs and is a lead worth reading for a typed comparison arm.\[10\]

An industry analogue exists. dbt's 2026 vendor benchmark claims its semantic layer, where an LLM picks metrics and dimensions and the query is compiled deterministically, "approaches or hits 100%" on covered queries [SNIPPET].\[11\] That is vendor material and not peer-reviewed, but expect reviewers to cite it.

**Defensible sentence.** "On the same unseen property graphs and the same local models, typed requests whose allowed values are computed from the schema and compiled by deterministic per-backend compilers achieve higher execution accuracy than LLM-written Cypher and Gremlin. The typed path's accuracy is backend-invariant, while free generation loses more on Gremlin than on Cypher."

**Experiment.**
1. Load several CypherBench graphs into Neo4j *and* a TinkerPop engine. Amazon Neptune serves both openCypher and Gremlin over the same data, which removes data confounds.\[12\]
2. Obtain gold Gremlin by translating gold Cypher, verified by result equality.
3. Run three arms with identical models (your local 27–35B model plus one frontier comparator), using result-set execution accuracy as the metric:
   - (i) free Cypher;
   - (ii) free Gremlin;
   - (iii) typed requests compiled to each.
4. Add a CYGNET-style corrector to the free arms so you beat the strongest free baseline, not a strawman.

### C-C. Calibrated cross-graph grounding: NARROWED

**Plain language.** "Calibrated" means that when the model says 80%, it is right about 80% of the time. That is what lets you set accept, ask and abstain thresholds that hold a promised error rate. Models trained once and reused on new knowledge graphs exist, and so does calibrated abstention in question answering, but I found no grounding model trained across many graphs that reports calibration on held-out graphs.

**Detail.** KG-R1 (2509.26383; preprint) [SNIPPET] trains an agentic KG retrieval policy (**T**) and transfers it zero-shot to unseen KGs "by swapping only the backend graph". Trained on WebQSP, it averages 77.50 Hits@1 across transfer benchmarks, ahead of ToG (56.84) and PoG (72.28).\[13\] It is cross-KG reuse of a trained model, but no calibration figures appear in what I saw.

Several other lines come close without closing the claim:
- KG foundation models (ULTRA; Semma, evaluated on 54 KGs [SNIPPET]) are T once and P on new graphs.\[14\] They do link prediction, not linking mentions in a question.
- Selective question answering under domain shift (Kamath, Jia and Liang, ACL 2020; peer-reviewed) [SNIPPET] establishes that out-of-domain confidence is miscalibrated and that a trained calibrator helps.\[15\]\[16\] Your claim is the graph-shift instance of this.
- NIL linking, meaning predicting that no knowledge-base entry matches, is old. BLINKout (2302.07189) [SNIPPET] adds a learned NIL entity.\[17\]
- A GenAIK 2025 paper on entity quality adds a "None of the above" option to LLM entity selection [SNIPPET], but the snippet shows no measured "none" accuracy.\[18\]

I found no measurement of how often LLMs correctly choose "none of these" in KG entity linking, so that half is clear but thinly searched.

There is a conceptual obstacle a reviewer will raise. Distribution-free threshold guarantees, such as conformal risk control (a method that sets thresholds from a held-out calibration set so the error rate stays under a target), assume the calibration and test data are exchangeable. An unseen graph breaks that assumption. To "hold a stated wrong-entity rate" on a new graph you need either calibration data from that graph, which must be synthesized to stay within your no-hand-labelling rule, or an empirical demonstration that the rate transfers. Your own numbers (d3-lite gives p = 0.614 on the right relation and 0.791 on the right entity) are average probabilities on the correct option, not calibration. The method class is **T**, trained once on the task but not per graph.

**Defensible sentence.** "A small decision model trained once on schema-synthesized questions from N graphs, and applied unchanged to held-out graphs, has expected calibration error ≤ x on entity and relation grounding. Thresholds set on synthesized calibration questions from the new graph hold the wrong-entity rate within y of target on real questions, including a correct 'none' rate of z."

**Experiment.** Use leave-one-graph-out across at least 8 graphs: CypherBench domains plus ATT&CK, CAPEC and CWE. Report:
- expected calibration error (ECE) and risk–coverage curves for entity and relation choices;
- the realised wrong-entity rate at thresholds set (a) on synthesized questions from the target graph and (b) on source graphs only;
- "none" precision and recall on questions whose entity is absent.

Compare against an LLM's verbalised confidence and its token probabilities as baselines.

### C-D. Interpretation verification: SCOOPED (mechanism); NARROWED (measurement)

**Plain language.** Checking that a database query actually means what the user asked, separately from checking that the answer matches the data, already exists. Text-to-SQL work translates the query back into English and compares it with the question, and knowledge-graph work uses type checks to catch the wrong entity. What is not published is a measurement showing that adding such a check on top of a claim verifier in a KG agent reduces confidently wrong answers.

**Detail.** "Developing and Benchmarking Verification Algorithms to Improve Text-to-SQL Generation" (Alrashed, Sukoon, Karger & Noy, Google; PVLDB 19(11):3732–3744, 2026; peer-reviewed) [ABSTRACT] defines verification as a standalone task: "assessing whether a candidate SQL query semantically satisfies a natural language request". It proposes two methods. *Round-Trip Critique* back-translates SQL to natural language to detect drift and is P. *Synthetic Execution Consistency* is the second. Together they "provide a robust signal for identifying incorrect queries, successfully flagging 64% of errors from a state-of-the-art generator". That figure belongs to the combined methods, not round-trip critique alone. GBV-SQL (2509.12612; preprint) [SNIPPET] has an SQL2Text back-translation validator.\[19\]

In KGQA, SAGA (2607.14494; preprint, P) [ABSTRACT] filters type-incompatible properties.\[20\] Its appendix examples [SNIPPET] show a missing domain-compatible property "signals a wrong entity", after which the agent re-searches, for example correcting a "WikiLeaks" prayer entity to the organisation.\[21\] CES-PK (2608.24824; preprint, with a Springer DOI suggesting a proceedings version; P) [ABSTRACT] verifies candidate answers against symbolic type, relation and exclusion constraints derived from the question, under three-valued semantics.\[22\] SAFE (2604.01993; preprint) [SNIPPET] detects entity mismatch, such as "Eden" vs "Lake Eden", in stepwise verification.\[23\]

CYGNET (2606.04645; preprint) [ABSTRACT] supplies the motivation in numbers. Structural validation catches 100% of parse, constraint and schema-reference errors, but "property sibling-swaps where the substituted name is valid on the target label score 0%".\[24\] That is precisely the binding error a schema check cannot see.

The first half of C-D, that claim-level verification cannot detect a wrong binding, is close to definitional and is already implicit in these papers. It is not a contribution.

**Defensible sentence.** "In a KG agent whose answers already pass claim-level verification against retrieved records, a separate check of the typed binding against the question reduces confident-wrong answers by x at a cost of y in coverage. Most of the gain comes from wrong-entity cases that the claim verifier accepts by construction."

**Experiment.**
1. Inject controlled wrong bindings into otherwise correct plans: a sibling entity, a sibling relation, a reversed direction.
2. Measure on natural failures as well.
3. Compare four configurations:
   - claim verifier only;
   - plus round-trip back-translation of the typed request;
   - plus a schema/type check in the style of SAGA and CES-PK;
   - plus a decision-model check of the binding against the question.
4. Report the confident-wrong rate, abstention rate and latency for each. Your gated-rewrite result, which doubled confident-wrong answers, makes this the right primary metric.

### C-E. Federated agents across engines at hub scale: NARROWED

**Plain language.** One agent answering across several separately run databases of different kinds has been benchmarked, but for relational and document-style systems rather than graph databases. A security-graph agent that uses both Cypher and SPARQL has been demonstrated, but not measured. No paper I found measures how latency degrades on highly connected "hub" nodes in a multi-million-node graph during question answering.

**Detail.** The Data Agent Benchmark (Ma, Shankar, … Gopal, Parameswaran, 2603.20576v3, 7 Oct 2026; preprint) [ABSTRACT] is "grounded in a study of enterprises building production data agents across six industries". It has "104 queries across 17 datasets and 4 database management systems", and "the best state-of-the-art agent achieves only 57% pass@1". The agents are P. An earlier version reported 54 queries and 38% for Gemini-3-Pro [SNIPPET], so cite the version you use.\[25\] This closes "one agent across independently run stores on different engines" *except* for graph engines.

AgCyRAG (Kurniawan et al., RAGE-KG @ ISWC 2025, CEUR Vol-4079; peer-reviewed workshop) [SNIPPET] combines "structured knowledge graph reasoning (via Cypher and" a SPARQL agent over the SEPSES cybersecurity KG (CVE, CWE, CAPEC, ATT&CK). It is evaluated "by means of three real-world cybersecurity use cases", which is a demonstration, not a quantitative evaluation.\[26\]\[27\] The earlier audit's concession of the architecture stands.

"Ozsoy (2026)" is mis-cited in your brief. The subagent found no security or federation paper by Ozsoy. The nearest is "Toward Multi-Database Query Reasoning for Text2Cypher" (Ozsoy, Neo4j, 2605.10373; preprint) [READ by subagent]. It is "a research roadmap rather than a fully implemented system", with three phases:
- database routing;
- multi-database decomposition across Neo4j graphs;
- heterogeneous reasoning over SQL, GQL and Cypher.\[28\]

It ran only 7 hand-made questions on Gemini-3.1-Flash-Lite (3/3, 1/3 and 0/3 across the phases) and states "Benchmarks for multi-database Text2Cypher does not exist."\[28\] It uses no Gremlin and no shared-identifier joins.

FedV-KGQA (Bappy and Seneviratne, RPI, 2608.24846; preprint) [READ by subagent] is not an LLM agent and uses no database engines. Relation-partitioned silos share embeddings, with an assumed "consistently aligned entity identifier space", and it reports no latency (**T**).\[29\] Agentic SPARQL (2603.06582; preprint) [ABSTRACT by subagent] evaluates MCP-connected agents over a federated KGQA benchmark, but all endpoints are SPARQL.\[30\]

For hub latency, "Graph Memory for LLM Agents: At What Cost?" (2609.23315; preprint) [SNIPPET] reports mean latency on a 1.02M-node graph, for example Neo4j at 6.92 ms.\[31\] It gives no breakdown by degree and benchmarks databases, not QA. Search-on-Graph (2510.08825) [SNIPPET] caps high-degree expansions at 1,000 but reports no hub latency.\[32\]

**Defensible sentence.** "We give the first quantitative evaluation of a single agent answering across independently administered property-graph stores on different engines (Neo4j/Cypher and TinkerPop/Gremlin), unmerged and joined on shared identifiers. We also report end-to-end latency stratified by anchor-node degree on multi-million-node graphs."

**Experiment.**
1. Host ATT&CK and CAPEC in Neo4j, CWE plus an LLM-extracted graph in a TinkerPop store, and a synthetic or Wikidata-derived multi-million-node graph with natural hubs.
2. Build cross-source questions that require identifier joins.
3. Compare against two baselines on accuracy and degree-bucketed p50/p95 latency:
   - (a) a merged single-store baseline;
   - (b) a DAB-style free-query agent.

## Prior-art descriptions in the brief: accuracy check

| Item | As described in brief | Finding |
|---|---|---|
| SAGA 2607.14494 | Schema-aware grounding, agentic text-to-SPARQL | Accurate [ABSTRACT]; training-free (P); Wikidata and Freebase\[20\] |
| CypherBench | Text-to-Cypher on unseen graphs | Accurate; "unseen" means held-out test graphs; gpt-4o 60.18% [SNIPPET]\[9\] |
| CYGNET 2606.04645 | Text-to-Cypher on unseen graphs | **Imprecise**: it is a pre-execution validation and correction gate evaluated on 7 CypherBench schemas; its generation-accuracy deltas are -0.01 to +1.35 pp [SNIPPET]\[33\] |
| CypherTurn 2609.36987 | Autonomy divergence | Accurate [ABSTRACT]: 721 sessions, best 64.7% EX, frontier models "self-limit to approximately two actions per turn"\[34\] |
| Wikidata Search Traces 2610.06650 | Harness keeps results out of context; 48M entities | Mechanism accurate [ABSTRACT]; 48M figure **unverified** |
| Canedo 2609.10237 | Answer path vs subgraph size | Accurate [ABSTRACT]; grounding instruction with empty context drops F1 0.299→0.035; it is not about truncation\[35\] |
| Jeffries 2610.32110 | Truncation labelling in tool output | Accurate [ABSTRACT]; non-archival workshop poster |
| KG-Guard 2606.00328 | Under-enumeration | **Likely mis-filed**: the abstract frames it as graph-based *hallucinated-answer-node detection* (T), not under-enumeration [SNIPPET]\[36\] |
| CES-PK 2608.24824 | Constrained entity selection | Accurate [ABSTRACT]; Hetionet; three-valued semantics\[22\] |
| AgCyRAG | Federated security KG agent | Partly accurate: Cypher plus SPARQL agents, demonstration only [SNIPPET]\[26\] |
| Ozsoy (2026) | Federated security KG agent | **Wrong**: nearest match is the 2605.10373 multi-database Text2Cypher roadmap, not security |
| Middleware, QueryAgent, GRASP, BYOKG-RAG, MoNaCo, QO-Bench, CLEAR-KGQA, ULTRA, KG-ICL, ZESHEL/BLINK | Various | **Not re-read this round** because of budget; do not rely on their row descriptions until read |

## Search log

About 18 web searches plus one subagent pass, grouped by claim and vocabulary (KGQA / SQL and databases / agents and tool use).

- **C-A:**
  - KGQA: "knowledge graph question answering list questions incomplete answers enumeration recall LLM agent truncated".
  - SQL/DB: "text-to-SQL agent truncated results LIMIT incomplete answer completeness".
  - Agents: fetched Jeffries, Wikidata Search Traces and Canedo directly.
  - Killing evidence for graphs: none found.
- **C-B:**
  - KGQA/graph: "text-to-Gremlin LLM benchmark accuracy"; "text-to-GQL graph query language LLM dataset 2025"; "Text2Gremlin dataset graph database natural language"; "LLM Gremlin traversal generation execution accuracy 2026"; "CypherBench … gpt-4o unseen graphs".
  - DB/cloud: "Gremlin query generation large language model Neptune".
  - IR: "text2ql language-agnostic intermediate representation".
  - Chinese-ecosystem results surfaced (EICopilot/Baidu, R3-NL2GQL and MTGQL on nGQL, HugeGraph Text2Gremlin, TuGraph).
- **C-C:**
  - KGQA: "zero-shot entity linking unseen knowledge graphs trained across multiple KGs KGQA transfer".
  - Calibration: "entity linking calibration selective prediction abstain knowledge graph question answering".
  - LLM: "LLM entity linking 'none of the above' NIL candidate abstention knowledge graph".
- **C-D:**
  - SQL: "text-to-SQL query verification back-translation SQL-to-text intent check".
  - KGQA/agents: "KGQA verify grounded entity matches question wrong entity detection LLM agent".
- **C-E:**
  - DB/agents: "LLM agent multiple databases heterogeneous engines polystore question answering benchmark".
  - Security KG: "AgCyRAG federated cybersecurity knowledge graph agent ATT&CK CAPEC CWE"; "Ozsoy 2026 multi-agent knowledge graph cybersecurity Neo4j federated"; "Ozsoy federated security knowledge graphs agent arXiv 2026".
  - Subagent: Ozsoy identity, FedV-KGQA full text, hub-latency papers.

## Venues and competing groups

- **C-A:**
  - Venues: the "Who Verifies the Agents?" NeurIPS workshop (where Jeffries appeared), ISWC/ESWC research tracks, the VLDB/SIGMOD data-agent tracks.
  - Competition: Jeffries' audit prompt is general. The Wikidata Search Traces team (an RLM harness on a single GPU) is closest in spirit.
- **C-B:**
  - Venues: GRADES-NDA (SIGMOD workshop; Ozsoy published there in 2026), the PVLDB Experiment, Analysis & Benchmark track (where Text2GQL-Bench targets), ACL/EMNLP Findings.\[37\]
  - Competition: TuGraph/Ant Group (a multi-GQL framework already advertising Gremlin); text2ql ("full-set evaluation is planned").
- **C-C:** Venues: ACL/EMNLP/TACL, ISWC. No announced competitor found.
- **C-D:** Venues: PVLDB (where the verification paper appeared), ACL. Competition: the SAGA authors (type-state grounding) are one step from measuring binding verification.
- **C-E:**
  - Venues: RAGE-KG @ ISWC, GRADES-NDA, VLDB/CIDR.
  - Competition: **Ozsoy/Neo4j has announced multi-database routing, decomposition and heterogeneous query reasoning as future work**; Kurniawan et al. (AgCyRAG) are in the same security domain; the Berkeley DAB group targets heterogeneous data agents.\[28\]

## Recommendations

1. Reframe all five claims as measurements. The mechanisms (bounded views, typed IRs, NIL/none options, interpretation checks, multi-store agents) are taken.
2. Prioritise C-B and C-E. They have the clearest gaps and the most active competitors. A Neptune-hosted dual-language CypherBench subset serves both.
3. Include the strongest existing fix as a baseline in every experiment: truncation labels for C-A, a CYGNET corrector for C-B, round-trip critique for C-D.
4. Correct the bibliography rows for Ozsoy, KG-Guard and CYGNET before reuse, and read the ten unverified prior-art items past their abstracts.

## Caveats

- Most 2026 items were read at abstract level only. Figures tagged [ABSTRACT] or [SNIPPET] are leads, not measured evidence.
- EICopilot's Gremlin numbers rest on expert ratings with partial credit, and the paper has internal inconsistencies.
- Text2GQL-Bench's abstract and its table snippet disagree on zero-shot scores.
- Search budget limits mean that "not found" for C-A (graphs), C-C (calibrated cross-graph grounding and the "none" rate) and C-E (hub latency) is evidence of absence only within the queries logged above.

## Bibliography

- Jeffries, "Who Verifies the Tools?", arXiv 2610.32110. https://arxiv.org/abs/2610.32110 [ABSTRACT]
- Chenene et al., "Wikidata Search Traces", arXiv 2610.06650. https://arxiv.org/abs/2610.06650 [ABSTRACT]
- Canedo, "The Answer Path and the Grounding Instruction…", arXiv 2609.10237. https://arxiv.org/abs/2609.10237 [ABSTRACT]
- Yun et al., "EICopilot", arXiv 2501.13746. https://arxiv.org/abs/2501.13746 [READ]
- Lyu et al., "Text2GQL-Bench", arXiv 2602.11745. https://arxiv.org/html/2602.11745v1 [READ intro/Table 1; results SNIPPET]
- Kumar, "text2ql", arXiv 2609.02115. https://arxiv.org/abs/2609.02115v1 [ABSTRACT/SNIPPET]
- Feng et al., "CypherBench", ACL 2025. https://aclanthology.org/2025.acl-long.438/ [SNIPPET]
- "SPOT: Zero-Shot Semantic Parsing Over Property Graphs", Findings ACL 2025. https://aclanthology.org/2025.findings-acl.524.pdf [SNIPPET]
- Tomczak, "CYGNET", arXiv 2606.04645. https://arxiv.org/abs/2606.04645 [ABSTRACT]
- Zhang et al., "CypherTurn", arXiv 2609.36987. https://arxiv.org/abs/2609.36987 [ABSTRACT]
- Zhang & Tsuda, "SAGA", arXiv 2607.14494. https://arxiv.org/abs/2607.14494 [ABSTRACT; appendix SNIPPET]
- Kitzelmann, "CES-PK", arXiv 2608.24824. https://arxiv.org/abs/2608.24824 [ABSTRACT]
- "Developing and Benchmarking Verification Algorithms to Improve Text-to-SQL Generation", PVLDB 19. https://dl.acm.org/doi/10.14778/3836663.3836721 [ABSTRACT]
- "GBV-SQL", arXiv 2509.12612. https://arxiv.org/pdf/2509.12612 [SNIPPET]
- "SAFE: LLM-as-Verifier…", arXiv 2604.01993. https://arxiv.org/html/2604.01993v3 [SNIPPET]
- "KG-Guard", arXiv 2606.00328. https://arxiv.org/html/2606.00328 [SNIPPET]
- "KG-R1: Efficient and Transferable Agentic KG RAG via RL", arXiv 2509.26383. https://arxiv.org/pdf/2509.26383 [SNIPPET]
- Kamath, Jia & Liang, "Selective Question Answering under Domain Shift", ACL 2020. https://arxiv.org/pdf/2006.09462 [SNIPPET]
- "Semma", arXiv 2505.20422. https://arxiv.org/html/2505.20422v2 [SNIPPET]
- "BLINKout", arXiv 2302.07189. https://arxiv.org/pdf/2302.07189v2 [SNIPPET]
- "Entity Quality Enhancement in KGs…", GenAIK 2025. https://aclanthology.org/2025.genaik-1.14.pdf [SNIPPET]
- Ma et al., "Data Agent Benchmark (DAB)", arXiv 2603.20576. https://arxiv.org/abs/2603.20576 [ABSTRACT]
- Kurniawan et al., "AgCyRAG", CEUR Vol-4079. https://ceur-ws.org/Vol-4079/paper11.pdf [SNIPPET]
- Ozsoy, "Toward Multi-Database Query Reasoning for Text2Cypher", arXiv 2605.10373. https://arxiv.org/abs/2605.10373v1 [READ by subagent]
- Bappy & Seneviratne, "FedV-KGQA", arXiv 2608.24846. https://arxiv.org/html/2608.24846 [READ by subagent]
- Dobriy et al., "Agentic SPARQL", arXiv 2603.06582. https://arxiv.org/abs/2603.06582 [ABSTRACT by subagent]
- "Graph Memory for LLM Agents: At What Cost?", arXiv 2609.23315. https://arxiv.org/html/2609.23315v1 [SNIPPET]
- "Search-on-Graph", arXiv 2510.08825. https://arxiv.org/pdf/2510.08825 [SNIPPET]
- Metabase issue #82850. https://github.com/metabase/metabase/issues/82850 [SNIPPET]
- dbt Labs, "Semantic Layer vs. Text-to-SQL: 2026 Benchmark Update" (vendor). https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026 [SNIPPET]

## Sources

1. [MCP: \`execute\_sql\` silently truncates results at the row limit and reports \`status: completed\` · Issue #82850 · metabase/metabase · GitHub](https://github.com/metabase/metabase/issues/82850)
2. <https://arxiv.org/pdf/2501.13746>
3. [Text2GQL-Bench: A Text to Graph Query Language Benchmark \[Experiment, Analysis & Benchmark\]](https://arxiv.org/html/2602.11745v1)
4. [GitHub - ldbc/Text2GraphQuery-DataGen: Fine-Tuning Dataset Auto-Generation for Graph Query Languages. · GitHub](https://github.com/ldbc/Text2GraphQuery-DataGen)
5. [ABSTRACT](https://arxiv.org/html/2609.02115)
6. [\[2609.02115v1\] text2ql: Multi-Target Natural Language Querying via a Language-Agnostic Intermediate Representation](https://arxiv.org/abs/2609.02115v1)
7. [text2ql: Multi-Target Natural Language Querying via a Language-Agnostic Intermediate Representation](https://arxiv.org/pdf/2609.02115)
8. [CYPHERBENCH: Towards Precise Retrieval over Full- ...](https://aclanthology.org/2025.acl-long.438.pdf)
9. [CypherBench: Towards Precise Retrieval over Full-scale ...](https://arxiv.org/pdf/2412.18702)
10. [SPOT: Zero-Shot Semantic Parsing Over Property Graphs](https://aclanthology.org/2025.findings-acl.524.pdf)
11. [Semantic Layer vs. Text-to-SQL: 2026 Benchmark Update](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)
12. [Managed Graph Database](https://aws.amazon.com/neptune/faqs/)
13. [Efficient and Transferable Agentic Knowledge Graph RAG via Reinforcement Learning](https://arxiv.org/pdf/2509.26383)
14. [Semma: A Semantic Aware Knowledge Graph Foundation Model](https://arxiv.org/html/2505.20422v2)
15. [Selective Question Answering under Domain Shift](https://arxiv.org/pdf/2006.09462)
16. [SELECTIVE PREDICTION UNDER DOMAIN SHIFT FOR QUESTION ANSWERING A DISSERTATION](https://amitakamath.github.io/thesis.pdf)
17. [arxiv.org](https://arxiv.org/pdf/2302.07189v2)
18. [Entity Quality Enhancement in Knowledge Graphs through ...](https://aclanthology.org/2025.genaik-1.14.pdf)
19. [GBV-SQL: Guided Generation and SQL2Text Back-Translation Validation for Multi-Agent Text2SQL](https://arxiv.org/pdf/2509.12612)
20. [SAGA: Schema-Aware Grounding for Agentic Text-to-SPARQL Generation](https://arxiv.org/abs/2607.14494)
21. [SAGA: Schema-Aware Grounding for Agentic Text-to-SPARQL Generation](https://arxiv.org/html/2607.14494)
22. [Constrained Entity Selection under Partial Knowledge for LLM-Based Knowledge Graph QA](https://arxiv.org/abs/2608.24824)
23. [SAFE: An LLM-as-Verifier Framework for Evidence-Grounded Multi-Hop Reasoning](https://arxiv.org/html/2604.01993v3)
24. [CYGNET: Cypher Gate for Neural Execution Triage and Cost Containment](https://arxiv.org/abs/2606.04645)
25. [Paper page - Can AI Agents Answer Your Data Questions? A Benchmark for Data Agents](https://huggingface.co/papers/2603.20576)
26. [AgCyRAG: an Agentic Knowledge Graph based RAG ...](https://ceur-ws.org/Vol-4079/paper11.pdf)
27. [From Legacy Documentation to OSCAL: An MCP-Based Agent Pipeline for Threat-Informed Continuous Compliance in Critical Infrastructure](https://arxiv.org/html/2607.08288v1)
28. <https://arxiv.org/html/2605.10373v1>
29. <https://arxiv.org/html/2608.24846>
30. [Agentic SPARQL: Evaluating SPARQL-MCP-powered Intelligent Agents on the Federated KGQA Benchmark](https://arxiv.org/abs/2603.06582)
31. [Graph Memory for LLM Agents: At What Cost? A Comparative Evaluation of Query, Ingest, and Update Performance Across Graph Database Engines](https://arxiv.org/pdf/2609.23315)
32. [Search-on-Graph: Iterative Informed Navigation for Large Language Model Reasoning on Knowledge Graphs](https://arxiv.org/pdf/2510.08825)
33. [CYGNET: Cypher Gate for Neural Execution Triage and Cost Containment](https://arxiv.org/html/2606.04645)
34. [CypherTurn: A Multi-Turn Benchmark for Conversational Text-to-Cypher Evaluation and the Autonomy Divergence](https://arxiv.org/abs/2609.36987)
35. [The Answer Path and the Grounding Instruction in LLM Question Answering over Knowledge Graphs](https://arxiv.org/abs/2609.10237)
36. [KG-Guard: Graph-Based Hallucination Detection for Knowledge Base Question Answering](https://arxiv.org/html/2606.00328)
37. [Neo4j research - Neo4j Graph Intelligence Platform](https://neo4j.com/research/)
