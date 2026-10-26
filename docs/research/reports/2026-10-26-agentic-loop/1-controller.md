# Ariadne's Controller Loop: What the 2023–2026 Agent Literature Supports

The design that fits Ariadne best is a single controller that runs a capped loop of plan, execute, check and repair. The controller should emit only typed tool calls whose arguments are identifiers, relation names and handles taken from the source cards, never natural-language sub-questions. Deterministic code should prepare the candidate entities and plans before the model's first call, and every recovery hint should also come from the executor rather than from the model. The evidence also says plainly that a Claude-Code-style free ReAct loop on a 27–32B local model will lose accuracy to autonomy and cost tens of seconds per question unless it is tightly constrained.

## TL;DR

- **Action space.** The best head-to-head evidence comes from Middleware (Gu et al., EMNLP 2024; [READ]). Letting the model choose from a list of valid actions ("decoupled generation") beat free tool calls with error feedback for every model tested. The gain was largest for weak models: Mistral-7B rose from 9.6 to 18.3 F1 and GPT-3.5 from 25.3 to 34.3 F1. Systems that keep the executor deterministic and return typed, diagnostic feedback do well, and none of them needs the model to write query text: QueryAgent/ERASER, SAGA, R2-KG and Middleware.
- **Small controllers and autonomy.** Untuned 7–32B controllers are the weak link. Mistral-7B without fine-tuning scored 4.76 F1 on CWQ in Interactive-KBQA [READ]. Moving from guided to fully autonomous operation cost frontier models 14–31 execution-accuracy points on CypherTurn [READ]. Small models running Think-on-Graph sometimes did worse than plain chain-of-thought [READ]. The fix that works is to shrink what the model has to decide: deterministic candidate panels, schema-filtered choices, diagnostic error messages, step caps and repeated-call guards.
- **Recommendation and first experiment.** Build one controller with about eight typed tools, a budget of 6 LLM calls (hard ceiling 8), and a validator-gated stop that abstains with the executed queries. Expect roughly 5–40 s per question, against about 13 ms per question today. Before building the loop, test the cheaper hypothesis: fixing the interface alone (typed plan arguments instead of NL sub-questions) may recover much of the 0.38 gold-coverage loss without any loop.

## Key Findings

**Read-status legend.** [READ] means full text read in this pass or by the delegated sub-search; [ABSTRACT] means abstract only; [SNIPPET] means search excerpt or secondary summary only. [SNIPPET] and [ABSTRACT] figures are leads, not measurements. **Class legend.** P = plug-and-play with an off-the-shelf model; B = needs an automatic one-time build step per graph; T = needs training or fine-tuning.

### One-page comparison table

| Method (ID, venue) | Action space | Control pattern | Class | LLM calls / question | Best measured result and where | Read status |
|---|---|---|---|---|---|---|
| Think-on-Graph, ToG (2307.07697, ICLR 2024) | Choose relations and entities from candidate lists | Beam search; the LLM prunes at each depth | P (but needs depth/width tuning per KG) | 2ND+D+1 at most (22 for N=D=3); 10–15 on average\[1\] | Average calls [SNIPPET]. As a baseline in R2-KG with GPT-4o on WebQSP: coverage 58.8, Hit 89.1\[2\]\[3\] | Paper [SNIPPET]; R2-KG figures [READ] |
| ToG-2 (2407.10805, ICLR 2025) | Choose entities/relations plus text context | Iterative KG and text retrieval | P | Not checked | Claims "training-free, plug-and-play"\[4\] | [ABSTRACT] |
| StructGPT (EMNLP 2023) | Fixed sequence of interface calls | Fixed pipeline (no real loop) | P | Few | As a baseline: KBQA-Agent F1 8.4–8.6; BIRD EX 31.8 (GPT-4)\[5\] | Figures [READ] via Middleware |
| Middleware (2402.14672, EMNLP 2024) | Typed function calls over 7 KB / 12 DB tools; or a menu of valid actions\[6\] | ReAct + error feedback, or decoupled generation | P (hand-built tools) | Not reported | KBQA-Agent F1 59.3 (GPT-4, decoupled) vs Pangu 27.1; BIRD (content needed) 38.3 vs 13.8\[5\]\[7\] | [READ] |
| KG-Agent (2402.11163, ACL 2025) | Typed tool calls (extraction, semantic, logic) with memory\[8\] | Iterative tool selection\[9\] | T (instruction-tuned LLaMA2-7B)\[10\] | Not checked | Not verified | [ABSTRACT] |
| Interactive-KBQA (2402.15131, ACL 2024) | Free SPARQL plus 3 tools (SearchNodes, SearchGraphPatterns, ExecuteSPARQL)\[11\] | ReAct | P with 2 hand-annotated exemplars per question type and a trained type classifier; T for open models | Not reported (cost about $0.50/question on CWQ) | CWQ F1 49.07, KQA Pro 71.89 (GPT-4 Turbo); Mistral-7B untuned CWQ 4.76\[11\] | [READ] |
| Plan-on-Graph (2410.23875, NeurIPS 2024) | Relation and entity choices plus sub-objectives | Decompose, explore, reflect, self-correct\[12\] | P | Not verified | Not verified | [ABSTRACT] |
| Paths-over-Graph (2410.14211) | Path selection | Multi-stage path search | P | "Up to 40% fewer than ToG" on GrailQA\[13\] | Not verified | [SNIPPET] |
| Generate-on-Graph (2404.14741, EMNLP 2024) | Search the KG **or generate triples from memory** | Think–Search–Generate loop | P\[14\]\[15\] | Not checked | WebQSP Hits@1 84.4 (GPT-4)\[16\] | [SNIPPET] (secondary summary) |
| Graph-CoT (2404.07103, Findings ACL 2024) | Typed graph functions (RetrieveNode, NodeFeature, NeighbourCheck, NodeDegree) | ReAct | P | Not checked | GRBench "GPT4score" 36.29 vs 23.09 baseline (GPT-3.5)\[17\] | [SNIPPET] |
| KnowAgent (2024) | Actions constrained by an action knowledge base | ReAct with action paths | T (self-learning fine-tune) | Not checked | Not verified | Not read |
| EffiQA (COLING 2025) | LLM plans; a small plug-in model explores | Plan, explore, self-reflect | Unclear (plug-in model) | Says baselines exceeded 30 calls\[18\] | Not verified | [SNIPPET] |
| FiDeLiS | Path retrieval with deductive beam search | Beam search | Not verified | Not checked | Not checked | Not found in this pass |
| ReKnoS (ICLR 2025) | Choose "super-relations" | Iterative; constant calls per step | P | 2L*+1\[19\] | Not verified | [SNIPPET] |
| ODA (2404.07677, Findings ACL 2024) | Neighbour exploration, path discovery, answer | Observe, act, reflect with recursive observation | P | Not checked | "+12.87% over ToG on QALD10-en"\[20\] | [SNIPPET] (secondary) |
| QueryAgent / ERASER (2403.11886, ACL 2024) | Typed PyQL function calls that build SPARQL | ReAct + rule-triggered error diagnosis | P (1-shot; hand-written error guidelines) | 5.2–6.2 SPARQL executions/question; 16.6 s per question\[21\] | GrailQA F1 60.5 (GPT-3.5) / 66.8 (GPT-4); ERASER adds 16.8 F1\[21\] | [READ] |
| KBQA-o1 (2501.18922, ICML 2025) | Atomic query tools building a logical form | ReAct + Monte Carlo tree search (MCTS) with policy and reward models\[22\] | T | Many (tree search) | Llama-3.1-8B WebQSP Hits@1 68.3 (as cited elsewhere)\[23\] | [SNIPPET] |
| RoG (ICLR 2024) | Fine-tuned planner generates relation paths | Plan then retrieve | T | 1–2 | Not checked | Not read |
| R2-KG (2502.12767, IJCNLP-AACL Findings 2025) | GetRelation / ExploreKG calls plus Verification | Operator–Supervisor loop; abstains at step limit | P | Operator 5.94–8.63 + Supervisor 1.04–1.43\[2\] | Qwen2.5-32B Operator + GPT-4o Supervisor on WebQSP: coverage 81.5, F1 79.4, Hit 89.5\[2\] | [READ]\[3\] |
| SAGA (2607.14494, preprint 2026) | search / lookup / examples / execute (SPARQL) / stop, with schema-filtered candidates\[24\] | ReAct with persistent type state\[25\] | B (schema index) + P | About 5.5–7.7 actions | Best F1 on 9/9 settings (gpt-oss-120B); empty results on WWQ 75.5% → 27.0% vs SPINACH\[24\] | [READ] |
| MAC-SQL (2023) | Free SQL | Selector / decomposer / refiner team | P | Not checked | Not checked | Not read |
| CHESS (2405.16755, ICML 2025) | Free SQL plus retrieval tools | Pipeline of 4 agents with revision and unit tests | B (value index) + P | Many | "Tokens cut 5×, accuracy up about 2%" on large schemas\[26\] | [ABSTRACT] |
| ReFoRCE (2502.00675) | Free SQL with exploration queries | Parallel self-refinement, majority vote, column exploration | P/B (schema compression) | Many | Spider 2.0-Snow EX 31.26 and Spider 2.0-Lite 30.35 (o1-preview), vs Spider-Agent 23.58 / 23.03 with the same model (ReFoRCE Table 1) | [ABSTRACT]/[SNIPPET] |
| Spider-Agent (2411.07763, ICLR 2025) | Free SQL/Bash/Python | ReAct code agent\[27\] | P | Many | Spider 2.0 success rate 21.3% (o1-preview)\[27\]\[28\] | [SNIPPET] |
| CypherTurn (2609.36987, preprint 2026) | Free Cypher plus INSPECT_SCHEMA / SEARCH_VALUES / ASK_USER | ReAct with a session budget | Benchmark | About 2 actions per turn (frontier)\[29\] | Best guided EX 0.647; best agentic EX 0.432\[29\] | [READ] |

### Question 1: Action space

**What the LLM emits, by family.**
- **Free query text** (SPARQL, SQL or Cypher, usually alongside exploration tools): Interactive-KBQA, SPINACH, SAGA, Spider-Agent, ReFoRCE, CHESS, MAC-SQL, and CypherTurn's agent protocol.\[11\]\[24\]\[25\]\[27\]
- **Typed function calls over primitives that a deterministic executor compiles into a query:** QueryAgent (PyQL), Middleware's KB tools, KG-Agent, Graph-CoT, KBQA-o1, and KBQA-R1. Of these, only QueryAgent and Middleware are plug-and-play.
- **A choice from a list** (relation, entity or path): ToG, ToG-2, PoG, ReKnoS, R2-KG, and Middleware's decoupled mode.\[3\]
- **Logical forms built step by step:** QueryAgent and KBQA-o1 (S-expression or SPARQL assembled from function calls).
- **Generated "facts":** GoG lets the LLM generate missing triples from memory.\[14\]\[15\]\[16\] That conflicts directly with Ariadne's rule that answers must be cited.

**Head-to-head evidence on the same benchmark.**
- **Middleware** [READ] is the only clean comparison of two action spaces with the same tools and models. Free tool calls with error feedback were compared with decoupled generation, where the model first writes a thought and then picks from an enumerated menu of valid actions. Every model improved with the menu: GPT-4 from 55.1 to 59.3 F1, GPT-3.5 from 25.3 to 34.3, Mixtral from 18.7 to 26.9, and Mistral-7B from 9.6 to 18.3. The authors conclude that "weaker models tend to benefit more from decoupled generation" because "the output space is strictly constrained to a list of valid actions."\[5\] This is the strongest single piece of evidence for Ariadne's design, and it matches the 2B result in Ariadne's own logs.
- **QueryAgent vs AgentBench** [READ]. Both emit stepwise typed calls. AgentBench showed hallucinations on 35% of questions. Adding ERASER's environment-derived diagnostics lifted AgentBench by 8.0–10.5 F1, and QueryAgent itself lost 16.8 F1 on GrailQA without ERASER.\[21\] So the content of the feedback matters as much as the action format.
- **Middleware vs StructGPT** [READ]. A richer typed toolset beat a fixed tool sequence by a wide margin (KBQA-Agent F1 55–59 vs about 8.5).\[5\] This compares tool sets rather than formats.
- **No study compares typed primitive calls with free query text on the same model and benchmark.** For Ariadne the design decision is already fixed, and the indirect evidence (CypherBench at about 60% for free text-to-Cypher; Ariadne's 0/17 Gremlin drafts) supports it.

**Which designs keep the executor deterministic.** QueryAgent, Middleware, Graph-CoT, R2-KG, ToG/PoG/ReKnoS (the LLM only selects) and SAGA's lookup tool all keep execution deterministic. SAGA, Interactive-KBQA, CypherTurn's agent and all the text-to-SQL agents let the LLM write the final query.\[11\]\[24\]\[25\] A design caution: in ToG-style list choice the LLM still makes every relation and entity decision. The ACL 2025 student-workshop study [READ] found that this exploration, not the final reasoning, is what breaks small models. Llama-3-8B scored 0.620 EM on WebQSP with ToG against 0.660 with plain chain-of-thought, and jumped to 0.805 when given triples that GPT-4.1 had retrieved.\[30\]

### Question 2: Control pattern, cost and accuracy

**Patterns observed.**
- **ReAct** (reason, act, observe; Yao et al. 2022): Interactive-KBQA, Middleware, QueryAgent, Graph-CoT, SAGA, Spider-Agent, CypherTurn.\[11\]\[24\]\[25\]\[27\]
- **Beam or tree search**, which keeps several partial paths alive (beam) or explores them by simulation (MCTS): ToG (beam), KBQA-o1 (MCTS).\[22\]\[31\]
- **Plan, execute, reflect/replan:** PoG, ODA, EffiQA.\[12\]
- **Fixed pipeline with a revision loop:** CHESS, MAC-SQL, ReFoRCE (parallel candidates, majority vote, then exploration only on low-consensus cases).\[32\] ReFoRCE is the clearest published example of a cascade that enters the expensive loop only on failure [ABSTRACT].
- **Dual-agent with abstention:** R2-KG.\[3\]

**Measured costs.**
- **ToG** needs at most 2ND+D+1 LLM calls (22 for width and depth of 3) and averages 10–15 on four multi-hop datasets [SNIPPET].\[1\]\[30\] R2-KG reports ToG at a minimum of 4 and a maximum of 25 calls [READ].\[2\]\[3\]
- **R2-KG**: 5.94–8.63 Operator calls plus 1.04–1.43 Supervisor calls per question [READ].\[2\]\[3\]
- **QueryAgent** on GrailQA [READ]: 16.6 s, 5.2 SPARQL executions and $0.019 per question, against AgentBench's 40.0 s and 7.4 executions. The few-shot KB-BINDER baseline needed 3,297.7 SPARQL executions and 51.2 s.\[21\]
- **SAGA**: about 5.5–7.7 actions per question [READ].\[24\]
- **CypherTurn**: frontier models settle at about two actions per turn regardless of budget [READ].\[29\]
- **Interactive-KBQA**: about $0.50 per CWQ question with GPT-4 Turbo [READ].\[11\]

**Graphs used.** Nearly all KGQA agents are evaluated on Freebase (WebQSP, CWQ, GrailQA, GraphQ) or Wikidata (QALD, KQA Pro, WWQ).\[1\]\[11\]\[24\]\[25\] Graph-CoT uses ten text-attributed domain graphs.\[33\] CypherTurn uses seven synthetic property graphs in Neo4j,\[29\] CypherBench uses Wikidata-derived property graphs,\[29\] and BIRD/Spider 2.0 are relational. **No published agent was evaluated on Gremlin/TinkerPop or on a federated multi-store setup like Ariadne's.**

**What this means for Ariadne.** At "several seconds per call," a 6-call loop costs about 20–40 s per question. The current deterministic path costs about 13 ms (1.6 s for 120 questions). That gap of more than three orders of magnitude matches the "about 3,000×" cost the brief attributes to LLM-written queries. Moving the LLM from writing queries to driving the loop does not remove the latency cost; only fewer calls do. That is the main argument for front-loading deterministic work so that easy questions finish in 1–2 calls.

### Question 3: Deciding when to stop

**How agents decide they have enough.**
- Most let the model declare it is done (Interactive-KBQA's `Done`, SAGA's `stop`, CypherTurn's `SUBMIT_ANSWER`).\[11\]\[24\]\[25\]\[29\]
- ToG asks the LLM whether the current paths suffice, and when it hits the depth limit it **answers from the LLM's own knowledge**. R2-KG [READ] counts those cases as abstentions.\[2\]\[3\]\[34\]
- R2-KG gates answering on a Supervisor verdict and abstains at its iteration limit T, which its authors present as a "reliability knob": lower T gives higher precision and higher T gives more coverage.\[2\]\[3\]

**Measured failure rates.**
- **Answering from memory.** No paper reports this rate directly. The best proxy is ToG's coverage in R2-KG [READ]: on WebQSP, ToG fell back to parametric memory on up to 41.2% of questions with GPT-4o and 69.5% with Mistral-Small. On MetaQA 3-hop the fallback was about 75%.\[2\]\[3\] These are upper bounds that we derive from coverage, not figures the paper reports as rates. GTSQA [READ] confirms the fallback mechanism but does not count it.\[34\]
- **Stopping too early.** GTSQA's authors observed that PoG "often prematurely stops the exploration… over-confidently" (qualitative, not counted) [READ].\[34\] SAGA's failure analysis shows a stop one hop too early: it returned Australia's capital when asked for its population [READ].\[24\]
- **Looping.** R2-KG names "repeated helper function requests" and malformed calls repeated from step 3 to step 14 as leading causes of abstention, without counts [READ].\[2\]\[3\] A 2026 preprint found that small models greedily repeat a just-failed tool call verbatim on 19% of items after the failure, versus 0% before it [SNIPPET].\[35\] CypherTurn shows the reverse problem in frontier models: encouraging them to use more budget *lowered* execution accuracy for six of seven models, because the extra actions were "repeated retries and unfocused searches" [READ].\[29\]

**What this means for Ariadne.** Never let the model's own "done" be the stopping signal. Ariadne already has the right primitive in its validation step. Stopping should require that (a) every claim maps to retrieved record identifiers and (b) the answer's node label matches the expected answer label in the plan. The second condition targets the "one hop short" failure.

### Question 4: Recovering

| Situation | What the literature does | Cost / evidence |
|---|---|---|
| Empty result | ERASER: rule-based diagnosis from KB results, interpreter errors and memory (e.g., "the chosen relation was never among the relations retrieved for this variable"), then a tailored hint\[21\] | 43% of GrailQA questions triggered ERASER; 30% of those were fully corrected; +16.8 F1 [READ]\[21\] |
| Empty result caused by type-incompatible relation | SAGA: filter candidate relations by domain/range before the model sees them\[24\]\[25\] | Empty results on WWQ 75.5% → 27.0% vs SPINACH [READ]\[24\] |
| Schema or format violation | Middleware: error message and retry; or a menu of valid actions only\[5\] | Menu beats retry for every model [READ]\[5\] |
| Wrong entity | Interactive-KBQA: model re-searches; SAGA: type state; R2-KG: Supervisor rolls back to an earlier hop\[2\] | Entity linking was 18% (WebQSP+CWQ) and 7% (KQA Pro) of Interactive-KBQA errors; SPINACH errors: 36.9% type-incompatible property, 33.3% wrong entity [READ]\[11\]\[24\] |
| Wrong path or branch | PoG reflection and backtracking; R2-KG rollback; KBQA-o1 MCTS | PoG/ODA not quantified [ABSTRACT/SNIPPET]; MCTS needs trained reward models (T) |
| Too many results | Middleware variables (sets kept server-side); ODA recursive top-P% pruning; SAGA compact annotated neighbourhoods\[20\] | Not measured as a separate rate |
| Asking the user | CypherTurn's ASK_USER; Interactive-KBQA's human-in-the-loop annotation\[29\] | No published measure of benefit for retrieval accuracy |

The common lesson is that **the executor should produce the diagnosis**. Intrinsic self-correction (the model critiquing itself with no outside signal) did not help: DIN-SQL's zero-shot self-correction prompt *lowered* QueryAgent's GrailQA F1 from 43.7 to 38.5 [READ].\[21\]

### Question 5: One agent or several

- **For KG/DB retrieval specifically**, the only controlled comparison found is R2-KG [READ]. Its dual-agent gains come from a *stronger* Supervisor (GPT-4o) paired with a weaker Operator. Its single-agent variant uses strict self-consistency: three runs must agree unanimously.\[2\] With Qwen2.5-32B and the multi-prompt variant, this reached Hit 93.6 on WebQSP but coverage of only 62.1, against 81.5 for the dual-agent version.\[3\] In other words, removing the stronger checker cost coverage, not precision.
- **In the general literature**, Tran & Kiela (Stanford; arXiv 2604.02460, a 2026 preprint) found that single agents "consistently match or outperform" five multi-agent designs on FRAMES and MuSiQue 4-hop when reasoning tokens are held constant, across Qwen3, DeepSeek-R1-Distill-Llama and Gemini 2.5 [ABSTRACT]. A 2025 empirical study found that multi-agent advantages shrink as base models improve [SNIPPET].\[36\] A medRxiv study found the opposite under batch-overload conditions: GPT-4.1-mini as a single agent fell from 96% to 33.9% while the orchestrated multi-agent version held 91.4–96% [SNIPPET].\[37\] That regime, many unrelated tasks in one context, is not Ariadne's.
- **Text-to-SQL teams** (CHESS, MAC-SQL) are fixed pipelines with specialised prompts, not autonomous teams.\[26\] Their gains come from schema selection and testing, not from dialogue between agents.

**What this means for Ariadne.** Ariadne already has the useful split: specialists are deterministic tools and the validator is a checker. Adding LLM "critic" or "planner" agents on the same local model would multiply calls and latency with no evidence of benefit for this task. If a second model is ever added, the R2-KG pattern (escalate to a stronger hosted model only for verification of hard cases) is the one with evidence behind it.

### Question 6: Small local controllers (7–32B)

**What breaks, with measurements.**
- **Format and grammar of tool calls.** Middleware found Llama2 models "struggle with even generating grammatical tool use"; Llama2-7B/13B scored 0.0–1.0 F1 [READ].\[5\] Interactive-KBQA's error analysis lists format-compliance errors as 17% of WebQSP+CWQ errors and 15% of KQA Pro errors, even with GPT-4 Turbo [READ].\[11\]
- **Exploration choices.** Untuned Mistral-7B scored 4.76 F1 on CWQ and 20.41 on KQA Pro with Interactive-KBQA, against 39.90 and 62.24 after fine-tuning [READ].\[11\] Under ToG, the 0.5B–8B models averaged 0.479 EM on WebQSP, below their chain-of-thought average of 0.511 [READ].\[30\]
- **Lost state over many turns.** On CypherTurn, Llama-3.1-8B fell from 0.291 guided to 0.137 agentic EX [READ]. QwQ-32B fell from 0.395 to 0.324 (on a 210-session subset). For collapsing models, the chain error rate rose above 0.83: once a turn failed, the next turn failed more than 83% of the time.\[29\]
- **Coverage loss rather than wrong answers when a checker exists.** With a GPT-4o Supervisor, Qwen2.5-32B and Qwen2.5-14B Operators kept F1 close to GPT-4o's but dropped WebQSP coverage to 81.5 and 76.4, against 85.3 for GPT-4o [READ].\[2\]\[3\]
- **Engine and template faults.** One 2026 preprint reports a 23% per-repeat engine-error rate for Qwen3.6-27B with reasoning mode on: the model planned a tool call inside its thinking block and then ended the turn without emitting it [SNIPPET].\[38\] A separate 2026 preprint reports that JSON-schema grammar masks for structured output can make tool-call tokens unreachable during decoding ("tool suppression") [SNIPPET].\[39\]

**Mitigations with measured effects.**
- **Constrain to a menu of valid actions:** about 2× F1 for Mistral-7B and Mixtral [READ].\[5\]
- **Executor-side diagnostics:** +16.8 F1 (ERASER) [READ].\[21\]
- **Schema-filtered candidates:** large reductions in empty results (SAGA) [READ].\[24\]\[25\]
- **Fewer tools in view.** On ToolBench, a cloud tool-access study (arXiv 2607.15593) reports that a baseline exposing all tools fell from 92.4% selection accuracy at 15 tools to 78.2% at 640, below all retrieval-based methods [SNIPPET]. RAG-MCP (Gan & Sun, arXiv 2505.03275) reports that retrieval-filtered tools more than triple selection accuracy, from 13.62% to 43.13%, while cutting prompt tokens by over 50% [ABSTRACT]. Ariadne needs about 8 tools, so this matters little unless the tool list multiplies per source.
- **More budget:** helps small models (Llama-3.1-8B nearly doubles to 0.261 at 10×) but not frontier ones [READ].\[29\]
- **Schema inspection behaviour:** the share of actions spent inspecting the schema correlates with agentic EX at Spearman ρ = 0.93 on CypherTurn [READ]. The authors treat this as a marker of resilient models, not a proven cause.\[29\]

**No measured evidence found** for compaction (summarising history) or repeated-call guards in KG agents specifically. Both are sensible engineering, but they are unvalidated for this task.

### Question 7: Grounding the plan in the schema

- **Card in the prompt vs tool-based discovery.** Middleware [READ] shows that putting environment samples into the prompt fails for large KBs: F1 stayed near 0 for 10–200 sampled triples, whereas tools that fetch information on demand worked.\[5\] On CypherTurn, models had to call INSPECT_SCHEMA to see the schema at all, and the models that did so most often kept accuracy best [READ].\[29\]
- **Schema size.** CHESS (Talaei et al., arXiv 2405.16755) reports that its Schema Selector cuts LLM tokens by 5× and raises accuracy by about 2% on very large database schemas [ABSTRACT]. Spider 2.0's 632 tasks run on databases that often exceed 1,000 columns, and its o1-preview code agent solved only 21.3% of them, against 91.2% on Spider 1.0 and 73.0% on BIRD [ABSTRACT]. No paper reports a clean "accuracy versus schema size" curve for KG agents.
- **Ariadne's case.** Its current cards (34 edge types across three graphs) are small enough to fit whole. The risk comes when LLM-extracted graphs add hundreds of relation types. Then the SAGA approach (a type-filtered schema slice per lookup) and a schema retrieval tool are the evidence-backed answers.\[25\]
- **Plug-and-play is a property of the method, not the paper.** R2-KG's authors criticise ToG for needing depth/width hand-tuning per KG and algorithm changes for temporal KGs [READ].\[2\]\[3\] Interactive-KBQA needs hand-annotated exemplars per question type [READ].\[11\] Both quietly fail Ariadne's "no hand-labelled data" rule.

## Recommended Loop for Ariadne

### Design principle
**Typed in, typed out.** No tool takes a natural-language sub-question. Every argument is either a source name, a label/relation/property from the card, a node identifier returned by a previous tool, or a result handle. This removes the current defect at its root: the keyword re-parsing of planner text that collapses the paraphrase tiers. The LLM's job becomes *choosing among options the executor proves are valid*, which is the action space with the best evidence for weak models.

### Tools

| Tool | Inputs | Returns | Targets |
|---|---|---|---|
| `list_sources()` | none | One line per online source: name, backend, description, identifier scheme, label and relation counts | Cross-source planning |
| `get_schema(source, labels?)` | Source and optional label filter | Allowed (source label, relation, target label) patterns with one-line glosses; filtered slice when the card is large | Schema grounding as graphs grow |
| `resolve(source, mention, expected_labels?)` | Surface text copied from the question, optional label constraint | Up to 10 candidates: id, label, name, short description, degree, match type (exact ID, alias, lexical, embedding); candidates incompatible with `expected_labels` removed; always includes `none` | "Entity named instead of identifier" (0.0990) and "paraphrased name" (0.0000) tiers; 35% wrong-entity choice |
| `describe(source, id)` | Node identifier | Properties plus, for each allowed relation, the count of neighbours (never the neighbours themselves) | Hub explosion; picking the relation that actually has data |
| `plan_candidates(source, anchor_ids, answer_label?, max_hops≤3)` | Resolved anchors and an optional expected answer label | Deterministically enumerated typed plans (chains, two-anchor intersections, cross-source joins) that respect the card's patterns, each with a pre-executed result count | Synonym-verb tier (0.4667), chained and cross-source questions (about −0.50 and −0.55) |
| `run(plan)` | A typed plan from the primitive grammar (describe / expand / join / chain / intersect) or the id of a `plan_candidates` entry | Result handle, row count, first 20 rows with record ids, the executed query text; on failure, a structured diagnosis | Deterministic execution and provenance |
| `refine(handle, filter / aggregate / limit)` | Handle plus a property filter, count or top-k | New handle and summary | Too many results |
| `answer(claims[], each with record ids)` | Draft claims with the record ids that support them | Validator verdict: accepted, or the list of unsupported claims | Confident-wrong answers |

**On the 35% wrong-entity rate.** The 35% came from an LLM choosing from a reranked list. Three changes are expected to help, each backed by indirect evidence:
- `resolve` removes schema-incompatible candidates before the model sees them (SAGA's mechanism).\[24\]\[25\]
- `plan_candidates` shows which candidates actually produce non-empty results along a valid pattern, so disambiguation is grounded in execution.
- `none` is always an option.

Whether these together bring the error well below 35% is unmeasured; Experiment 3 tests it.

### Control pattern: deterministic prelude, then a capped plan–execute–check–repair loop

1. **Prelude (no LLM, milliseconds).** Run `list_sources`. Detect identifiers in the question by scheme (e.g., T1176, CWE-79). Run `resolve` on identifier hits and on n-gram mentions against the build-time name/alias/description index (this index is the B step). Run `plan_candidates` for the top anchors. Put all of this into the first observation as a **candidate panel**.
2. **Call 1.** The controller reads the question, the cards and the panel, then either submits `run(plan_candidate_id)` or makes targeted exploration calls. Several tool calls may go in one turn, executed in parallel, as R2-KG does.\[2\]\[3\]
3. **Calls 2–5.** Read the shaped results and repair using the recovery rules below.
4. **Final call.** `answer(...)`, then the validator. If the validator rejects, allow one repair; otherwise abstain.

This is closest to QueryAgent plus Middleware's decoupled mode, with SAGA's filtering and R2-KG's abstention. It is deliberately **not** a ToG-style beam search, which costs too many calls, and **not** free ReAct over raw tools. CypherTurn shows that free autonomy costs 14–31 points even for frontier models.

### Stopping rule
- Stop and return when the validator accepts every claim, **and** the answer's node label equals the plan's expected answer label, **and** every anchor in the question has been used or explicitly marked irrelevant.
- Otherwise continue until the budget runs out, then **abstain**, returning the executed queries, their result counts and the unresolved candidates as proof.
- The model never answers without at least one supporting record. That rule shuts off the ToG/GoG memory fallback.

### Recovery rules (all diagnoses produced by the executor)
- **Empty result.** Return: (a) whether the relation is allowed for the anchor's label; (b) per-relation neighbour counts from `describe`; (c) up to three deterministic relaxations, ranked by non-empty count (reverse direction, a one-hop detour via an allowed pattern, a dropped property filter). This follows ERASER's diagnose-then-guide approach.
- **Schema or type violation.** Reject before execution and return the valid alternatives as a menu. The violation costs no database round trip.
- **Ambiguous or wrong entity.** Re-rank candidates by execution (which candidates yield non-empty results on the intended pattern). If two or more remain viable, either answer for each with labelled provenance or abstain with the list. Ask the user only if the embedding caller declares an interactive channel. No evidence was found that asking the user improves retrieval accuracy.
- **Too many rows.** Never return more than 20 rows. Return the count, the label distribution and a degree-sorted sample, then require `refine`.
- **Repeated call.** If a tool call matches an earlier one exactly, return the cached result plus "already executed; result was X" and do not count it as progress. A second repeat forces abstention. In the transcript, replace failed calls with the diagnosis rather than echoing the failed call text. This is a hypothesis drawn from the 19% repeat finding [SNIPPET].
- **Malformed tool call or a turn with no tool call.** Constrain tool-call arguments by grammar, but do not also force a JSON schema on the final answer in the same decoding pass, given the tool-suppression report [SNIPPET]. If a reasoning-mode turn ends with neither a tool call nor an answer, re-prompt once with "emit the call."

### Step budget
- **Target 6 LLM calls; hard ceiling 8;** at most 4 tool calls per turn; one validator repair.
- Reasons: R2-KG's Operator averages 6–9 calls;\[3\] QueryAgent needs about 5–6 executions; SAGA about 5.5–7.7 actions. CypherTurn shows that budgets beyond what models naturally use do not help frontier models. Ariadne's depth cap of 3 bounds legitimate plans at about 3 expansions plus a join.
- **Latency.** Expect a median of about 2–3 calls (10–15 s) when the candidate panel contains the right plan, and about 25–40 s worst case. That is far slower than today's 13 ms. The second priority (speed) is therefore served only by the prelude and the cap.

### What each element targets
- Typed arguments and the candidate panel: wording sensitivity (all paraphrase tiers) and the 77/284 "planner retrieved nothing" cases.
- `plan_candidates` and `run(plan)`: the chained and cross-source drops.
- `resolve` with label filter and `none`: the named-entity and paraphrased-name tiers and the 35% wrong-entity rate.
- The validator-gated stop and abstention: the doubled confident-wrong answers seen with the rewrite stage.
- Diagnostic recovery: empty retrievals.
- Shaped results and `refine`: hubs and the 1,000-row limit.

## Methods That Look Right but Fail the Constraints

- **KG-Agent, KBQA-o1, KBQA-R1, RoG, KnowAgent, GraphWalker, KG-R1 (T).** Each trains on the target KG or task, or on KGQA data.\[14\] KBQA-o1's MCTS also needs policy and reward models and many calls per question.\[22\]
- **Interactive-KBQA (hand-labelled data and free SPARQL).** It needs two hand-annotated exemplars per question type plus a trained type classifier, and its open-model results come from fine-tuning. Without it, Mistral-7B scored 4.76 on CWQ [READ].\[11\]
- **Think-on-Graph and ToG-2.** Up to 22–25 calls per question [SNIPPET]/[READ]; depth and width tuned per KG; falls back to model memory at the depth limit;\[1\]\[2\]\[3\] and small models do worse with it than without it on WebQSP [READ].
- **Generate-on-Graph.** Its "generate" action creates facts from the model's memory.\[14\]\[15\]\[16\] That is exactly the uncited behaviour Ariadne's validator exists to block.
- **CHESS, ReFoRCE, MAC-SQL, Spider-Agent, SPINACH, SAGA as published.** All have the LLM write the final query text.\[25\] Their lessons transfer (schema pruning, value exploration, consensus, type filtering) but their executors do not.
- **R2-KG as published.** It depends on a hosted GPT-4o Supervisor, which conflicts with local-by-default operation.\[2\] Its single-agent variant runs three times per question, tripling cost.\[3\]
- **QueryAgent/ERASER as published.** Its error guidelines are hand-written per error type,\[21\] which conflicts with "no hand-written rules." For Ariadne the diagnoses must be generated from the card (allowed patterns, counts), which is feasible because the card already encodes them.
- **Multi-agent critic/planner teams.** More calls on the same local model, with no task-specific evidence of benefit.

## Experiments to Run on Ariadne's Banks

1. **Interface fix without a loop.** Keep the current planner but make it emit typed plans (ids, relations, handles) checked against the card, removing the keyword re-reading.
   - *Measure:* records-exact by paraphrase tier; self-planned gold coverage on the 284 questions; the count of "planner empty where gold had records" (currently 77).
   - *Worked if* the synonym-verb tier rises above 0.80 and coverage rises above 0.65 at about current latency. If it does, the loop is only needed for the residue. *Failed if* tiers barely move, which would show the bottleneck is entity resolution or plan choice rather than the interface.
2. **Single-shot vs capped loop.** Compare (a) one LLM call that picks from `plan_candidates`, (b) the full loop capped at 6 calls, and (c) the same loop with a hosted frontier model as an upper bound.
   - *Measure:* gold coverage (target ≥ 0.75 against the 0.8611 oracle); judged correctness on the 282 sealed questions (must stay ≥ 0.90); confident-wrong rate (must not exceed the current pipeline's); abstention rate; LLM calls; p50 and p95 latency.
   - The loop is justified only if it beats (a) by a margin worth its latency.
3. **Action-space ablation for entities and relations.** Free tool arguments vs menu-only selection (Middleware's decoupled generation), each with and without schema-compatibility filtering and `none`.
   - *Measure:* wrong-entity rate (baseline 35%), malformed-call rate, and records-exact on the entity-named and paraphrased-name tiers (baselines 0.0990/0.3762 and 0.0000).
4. **Recovery and loop-hygiene ablation.** With and without executor diagnoses on empty results; with and without the repeated-call guard and transcript rewriting.
   - *Measure:* share of initially empty trajectories that end with validated records, exact-repeat rate per trajectory, and calls spent per recovered question.
5. **Stopping-rule comparison.** Model-declared stop vs validator-gated stop vs validator plus answer-label check.
   - *Measure:* selective accuracy (accuracy on answered questions), coverage, and confident-wrong count. Also count "answered one hop short" cases, identified by comparing the answer label with the gold answer label.
   - *Success:* confident-wrong falls without coverage dropping more than about 5 points.

## Caveats

- **Evidence gaps.** No published agent was evaluated on Gremlin, on federated multi-store joins, or on security KGs like ATT&CK/CAPEC/CWE. Every transfer to Ariadne is an inference.
- **No numeric rates.** No paper reports numeric rates for looping, premature stopping or answering from memory in a 7–32B controller. The ToG memory-fallback figures here are upper bounds derived from coverage.
- **Recent preprints.** Several 2026 preprints (SAGA, CypherTurn, tool-suppression, repeated-call) are not peer-reviewed. CypherTurn uses synthetic graphs,\[29\] and SAGA's controller is 120B, not 27–32B.\[24\]
- **Unverified sources.** FiDeLiS, KnowAgent, MAC-SQL and RoG were not read in this pass, so their table rows contain no verified figures. GoG, Graph-CoT and ODA figures come from secondary summaries.
- **Where the brief's assumptions look weak.**
  - The defect is the interface, not the absence of a loop. A loop that still passes NL sub-questions to keyword rules will inherit the 0.0 tiers.
  - A Claude-Code-style loop is the least constrained option. The strongest evidence favours shrinking the model's choices, not widening them.
  - Speed and the loop are in direct tension. A local 27–32B model at several seconds per call cannot match the current deterministic path, so latency targets for embedded callers must be renegotiated or gated by the prelude.
- **Bibliography.** Identifiers (arXiv IDs and venues) and read status are given in the comparison table; a separate reference list is omitted because a downstream pass attaches citations.

## Sources

1. [Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph](https://arxiv.org/pdf/2307.07697)
2. [R2-KG: General-Purpose Dual-Agent Framework for ...](https://aclanthology.org/2025.findings-ijcnlp.29.pdf)
3. <https://arxiv.org/pdf/2502.12767v7>
4. [\[2407.10805\] Think-on-Graph 2.0: Deep and Faithful Large Language Model Reasoning with Knowledge-guided Retrieval Augmented Generation](https://arxiv.org/abs/2407.10805)
5. <https://arxiv.org/pdf/2402.14672>
6. [Middleware for LLMs: Tools Are Instrumental for Language Agents in Complex Environments — Lacuna](https://lacuna.tiptreesystems.com/work/middleware-for-llms-tools-are-instrumental-for-language-agents-in-complex/wrk_0544c13343b4c86ae30152189226b788)
7. [\[Quick Review\] Middleware for LLMs: Tools Are Instrumental for Language Agents in Complex Environments](https://liner.com/review/middleware-for-llms-tools-are-instrumental-for-language-agents-in)
8. [KG-Agent: An Efficient Autonomous Agent Framework for Complex Reasoning over Knowledge Graph](https://arxiv.org/pdf/2402.11163)
9. [KG-Agent: An Efficient Autonomous Agent Framework for Complex Reasoning over Knowledge Graph - ACL Anthology](https://aclanthology.org/2025.acl-long.468/)
10. [\[Literature Review\] KG-Agent: An Efficient Autonomous Agent Framework for Complex Reasoning over Knowledge Graph](https://www.themoonlight.io/en/review/kg-agent-an-efficient-autonomous-agent-framework-for-complex-reasoning-over-knowledge-graph)
11. <https://arxiv.org/html/2402.15131v2>
12. [\[2410.23875\] Plan-on-Graph: Self-Correcting Adaptive Planning of Large Language Model on Knowledge Graphs](https://arxiv.org/abs/2410.23875)
13. [Paths-over-Graph: Knowledge Graph Empowered Large Language Model Reasoning](https://arxiv.org/pdf/2410.14211)
14. [GraphWalker: Agentic Knowledge Graph Question Answering via Synthetic Trajectory Curriculum](https://arxiv.org/pdf/2603.28533)
15. [Generate-on-Graph: Treat LLM as both Agent and KG in Incomplete Knowledge Graph Question Answering](https://arxiv.org/html/2404.14741v1)
16. [\[Quick Review\] Generate-on-Graph: Treat LLM as both Agent and KG for Incomplete Knowledge Graph Question Answering](https://liner.com/review/generateongraph-treat-llm-as-both-agent-and-kg-for-incomplete)
17. [Graph Chain-of-Thought: Augmenting Large Language Models by Reasoning on Graphs — Lacuna](https://lacuna.tiptreesystems.com/work/graph-chain-of-thought-augmenting-large-language-models-by-reasoning-on-graphs/wrk_4317842304d25e529d190e8c3f7f5bc9)
18. [EffiQA: Efficient Question-Answering with Strategic Multi- ...](https://aclanthology.org/2025.coling-main.479.pdf)
19. [Published as a conference paper at ICLR 2025](https://jshun.csail.mit.edu/Reknos.pdf)
20. [ODA: Observation-Driven Agent for integrating LLMs and Knowledge Graphs — Lacuna](https://lacuna.tiptreesystems.com/work/oda-observation-driven-agent-for-integrating-llms-and-knowledge-graphs/wrk_d0825463205a167f6df7e991b0ff4e9f)
21. <https://arxiv.org/html/2403.11886v1>
22. [KBQA-o1: Agentic Knowledge Base Question Answeringwith Monte Carlo Tree Search](https://arxiv.org/html/2501.18922)
23. [Co-Evolving Graph and Text Memory for Training-Free Multi-Hop Question Answering](https://arxiv.org/pdf/2607.23278)
24. [SAGA: Schema-Aware Grounding for Agentic Text-to-SPARQL Generation](https://arxiv.org/html/2607.14494)
25. [SAGA: Schema-Aware Grounding for Agentic Text-to-SPARQL Generation](https://arxiv.org/html/2607.14494v1)
26. [ICML CHESS: Contextual Harnessing for Efficient SQL Synthesis](https://icml.cc/virtual/2025/49375)
27. [Spider 2.0: Evaluating Language Models on Real-World Enterprise Text-to-SQL Workflows](https://arxiv.org/html/2411.07763v2)
28. [\[2411.07763\] Spider 2.0: Evaluating Language Models on Real-World Enterprise Text-to-SQL Workflows](https://arxiv.org/abs/2411.07763)
29. [CypherTurn: A Multi-Turn Benchmark for Conversational Text-to-Cypher Evaluation and the Autonomy Divergence](https://arxiv.org/html/2609.36987)
30. <https://aclanthology.org/2025.acl-srw.67.pdf>
31. [(PDF) Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph](https://www.researchgate.net/publication/372416758_Think-on-Graph_Deep_and_Responsible_Reasoning_of_Large_Language_Model_with_Knowledge_Graph)
32. [\[2502.00675\] ReFoRCE: A Text-to-SQL Agent with Self-Refinement, Consensus Enforcement, and Column Exploration](https://arxiv.org/abs/2502.00675)
33. [\[2404.07103\] Graph Chain-of-Thought: Augmenting Large Language Models by Reasoning on Graphs](https://arxiv.org/abs/2404.07103)
34. [Ground-Truth Subgraphs for Better Training and Evaluation of Knowledge Graph Augmented LLMs](https://arxiv.org/pdf/2511.04473)
35. [Feedback That Backfires: Why Small Language Model Agents Repeat the Call They Just Watched Fail](https://arxiv.org/pdf/2608.23651)
36. [Single-agent or Multi-agent Systems? Why Not Both?](https://arxiv.org/pdf/2505.18286)
37. [Orchestrated multi agents sustain accuracy under clinical-scale workloads compared to a single agent](https://www.medrxiv.org/content/10.1101/2025.08.22.25334049.full.pdf)
38. [Fidelity Is Not Enough: Dispatch-Level Instrumentation for Agentic Datasheet Extraction](https://arxiv.org/pdf/2608.28439)
39. [Constraint Tax in Open-Weight LLMs: An Empirical Study of Tool Calling Suppression Under Structured Output Constraints](https://arxiv.org/pdf/2606.25605)
