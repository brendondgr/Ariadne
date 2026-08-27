# Novelty Audit — Cross-Language Graph Federation for Security Question Answering

**Audit date: 26 August 2026.** All findings below were produced by adversarial search — the goal was to refute each claim, not to support it.

**Evidence convention used throughout:**

- ✅ **READ** — the full text was retrieved and read.
- 📄 **ABSTRACT** — only the abstract or landing page was retrieved. Cannot be used as evidence about a results section.
- ⚠️ **SNIPPET** — known only from a search result. A lead, not a finding.
- **UNVERIFIED** — a specific field (venue, year, author list, number) could not be confirmed from a retrieved page.

---

## Executive summary — read this first

Three things break, and one of them is load-bearing.

**1. The stated basis of your novelty claim does not exist.** Section 2 of your brief says Sikos (2023) §7 *names* cross-KG federation for security and *cites nothing for it*, and that this absence is "the current basis of our novelty claim." The paper was retrieved and read in full. The word "federat" appears **exactly once in the entire article**, and the worked example attached to it is not federation at all — it is a single-store SPARQL query using `FROM NAMED` over three named graphs in one triplestore. The strings `SERVICE`, `endpoint` and `interlink` appear **zero times**. The paper has no future-work or open-problems section. Sikos does not name a gap; he makes a passing remark about a capability he treats as already available. **Stop citing Sikos §7 as establishing the gap.** A reviewer who opens that paper will find the citation does not support the sentence it is attached to, and that is exactly the failure mode this audit exists to prevent.

**2. Q8 is dead.** A peer-reviewed journal paper published **28 July 2026 — four weeks before this audit** — already covers the security of natural-language interfaces to graph databases: injection dataset, unsafe-operation rate, read-only enforcement via a validator agent, and schema-boundary access control. You cannot claim this territory.

**3. Q3's mechanism is scooped twice over.** Mechanical earliest-failing-stage attribution now exists in a peer-reviewed EACL 2026 paper and in a 2026 preprint that states the localisation rule almost verbatim. Your *finding* about where the loss sits survives; the *method* does not.

Against that, four claims come through in usable shape, and two of them look genuinely unoccupied.

### Verdict table

| # | Claim | Verdict | Closest published work | Delta in one sentence | Confidence in the check |
|---|---|---|---|---|---|
| **Q1** | Cross-*language* graph federation from natural language | **Narrowed but standing** | Ozsoy, *Toward Multi-Database Query Reasoning for Text2Cypher*, arXiv:2605.10373, 2026 — **preprint** (CEUR-formatted; volume UNVERIFIED) | Ozsoy proposes exactly this as a research roadmap and explicitly builds nothing, evidencing seven hand-written questions over Cypher-plus-SQL, never two graph languages. | Medium-high |
| **Q2** | Federated vs merged, compared on *answer accuracy* | **Clear** | *Open Biomedical Knowledge Graphs at Scale… Samyama*, arXiv:2603.15080, 2026 — **preprint** 📄 | It uses the word "federation" for what is actually materialisation into one tenant, all in one query language, and its accuracy table compares interfaces rather than architectures. | Medium |
| **Q3** | Stage-wise failure attribution locating the planning stage | **Partially scooped** (mechanism scooped; result standing) | Leung et al., *Classifying and Addressing the Diversity of Errors in RAG Systems*, **EACL 2026**, pp. 3185–3207 — **peer-reviewed** ✅ | They already walk pipeline stages in order and stop at the earliest error, but their pipeline has no planning stage and their distribution runs the opposite way — generation is the largest bucket, not the smallest. | Medium-high |
| **Q4** | Templates vs schema-derived construction, measured | **Narrowed but standing** | Ding, Hu, Xu, Qu, *Leveraging Frequent Query Substructures…*, **EMNLP-IJCNLP 2019** — **peer-reviewed** ✅ | They measure the coverage cost of templates and name the mechanism, but never measure abstention and never leave DBpedia, so the cross-schema reversal has no opportunity to appear. | Medium |
| **Q5** | Abstention that returns the executed query as its proof | **Partially scooped** | Sawhney, Yadav, Bhattacharya, Mausam, *Iterative Repair with Weak Verifiers…*, **Findings of ACL 2025** — **peer-reviewed** ✅ | Their task definition already outputs a valid logical form paired with "No Answer," but treats it as a parse to be scored, never as an artifact a reader is meant to check. | High |
| **Q6** | Developer-authored benchmark inflation, measured | **Narrowed but standing** | Xu, Agrawal, Zouhar, Freitag, Deutsch, *When LLMs Benchmark Themselves*, arXiv:2509.26600, 2026 — **preprint** ✅ | They measure test-set-authorship bias when a *language model* writes the questions; nobody measures it when a *human research team* writes them for its own system. | High |
| **Q7** | A graph-*query* benchmark over ATT&CK or CAPEC | **Narrowed but standing** | Simoni, Fontanta, Saracino, Mori, *TITAN*, arXiv:2510.14670, 2025 — **preprint, venue UNVERIFIED** ✅ | TITAN publishes 88,209 question–path pairs over an ATT&CK graph, but its targets are relation-chain strings walked by a Python library, not queries in any query language. | High |
| **Q7-bis** | No ATT&CK/CAPEC question set with human-*written* questions | **Clear** | AttackQA (SambaNova), OpenReview — **preprint** ✅ | Its `human_question` column means a human wrote the *generator script*; the calibration trap in your brief fired exactly as predicted. | High |
| **Q8** | Security of natural-language interfaces to graph databases | **Fully scooped** | Szlobodnyik, *Feedback-Guided Prompt Injection Defense in Retrieval-Augmented Text-to-Cypher Generation*, ***Analytics* (MDPI) 5(3):25, published 28 July 2026** — **peer-reviewed journal** ✅ | It already has the injection dataset, the unsafe-operation and attack-success metrics, the read-only validator and the schema-boundary access control — everything except a security-taxonomy schema. | High |
| **Q9** | Cross-source leakage in multi-source retrieval | **Narrowed but standing** | Arceo & Narsing, *Securing the Agent*, **ACM CAIS 2026** — **peer-reviewed** ✅ | They formalise and measure the relevance–authorisation gap, but their failure predicate is *unauthorised*, so an authorised record from the wrong source is at worst a precision loss and never a violation. | Medium-high |

**Score: one claim killed, two partially scooped, five narrowed but standing, one clear.**

---

## Part 1 — Corrections to your prior-art table

Every row in your §2 table was checked against a retrieved document. Four of the eight rows are described inaccurately, and two of the inaccuracies matter.

### AgCyRAG — closer than you thought on architecture, and two of your beliefs are wrong

✅ **READ in full** (CEUR-WS Vol-4079, paper 11, pp. 132–144).

**Corrected citation.** Kabul Kurniawan, Rayhan Firdaus Ardian, Elmar Kiesling, Andreas Ekelhart. "AgCyRAG: an Agentic Knowledge Graph based RAG Framework for Automated Security Analysis." *Second International Workshop on Retrieval-Augmented Generation Enabled by Knowledge Graphs (RAGE-KG 2025)*, co-located with ISWC 2025, Nara, Japan, 2–6 November 2025. CEUR-WS Vol-4079, pp. 132–144. Published 27 October 2025. **Non-archival workshop paper** (21 submitted, 15 accepted).

Note: **four** authors, and Ardian is **second**, not third. Your table lists three names in the wrong order.

**Your belief about evaluation is correct, and stronger than you stated.** There is no evaluation section, no metrics, no baselines, no dataset split, and no numbers of any kind. §4.2 is titled "Use Case Application" and contains three qualitative walkthroughs — one ATT&CK question, one log question, one combined — presented as coloured transcript boxes. The authors say so themselves in the conclusion:

> "For future work, we aim to conduct comprehensive evaluations of the framework using a variety of LLM models (including local and specialized models), datasets, and use cases…"

**Your belief about "predefined rather than generated queries" is half wrong, and this is the correction that matters.** SPARQL is predefined; Cypher is generated by a language model.

> "we implemented several predefined SPARQL queries in functions and exposed them via MCP" (§4.1)
>
> "the Cypher agent generates a Cypher query by means of an LLM to extract structured, security-relevant relationships from the log graph."

If you write "AgCyRAG uses predefined queries throughout," a reviewer who opens the paper will catch it.

**It is not a federation in the query-engine sense.** There is no materialisation — the two stores stay separate and SEPSES is queried live over its public endpoint — so that half of your description holds. But there is no `SERVICE` clause, no query decomposition, and no cross-store join. Integration happens in the agent orchestration layer: a guardrail agent routes, a reflection agent decides whether to fire the second store based on the first store's results, and a synthesis agent merges the outputs inside a prompt. The defensible description is **agent-level orchestration across heterogeneous stores**, not federation.

**Net effect on you.** The architectural sentence "first agentic system issuing both Cypher and SPARQL against heterogeneous, unmerged security graph stores" is **already occupied**, by a peer-reviewed workshop paper with public code (`github.com/sepses/multi-agents-cykg-rag`). What is not occupied is any of it being measured.

### Sikos (2023) §7 — the belief is wrong, and it is the one that hurts

✅ **READ in full** (open access).

**Corrected citation.** Leslie F. Sikos. "Cybersecurity knowledge graphs." *Knowledge and Information Systems* 65:3511–3531, 2023. Springer, open access, **single author**, peer-reviewed journal survey. Accepted 11 March 2023, published online 29 April 2023.

Section 7 is titled "Data aggregation and data fusion using cybersecurity knowledge graphs" (pp. 3524–3527). The paper has eight top-level sections and no subsections.

The entire textual basis for your claim is this one sentence:

> "By running federated queries on such a cyber-knowledge graph, entities having certain property values according to data derived from multiple data sources simultaneously can be found effectively."

Three problems:

1. **The accompanying example is not federation.** It is `SELECT ?cve FROM NAMED MITRE FROM NAMED CISCO FROM NAMED NIST WHERE {…}` — a single-store query over named graphs inside one triplestore. No remote endpoint, no distributed execution.
2. **The paragraph cites nothing.** True — but that is because it is an offhand remark, not because a gap is being flagged.
3. **It is framed as an existing capability, not an open problem.** The paper has **no** future-work, open-problems or research-challenges section. §8 is a nine-sentence backward-looking conclusion that cites nothing.

**What to do.** Delete this citation from your novelty argument entirely. It does not support the claim, and the mismatch is discoverable in about ninety seconds by anyone who downloads the paper. If you want a citation for "cross-language security KG federation is unaddressed," you will have to argue it from the *absence* pattern across the CTI systems literature (see the annotated bibliography), not from a survey's non-existent gap statement.

### FinAI Data Assistant — retrieved, and its results section is unusable

✅ **READ in full** (arXiv:2510.14162v2).

**Corrected citation.** Juhyeong Kim, Yejin Kim, Youngbin Lee, Hyunwoo Byun. "FinAI Data Assistant: LLM-based Financial Database Query Processing with the OpenAI Function Calling API." arXiv:2510.14162. LaTeX metadata declares CIKM 2025, Seoul. **Venue UNVERIFIED as to track** — search evidence points to an OpenReview group `ACM.org/CIKM/2025/Workshop/FinAI`, so this is most likely the CIKM 2025 **FinAI workshop**, not the main track. Do not cite it as a CIKM main-conference paper.

**The design thesis is confirmed as prior art.** §3.2: "we build separate base statements for market data and fundamental data. We then implement linking functions that execute these statements with validated parameters. Finally, an LLM determines which linking function to use and what parameter values to supply." So "route to vetted parameterised queries instead of generating them" is in print, ahead of you, in the SQL modality.

**But the library is never enumerated** — no count of functions, no schemas, no code. Only two base statements are inferable.

**And the load-bearing comparison has no numbers.** RQ3 compares function calling against text-to-SQL. There is **not a single number in the text or in any table** — everything lives inside a bitmap figure. The text-to-SQL baseline is never named (no model, no prompt, no system), its failure rate is never quantified, and the database is never specified. There is also no limitations section, despite the abstract promising one.

**Net effect on you.** They stake the idea; they do not defend it. Cite them for the design thesis, and note in one sentence that their comparison is not quantitatively recoverable. That is an honest observation, not a cheap shot — the numbers genuinely are not in the paper.

### LinkQ — a short paper with a demonstration, not an evaluation

✅ **READ in full** (arXiv:2406.06621 and the IEEE VIS programme page).

**Corrected citation.** Harry Li, Gabriel Appleby, Ashley Suh. "LinkQ: An LLM-Assisted Visual Interface for Knowledge Graph Question-Answering." **IEEE VIS 2024 — VIS Short Paper**, DOI 10.1109/VIS55277.2024.00031. Peer-reviewed short-paper track. Wikidata, SPARQL.

**The "faithfulness guarantee" is not a guarantee.** The mechanism is a prompt-driven tool-calling loop: the backend fuzzy-searches Wikidata for entity identifiers and feeds ground-truth identifiers into the system prompt before the model writes SPARQL. **There is no check that the emitted query actually uses the supplied identifiers** — that verification is delegated to the human, via an on-screen entity–relation table "intended to help users assess whether the LLM has identified the correct IDs." The model's prose summary is unverified. The paper's own conclusion softens the abstract's language to "a scalable protocol to *reduce the frequency* of LLMs hallucinating."

**There is essentially no empirical evaluation.** §5 is titled "DEMONSTRATION": five data scientists, six scripted questions, three use cases. No KGQA benchmark — no QALD, no LC-QuAD, no WebQSP. No accuracy, precision, recall or hallucination rate. The entire quantitative record is "participants observed two inaccuracies" and "in 2/3 cases our system successfully resulted in syntactically correct SPARQL queries and correct IDs." The authors write: "In the future, we would like to quantitatively evaluate the effectiveness of LinkQ…"

**Net effect on you.** LinkQ is the closest prior art to your verifier in *intent*, and it is a much weaker artifact than its reputation. Your claim-level verifier, if it actually checks that retrieved records ground each claim, is a stronger construct than LinkQ's — and, unlike LinkQ's, it can be measured.

### GCR / KG-Trie — ICML 2025 confirmed

✅ **READ** (PMLR proceedings page with BibTeX).

Linhao Luo, Zicheng Zhao, Gholamreza Haffari, **Yuan-Fang Li**, Chen Gong, Shirui Pan. "Graph-constrained Reasoning: Faithful Reasoning on Knowledge Graphs with Large Language Models." *Proceedings of the 42nd International Conference on Machine Learning (ICML 2025)*, PMLR vol. 267, pp. 41540–41565. Your suspicion is correct: **ICML, not ICLR**. Note that a widely circulated author list omits Yuan-Fang Li; the PMLR order is as above. (Results tables **UNVERIFIED** — proceedings page and abstract only.)

### Template-KBQA family and PICARD — all five confirmed

All verified from retrieved DBLP or ACL Anthology records. Bast & Haussmann, CIKM 2015, pp. 1431–1440. Zheng, Yu, Zou & Cheng, PVLDB 11(11), 2018, pp. 1373–1386. Abujabal, Yahya, Riedewald & Weikum, WWW 2017, pp. 1191–1200. Gu, Pahuja, Cheng & Su, AKBC 2022 (**no page numbers** — online proceedings; do not invent a range). Scholak, Schucher & Bahdanau, PICARD, EMNLP 2021 **main conference** (not Findings), pp. 9895–9901.

---

## Part 2 — The nine claims, adjudicated

### Q1. Cross-language federation — **narrowed but standing**

Two sub-claims are dead, and the core survives.

**Dead: "first to identify the problem."** Makbule Gulcin Ozsoy (Neo4j). *Toward Multi-Database Query Reasoning for Text2Cypher.* arXiv:2605.10373, May 2026 — **preprint**, CEUR-formatted, volume UNVERIFIED. ✅ READ. Its Phase 3 is verbatim "heterogeneous query reasoning… where multiple query languages, such as SQL, GQL, Cypher, coexist." It also says of the problem "to our knowledge, this problem remains largely unexplored," which is a citation you can use and a claim you can no longer make first.

But it builds nothing. It self-describes as "a position paper proposing a research roadmap rather than a fully implemented system," and its entire evidence base is seven hand-crafted questions over three Neo4j schemas plus one relational schema — Cypher paired with **SQL**, never two graph languages.

**Dead: "first natural-language-to-Gremlin."** Yun, Ye, Li, Li, Deng, Li & Xiong. *EICopilot.* arXiv:2501.13746, January 2025 — **preprint**. 📄 An LLM agent that generates and executes Gremlin from natural language, deployed in Baidu Enterprise Search, reporting 82.14% execution correctness. One store, one language, one domain — but it forecloses any "first" framing on Gremlin generation.

**Standing: the implemented, benchmarked, two-graph-languages, two-live-stores system.** Not found in a search of Google/Bing web search, arXiv, CEUR-WS, ACL Anthology and Semantic Scholar on 26 August 2026 using 22 logged query strings across three field vocabularies.

Two near-misses worth pre-empting, because a reviewer will raise them:

- **UniQGen** (Wang, Jedema, Pandey, Krishnan, Lehmann, Wu; arXiv:2605.00845, 2026 — preprint) ✅ renders both SPARQL and openCypher from one pipeline, and explicitly frames "graph-model lock-in." But both languages hit the **same** Neptune endpoint. That is dual *rendering*, not federation.
- **Agentic SPARQL** (Dobriy, Bauer, Azzam, Banerjee, Polleres; arXiv:2603.06582, 2026 — preprint) 📄 does genuine agentic federation over live endpoints with endpoint discovery and source selection. But its whole premise is that SPARQL is standardised and natively federates, so the cross-language problem never arises. This is the strongest scoop risk in the semantic-web community for the *agentic federated KGQA* half of your framing.

**Recommended wording:** *"the first implemented and benchmarked system that answers natural-language questions by dispatching native queries in two different graph query languages to two live, unmerged graph stores."* Cite Ozsoy, EICopilot, UniQGen and Agentic SPARQL explicitly, or a reviewer will do it for you.

**Confidence: medium-high.** Residual risk sits in CEUR/ISWC/ESWC workshop volumes, which general web search indexes poorly, and the arXiv full-text API returned empty bodies throughout, so no systematic `abs:Gremlin` sweep was possible.

### Q2. Federation versus merging, measured on answer accuracy — **clear**

Not found in a search of Google/Bing web search, arXiv (abstracts and HTML full text), CEUR-WS, ACL Anthology, ACM DL, Springer, ScienceDirect and PubMed Central on 26 August 2026, using eight targeted query strings, for any paper that builds both a federated and a merged version of the *same* knowledge-graph QA system and reports a head-to-head **answer-accuracy** comparison.

Two literatures were checked and both miss:

1. **Virtual versus materialised integration** in databases — mediator-wrapper, ontology-based data access, polystores, federated SPARQL engine benchmarks. Every comparison found is on **latency, cost, freshness or source-selection efficiency**. No correctness-of-answer axis.
2. **"Federated" in the model sense** — searches for federated-versus-centralised accuracy return **federated *learning***, a homonym. Worth a defensive sentence in your related-work section, because a skimming reviewer will conflate them.

**Two terminological collisions to pre-empt.** The Samyama preprint (arXiv:2603.15080, 2026, 📄 abstract only, **authors UNVERIFIED**) calls itself "cross-KG federation" while describing "loading all three snapshots into a single graph tenant" — i.e. it uses "federation" to mean *your merged condition*. Its 98% / 85% / 75% accuracy numbers on a 40-question biomedical set compare *interfaces* (tool calls vs text-to-Cypher vs bare model), not architectures.

**Confidence: medium.** This negative is genuinely hard to establish — the comparison could exist as an unnamed ablation table inside a paper whose title and abstract mention neither word. **Write "we are not aware of," never "no one has compared these."**

### Q3. Stage-wise failure attribution — **partially scooped; the mechanism is gone, the finding survives**

This is the claim that moved most during the audit, and it moved against you twice.

**Scoop 1 — the peer-reviewed one.** Leung, Belbahri, Sui, Labach, Zhang, Rose & Cresswell. *Classifying and Addressing the Diversity of Errors in Retrieval-Augmented Generation Systems.* **EACL 2026, Long Papers, pp. 3185–3207.** Peer-reviewed (venue confirmed from an ACL Anthology search result, not a fetched landing page — VENUE SNIPPET-CONFIRMED). ✅ READ in full. From their appendix:

> "we proceed sequentially over the stages of the RAG pipeline in order, starting with chunking. At each stage, an LLM is prompted with context to determine if an error occurred at this stage… **Once the earliest error is identified, the evaluation stops.**"

That is mechanical earliest-stage localisation with a stopping rule. They then report the resulting distribution over 832 and 1,222 erroneous responses, and validate the attribution by intervening on the weak stages and re-running.

**Their result runs the opposite way to yours**, which is the interesting part:

| Stage | DragonBall-EN | CLAPnq |
|---|---|---|
| Chunking | 29.7% | — |
| Retrieval | 31.5% | 21.7% |
| Reranking | 7.1% | 2.0% |
| Generation | **32.7%** | **76.4%** |

Generation — the faithfulness stage — is the plurality in one setting and the overwhelming majority in the other. Your claim that faithfulness failures are a small minority is therefore not merely unpublished; it **contradicts the only comparable published distribution.** That is a strength if you can explain it (their pipeline has no planning stage and no structured store; yours has both) and a liability if you cannot.

**Scoop 2 — the localisation rule, stated almost verbatim.** Two 2026 preprints own it independently:

- Shah. *Causal Agent Replay.* arXiv:2606.08275, June 2026 — **preprint, single author**. ✅ READ. "a **point-of-commitment rule: the causal locus is the latest step whose effect's confidence interval still excludes zero—the last point at which re-deciding still rescues the run**." That is literally "the last stage at which the correct answer was still recoverable." But it is a debugging tool validated on synthetic causal models with planted ground truth; no knowledge graph, no query generation, and **no empirical finding about where loss concentrates**.
- *Doctor-RAG: Failure-Aware Repair for Agentic Retrieval-Augmented Generation.* arXiv:2604.00865, 2026 — **preprint, venue UNVERIFIED**. ✅ READ (via the `/html/` route; the PDF has no machine-readable text). Equation 3 defines `k† = min{k | ρ(k) is classified as erroneous}` — "k† identifies the earliest action that is inconsistent with the admissible behavior of its error category… All actions preceding k† are treated as conditionally valid and form a reusable prefix." Its error taxonomy is coverage-gated and includes a *search* category (the closest published analogue to your planning stage). Its aggregate distribution exists only inside a figure image, so the numbers are **UNVERIFIED**.

  One narrow distinction survives: Doctor-RAG is **repair-oriented, not recoverability-oriented** — every localised failure is assumed repairable by local intervention, so it never asks whether the answer was still recoverable. That is a thin distinction and I would not build a contribution on it.

**One lead was checked and does *not* threaten you.** Ma et al., arXiv:2509.08682 (2025), ✅ READ, does agent-level Shapley attribution and "decisive error step" prediction in multi-agent systems — but reports attribution *accuracy* against ground-truth labels, never a breakdown of what fraction of failures originate where. No stage distribution, no recoverability criterion.

**One counter-example you must handle.** LogRouter (arXiv:2605.18015, 2026 — preprint, authors UNVERIFIED) ✅ reports routing accuracy alongside answer quality and states: "**The relationship between routing accuracy and answer quality is direct.**" If you claim the routing literature generally shows high routing accuracy with low answer accuracy, this is the citation a reviewer will reach for. The Routing Plateau paper (arXiv:2606.07587, 2026 — preprint) is a better fit for your argument, but note its gap is *router versus oracle router* (10–30 percentage points), which is model-selection quality, not a routing/answering discrepancy.

**Two statistics you may have seen: do not use them.** Prose circulating in search results attributes "planning… representing 33% of total errors" and "29% incorrect planning or decomposition / 47% reasoning over retrieved evidence / 10% retrieval failures" to a real paper. A dedicated tracing pass could not resolve either to a retrievable document. The second was attributed by a search engine to an ACM TKDD article (DOI 10.1145/3789506), but the ACM page returned an empty body and no preprint surfaced. **Not traced in a search of Google/Bing web search, arXiv and ACM DL on 26 August 2026** using five logged query strings. Treat both as probable search-engine synthesis.

**Surviving claim:** mechanical last-recoverable-stage localisation applied to a **knowledge-graph** pipeline with an explicit **planning** stage, yielding the finding that loss concentrates in planning and faithfulness failures are a minority. Every component is published separately; the conjunction, and specifically the *direction* of the result, is not.

### Q4. Templates versus schema-derived construction — **narrowed but standing**

**The coverage half is already published.** Ding, Hu, Xu & Qu. *Leveraging Frequent Query Substructures to Generate Formal Queries for Complex Question Answering.* **EMNLP-IJCNLP 2019**, peer-reviewed. ✅ READ including all result tables. Their template baseline (NLIWOD) scores 0.48 average F1 on LC-QuAD against 0.846 for their own method, and their diagnosis is explicit: "their accuracy and coverage are limited by the rules and templates," and template systems "cannot handle questions with unseen query structures, since they cannot generate new query structures."

**Three things they do not do, and all three are yours:**

1. **They never measure abstention.** No answer/refuse split, no precision-under-refusal. The word does not appear.
2. **They never leave DBpedia.** Both benchmarks sit on the same schema, so there is no cross-schema condition in which a template precision advantage *could* reverse.
3. **Their templates simply lose everywhere**, so the specific trade you report — precision plus reliable abstention, paid for in coverage, with the precision edge inverting off-schema — is not what they found.

The specific reversal result was **not found in a search of Google/Bing web search, the ACL Anthology, arXiv, CEUR-WS and openproceedings.org (EDBT) on 26 August 2026**, using seven exact query strings across the KGQA, database and security vocabularies (logged in Part 5). Roughly nine to ten results each; zero returned a head-to-head precision/coverage/abstention measurement across schemas.

**One adjacent paper that could be mistaken for a scoop:** Gao, Lau & Qi, *SG-KBQA*, **EMNLP 2025**, peer-reviewed. 📄 **Abstract only — cannot be used as evidence about its results.** From the abstract, its comparisons are against other neural KBQA models rather than hand-written templates, and its axis is compositional generalisation within Freebase-style benchmarks rather than cross-schema template transfer.

**Confidence: medium**, and the weakness is specific. The primary template-QA systems — QUINT, TeBaQA, QAnswer/WDAqua — were **not opened**. TeBaQA in particular claims portability "to a new domain… partially proven by evaluation over different KGs," and if that evaluation contains a precision-versus-coverage table across knowledge graphs, Q4 narrows further. **Open those four papers before you submit.**

### Q5. Abstention that carries its proof — **partially scooped**

**The scoop.** Sawhney, Yadav, Bhattacharya & Mausam. *Iterative Repair with Weak Verifiers for Few-shot Transfer in KBQA with Unanswerability.* **Findings of ACL 2025**, peer-reviewed. ✅ READ. Their task definition puts the query in the abstention output:

> "the model needs to output (a) a logical form l and a non-empty answer A for answerable q, (b) l = NK (No Knowledge) for schema-level unanswerable q, or (c) **a valid logical form l and A = NA (No Answer) for data-level unanswerable q**."

For data-level unanswerability that is exactly your artifact: the executable query, paired with the empty result.

**Three deltas survive, and together they are a real contribution:**

1. **They score it; you show it.** The query is a semantic-parsing output evaluated by exact match and F1. The paper contains no notion of a user; the word "justification" never appears; there is no auditability or provenance discussion anywhere. Their own verifier prompt treats an empty result as *an error to repair* — "Please generate again a different executable sparql" — which is the precise opposite of treating it as evidence.
2. **Their schema-level abstention returns nothing.** The `NK` label carries zero evidentiary content. If your system abstains with an executed query even when the failure is at the schema level, that case is unoccupied.
3. **The provenance connection is unmade.** A system combining database **why-not / empty-result provenance** with a natural-language abstention decision was **not found in a search of Google/Bing web search, arXiv, the ACL Anthology and DBLP-indexed VLDB/EDBT results on 26 August 2026**, using 17 logged query strings. The why-not literature (NedExplain, EDBT 2014; PUG, PVLDB 2018 — both ⚠️ SNIPPET, not opened) and the QA-abstention literature remain disjoint. **That intersection is your strongest ground here.**

**Frame the contribution as the evidentiary discipline, not the output tuple.** The tuple is in Findings 2025.

### Q6. Benchmark authorship bias — **narrowed but standing**

**The closest work measures the language-model analogue, not yours.** Xu, Agrawal, Zouhar, Freitag & Deutsch. *When LLMs Benchmark Themselves: Deconstructing Self-Bias in Automated Evaluation.* arXiv:2509.26600v2 — **preprint only; no venue, no DOI, no acceptance statement.** ✅ READ. They decompose self-bias into a test-set-authorship component and an evaluator component, and isolate each with a clean design (a non-model metric as neutral scorer isolates test-set bias; human-authored inputs isolate evaluator bias).

Measured, in mean per-segment rank difference (negative = self-favouring):

| Component | Gemini | GPT-4.1 | Claude Opus 4 |
|---|---|---|---|
| Test set alone | −0.124 | −0.239 | −0.093 |
| Evaluator alone | −0.302 | −0.443 | −0.303 |
| Both combined | −0.261 | −0.294 | −0.550 |

Two caveats worth knowing. Their claim that the components are additive is asserted but **not supported by their own table** — for two of three models the combined figure is *smaller* in magnitude than the evaluator component alone. And they never mention contamination, so they neither test nor rule it out as a confound.

**The delta is the author.** Their bias arises because a *model* wrote the inputs, and they attribute it to stylistic homogeneity. Yours arises because a *human research team* wrote the questions for its own system — a different agent, a different mechanism (design and framing choices, not stylistic fingerprint), and a different unit (score points, not rank units). Their paper treats human-authored evaluation sets only as a neutral control.

**Three things this is not, all well covered — do not claim any of them.** Judge self-preference (they measure it at two to three times the size of test-set bias). Training-data contamination (Retro-Holdouts, arXiv:2410.09247, ⚠️ SNIPPET, reports up to 16 percentage points). Selective submission and disclosure (*The Leaderboard Illusion*, **NeurIPS 2025 poster**, ⚠️ SNIPPET, reports up to roughly 100 arena points).

**Two papers name the risk and measure nothing.** PeerBench (arXiv:2510.07575, preprint, 📄) warns that "benchmark creators may collude with model creators." *Measuring what Matters: Construct Validity in LLM Benchmarks* (**NeurIPS 2025 Datasets & Benchmarks**, ⚠️ SNIPPET) reviews 445 benchmark papers and finds pervasive construct-validity weaknesses. Neither isolates developer authorship or attaches an effect size. **PeerBench is the paper that would have scooped you and did not.**

**The named analogue lives in another field.** *Industry sponsorship bias* in clinical meta-research (Catalogue of Bias, Oxford CEBM; ⚠️ SNIPPET) is the mature, quantified version of this effect — and nobody appears to have ported it to machine-learning benchmarking. Borrowing that frame explicitly would strengthen the paper.

**Not found** in a search of WebSearch (Google/Bing-backed), arXiv, the ACL Anthology, OpenReview and NeurIPS proceedings on 26 August 2026, using the queries in Part 5, for a named and quantified effect of benchmark inflation caused by the benchmark being authored by the developers of the system under test.

### Q7. A graph-query benchmark over ATT&CK or CAPEC — **narrowed but standing**

**Your belief as stated is too strong and will read as an omission.** Three artifacts sit in the gap you claim is empty.

**The nearest.** Simoni, Fontanta, Saracino & Mori. *TITAN: Graph-Executable Reasoning for Cyber Threat Intelligence.* arXiv:2510.14670, 2025 — **preprint, venue UNVERIFIED** (LNCS-formatted, ~6 pages). ✅ READ. It releases **88,209** natural-language-question ↔ typed-relation-path pairs over a MITRE ATT&CK STIX graph (2,350 nodes, 48,795 edges). Never write "no natural-language question resource over an ATT&CK graph exists."

But its targets are relation-chain strings such as `<PATH> uses_attack_pattern <SEP> mitigated_by_course_of_action </PATH>`, executed by a NetworkX walker. **No query language, no graph database, no execution accuracy** — only exact match on the path string plus text-similarity scores on the reasoning prose. No CAPEC. No human validation of any generated example. The split is a random 80/5/15 of one generated pool.

**Two others to cite.** CyKG-RAG (RAGE-KG @ ISWC 2024, CEUR Vol-3950) and AgCyRAG (Vol-4079) ✅ both generate Cypher and SPARQL over exactly these taxonomies — and ship **three anecdotal example questions between them, zero gold queries and zero metrics**. And CTIConnect (Cheng, Liu, Li, Song & Gao, **KDD 2026**, peer-reviewed, DOI 10.1145/3770855.3817527) ✅ is the strongest peer-reviewed CTI retrieval baseline — 1,860 expert-*verified* pairs over CVE/CWE/CAPEC/ATT&CK — but retrieves with dense vectors and BM25, with no query language and no gold queries. Reviewers will expect you to engage with it.

Meanwhile every real text-to-Cypher benchmark — CypherBench, SpCQL, MindTheQuery, SynthCypher, CyQuark — has **zero security-taxonomy content**, confirming the "Wikidata and enterprise graphs" half of your belief.

**D3FEND and ATLAS:** no question set of any kind, graph or flat, was located. Not found in a search of Google/Bing web search, arXiv, CEUR-WS, ACL Anthology, ACM DL and Hugging Face on 26 August 2026.

**Recommended wording:** *"No benchmark exists that pairs natural-language questions with executable gold queries in a standard graph query language, against a live graph store, scored by execution-based correctness, over MITRE ATT&CK, CAPEC, CVE, CWE, D3FEND or ATLAS."*

### Q7-bis. Human-written ATT&CK/CAPEC questions — **clear, and the trap fired**

Your calibration warning was exactly right, and it fired on the most-cited candidate.

**AttackQA's `human_question` column does not mean a human wrote the question.** ✅ READ. §3.3, "Manual Q&A Generation," verbatim:

> "Twenty percent of the Q&A pairs were generated by humans **using heuristics embedded in code**, relying solely on the relationships table for their creation."

That is a script iterating the ATT&CK relationships table. A further 50% are human-*templated* questions with model-written answers; the remaining 30% are fully Llama-3-8B-generated. **Zero individually human-authored questions.**

Every other candidate falls the same way:

| Dataset | Question origin | Human role | Graph queries? |
|---|---|---|---|
| AttackQA ✅ | 20% human-written *code* templates, 50% templated + LLM answers, 30% Llama-3 | scored a judge, not the questions | No |
| CTIBench ✅ | GPT-4o generated from source pages; only **40 of 2,500** manually collected | ~3,000 sampled for manual validation and correction | No |
| CTIConnect ✅ | template-constrained LLM synthesis from MITRE/NVD seed mappings | GPT-4 filter → two practitioners → adjudicator ("expert-**verified**") | No |
| TITAN ✅ | ~700 hand-written templates × entity expansion × LLM paraphrase | template authoring only; **no validation reported** | relation paths, not queries |
| Beyond RAG for CTI ✅ | LLM-generated from LLM-generated Cypher over LLM-extracted graphs | none — conceded in limitations | gold Cypher never released or scored |
| SecBench ✅ | human contest submissions + auto-extraction from exams/books | experts assign quality tiers; GPT-4 labels domains | No |
| ASU thesis ✅ | 30 genuinely author-written questions | author only | No — cosine similarity to prose |

**CTIBench's methodology is now verified**, not secondary: "We utilize GPT-4o to prepare the MCQs… We then randomly sample approximately 3000 questions for manual validation," followed by removal of unanswerable and multiply-correct items and correction of wrong annotations.

**SecBench is now closed too.** ✅ READ (arXiv:2412.20787, Jing et al., **preprint — no venue stated**). Its 34,272 contest questions *are* genuinely human-written, and language models are confined to labelling and grading. But its taxonomy is nine self-devised domains, and **MITRE, ATT&CK, CAPEC and CWE appear nowhere in the body, prompts or references.** There is no ATT&CK slice. It also skews heavily: 80.4% of its multiple-choice items are in Chinese, and 90.8% test knowledge retention.

**Verdict holds at clear.** The only genuinely hand-written ATT&CK-adjacent artifact found is a 30-question master's-thesis appendix with visible question-to-answer misalignment errors.

### Q8. Security of natural-language interfaces to graph databases — **fully scooped**

**Lead with this, because it is the paper that collapses a claim.**

Gergely Szlobodnyik. *Feedback-Guided Prompt Injection Defense in Retrieval-Augmented Text-to-Cypher Generation.* ***Analytics* (MDPI), 2026, 5(3), 25.** Peer-reviewed journal article. Received 18 May 2026, accepted 21 July, **published 28 July 2026 — four weeks before this audit.** DOI 10.3390/analytics5030025. ✅ READ in full.

It already contains, in one paper:

- a systematically constructed text-to-Cypher **prompt-injection dataset** across six categories (instruction override, role confusion, output-format manipulation, misleading prompts, chained instructions, obfuscation), from sixteen parameterised templates;
- an **Unsafe Operation Rate** and **Attack Success Rate** metric pair;
- a **validator agent** that intercepts destructive Cypher and recovers "a read-only, schema-consistent query";
- an identity-provider-driven **access-control layer limiting execution to the authorised portion of the graph schema** (both role-based and attribute-based);
- a jury-of-models classifier labelling outputs faithful, malicious or diverged;
- five foundation models and six training-free injection-defence baselines, plus a fine-tuned comparison.

That is your Q8, minus a security-taxonomy schema.

**What actually survives, and it is narrower than you will like:**

1. **Domain.** Szlobodnyik evaluates on the Neo4j text2cypher corpus with a movie-domain worked example; Hamzić et al. evaluate on report-derived CTI graphs. Nobody evaluates over a **security taxonomy schema**, where the data itself describes attacks and the schema boundary is a classification boundary.
2. **Language.** No adversarial probe suite exists for **Gremlin** generation that could be found.
3. **Enforcement level.** His defence is prompt-and-validator-level; it is never tested against **database-level privilege enforcement** or execution against a live store.
4. **Probe authorship.** His injection templates are model-authored, so an **analyst-authored** adversarial probe suite is still unclaimed — and note this dovetails with your Q6 argument about who writes the test set.

**Second required citation.** Hamzić, Skopik, Landauer, Wurzenberger & Rauber. *Beyond RAG for Cyber Threat Intelligence: A Systematic Evaluation of Graph-Based and Agentic Retrieval.* arXiv:2604.11419, April 2026 — **preprint** (ACM template placeholders unfilled). ✅ READ. Contributes read-only Cypher restriction as a *prompt* constraint, a **schema-evasion attack with 82.5% success rate**, a "structural hallucination" failure mode, an abstention/overconfidence table, and a **timing side channel** (failed queries 292.6s versus 45.0s, a 6.5× ratio). Note its "3,300 QA pairs" is 660 unique questions × 5 models.

Also worth one line each: **CVE-2024-7042**, a Cypher-injection vulnerability in LangChain's `GraphCypherQAChain` (⚠️ SNIPPET), as evidence the class is real in deployed software; and Neo4j's own production guidance on read-only users, timeouts and automatic `LIMIT` injection (⚠️ SNIPPET), which establishes that the mitigations currently circulate as folklore rather than measurement — an argument *for* a measurement paper.

### Q9. Cross-source leakage — **narrowed but standing**

The **authorisation** axis is now peer-reviewed and well covered. The **provenance** axis you describe is not.

**The closest work.** Francisco Javier Arceo & Varsha Prasad Narsing (Red Hat AI). *Securing the Agent: Vendor-Neutral, Multitenant Enterprise Retrieval and Tool Use.* **ACM Conference on AI and Agentic Systems (CAIS '26)**, San Jose, 26–29 May 2026. Peer-reviewed. DOI 10.1145/3786335.3813145. ✅ READ. They formalise the **relevance–authorisation gap** and measure cross-tenant leakage: 98–100% of probes leak without gating, 0% with attribute-based gating; 62–80% leakage on 90 injection probes ungated.

**But their failure predicate is strictly *unauthorised*** — wrong tenant, wrong access-control list — within a **single shared vector index** over a synthetic 300-document corpus. A record the user *is* authorised to see, which came from the wrong source, scores at worst as a precision loss and never as a violation. No multi-store fan-out, no graph retrieval, no released probe suite.

**Two adjacent papers ruled out by direct reading:**

- Mu & Li. *A Wolf in Sheep's Clothing: Targeted Routing Hijacking in Federated RAG.* arXiv:2605.28112, 2026 — preprint. ✅ Has the exact fan-out architecture you describe, but the wrong source is wrong because it is **malicious**, not honest-but-off-topic. No leakage metric at all.
- Burnat & Davidson. *Auditing Privacy in Multi-Tenant RAG under Account Collusion.* arXiv:2605.19847, May 2026 — preprint. ✅ Explicitly forbids the multi-store case: "each query is scored against only that account's tenant index," and cross-tenant regimes have "zero leakage by design." Its "each action legal, aggregate illegal" structure is the right *shape* on the wrong *axis* — accounts, not sources. Generation is out of scope, so "a record reaching the answer" is never modelled.

**The one gap in this negative is now closed.** FeB4RAG — Wang, Khramtsova, Zhuang & Zuccon, *"FeB4RAG: Evaluating Federated Search in the Context of Retrieval Augmented Generation,"* **SIGIR 2024, pp. 763–773** (venue metadata from the ACM listing, **UNVERIFIED by fetch**; arXiv full text ✅ READ) — was the single most plausible hiding place for a cross-source metric. It is not there. A full-text search for *contaminat*, *confidential*, *privacy*, *leakage*, *cross-source*, *provenance* and *attribution* returns **zero matches**. Its metrics are nDCG@k and nP@k over 790 requests and 16 engines: resource selection and result merging quality, nothing about confidentiality.

**Surviving claim:** no published work defines or measures a **cross-source contamination metric** for the case where one question fans out to several distinct stores, each sub-query is individually authorised for the store it hits, and the aggregate answer mixes provenance. The nearest metrics are all one-sided — Arceo & Narsing's are identity-based on a single index; CTIConnect's "cross-source semantic gap" and "semantic drift" measure wrong-*record* retrieval without ever treating the *source* as a variable; Mu & Li's measure whether a *malicious* source won a routing slot.

---

## Part 3 — Scoop watch, ranked by threat

| Rank | Threat | Work | Status | Hits | What to do |
|---|---|---|---|---|---|
| **1** | 🔴 Critical | Szlobodnyik, *Analytics* 5(3):25, **published 28 July 2026**, peer-reviewed journal | ✅ READ | Q8 | Q8's generic framing is dead. Rewrite as security-taxonomy-specific, or drop it to a paragraph. Must cite. |
| **2** | 🔴 Critical | **Sikos 2023 §7 does not say what you think** | ✅ READ | Whole novelty argument | Remove the citation. Rebuild the gap argument from the absence pattern across CTI systems. |
| **3** | 🔴 High | Leung et al., **EACL 2026**, peer-reviewed | ✅ READ | Q3 | Method scooped, and their distribution contradicts yours. Cite, and explain the difference by pipeline structure. |
| **4** | 🟠 High | Doctor-RAG, arXiv:2604.00865, 2026 preprint | ✅ READ | Q3 | Earliest-error localisation with a *search* error category. The closest published analogue to your planning stage. |
| **5** | 🟠 High | AgCyRAG, RAGE-KG @ ISWC 2025, workshop | ✅ READ | Q1, Q7 | Occupies the architecture. Correct your description of it (Cypher *is* generated; not query-engine federation) before a reviewer does. |
| **6** | 🟠 High | Ozsoy, arXiv:2605.10373, 2026 preprint | ✅ READ | Q1 | Owns the problem statement. Cite and position against; you own the implementation. |
| **7** | 🟠 High | Arceo & Narsing, **ACM CAIS 2026**, peer-reviewed | ✅ READ | Q9 | Owns the relevance–authorisation gap with hard numbers. Position yours as the orthogonal provenance axis. |
| **8** | 🟠 High | Shah, *Causal Agent Replay*, arXiv:2606.08275 | ✅ READ | Q3 | States your localisation rule almost verbatim, with a causal justification you must cite. |
| **9** | 🟡 Medium | Simoni et al., *TITAN*, arXiv:2510.14670 | ✅ READ | Q7 | Never say "no ATT&CK question resource exists." Scope to query language + live store + execution accuracy. |
| **10** | 🟡 Medium | Sawhney et al., **Findings of ACL 2025** | ✅ READ | Q5 | Owns the (query, no-answer) output tuple. Reframe around evidentiary discipline and the schema-level case. |
| **11** | 🟡 Medium | Xu et al., arXiv:2509.26600 | ✅ READ | Q6 | Measures the model-authored analogue. Cite, then distinguish the human-authorship mechanism. |
| **12** | 🟡 Medium | Cheng et al., **CTIConnect, KDD 2026**, peer-reviewed | ✅ READ | Q7, Q9 | Strongest peer-reviewed CTI retrieval baseline with a live leaderboard. Engage or be asked why not. |
| **13** | 🟡 Medium | Hamzić et al., arXiv:2604.11419 | ✅ READ | Q7, Q8 | Schema-evasion taxonomy, abstention table, latency side channel. Same institute cluster as CyKG-RAG. Watch for a venue. |
| **14** | 🟡 Medium | Dobriy et al., *Agentic SPARQL*, arXiv:2603.06582 | 📄 | Q1 | Owns agentic federated KGQA in the semantic-web community. Cross-language is what distinguishes you. |
| **15** | 🟡 Medium | **The Kurniawan/Kiesling/Ekelhart group itself** | ✅ READ ×2 | Q1, Q7, Q8 | They have said in *two consecutive papers* that comprehensive evaluation is future work. That is your benchmark, unbuilt, by an active group. **RAGE-KG 2026 is the venue to watch.** |
| 16 | 🟢 Low | Ding et al., EMNLP-IJCNLP 2019 | ✅ READ | Q4 | Owns the coverage half. Cite as the baseline your abstention and cross-schema results extend. |
| 17 | 🟢 Low | UniQGen (2605.00845); EICopilot (2501.13746) | ✅ / 📄 | Q1 | Foreclose "first dual-language rendering" and "first NL-to-Gremlin" respectively. Cite both. |
| 18 | 🟢 Low | LogRouter, arXiv:2605.18015 | ✅ READ | Q3 | A published counter-example to your routing sub-claim. Soften that sentence. |
| 19 | 🟢 Low | *The Leaderboard Illusion* (NeurIPS 2025); *Measuring what Matters* (NeurIPS 2025 D&B); PeerBench | ⚠️ / 📄 | Q6 | Adjacent framings a reviewer will name. Distinguish each in one sentence. |
| 20 | 🟢 Low | CyQuark, CypherBench, SpCQL, MindTheQuery, PIPE-Cypher, KG2Cypher | ✅ / ⚠️ | Q7 | Zero security content today, but a domain-transfer paper is cheap for them to write. |

---

## Part 4 — The surviving claim, and the attack on it

### The strongest honest novelty statement

> We present the first implemented and empirically evaluated system that answers natural-language questions by dispatching native queries in two different graph query languages — Cypher and Gremlin — to live, independently administered graph stores that are never merged into a common representation, joined at answer time through a declared key with identifier reconciliation across two identifier schemes. Because the system generates no queries with a language model, we can measure things that generation-based architectures cannot isolate: we localise the last pipeline stage at which the correct answer remained recoverable and find that loss concentrates in planning rather than in query construction or answer synthesis; we compare hand-written templates against schema-derived generic query construction across two schemas and find that the precision advantage of templates reverses on a schema for which no templates were written; we compare a federated against a materialised configuration of the same system and find no answer-accuracy advantage for either; and we quantify the score inflation contributed by a question set authored alongside the system that answers it. We contribute the first question set over MITRE ATT&CK and CAPEC that pairs natural-language questions with executable gold queries scored by execution-based correctness.

Note what has been removed: any claim to have identified the cross-language problem first (Ozsoy, 2026), any claim to first Gremlin generation (EICopilot, 2025), any claim about the security of natural-language graph interfaces (Szlobodnyik, *Analytics*, July 2026), and any appeal to Sikos as evidence of a gap.

### The sentence a hostile reviewer will use

> "The architecture is AgCyRAG with a different second query language and a benchmark attached; the cross-language framing was proposed by Ozsoy in 2026 and the individual mechanisms — templates instead of parsing, earliest-stage error attribution, abstention returning a logical form, read-only enforcement on generated graph queries — are each published elsewhere, so the contribution is an engineering integration whose headline empirical results are three null findings."

### Can you answer it?

**Partly — and the honest answer is that it depends entirely on the evaluation, not on the architecture.**

What you can say: AgCyRAG generates its Cypher, reports no numbers of any kind, and is not a federation in the query-engine sense; Ozsoy explicitly builds nothing and never pairs two graph languages; and a system that eliminates generation is a *different measurement instrument*, not merely a different implementation — it is what makes stage-wise attribution and the template/schema comparison possible at all, because there is no stochastic query-writing step to confound them.

What you cannot say: that the architecture is novel in kind. It is not. Nor can you claim the failure-attribution *method*, which Leung et al. published at EACL 2026 and Doctor-RAG states as an explicit minimisation rule.

**The strategic implication is uncomfortable but clear. Your architecture is your method section, not your contribution.** The contribution is the four measurements, of which three are nulls, plus the benchmark. Papers built on null results need unusually clean experimental design and unusually careful claims — and one of your nulls (planning-dominant loss with minority faithfulness failures) currently **contradicts** the only comparable published distribution. Explaining that contradiction structurally, rather than waving at it, is the single highest-value thing you can do before submission.

**One reframing worth considering.** The benchmark may be the stronger paper. It is the cleanest gap the audit found — no existing artifact pairs security-taxonomy questions with executable gold graph queries — and it is exactly the thing the most active competing group has twice declared to be future work.

---

## Part 5 — What to stop claiming

| Stop claiming | Because | Replace with |
|---|---|---|
| That Sikos (2023) §7 names cross-KG federation for security as an uncited gap | The word appears once, uncited, describing a `FROM NAMED` query as an existing capability; there is no future-work section | Argue the gap from the absence pattern across the CTI systems literature, and cite Ozsoy (2026) for the explicit problem statement |
| Anything about the security of natural-language graph-query interfaces as unaddressed | Szlobodnyik, *Analytics* 5(3):25, published 28 July 2026 — peer-reviewed, and it covers all four of your mechanisms | Narrow to security-taxonomy schemas, Gremlin, database-level enforcement, or analyst-authored probes — or cut it to a paragraph |
| That AgCyRAG uses predefined queries throughout | Its Cypher is model-generated; only SPARQL is predefined | "AgCyRAG predefines its SPARQL access and generates its Cypher" |
| That AgCyRAG is a federated system | No `SERVICE`, no decomposition, no cross-store join — integration is in the prompt | "agent-level orchestration across heterogeneous stores" |
| Priority on identifying cross-language graph federation | Ozsoy, arXiv:2605.10373, May 2026 | Priority on *implementing and measuring* it |
| First natural-language-to-Gremlin | EICopilot, arXiv:2501.13746, January 2025, deployed at Baidu | First to route to Gremlin *as one of two languages in a federated plan* |
| That no natural-language question resource exists over an ATT&CK graph | TITAN, 88,209 pairs, 2025 | No resource pairs questions with executable gold queries in a graph query language, scored by execution |
| That returning the query on abstention is unprecedented | Findings of ACL 2025 defines exactly that output for data-level unanswerability | The query as a *reader-checkable* artifact, plus the schema-level case, plus the why-not provenance connection |
| That mechanical stage-wise failure localisation is new | EACL 2026 and Doctor-RAG both do it | The *finding* — planning-dominant loss in a KG pipeline — not the mechanism |
| That routing work shows high routing accuracy with low answer accuracy, generally | LogRouter reports the relationship is direct | Cite the Routing Plateau's oracle gap instead, and state the caveat |
| That LinkQ offers a faithfulness *guarantee* | Nothing checks that the emitted query uses the supplied identifiers; verification is delegated to the user | "a design goal of reducing hallucination frequency, evaluated qualitatively" |

---

## Part 6 — Search log

All searches run **26 August 2026** via a Google/Bing-backed web search tool, with primary sources retrieved by direct fetch. "Rel." counts results judged worth opening.

### Prior-art verification (11 queries)

| # | Query string | Rel. |
|---|---|---|
| 1 | `AgCyRAG Kurniawan Kiesling Ekelhart agentic RAG cybersecurity knowledge graph` | ~3 |
| 2 | `RAGE-KG workshop ISWC 2025 CEUR proceedings retrieval augmented generation knowledge graphs` | ~5 |
| 3 | `"FinAI Data Assistant" LLM parameterized SQL queries routing paper` | ~3 |
| 4 | `LinkQ LLM knowledge graph question answering SPARQL faithfulness arXiv` | ~3 |
| 5 | `graph-constrained reasoning KG-Trie Luo faithful LLM reasoning knowledge graph ICML 2025` | ~6 |
| 6 | `"FinAI Data Assistant" CIKM 2025 ACM proceedings Kim Byun` | ~4 |
| 7 | `LinkQ "IEEE" visualization 2024 knowledge graph question answering VIS` | ~4 |
| 8 | `Sikos "Cybersecurity knowledge graphs" 2023 Knowledge and Information Systems survey federation SPARQL` | ~5 |
| 9 | `2026 agentic LLM cybersecurity knowledge graph question answering multiple graph stores Cypher SPARQL federation` | ~4 |
| 10 | `security knowledge graph QA agent 2026 evaluation benchmark property graph and RDF triple store heterogeneous query languages` | ~2 |
| 11 | `"AgCyRAG" cited 2026` | 1 |

### Q1–Q2 (22 queries)

| # | Query string | Rel. |
|---|---|---|
| 1 | `text-to-Gremlin natural language to Gremlin query generation LLM` | 2 |
| 2 | `federated question answering over multiple graph databases different query languages Cypher SPARQL without materialization` | 2 |
| 3 | `natural language interface polystore multi-model database LLM agent heterogeneous query languages` | 2 |
| 4 | `multi-agent LLM querying Neo4j and RDF triplestore simultaneously federated knowledge graph question answering property graph` | 0 |
| 5 | `cyber threat intelligence knowledge graph question answering ATT&CK CAPEC LLM federated multiple graph databases` | 5 |
| 6 | `Ozsoy "Multi-Database Query Reasoning for Text2Cypher" CEUR workshop 2026` | 2 |
| 7 | `federated versus materialized knowledge graph integration answer accuracy comparison question answering ablation` | 0 |
| 8 | `virtual integration versus materialized integration data quality accuracy comparison ontology-based data access warehouse` | 0 |
| 9 | `GraphRAG ablation single merged knowledge graph versus multiple separate graphs retrieval accuracy` | 0 |
| 10 | `"Cypher" "Gremlin" "SPARQL" cross query language translation layer natural language interface LLM agent tools` | 2 |
| 11 | `LLM agent routes questions to multiple graph database tools Neo4j Neptune TigerGraph different query languages federation system 2026` | 1 |
| 12 | `"federated" versus "merged" knowledge graph question answering accuracy no significant difference null result` | 0 |
| 13 | `entity resolution knowledge graph fusion impact on downstream question answering accuracy evaluation study` | 1 |
| 14 | `security knowledge graph SOC copilot federated query MITRE ATT&CK separate graph stores natural language 2026` | 1 |
| 15 | `"text-to-Gremlin" OR "NL2Gremlin" OR "Text2Gremlin" benchmark dataset evaluation` | **0 exact-phrase hits** |
| 16 | `mediator wrapper natural language question answering heterogeneous data sources query translation SQL SPARQL Cypher unified agent survey 2026` | 3 |
| 17 | `Apache TinkerPop Gremlin large language model query generation research paper JanusGraph natural language` | 0 academic |
| 18 | `Spider4SSC SPARQL SQL Cypher unified dataset one question three query languages` | 2 |
| 19 | `"data warehouse" versus "federated" query answer correctness quality empirical comparison integration accuracy VLDB` | 0 |
| 20 | `does merging knowledge graphs improve question answering accuracy compared to querying them separately study 2025 2026` | 0 |
| 21 | `federated KGQA baseline comparison centralized single endpoint accuracy drop federation overhead evaluation LLM` | 0 (all federated *learning*) |
| 22 | `CEUR-WS workshop 2026 LLM agent question answering across RDF triplestore and property graph both native query languages no materialization` | 2 |

### Q3–Q4 (20 queries)

| # | Query string | Rel. |
|---|---|---|
| 1 | `oracle ablation per-stage upper bound error attribution RAG pipeline stage recoverability` | 1 |
| 2 | `KGQA error analysis taxonomy failure modes planning retrieval answer generation LLM pipeline stage attribution` | 4 |
| 3 | `template-based KBQA versus schema-guided query generation cross-domain generalization precision coverage trade-off` | 3 |
| 4 | `arXiv 2025 agentic RAG error attribution which stage failed planning vs retrieval vs synthesis analysis` | 1 |
| 5 | `"routing accuracy" high but low end-to-end answer accuracy tool routing LLM benchmark gap` | 3 |
| 6 | `Spider text-to-SQL error analysis taxonomy schema linking vs generation errors oracle upper bound stage` | 2 |
| 7 | `Cresswell 2025 "Classifying and addressing the diversity of errors in retrieval-augmented generation systems"` | 3 |
| 8 | `template-based question answering abstention precision unanswerable vs LLM generative SPARQL Cypher comparison coverage` | 0 |
| 9 | `"error propagation" ablation gold intermediate injection KGQA stages entity linking relation linking query generation contribution` | 2 |
| 10 | `"Which Agent Causes Task Failures and When?" automated failure attribution LLM multi-agent decisive step ICML 2025` | 4 |
| 11 | `GraphRAG KGQA bottleneck is planning not query generation ablation gold plan oracle subgraph upper bound study` | 0 |
| 12 | `ontology-driven generic query construction versus handcrafted SPARQL templates evaluation new domain transfer ESWC ISWC` | 0 |
| 13 | `"schema-agnostic" query generation knowledge graph question answering generalize unseen schema template coverage limitation empirical` | 1 |
| 14 | `handcrafted templates outperform LLM in-domain but fail out-of-domain question answering knowledge base reversal precision experiment` | 0 |
| 15 | `MITRE ATT&CK question answering template queries versus LLM generated Cypher comparison abstention coverage security knowledge graph benchmark` | 0 |
| 16 | `query templates versus neural semantic parsing head-to-head evaluation coverage precision unseen domain KBQA study` | 1 |
| 17 | `"text-to-SQL" OR "NL2SQL" rule-based template baseline versus LLM generation comparison precision recall coverage industrial study 2025` | 1 |
| 18 | `TeBaQA QAnswer WDAqua template-based KGQA cross knowledge graph generalization evaluation QALD DBpedia Wikidata comparison` | 2 |
| 19 | `planning errors dominate LLM agent question answering "sub-question" decomposition oracle gold plan substitution recovers answer percentage` | 0 usable |
| 20 | `federated query processing natural language interface database "query templates" versus generic schema-driven construction coverage precision empirical comparison VLDB` | 0 |

### Q5–Q6 (17 queries)

| # | Query string | Rel. |
|---|---|---|
| 1 | `why-not provenance empty query result explanation database` | 7 |
| 2 | `abstention KGQA return executed SPARQL query as evidence of absence` | 4 |
| 3 | `selective prediction QA abstention verifiable justification executed query artifact` | 3 |
| 4 | `"benchmark authorship" bias developers of system under test inflated scores evaluation` | 2 |
| 5 | `TREC topic author assessor relevance judgment bias own topics system effect` | 3 |
| 6 | `quantifying evaluation bias benchmarks created by system authors versus independent benchmark score difference` | 3 |
| 7 | `"self-preference bias" LLM judge distinguish from benchmark design bias measured points` | 6 |
| 8 | `construct validity "researcher degrees of freedom" NLP benchmark authored by same team inflates reported results` | 3 |
| 9 | `natural language question answering empty answer explanation why-not provenance abstain no results exist` | 4 |
| 10 | `"home field advantage" OR "home team" bias AI benchmark created by model developers quantified inflation` | 2 |
| 11 | `"Leaderboard Illusion" arena benchmark bias private testing selective disclosure measured` | 4 |
| 12 | `sponsorship bias effect size analogy AI evaluation benchmark authored by proposing team measured inflation points` | 4 |
| 13 | `"self-designed" evaluation benchmark bias RAG agent paper own test set versus external benchmark drop` | 3 |
| 14 | `arXiv "When LLMs Benchmark Themselves" self-bias testset evaluator decomposition results points` | 2 |
| 15 | `proof of non-membership authenticated query verifiable empty result certificate completeness guarantee` | 3 |
| 16 | `text-to-SQL agent refuses to answer shows generated SQL empty result auditable "no rows" justification user` | 1 (no papers) |
| 17 | `co-designed benchmark and system evaluation inflation ablation external held-out question set authored by third party NLP` | 3 |

### Q7–Q9 (20 queries)

| # | Query string | Rel. |
|---|---|---|
| 1 | `text-to-Cypher benchmark MITRE ATT&CK knowledge graph question answering` | 5 |
| 2 | `AttackQA dataset MITRE ATT&CK question answering human-written` | 4 |
| 3 | `cybersecurity knowledge graph Cypher query benchmark CVE CWE CAPEC natural language to graph query evaluation 2026` | 3 |
| 4 | `CTIBench SecEval CyberBench SecQA benchmark question construction human expert written questions` | 6 |
| 5 | `SecBench cybersecurity benchmark question design contest human experts arxiv` | 3 |
| 6 | `Cypher injection LLM natural language graph database security read-only guardrail destructive query prevention` | **6** |
| 7 | `multi-tenant RAG tenant isolation cross-source leakage access control aware retrieval benchmark` | **6** |
| 8 | `"cross-corpus" OR "cross-source" leakage retrieval augmented generation multiple knowledge sources confidentiality evaluation` | 2 |
| 9 | `permission-aware KGQA access control knowledge graph question answering leakage "need to know" retrieval multiple stores` | 3 |
| 10 | `text-to-SQL prompt injection benchmark adversarial security LLM database agent unsafe query generation 2025 2026` | 4 |
| 11 | `security knowledge graph natural language query benchmark ATT&CK Neo4j text2cypher evaluation dataset gold Cypher queries` | 5 (all non-security) |
| 12 | `SPARQL question answering benchmark cybersecurity ontology D3FEND ATLAS UCO ISWC workshop` | 3 |
| 13 | `"Feedback-Guided Prompt Injection Defense in Retrieval-Augmented Text-to-Cypher Generation" authors Analytics MDPI` | 2 |
| 14 | `"ATT&CK" benchmark "Cypher" OR "SPARQL" question answering evaluation gold queries cyber threat intelligence knowledge graph 2026` | **6** |
| 15 | `CTIBench CTI-MCQ dataset construction how questions were generated LLM template MITRE ATT&CK CAPEC NeurIPS 2024` | 4 |
| 16 | `Gremlin injection SPARQL injection LLM generated query safety agent tool-use database sandboxing benchmark` | 3 (none graph-query) |
| 17 | `huggingface dataset MITRE ATT&CK cypher query pairs graph question answering security taxonomy` | 4 (surfaced TITAN) |
| 18 | `federated retrieval leakage multi-source RAG router wrong corpus retrieved confidentiality benchmark measure source attribution` | 4 |
| 19 | `AttackSeqBench question generation LLM-generated human validated MITRE ATT&CK benchmark construction` | 3 |
| 20 | `"written by" security analysts expert-authored questions benchmark MITRE ATT&CK SOC analyst queries dataset not LLM-generated` | 1 |

### Lead-closure pass (5 queries)

| # | Query string | Outcome |
|---|---|---|
| 1 | `FeB4RAG "test collection" federated search RAG SIGIR 2024 resource paper Wang Zhuang Zuccon` | Retrieved; no confidentiality metric |
| 2 | `"29% of errors" planning decomposition "47%" reasoning retrieved evidence "10%" retrieval failures RAG error analysis` | **Not traced** |
| 3 | `"33% of total errors" planning error analysis LLM agent QA` | **Not traced** |
| 4 | `"incorrect planning or decomposition" "sub-questions" error analysis multi-hop RAG structured planning TKDD` | ACM DL returned empty body |
| 5 | `"representing 33% of total errors" planning` | **Not traced** |

**Total: 95 distinct search queries across the KGQA/NLP, database/data-integration and security/SOC vocabularies.**

### Retrieval failures to disclose

- The **arXiv full-text API** returned empty bodies on every attempt, so no systematic field search (for example `abs:Gremlin`) was possible. This is the single largest coverage gap.
- **CEUR-WS volume pages were never enumerated directly.** Workshop proceedings are the weakest-covered venue class in this audit, and — as your own brief notes — that is exactly where the scoop risk lives.
- **ACM Digital Library** (`dl.acm.org/doi/10.1145/3789506`) returned an empty body, blocking verification of one untraced statistic.
- Several arXiv PDFs (Doctor-RAG 2604.00865, 2508.01815, 2607.00508) returned no machine-readable text. **Workaround: use `arxiv.org/html/<id>v1`.**
- ScienceDirect fetches returned empty or unparseable content.
- The sandbox shell has no network egress, so all retrieval went through the fetch tool.

---

## Part 7 — Annotated bibliography

Every entry carries a **how it differs from you** line. Evidence depth is tagged per entry.

### Closest architectural prior art

**1.** Kurniawan, K.; Ardian, R. F.; Kiesling, E.; Ekelhart, A. *AgCyRAG: an Agentic Knowledge Graph based RAG Framework for Automated Security Analysis.* RAGE-KG 2025 @ ISWC 2025, CEUR-WS Vol-4079, pp. 132–144. Workshop, non-archival. ✅
→ *Differs:* generates its Cypher with a language model while predefining only its SPARQL; integrates at the prompt level with no cross-store join; and reports zero metrics over three demonstration questions.

**2.** Kurniawan, K.; Kiesling, E.; Ekelhart, A. *CyKG-RAG.* RAGE-KG 2024 @ ISWC 2024, CEUR-WS Vol-3950 paper 1. Workshop. ✅
→ *Differs:* the predecessor system, three narrative walkthroughs, no question set, no gold queries, no metrics; authors state comprehensive evaluation is future work.

**3.** Ozsoy, M. G. *Toward Multi-Database Query Reasoning for Text2Cypher.* arXiv:2605.10373, 2026. Preprint; CEUR volume UNVERIFIED. ✅
→ *Differs:* a roadmap that builds nothing, evidenced by seven hand-crafted questions, whose worked multi-language example pairs Cypher with SQL rather than two graph languages.

**4.** Wang, M.; Jedema, N.; Pandey, R.; Krishnan, R.; Lehmann, J.; Wu, Y. *Graph Query Generation with Constraint-guided Large Language Agents* (UniQGen). arXiv:2605.00845, 2026. Preprint. ✅
→ *Differs:* renders SPARQL and openCypher for the **same** Neptune-hosted graph — dual rendering against one store, not dispatch across two.

**5.** Yun, Y.; Ye, H.; Li, X.; Li, R.; Deng, J.; Li, L.; Xiong, H. *EICopilot.* arXiv:2501.13746, 2025. Preprint. 📄
→ *Differs:* real natural-language-to-Gremlin, deployed, but one store, one language, one domain, with no routing or federation.

**6.** Dobriy, D.; Bauer, F.; Azzam, A.; Banerjee, D.; Polleres, A. *Agentic SPARQL.* arXiv:2603.06582, 2026. Preprint. 📄
→ *Differs:* genuine agentic federation, but built on SPARQL's standardisation — the cross-language problem is definitionally absent, and no materialised counterpart is constructed.

**7.** [Authors UNVERIFIED]. *Open Biomedical Knowledge Graphs at Scale… Samyama.* arXiv:2603.15080, 2026. Preprint. 📄
→ *Differs:* calls materialisation into one tenant "federation," uses one query language throughout, and its accuracy table compares interfaces rather than architectures.

**8.** Sikos, L. F. *Cybersecurity knowledge graphs.* Knowledge and Information Systems 65:3511–3531, 2023. Peer-reviewed survey. ✅
→ *Differs:* mentions federated queries once, uncited, illustrated by a single-store named-graph query, and has no open-problems section — it does not establish the gap it is cited for.

**9.** Thakkar, H. et al. [UNVERIFIED]. *Gremlinator / Killing Two Birds with One Stone.* arXiv:1801.09556; ICSC 2020. ⚠️
→ *Differs:* a pre-language-model SPARQL-to-Gremlin transpiler — a component you could have used, with no natural-language layer and no federation.

**10.** Sivasubramaniam et al. [UNVERIFIED]. *SM3-Text-to-Query.* arXiv:2411.05521, 2024. Venue UNVERIFIED. 📄
→ *Differs:* four query languages evaluated independently over four stores; no query ever spans two stores.

**11.** Vejvar, M.; Fujimoto, Y. *Spider4SSC & S2CLite.* arXiv:2511.09354, 2025. ⚠️
→ *Differs:* a matched-question dataset and a rule-based transpiler — static artifacts with no runtime, no live stores and no Gremlin.

**12.** Li, S.; Gupta, A. *Natural Language to What? A Vision for Intermediate Representations in NL-to-X Querying.* arXiv:2604.10776, 2026. Preprint. 📄
→ *Differs:* names heterogeneous compilation as open terrain and builds nothing; useful for motivation, harmless as prior art.

### Failure attribution and pipeline analysis

**13.** Leung, K. K.; Belbahri, M.; Sui, Y.; Labach, A.; Zhang, X.; Rose, S.; Cresswell, J. C. *Classifying and Addressing the Diversity of Errors in RAG Systems.* EACL 2026, pp. 3185–3207. Peer-reviewed. ✅
→ *Differs:* localises the earliest failing stage in a text pipeline with **no planning stage**, and finds generation dominant (32.7% and 76.4%) rather than a minority — the direct empirical counterweight to your headline.

**14.** *Doctor-RAG: Failure-Aware Repair for Agentic RAG.* arXiv:2604.00865, 2026. Preprint; venue UNVERIFIED. ✅
→ *Differs:* minimises over the earliest erroneous action for **repair**, reusing the valid prefix, and never asks whether the answer was still recoverable; its aggregate distribution is figure-only and unverified.

**15.** Shah, J. *Causal Agent Replay.* arXiv:2606.08275, 2026. Preprint, single author. ✅
→ *Differs:* owns the last-recoverable-step primitive with a causal justification, but validates on synthetic causal models and reports no finding about where loss concentrates in any real system.

**16.** Ma et al. *Automatic Failure Attribution and Critical Step Prediction via Causal Inference.* arXiv:2509.08682, 2025. Preprint. ✅
→ *Differs:* reports attribution *accuracy* against labels in multi-agent systems, never a distribution of failures across stages, and has no recoverability criterion.

**17.** Zhang, S. et al. *Which Agent Causes Task Failures and When?* ICML 2025 (Spotlight), PMLR v267. Peer-reviewed. ⚠️ (corroborated inside a retrieved paper)
→ *Differs:* shows that model-judge step attribution is unreliable (14.2% step-level accuracy) — an argument **for** mechanical localisation rather than a scoop of it.

**18.** Zhang, G. et al. *AgenTracer.* arXiv:2509.03312, 2025. Preprint. 📄
→ *Differs:* oracle-substitution replay for training a tracer model over agent trajectories, not stage-wise loss accounting in a knowledge-graph pipeline.

**19.** Agrawal, S.; Kumarage, T.; Alghamdi, Z.; Liu, H. *Mindful-RAG.* arXiv:2407.12216. Preprint; venue UNVERIFIED. ✅
→ *Differs:* the closest KGQA error taxonomy, but its categories are semantic and human/model-assigned, with no mechanical localisation and no stage percentages.

**20.** Garani. *A Systematic Taxonomy of Failure Modes in RAG Systems.* TrustNLP 2026 @ ACL, pp. 413–424. Peer-reviewed workshop. ✅
→ *Differs:* a literature review with zero new measurements that grades planning-failure evidence as *Limited* — a supporting citation for your gap, not a threat.

**21.** *The Routing Plateau.* arXiv:2606.07587, 2026. Preprint; authors UNVERIFIED. ✅
→ *Differs:* measures router-versus-oracle-router gap (10–30 points), which is model-selection quality, not a routing/answering discrepancy.

**22.** *LogRouter.* arXiv:2605.18015, 2026. Preprint; authors UNVERIFIED. ✅
→ *Differs:* **contradicts** your routing sub-claim — states the relationship between routing accuracy and answer quality is direct.

### Templates versus generic construction

**23.** Ding, J.; Hu, W.; Xu, Q.; Qu, Y. *Leveraging Frequent Query Substructures to Generate Formal Queries for Complex Question Answering.* EMNLP-IJCNLP 2019. Peer-reviewed. ✅
→ *Differs:* measures the coverage cost of templates and names the mechanism, but never measures abstention and never leaves DBpedia, so no cross-schema reversal can appear.

**24.** Gao, Y.; Lau, J. H.; Qi, [initial UNVERIFIED]. *SG-KBQA.* EMNLP 2025, pp. 8753–8772. Peer-reviewed. 📄
→ *Differs (from the abstract only):* compares against neural KBQA models rather than hand-written templates, on within-benchmark generalisation rather than cross-schema transfer.

**25.** Bast, H.; Haussmann, E. CIKM 2015 · Zheng, W. et al. PVLDB 11(11) 2018 · Abujabal, A. et al. WWW 2017 · Gu, Y. et al. AKBC 2022 · Scholak, T. et al. PICARD, EMNLP 2021. All peer-reviewed. ✅ (records verified)
→ *Differ:* establish that templates-instead-of-parsing and constrained generation are both a decade old and not yours to claim; PICARD in particular is the "constrain rather than eliminate" objection you must answer directly.

**26.** Luo, L.; Zhao, Z.; Haffari, G.; Li, Y.-F.; Gong, C.; Pan, S. *Graph-constrained Reasoning* (GCR / KG-Trie). ICML 2025, PMLR 267:41540–41565. Peer-reviewed. ✅ (results UNVERIFIED)
→ *Differs:* constrains decoding to encoded reasoning paths within one graph — the strongest form of the "constrain, don't eliminate" alternative, and the paper your architectural argument must beat on its merits.

### Abstention and verification

**27.** Sawhney, R.; Yadav, S.; Bhattacharya, I.; Mausam. *Iterative Repair with Weak Verifiers for Few-shot Transfer in KBQA with Unanswerability.* Findings of ACL 2025. Peer-reviewed. ✅
→ *Differs:* returns the logical form with "No Answer" as a *parse to be scored*, treats empty results as errors to repair, has no user and no provenance, and returns nothing at all for schema-level unanswerability.

**28.** Li, H.; Appleby, G.; Suh, A. *LinkQ.* IEEE VIS 2024 Short Paper. Peer-reviewed. ✅
→ *Differs:* never checks that the emitted query uses the supplied identifiers — verification is delegated to the user — and its evaluation is a five-person demonstration with no benchmark and no rates.

**29.** Deutch, D.; Frost, N.; Gilad, A. et al. *Explaining Natural Language Query Results.* The VLDB Journal 29(1), 2020. Peer-reviewed. 📄
→ *Differs:* natural-language provenance for tuples that **are** in the result; abstention and empty results are out of scope.

**30.** Kang; Fu; Zhao. *When Correct Edges Cannot Be Verified.* arXiv:2606.15833, 2026. Preprint; venue UNVERIFIED. 📄
→ *Differs:* abstains when textual support for a completed edge is missing — provenance-keyed abstention, but the artifact is a retrieved passage, not an executed query returned to the reader.

**31.** Lee; Ludwig; Glavic et al. *PUG*, PVLDB 11(12), 2018 · Bidoit et al. *NedExplain*, EDBT 2014. ⚠️
→ *Differ:* the canonical why-not literature — explains missing answers over structured queries with no natural-language layer and no abstention decision. **The field to connect to; nobody has.**

### Evaluation methodology

**32.** Xu, W.; Agrawal, S.; Zouhar, V.; Freitag, M.; Deutsch, D. *When LLMs Benchmark Themselves.* arXiv:2509.26600v2, 2026. **Preprint only.** ✅
→ *Differs:* measures test-set-authorship bias in rank units for a **model** author, attributed to stylistic homogeneity; never addresses a human team authoring an evaluation for its own system, and never controls for contamination.

**33.** Singh; Fraser; Hooker et al. *The Leaderboard Illusion.* NeurIPS 2025 poster. Peer-reviewed. ⚠️
→ *Differs:* selective submission and disclosure on a third-party arena — reporting bias, with a neutral benchmark author.

**34.** *Measuring what Matters: Construct Validity in LLM Benchmarks.* NeurIPS 2025 Datasets & Benchmarks. Peer-reviewed. ⚠️
→ *Differs:* diagnoses the disease class across 445 papers without isolating developer authorship or attaching an effect size.

**35.** *Position: Benchmarking is Broken — Don't Let AI be its Own Judge* (PeerBench). arXiv:2510.07575. Preprint. 📄
→ *Differs:* asserts benchmark-creator collusion as a systemic risk and measures nothing. **The paper that would have scooped you and did not.**

**36.** *Benchmark Inflation: Revealing LLM Performance Gaps Using Retro-Holdouts.* arXiv:2410.09247. Acceptance UNVERIFIED. ⚠️
→ *Differs:* measures contamination inflation (up to 16 points) — the effect you explicitly exclude — but supplies the methodological template for a same-system, different-author design.

**37.** Koo et al. *CoBBLEr*, Findings of ACL 2024 · Wataoka et al. arXiv:2410.21819. ⚠️
→ *Differ:* judge-side egocentric bias — the grader favours its own text. Your effect is upstream, in who wrote the questions.

**38.** *Industry Sponsorship Bias*, Catalogue of Bias (Oxford CEBM); GRADE Notes 3, J. Clin. Epidemiol. 2023. ⚠️
→ *Differ:* the mature, named, meta-analytically quantified version of your effect — in clinical trials. Nobody has ported it to machine-learning benchmarking. **Borrow the frame.**

### Security benchmarks and question sets

**39.** Simoni, M.; Fontanta, A.; Saracino, A.; Mori, P. *TITAN.* arXiv:2510.14670, 2025. Preprint; venue UNVERIFIED. ✅
→ *Differs:* 88,209 pairs over an ATT&CK graph whose targets are relation-path strings walked by a Python library — no query language, no database, no execution accuracy, no CAPEC, no validation.

**40.** Sharma et al. (SambaNova). *AttackQA.* OpenReview PRJ4n3CBzU. Preprint. ✅
→ *Differs:* flat text-with-retrieval, and its `human_question` flag means a human wrote the **generator heuristic in code**. The canonical instance of your calibration trap.

**41.** Cheng; Liu; Li; Song; Gao. *CTIConnect.* KDD 2026. Peer-reviewed. DOI 10.1145/3770855.3817527. ✅
→ *Differs:* dense-vector and BM25 retrieval with no query language and no gold queries; questions are template-constrained model syntheses that experts *verified* rather than wrote.

**42.** Feng et al. *CTIBench.* NeurIPS 2024 Datasets & Benchmarks (venue UNVERIFIED by fetch). ✅ (methodology now verified)
→ *Differs:* 2,500 flat multiple-choice questions, GPT-4o-generated from source pages with ~3,000 sampled for human correction; only 40 items manually collected; no graph, no queries.

**43.** Jing; Tang; Shi; Zheng; Nie; Wu; Yang; Luo. *SecBench.* arXiv:2412.20787, 2024. **Preprint — no venue stated.** ✅
→ *Differs:* genuinely human-written contest questions, but organised into nine self-devised domains with **no MITRE, ATT&CK, CAPEC or CWE grounding anywhere**, 80.4% Chinese, 90.8% knowledge-retention.

**44.** Hamzić, D.; Skopik, F.; Landauer, M.; Wurzenberger, M.; Rauber, A. *Beyond RAG for Cyber Threat Intelligence.* arXiv:2604.11419, 2026. Preprint. ✅
→ *Differs:* narrative CTI reports with no taxonomy grounding; questions, gold answers and judge are all models; gold Cypher exists at generation time but is never released or scored.

**45.** Sanchez, D. *Augmenting the Unified Cybersecurity Knowledge Graph…* MS thesis, Angelo State University, 2025. Not peer-reviewed. ✅
→ *Differs:* 30 genuinely hand-written questions, but gold answers are prose scored by cosine similarity, released only as a PDF appendix with visible question-to-answer misalignments.

**46.** Cazzaro; Lennon; Quattoni. *CyQuark.* arXiv:2606.14325, 2026. Preprint. ✅
→ *Differs:* zero security content; releases a generator rather than a benchmark; its own 100-sample human audit finds only **65% correct** — the methodological yardstick your generation pipeline must beat.

**47.** CypherBench (2412.18702) · SpCQL · SynthCypher (2412.12612) · MindTheQuery (EMNLP 2025) · PIPE-Cypher (2606.08481) · KG2Cypher (2606.27742). ⚠️
→ *Differ:* real gold Cypher with execution accuracy over Wikidata, film, sport, finance and enterprise schemas — **no security taxonomy in any of them.**

### Graph-query interface security

**48.** Szlobodnyik, G. *Feedback-Guided Prompt Injection Defense in Retrieval-Augmented Text-to-Cypher Generation.* Analytics (MDPI) 5(3):25, published 28 July 2026. Peer-reviewed journal. ✅
→ *Differs:* it does not meaningfully differ — it **is** your Q8, minus a security-taxonomy schema, minus Gremlin, minus database-level privilege enforcement, and with model-authored rather than analyst-authored probes.

**49.** CVE-2024-7042 — Cypher injection in LangChain's `GraphCypherQAChain`. ⚠️
→ *Differs:* a software vulnerability record, not a research contribution — cite as evidence of real-world incidence.

**50.** Neo4j, *Production-proofing your Cypher MCP server* (vendor guidance, 2026). ⚠️
→ *Differs:* engineering folklore with no threat model and no measurement — which strengthens rather than weakens the case for a measurement paper.

**51.** SafeClawBench (2606.18356) · AgentSecBench (2605.26269) · AgentSpec (ICSE 2026) · IPIGuard (2508.15310) · ToolEmu · AgentDojo/CaMeL. ⚠️
→ *Differ:* generic agent tool-use and sandbox safety; none instruments a graph query language, a graph schema boundary, or destructive-traversal semantics.

### Multi-source and multi-tenant retrieval

**52.** Arceo, F. J.; Narsing, V. P. *Securing the Agent.* ACM CAIS 2026. Peer-reviewed. DOI 10.1145/3786335.3813145. ✅
→ *Differs:* single shared index, three synthetic tenants, 300 fabricated documents, and a failure predicate defined purely as an *unauthorised* chunk — an authorised wrong-source record is never a violation.

**53.** Mu, J.; Li, Q. *A Wolf in Sheep's Clothing.* arXiv:2605.28112, 2026. Preprint. ✅
→ *Differs:* the wrong source is wrong because it is **malicious**; framed as a profile-integrity rather than confidentiality failure, with no leakage metric.

**54.** Burnat, F.; Davidson, B. *Auditing Privacy in Multi-Tenant RAG under Account Collusion.* arXiv:2605.19847, 2026. Preprint. ✅
→ *Differs:* every query hits exactly one tenant index by construction; cross-tenant leakage is zero by design, and generation is explicitly out of scope.

**55.** Wang, S.; Khramtsova, E.; Zhuang, S.; Zuccon, G. *FeB4RAG.* SIGIR 2024, pp. 763–773 (metadata UNVERIFIED by fetch). Peer-reviewed. ✅
→ *Differs:* measures resource selection and merging with nDCG@k and nP@k; a full-text search for *contaminat*, *confidential*, *privacy*, *leakage*, *cross-source*, *provenance* and *attribution* returns **zero matches**. The Q9 negative is now closed.

**56.** PerKGQA (Amazon Science) · *Privacy-protected RAG for KGQA* (arXiv:2508.08785) · US Patent 11,062,700. ⚠️
→ *Differ:* per-user graph partitioning and entity anonymisation — access control as an architecture, never as a measured leakage rate, never in a multi-store fan-out.

---

## Part 8 — What is still open

Five things this audit could not close. All are cheap to close and worth closing before submission.

1. **CEUR-WS workshop volumes were never enumerated directly.** Your own brief identifies workshop papers as where the scoop risk lives, and general web search indexes them poorly. **Manually sweep the ESWC 2026 and ISWC 2026 workshop proceedings**, and watch RAGE-KG 2026 specifically — the group with the closest architecture has twice said evaluation is future work.
2. **The primary template-QA systems were not opened** — QUINT, TeBaQA, QAnswer/WDAqua. TeBaQA claims cross-knowledge-graph portability, and a buried precision-versus-coverage table there would narrow Q4 further.
3. **SG-KBQA (EMNLP 2025) is abstract-only.** Q4's adjudication cannot be final until its results section is read.
4. **The arXiv full-text API was unavailable throughout**, so no systematic field search for terms such as `Gremlin` in abstracts was possible. This is the main structural gap in the Q1 negative.
5. **Two circulating statistics remain untraced** and should not be used. See Q3.

---

*Prepared 26 August 2026. Ninety-five distinct search queries across three field vocabularies; forty-one documents retrieved and read in full; fifteen retrieved at abstract level; the remainder recorded as leads rather than findings.*
