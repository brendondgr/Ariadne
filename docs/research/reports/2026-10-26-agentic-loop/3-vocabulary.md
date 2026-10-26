# Getting the User's Words into the Graph's Vocabulary: Making Ariadne's Controller→Specialist Boundary Reliable

The evidence supports the proposed boundary: an LLM controller that emits typed, card-derived requests is the best-supported design, and every published head-to-head favours tool-mediated, schema-grounded actions over free query text. But typed fields do not remove the vocabulary problem. They move it into two decisions the controller must now make: which entity, and which relation. Both need their own guards. A schema-valid request can still name the wrong node, and Ariadne's claim validator cannot catch that, because the records really do support claims about the wrong node.

## TL;DR

- **Typed requests beat query text, but only with lookup tools and teaching errors around them.** The closest evidence is GRASP's function-set ablation (Qwen2.5-72B, F1 on Freebase). A model allowed only to execute queries scored 6.5 on CWQ and 19.8 on WQSP; the same model with search and list tools scored 29.9 and 40.8 [READ-sub]. Middleware's KB tools with "decoupled generation" (the model picks from an enumerated list of permitted actions that includes "none") reached F1 59.3 against Pangu's 27.1 with GPT-4 [READ].\[1\] No study compares typed requests with Cypher or Gremlin text on unseen property graphs. That comparison would be new work.
- **Constrain the arguments, not the thinking, and keep each enum short.** Grammar overhead is negligible with XGrammar-class engines: 4–8 ms schema compilation and a 1.6–3.7% throughput cost [READ].\[2\] Even per-request dynamic grammars compile in about 10 ms with XGrammar-2 [READ-sub]. The binding constraint is accuracy as the option list grows. gpt-3.5 picked the right class 94.29% of the time from 2 options and 32.51% from 60 [READ-sub]. So compute per-step enums from the card (relations valid from the anchor's label, a few at a time) and never enumerate entity IDs. Let the model reason freely first, then constrain only the tool-call JSON (the CRANE/DCCD pattern).\[3\]
- **Ariadne's two failed experiments match published effects, and both point to the same fix.** Prompt-only rewriting is known to hurt queries that already match the corpus's wording: Kotte's "Not All Queries Need Rewriting" (arXiv 2603.13301) found that across three BEIR benchmarks rewriting degraded nDCG@10 by 9.0% on FiQA, improved it by 5.1% on TREC-COVID and had no significant effect on SciFact, and that selective gating "does not reliably outperform never rewriting" [READ-sub]. Picking from long candidate lists is known to degrade with list length and to depend on where the answer sits [READ-sub]. The fix for both is to ground inside the loop, against execution results: keep the original question, filter entity candidates by whether they have an edge of the planned relation, offer "none" and an ask-the-user action, and return empty-result diagnostics. Expect 2–4 controller calls per question, which on a local 27–32B model means tens of seconds, not milliseconds. That is the real cost of this design.

## One-page technique table

Class: **P** = works with an off-the-shelf model; **B** = needs an automatic one-time build per graph; **T** = needs training on the target graph or task. Read status refers to the source of the evidence. [READ-sub] means the full text was read by my research sub-agent, not by me.

| Technique | Class | LLM calls added | Best evidence (what was measured) | Status of source | Read |
|---|---|---|---|---|---|
| Typed tool calls with card-derived argument enums | B (card) | 0 (replaces NL handoff) | GRASP: execute-only set B vs. search tools S_E, CWQ 6.5→29.9, WQSP 19.8→40.8 (Qwen2.5-72B) | Peer-reviewed (ISWC 2025) | READ-sub |
| Navigational + functional KB tools ("middleware") | B | Loop: several per question | KBQA-Agent F1 59.3 (GPT-4, decoupled) vs Pangu 27.1; perfect entity linking assumed | Peer-reviewed (EMNLP 2024) | READ\[1\] |
| Decoupled generation (think, then pick from enumerated permissible actions incl. "none") | P | +1 per step | Mixtral 18.7→26.9 F1; Mistral-7B 9.6→18.3 vs error feedback alone | Peer-reviewed (EMNLP 2024) | READ\[1\] |
| Grammar/JSON-schema constrained tool args (XGrammar, Outlines, llama.cpp) | P | 0 | Schema validity 78.6–92.9%→100% on 0.6–4B models; semantic failures persist | Preprint | READ\[2\] |
| Think-then-constrain (CRANE; DCCD) | P | 0 (CRANE) / +1 (DCCD) | CRANE (Banerjee et al., arXiv 2502.09061v4): "up to 10% points accuracy improvement over baselines" on GSM-Symbolic and FOLIO; DCCD (Reddy et al., ICML 2026, PMLR 306): strict structured accuracy up to +24 points over standard constrained decoding, e.g. 15.2%→39.0% on GSM8K with a 1B model | CRANE: arXiv; DCCD: ICML 2026 proceedings | ABSTRACT / READ-sub |
| Entity search tool (SearchNodes-style; returns description + type) | B (index) | +1 per mention | Interactive-KBQA EL F1 80.00 vs ELQ 41.30 on WebQSP; gold entities add +7.44 F1 | Peer-reviewed (ACL 2024) | READ |
| Schema/relation search tool | B (index) | +1 | Interactive-KBQA: 6/100 errors were predicate search; GRASP: model often skips property search and invents IRIs | ACL 2024 / ISWC 2025 | READ / READ-sub |
| Iterative column/value exploration (text-to-SQL) | P | Several | ReFoRCE: ablating column exploration costs about 3–4% EX on Spider 2.0 (secondary summary) | arXiv/OpenReview | SNIPPET\[4\] |
| Error feedback with retry | P | +1 per error | Middleware: error feedback lifts validity; Self-Debugging: successful repairs mostly within 3 turns (cap 10) | EMNLP 2024; ICLR 2024 | READ / SNIPPET\[1\]\[5\] |
| Edit-on-failure of a whole plan (Readi) | P | Avg 1.55 edit calls | Cheng et al.: 1.55 edit calls on average vs 4–8 calls for step-by-step interaction; 46%–60% of initial LLM paths instantiate without editing | Peer-reviewed (Findings ACL 2024) | READ-sub |
| Post-hoc constraint filter on candidates (type/relation, three-valued) | P (deterministic) | 0 | CES-PK: +0.04 precision, recall preserved, on Hetionet | Preprint | SNIPPET\[6\] |
| Ambiguity-triggered clarification (entropy over candidates) | P + tuned thresholds | +1 per ask | CLEAR-KGQA: WebQSP F1 71.20→83.00 (GPT-4o, simulated user with gold query) | Preprint (venue unverified) | READ |
| Rewrite before retrieval | P | +1 | Kotte (arXiv 2603.13301): nDCG@10 −9.0% on FiQA, +5.1% on TREC-COVID, no significant effect on SciFact; selective gating "does not reliably outperform never rewriting" | Preprint | READ-sub |
| Fine-tuned KG agent (KG-Agent; Interactive-KBQA SFT) | T | Loop | Out of scope for plug-and-play; cited for contrast | ACL 2025 / ACL 2024 | ABSTRACT / READ |

## Key Findings by Question

### 1. Typed requests instead of text

**Who does it.** The published systems fall on a spectrum:
- **Pure query-text generation**: CypherBench zero-shot prompting.
- **Query text generated inside a tool loop**: Interactive-KBQA still writes SPARQL through `ExecuteSPARQL`; GRASP writes SPARQL but grounds every IRI via search tools.\[7\]
- **Function calls with schema-item arguments and no query text at all**: Middleware's KB tools such as `get_relations(entity)` and `get_neighbors(var, relation)`, where "the arguments for each function are either a variable or an item from the KB schema" [READ];\[1\] KG-Agent's toolbox, which is fine-tuned (T) [ABSTRACT].\[8\]
- **Enumerate, then discriminate**: Pangu, already covered by the earlier pass.

Ariadne's proposal sits in the third group. That is the most constrained design, and it is the one Middleware evaluated.

**Evidence that typed actions beat text on unseen schemas.** All of it is indirect:
- **GRASP** (Walter & Bast, ISWC 2025) is the cleanest within-system comparison [READ-sub]. Holding the model fixed (Qwen2.5-72B), the execute-only function set scored CWQ 6.5 / WQSP 19.8. The set with entity/property search and list tools scored 29.9 / 40.8. With GPT-4.1 zero-shot, GRASP reached QALD-10 72.5 and WWQ 75.3 on Wikidata.\[9\] Its error analysis says the model "often skips the property search and invents property IRIs." That is exactly the failure that card-derived enums make impossible.
- **Middleware** (Gu et al., EMNLP 2024) [READ]:
  - On the 500-question KBQA-Agent set, tool-using GPT-4 scored F1 59.3 (decoupled) and 55.1 (error feedback). Pangu scored 27.1, KB-Binder 5.2 and StructGPT 8.4.\[1\]
  - On BIRD questions that need database content, GPT-4 with tools scored EX 38.3 against 13.8 for schema-in-prompt.\[1\]
  - Caveat: the KB results "assume perfect entity linking for all methods", so they say nothing about Ariadne's named-entity and description tiers.\[1\]
- **CypherBench** (Feng, Papicchio & Rahman, Megagon Labs, ACL 2025) is "the first benchmark with 11 large-scale, multi-domain property graphs with 7.8 million entities and over 10,000 questions." On it, free text-to-Cypher reaches 60.18% EX with gpt-4o, and no model under 10B parameters exceeds 20% [SNIPPET]. A later preprint (CYGNET) notes that structural errors shrink with model size but "the remaining accuracy gap is dominated by semantic failures that structural validation cannot reach" [SNIPPET].\[10\]

**What this means for Ariadne.** Typed requests remove the syntactic failure class: invalid Gremlin, and invented relations or labels. That class is real; your 2B model produced 0 of 17 working Gremlin drafts, and Mixtral emitted invalid actions more often than GPT-3.5 in Middleware [READ].\[1\] The semantic class remains: wrong relation among valid ones, wrong direction, wrong anchor. No paper isolates the two on unseen property graphs, so your experiment E1 below would be a contribution.

One more point. Interactive-KBQA's error analysis of 100 failures on WebQSP+CWQ found [READ]:
- Reasoning: 32
- Hallucination: 19
- Entity linking: 18
- Format compliance: 17
- Predicate search: 6\[7\]

Typed enums should erase most format and hallucination errors, about a third of failures. They do nothing for reasoning or entity-linking errors.

### 2. Constrained decoding with schema enums

**Latency is not the problem.**
- **Chavan** (preprint, 2026) [READ], on 0.6–4B models:
  - XGrammar: 4–8 ms schema compilation and 1.6–3.7% throughput loss.\[2\]
  - Outlines: 2.0–4.9 s compilation (peak 19.5 s) and 9–13% slower generation.\[2\]
- **JSONSchemaBench** (Geng et al.) [READ]:
  - Llama-3.1-8B on llama.cpp: llama.cpp's grammar compiled in 0.05 s, but time per output token was about 30 ms against 15.4 ms unconstrained on the GlaiveAI function-call schemas.\[11\] That roughly doubles the per-token cost. This matters if Ariadne serves through llama.cpp.
  - Guidance came in at 6.37 ms per token, below the unconstrained baseline.\[11\]
  - The benchmark also reports that constrained decoding "can speed up the generation process by 50%" and "improves the performance of downstream tasks up to 4%."\[11\]
- **XGrammar-2** (ACM CAIS '26) targets enums that change per step and per request [READ-sub]:\[12\]\[13\]
  - Dynamic tool-calling grammars compile in about 10 ms, against more than 1,000 ms for XGrammar.\[12\]
  - End-to-end latency is within 6% of unconstrained decoding on BFCL-v3.\[12\]
  - With 100 tags, plain EBNF compiled in 15,483 ms against 2,002 ms with its TagDispatch.\[12\]
  - Recommendation: if enums are rebuilt per step, use XGrammar-2 (vLLM/SGLang) rather than Outlines or llama.cpp's grammar engine.

**Accuracy as enum size grows.** No paper measures a single argument enum at tens, hundreds and thousands of values. The closest proxies all point the same way:
- **Classification-label count** (Lu et al., 2406.07001) [READ-sub]: gpt-3.5-turbo fell from 94.29% with 2 options to 32.51% with 60. Fixing the answer's position swung LLaMA2-70B by 35.29 points.\[14\]
- **Tool-catalog size** (LongFuncEval, preprint) [READ-sub]: as the tool list grows to 120K tokens, BFCL AST accuracy drops by 7.59% to 85.58%. QwQ-32B, the closest model to your class, fell from 0.91 to 0.45.\[15\] A third-party reviewer flags possible duplicate tools in the padding (not verified).\[16\]
- **Tool shortlists** (preprint, 2605.24660) [SNIPPET]: Claude chose the gold tool 93.1% of the time with about 2.2 options shown, against 87.1% with 5.\[17\]

**What this means for Ariadne.**
- Ariadne's whole vocabulary is small: 34 relations, and labels in the tens. Per-step enums of relations valid from the anchor's label will usually have single-digit size. That is the regime where both latency and choice accuracy are good.
- Entity identifiers (10k now, millions later) must never be an enum. Get them from a search tool, then constrain the next call to the returned candidate IDs plus `NONE`: a dynamic enum of about 10 values.
- Constrained decoding guarantees the value exists. It does not guarantee it is right. Chavan's "CD-resistant" class (a missing second function call, or "hollow" arguments) is the analogue of choosing a valid but wrong relation.\[2\]

**Does constraining hurt reasoning?** The evidence is contested:
- *Let Me Speak Freely?* (Tam et al., EMNLP 2024 per Semantic Scholar) reported "a significant decline in LLMs' reasoning abilities under format restrictions," worse under stricter constraints, but better accuracy on classification tasks [ABSTRACT].\[18\]\[19\]\[20\]
- dottxt's rebuttal (blog, not peer-reviewed) argues the prompts were mismatched across conditions, and that matched structured generation equals or beats free text [SNIPPET].\[20\]\[21\]\[22\]
- CRANE (Banerjee, Suresh, Ugare, Misailovic & Singh, arXiv 2502.09061v4) argues formally that an overly restrictive grammar reduces expressivity, and fixes it by letting reasoning run unconstrained between delimiters, reporting "up to 10% points accuracy improvement over baselines on challenging symbolic reasoning benchmarks GSM-symbolic and FOLIO" [ABSTRACT].
- DCCD (Reddy, Walker, Ide & Bedi, ICML 2026, PMLR 306) drafts freely, then constrains conditioned on the draft. It names the cost a "projection tax" from masking low-probability valid continuations, and "improves strict structured accuracy by up to +24 percentage points over standard constrained decoding (e.g., 15.2% to 39.0% on GSM8K with a 1B model)" [READ-sub].

The practical consensus, which holds whichever side is right, is to **separate thinking from the constrained payload**. A local reasoning model already emits a free thinking block. Apply the grammar only to the tool-call JSON that follows (most serving stacks' tool-call parsers do this), and put no "reasoning" field inside the constrained object after the answer fields. This is the same move as Middleware's decoupled generation, which helped weaker open models most [READ].\[1\]

### 3. Lookup tools for vocabulary

**What the agents use:**
- **Interactive-KBQA** [READ]: `SearchNodes(name)` returns formal names *plus description and type* for entity linking. `SearchGraphPatterns(sparql, semantic)` ranks one-hop predicates around an entity by semantic similarity to a phrase. It reached entity-linking F1 80.00 on WebQSP against ELQ's 41.30. Gold entities would add only 7.44 F1 (71.20→78.64).\[7\]
- **GRASP** [READ-sub]: an entity search with a prefix-keyword index, a property search with embedding similarity, property-of-entity and object-of-property searches, a constrained search, and a list of matching triples. Each returns the top 10.\[9\]
- **Middleware** [READ]: `get_relations`, `get_neighbors`, `get_attributes`, `count`, `intersection` for KBs; `get_distinct_values` and `find_columns_containing_value` for databases.\[1\]
- **ReFoRCE** on Spider 2.0: iterative exploratory SQL over columns and values. An ablation summary attributes about 3–4% EX to it [SNIPPET].\[4\]

**Tools vs. schema in the prompt.**
- In Middleware, prompting GPT-4 directly with 10–200 retrieved Freebase triples gave F1 near 0, while tools gave 59.3. On BIRD, adding sampled rows to a schema prompt "initially boosts... but eventually decreases" accuracy [READ].\[1\]
- For Ariadne the honest reading is narrower. Your *schema* (card) is small enough to fit in the prompt and should stay there; nothing argues for hiding 34 relations behind a tool. What cannot go in the prompt is the *instance vocabulary*: names, aliases, descriptions, and which relations a given node actually has. Lookup tools are needed for that.
- Interactive-KBQA's 6% predicate-search failures ("locate in" did not retrieve `organization.headquarters`) are exactly Ariadne's synonym-verb tier. They come from a similarity-ranking tool.\[7\] With a fully visible card, the controller can choose MITIGATES for "defend against" by reasoning over the one-line glosses rather than through retrieval.

### 4. Rewriting the question

**Ariadne's result is a known effect.**
- Kotte's "Not All Queries Need Rewriting" (arXiv 2603.13301, March 2026) found that across three BEIR benchmarks prompt-only rewriting "degrades nDCG@10 by 9.0 percent on FiQA, improves it by 5.1 percent on TREC-COVID, and has no significant effect on SciFact," and that selective gating "does not reliably outperform never rewriting" [READ-sub]. Degradation co-occurred with reduced lexical overlap with relevant documents, and a search excerpt reports harm rates of 23.6% for minimal rewrites and 42.4% for aggressive ones [SNIPPET].
- Elastic's engineering blog (vendor, not peer-reviewed) reports that replacing the original query with LLM output "deteriorates recall," and recommends strict templates over free rephrasing [SNIPPET].\[23\]

Your rewrite stage hit precisely this. It lifted the hard tiers (0.088, 0.164), where the wording was far from the graph's, but drifted wording that already matched. Because downstream records then existed for the drifted interpretation, it produced confident wrong answers rather than empty ones.

**What prevents it:**
1. **Never replace the original.** Keep the user's text in context for every step and for the validator. Mapping words to vocabulary becomes a series of field choices, each checked against the graph, not one free rewrite.
2. **Rewrite against execution feedback.** Readi edits only on failure: Cheng et al. report "an average of 1.55 calls for editing," against 4 to 8 calls for step-by-step interaction, and find that "46%-60% of reasoning paths initially generated by LLMs can be well instantiated" without editing [READ-sub]. Middleware's error feedback and Self-Debugging (repairs mostly within 3 turns) [SNIPPET] use the same principle: let execution decide whether the translation was right.\[5\]\[24\]
3. **Gate on lexical match.** If the question already contains a card label or relation, or an identifier matching the card's ID scheme, take the deterministic path first; the original tier is at 1.0000.

No study measures "confident-wrong" specifically under rewriting. That metric is Ariadne's, and worth reporting.

### 5. Wrong-entity risk

What published systems do, from strongest to weakest evidence:

- **Return distinguishing features, not bare names.** Interactive-KBQA's `SearchNodes` returns description and type. Its error analysis notes that when Freebase results lacked descriptions, the model rejected correct hits and searched again [READ].\[7\] For Ariadne: return label, ID, primary name, aliases, the one-line description, and a degree count per relation.
- **Shrink and de-bias the choice list.** Accuracy falls with option count and depends on position [READ-sub].\[14\] Your 35% wrong-entity rate from a reranked list is in line with that literature. Filter first, then show a short list in a randomised or ID-sorted order.
- **Relation and type compatibility, deterministically.**
  - CES-PK (preprint) uses three-valued constraint checks (satisfied / violated / unknown) and drops only explicit violations. That gained +0.04 precision with recall unchanged, as a post-hoc filter on Hetionet [SNIPPET].\[6\]\[25\]
  - Middleware's decoupled generation lets the model pick only actions consistent with prior observations, e.g. a relation argument must come from `get_relations` on that entity, and always includes "None of the actions corresponds to the thought" [READ].\[1\]
  - For Ariadne this becomes a hard rule: an anchor candidate is admissible for `expand(relation=R, direction=d)` only if the store confirms at least one R-edge in direction d. A cheap existence or degree query.
- **Ambiguity scoring and asking.** CLEAR-KGQA computes a normalised entropy over candidates, using a popularity prior and LLM perplexity of the question given each description. It asks when entity entropy exceeds 0.6 or intent entropy exceeds 0.8 [READ]. With GPT-4o, WebQSP F1 rose from 71.20 to 83.00. Ablation: simply giving the LLM an `AskForClarification` tool without the scorer gave 73.15, so models under-use the ask tool on their own.\[26\]
  - Caveats: the simulated user sees the gold SPARQL, which is optimistic; thresholds were grid-searched on 100 labelled samples; CWQ exact match went *down* with the full plugin (66.33 vs 69.55 without the entity score).\[26\]
- **A "none" option** is standard in decoupled generation and in NIL-aware entity linking,\[27\]\[28\] but I found no paper reporting how often LLMs correctly choose "none". That is a gap.

**The critical point for Ariadne.** The final claim validator checks claims against retrieved records. A wrong-entity answer passes, because the records genuinely support claims about the wrong entity. Wrong-entity defence must happen at grounding time, and the answer should echo the resolved entity ("Interpreting 'the Chrome extension technique' as T1176 Browser Extensions") so that callers can catch it.

### 6. Error messages that teach

Evidence that executor feedback helps:
- **Middleware** [READ]: error feedback with "concrete tool use error information" ("api.site is not a relation from #0. Please retry.") lifted GPT-4 to F1 55.1 and validity 78.0 on KBQA-Agent. KB error messages were "simple templates" written once per tool: generic, not per graph, so they fit your no-hand-written-rules constraint. But the authors warn self-correction "may not always be reliable when the underpinning LLM is weak, potentially leading to the repetition of the same mistakes." For weak models, listing the valid options (decoupled generation) beat free retry by 8–9 F1 points.\[1\]
- **Self-Debugging** (ICLR 2024): turns capped at 10, "the successful debugging processes mostly end within 3 turns" [SNIPPET].\[5\]\[29\]
- **Readi**: "an average of 1.55 calls for editing," against 4 to 8 calls for step-by-step interaction (Cheng et al., Findings ACL 2024) [READ-sub].
- **GRASP-F** (with a feedback step): CWQ 44.2→58.5 and WQSP 52.1→62.2 with GPT-4.1, but slightly *lower* on QALD-10 (72.5→70.6) [READ-sub].\[9\] Feedback is not free.

**Implication.** Cap retries at 2. Every rejection must list the valid options, which with card-derived enums is cheap and exact. The most valuable "error" is the **empty result** case (your 77/284), not a malformed request. Return a diagnostic: does the anchor exist; which relations it actually has, with counts; whether the reverse direction would match. That turns a silent empty result into a Readi-style edit signal.

### 7. Ask or guess

- LLMs are poor at deciding *when* to ask. CLAMBER (Zhang et al., Sichuan Univ./NUS, ACL 2024), a benchmark of about 12K examples, found that chain-of-thought and few-shot prompting "may result in overconfidence in LLMs and yield only marginal enhancements in identifying ambiguity" [READ-sub].
- Related work cited in AgentAbstain reports an "under-clarification bias" (ClarifyMT-Bench), and agents that "fabricate missing arguments rather than ask" (Noisy-ToolBench) [SNIPPET].\[30\]
- In text-to-SQL, ABISS (preprint) found ambiguous-question accuracy of 32.3%/39.8% when the category was given, against 17.6%/22.6% when it was predicted. A reviewer flags a 25% gold-SQL error rate [SNIPPET].\[31\]
- AmbiSQL reports 87.2% precision in detecting ambiguity [SNIPPET].\[32\]

**When asking beats guessing.** The evidence that supports asking is CLEAR-KGQA's result: asking helps when a *computed* signal over tool results (candidate entropy) exceeds a threshold, not when the LLM decides alone [READ]. Lower thresholds meant more asks and higher F1, so the rate is a cost dial.\[26\]

**For an embedded Ariadne,** where the caller may be another agent, "ask" should be a structured return (`needs_clarification` with candidate IDs and descriptions), not a blocking prompt. No published evidence gives an optimal asking rate; set it from your own cost of a confident-wrong answer.

## Recommended Request Schema and Lookup Tools

### Specialist request (the only thing a specialist ever reads)

```json
{
  "op":        "describe | expand | join | chain | intersect",
  "source":    "<enum: source ids of online cards>",
  "anchors":   [{"id": "<string, regex = card.id_scheme>", "label": "<enum: card labels>"}],
  "relation":  "<enum: computed per step, see below>",
  "direction": "out | in",
  "target_label": "<enum: computed>",
  "filters":   [{"property": "<enum: properties of target_label>", "op": "eq | contains | in | range", "value": "<typed by property>"}],
  "join_key":  "<enum: identifier properties shared across online cards>",
  "then":      "<nested request for chain; max depth 3>",
  "limit":     "<int 1..1000>",
  "note":      "<free text: logged for audit, never parsed>"
}
```

**How the per-step enums are computed** (deterministic, from the card, no LLM):
- `relation`: the set {R | (anchor.label, R, *) ∈ card.patterns} for `out`, and {R | (*, R, anchor.label) ∈ card.patterns} for `in`. Show each value with its gloss in the tool description.
- `target_label` is then fixed by the pattern, or limited to the few labels it allows.
- `anchors[].id` is never an enum over the graph. After `search_entities`, the next call's grammar may restrict the ID to the returned candidates plus `"NONE"`, compiled per request (about 10 ms with XGrammar-2).
- `filters[].property`: the target label's properties from the card.
- Build the grammar per step with XGrammar-2 (vLLM/SGLang). Keep free-form thinking outside the constrained JSON.

**Error contract** (every response is one of these):
- `ok`: records, the executed query text (proof), row count, truncation flag.
- `invalid_request`: `{field, got, code: unknown_value | pattern_not_in_card | depth_exceeded | id_scheme_mismatch, valid_options: [...≤20, with glosses], nearest: [...≤3 by string similarity]}`.
- `empty`: `{executed_query, anchor_exists: bool, anchor_relations: {REL: count, ...}, reverse_direction_count: int, hint}`.
- `ambiguous_anchor`: returned if the anchor fails the compatibility check (no edge of the requested relation): `{compatible_candidates: [...]}`.
- `limit_hit` / `timeout`: partial records plus counts, so the controller can narrow with filters.

### Lookup tools for the controller

1. `get_cards()`: compact card text for all online sources. **Put this in the system prompt**, since the vocabulary is small.
2. `search_entities(text, label?, source?, k=10)`: build-time (B) index over names, aliases and one-line descriptions, combining keyword and embedding search. Returns ID, label, name, aliases, description, and degree per relation.
3. `relations_of(id)`: actual relations with counts, in both directions. This is what implements the edge-of-planned-relation guard.
4. `describe_node(id)`: properties plus 1-hop relation summary.
5. `search_schema(text)`: labels and relations ranked by similarity to their glosses. A fallback only, since the card is in the prompt.
6. `ask_user(question, options[])`: returned to the caller as `needs_clarification` when Ariadne is embedded.

## Experiments on Ariadne's Paraphrase Tiers

For every experiment, report on each tier (original, synonym verb, named entity, paraphrased name, description only):
- records-exact
- answered rate
- **wrong-entity rate** (resolved anchor ≠ gold anchor, among answered)
- **confident-wrong rate** (answered, validator passed, records ≠ gold)
- abstain / ask rate
- controller calls and wall-clock per question

1. **E1. Typed boundary vs. NL handoff.**
   - Arms: (a) current planner with NL sub-questions; (b) controller emits typed requests with lookup tools, original question always retained; (c) arm b plus a deterministic fast path when the question already contains card vocabulary or IDs.
   - *Decision:* adopt b or c if the summed records-exact gain on the named-entity and paraphrased-name tiers is at least 0.30, original-tier records-exact stays ≥ 0.98, and confident-wrong does not exceed arm a's on any tier.
2. **E2. Constraint placement.**
   - Arms: unconstrained tool JSON with validator; per-step enum grammar on the JSON only (thinking free); a constrained "reasoning" field inside the JSON.
   - *Decision:* the invalid-request rate *and* the wrong-but-valid relation rate on the synonym-verb tier. Prefer the arm that lowers the second; the first is fixable by retries.
3. **E3. Entity grounding guard.**
   - Arms: the reranked-list pick (your 35% baseline); `search_entities` plus a short shuffled list plus `NONE`; the same plus the hard filter "candidate has ≥1 edge of the planned relation/direction".
   - *Decision:* wrong-entity rate on the named, paraphrased and description tiers at matched coverage. Plot risk against coverage, and require wrong-entity below 10% before enabling.
4. **E4. Teaching errors.**
   - Arms: bare error; error with valid_options and nearest; additionally the `empty` diagnostics. Retry cap 2.
   - *Decision:* the share of the 77 planner-empty cases recovered; the retry distribution (median ≤1 expected); confident-wrong introduced by recoveries.
5. **E5. Ask vs. guess.**
   - Set an entropy threshold over `search_entities` and relation candidates (CLEAR-style), swept from 0.5 to 0.9. Use a simulated caller that knows the gold anchor but *not* the gold query.
   - *Decision:* records-exact gained per clarification asked, and confident-wrong averted per ask. Choose the threshold where the marginal ask still prevents at least 0.5 confident-wrong answers. Also log how often the model picks `NONE` unprompted.

## Caveats

- **Speed is the price.** The deterministic path answers 120 questions in 1.6 s, about 13 ms each. A 2–4-call controller loop on a local 27–32B model at several seconds per call is 10–30 s per question, three orders of magnitude slower. The deterministic fast path in E1 arm (c) is the mitigation.
- **Transfer to local models is unproven.** Most loop evidence uses GPT-4-class models. Interactive-KBQA's Mistral-7B without fine-tuning scored 4.76 F1 on CWQ, and GPT-3.5 Turbo 13.42, against GPT-4 Turbo's 49.07 [READ].\[7\] LongFuncEval's QwQ-32B is the closest evidence for your class, and it degraded sharply with long tool lists.\[15\] Keep tool lists and enums short.
- **Benchmark mismatch.** Nearly all KGQA evidence comes from Freebase or Wikidata. None comes from security ontologies like ATT&CK, CAPEC and CWE, from federated property graphs, or from Gremlin.
- **Secondhand figures.** Figures tagged [SNIPPET] or [ABSTRACT] are leads, not measurements. In particular: CLAMBER's 50.37% accuracy and 34.27% F1 for Llama2-70B, which appear only in a secondary summary and were not found in the paper text the enrichment pass fetched; the 23.6%/42.4% rewrite harm rates, which appear only in a search excerpt; and ReFoRCE's ablation. Readi's 1.55 edit calls and DCCD's 15.2%→39.0% were since confirmed in the full texts (Findings ACL 2024; ICML 2026, PMLR 306).
- **Peer-review status** is as stated in the table. Several key sources (Chavan, LongFuncEval, CES-PK, CLEAR-KGQA's venue, the rewriting study) are preprints.
- **No direct evidence exists for:** typed requests vs. Cypher/Gremlin text on unseen property graphs; accuracy as a single argument enum grows from tens to thousands of values; how often LLMs correctly choose "none"; or confident-wrong rates under rewriting.

## Bibliography

- Gu et al., "Middleware for LLMs: Tools Are Instrumental for Language Agents in Complex Environments," EMNLP 2024 (peer-reviewed). https://arxiv.org/abs/2402.14672 [READ]
- Xiong, Bao, Zhao, "Interactive-KBQA," ACL 2024 (peer-reviewed). https://arxiv.org/abs/2402.15131 [READ]
- Wen et al., "CLEAR-KGQA: Clarification-Enhanced Ambiguity Resolution for KGQA," arXiv 2504.09665 (venue unverified; treat as preprint). https://arxiv.org/abs/2504.09665 [READ]
- Walter & Bast, "GRASP," ISWC 2025 (peer-reviewed). https://arxiv.org/abs/2507.08107 [READ-sub]
- Geng et al., "JSONSchemaBench," arXiv 2501.10868 (preprint). https://arxiv.org/abs/2501.10868 [READ, sections 1–4]
- Chavan, "Constrained Decoding Eliminates Structural Failures in Small LLMs but Reveals a Scale-Dependent Semantic Gap," arXiv 2609.23742 (preprint). https://arxiv.org/abs/2609.23742 [READ]
- Li, Dong et al., "XGrammar-2," ACM CAIS '26 (peer-reviewed per paper header). https://arxiv.org/abs/2601.04426 [READ-sub]
- Dong et al., "XGrammar," arXiv 2411.15100. https://arxiv.org/abs/2411.15100 [SNIPPET]
- Kate et al., "LongFuncEval," arXiv 2505.10570 (preprint). https://arxiv.org/abs/2505.10570 [READ-sub]
- Lu et al., "Mitigating Boundary Ambiguity and Inherent Bias for Text Classification," arXiv 2406.07001 (Findings ACL 2024, unverified). https://arxiv.org/abs/2406.07001 [READ-sub]
- Tam et al., "Let Me Speak Freely?," EMNLP 2024 (per Semantic Scholar). https://arxiv.org/abs/2408.02442 [ABSTRACT]
- Kurt (dottxt), "Say What You Mean: A Response to 'Let Me Speak Freely'" (blog). https://blog.dottxt.ai/say-what-you-mean.html [SNIPPET]
- Banerjee, Suresh, Ugare, Misailovic & Singh, "CRANE: Reasoning with constrained LLM generation," arXiv 2502.09061v4. https://arxiv.org/abs/2502.09061 [ABSTRACT]
- Reddy, Walker, Ide & Bedi, "The Hidden Cost of Structured Generation in LLMs: Draft-Conditioned Constrained Decoding," ICML 2026, PMLR 306 (peer-reviewed). https://arxiv.org/abs/2603.03305 [READ-sub]
- Feng, Papicchio, Rahman, "CypherBench," ACL 2025 (peer-reviewed). https://arxiv.org/abs/2412.18702 [SNIPPET]
- "CYGNET: Cypher Gate for Neural Execution Triage," arXiv 2606.04645 (preprint). https://arxiv.org/abs/2606.04645 [SNIPPET]
- Deng et al., "ReFoRCE," arXiv 2502.00675. https://arxiv.org/abs/2502.00675 [SNIPPET]
- Jiang et al., "KG-Agent," ACL 2025 (peer-reviewed). https://arxiv.org/abs/2402.11163 [ABSTRACT]
- Cheng et al., "Call Me When Necessary (Readi)," Findings of ACL 2024. https://arxiv.org/abs/2403.08593 [READ-sub]
- Chen et al., "Teaching Large Language Models to Self-Debug," ICLR 2024. https://arxiv.org/abs/2304.05128 [SNIPPET]
- Kotte, "Not All Queries Need Rewriting," arXiv 2603.13301 (preprint). https://arxiv.org/abs/2603.13301 [READ-sub]
- "Query rewriting strategies for LLMs & search engines," Elastic Search Labs (vendor blog). https://www.elastic.co/search-labs/blog/query-rewriting-llm-search-improve [SNIPPET]
- "Constrained Entity Selection under Partial Knowledge (CES-PK)," arXiv 2608.24824 (preprint). https://arxiv.org/abs/2608.24824 [SNIPPET]
- Zhang et al., "CLAMBER," ACL 2024. https://arxiv.org/abs/2405.12063 [READ-sub]
- "AgentAbstain: Do LLM Agents Know When Not to Act?," arXiv 2607.10059 (preprint). https://arxiv.org/abs/2607.10059 [SNIPPET]
- "ABISS: Evaluating Text-to-SQL Systems Through Agent Interaction," arXiv 2607.23340 (preprint). https://arxiv.org/abs/2607.23340 [SNIPPET]
- "How Many Tools Should an LLM Agent See?," arXiv 2605.24660 (preprint). https://arxiv.org/abs/2605.24660 [SNIPPET]

## Sources

1. <https://arxiv.org/pdf/2402.14672>
2. <https://arxiv.org/pdf/2609.23742>
3. [Draft-Conditioned Constrained Decoding for Structured Generation in LLMs (arXiv:2603.03305)](https://paperswithcode.co/paper/2603.03305)
4. [Spider 2.0: Enterprise Text-to-SQL Benchmark](https://www.emergentmind.com/topics/spider-2-0-benchmark)
5. [Teaching Large Language Models to Self-Debug](https://arxiv.org/html/2304.05128v2)
6. [Constrained Entity Selection under Partial Knowledge for LLM-Based Knowledge Graph QA](https://arxiv.org/html/2608.24824v1)
7. <https://arxiv.org/pdf/2402.15131>
8. [KG-Agent: An Efficient Autonomous Agent Framework for Complex Reasoning over Knowledge Graph](https://www.emergentmind.com/papers/2402.11163)
9. <https://arxiv.org/pdf/2507.08107>
10. [CYGNET: Cypher Gate for Neural Execution Triage and Cost Containment](https://arxiv.org/pdf/2606.04645)
11. [JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models](https://arxiv.org/html/2501.10868v3)
12. [XGrammar-2: Dynamic and Efficient Structured Generation Engine for Agentic LLMs](https://arxiv.org/html/2601.04426)
13. [XGrammar-2: Dynamic and Efficient Structured Generation Engine for Agentic LLMs](https://arxiv.org/pdf/2601.04426)
14. <https://arxiv.org/pdf/2406.07001>
15. <https://arxiv.org/html/2505.10570v1>
16. [LongFuncEval: Measuring the effectiveness of long context models for function calling · Pith](https://pith.science/paper/2505.10570)
17. [How Many Tools Should an LLM Agent See?A Chance-Corrected Answer](https://arxiv.org/html/2605.24660v1)
18. [\[2408.02442\] Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models](https://arxiv.org/abs/2408.02442)
19. [\[2408.02442\] Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models](https://ar5iv.labs.arxiv.org/html/2408.02442)
20. [Paper page - Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models](https://huggingface.co/papers/2408.02442)
21. [What is structured output in AI models?](https://www.sanity.io/glossary/structured-output)
22. [Setting Logits to Negative Infinity: How LLMs Actually Output JSON](https://www.adambutterworth.com/posts/setting-logits-to-negative-infinity)
23. [Query rewriting strategies for LLMs & search engines](https://www.elastic.co/search-labs/blog/query-rewriting-llm-search-improve)
24. [Published as a conference paper at ICLR 2024 TEACHING LARGE LANGUAGE MODELS](https://proceedings.iclr.cc/paper_files/paper/2024/file/2460396f2d0d421885997dd1612ac56b-Paper-Conference.pdf)
25. [Constrained Entity Selection under Partial Knowledge for LLM-Based Knowledge Graph QA](https://arxiv.org/pdf/2608.24824)
26. <https://arxiv.org/pdf/2504.09665>
27. [Musical Heritage Historical Entity Linking](https://arxiv.org/pdf/2502.09168)
28. [Enhancing Entity Linking and Disambiguation](https://medium.com/@EleventhHourEnthusiast/enhancing-entity-linking-and-disambiguation-39db28b02456)
29. [TEACHING LARGE LANGUAGE MODELS TO SELF- DEBUG Xinyun Chen1 Maxwell Lin2](https://arxiv.org/pdf/2304.05128)
30. [AgentAbstain: Do LLM Agents Know When Not to Act?](https://arxiv.org/pdf/2607.10059)
31. [ABISS: Evaluating Text-to-SQL Systems Through Agent Interaction · Pith Review](https://pith.science/paper/2607.23340)
32. [(PDF) To RAG or Not to RAG, That Is the Question: Effective Text-to-SQL Generation Under Ambiguity](https://www.researchgate.net/publication/401528766_To_RAG_or_Not_to_RAG_That_Is_the_Question_Effective_Text-to-SQL_Generation_Under_Ambiguity)
