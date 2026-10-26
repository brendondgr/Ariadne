# The agentic retrieval loop — what four deep-research reports add up to (2026-10-26)

**Status: Draft.** Reads across the four external reports in this folder, the GAIFA agent
loop, a latency probe run today ([`probe/RESULTS.md`](probe/RESULTS.md)) and the research
record. Ariadne figures are quoted from [`../../CURRENT.md`](../../CURRENT.md) and the
experiments it indexes. Report figures keep the report's own read-status tag; a figure tagged
[ABSTRACT] or [SNIPPET] is a lead, not evidence.

| File | Prompt | Question |
|---|---|---|
| [`1-controller.md`](1-controller.md) | [prompt 1](../../../prompts/2026-10-26-agentic-loop-1-controller.md) | Loop design: action space, control pattern, stopping, recovery, small models |
| [`2-observations.md`](2-observations.md) | [prompt 2](../../../prompts/2026-10-26-agentic-loop-2-observations.md) | What the controller sees: hubs, million-node graphs, completeness |
| [`3-vocabulary.md`](3-vocabulary.md) | [prompt 3](../../../prompts/2026-10-26-agentic-loop-3-vocabulary.md) | The boundary: getting the user's words into the card's vocabulary |
| [`4-embedding.md`](4-embedding.md) | [prompt 4](../../../prompts/2026-10-26-agentic-loop-4-embedding.md) | Ariadne as a component: protocol, contract, speed, safety, tests |

---

## 1. What each report covers

### Report 1 — the controller loop

Surveys about 25 agent designs (Think-on-Graph, Middleware, QueryAgent/ERASER, R2-KG,
SAGA, Interactive-KBQA, the text-to-SQL agents, CypherTurn) and asks which fits a model
that drives deterministic executors.

- **Letting the model pick from a list of valid actions beats free tool calls, most of all
  for weak models.** Middleware (EMNLP 2024, [READ]) is the only clean head-to-head: every
  model improved, Mistral-7B from 9.6 to 18.3 F1.
- **Autonomy costs accuracy.** On CypherTurn ([READ], 2026 preprint), moving from guided
  to fully autonomous cost frontier models 14–31 execution-accuracy points. Small models on
  Think-on-Graph sometimes scored below plain chain-of-thought.
- **The executor should produce the diagnosis.** ERASER's executor-side hints added
  16.8 F1 ([READ]); the model critiquing itself lowered F1.
- **Never let the model's own "done" stop the loop.** Stop on the validator.
- **Recommends:** about eight typed tools, a deterministic prelude that prepares candidate
  entities and plans before the first model call, a cap of six calls (eight hard), and
  abstention at the cap. **First experiment: fix the interface without any loop.**

### Report 2 — what the controller sees

- **Shrinking what the model reads is cheap; losing the answer path is not.** Canedo
  (2026 preprint, [READ], 30,841 trials): swapping out irrelevant triples moved F1 by +0.003,
  removing the answer chain dropped it to 0.231. Subgraph size from 0 to 200 triples had no
  measurable effect.
- **Unlabelled truncation makes agents claim completeness they don't have.** One study,
  weak (single-author workshop poster, [ABSTRACT]). LLMs under-enumerate list answers
  (MoNaCo, KG-Guard, [ABSTRACT]/[SNIPPET]). So a deterministic composer is needed for
  "list every X".
- **Hubs are handled at the query level:** probe degree first, expand only along typed,
  directed relations, cap per row. Never emit an unlabelled `in()`/`both()` on Neptune.
- **The closest published setup to Ariadne:** a 48M-entity Wikidata agent where keeping
  results outside the model's context took an open 27B model from 60 to 74 of 100
  (Chenene et al. 2026 preprint, [READ]).
- **Recommends** a result envelope: exact totals, facet counts, a labelled sample of at most
  20, a `complete` flag, a handle the controller can page with, and Cypher and Gremlin
  query patterns for hubs.

### Report 3 — the vocabulary boundary

- **Typed requests beat query text, but only with lookup tools and teaching errors around
  them.** GRASP (ISWC 2025, [READ-sub]): with execute-only tools a 72B model scored 6.5 F1 on
  CWQ; with search tools added, 29.9.
- **Constrain the tool-call arguments, not the thinking, and keep each option list short.**
  Grammar overhead is milliseconds; accuracy falls as the list grows (94% at 2 options to 33%
  at 60 for gpt-3.5, [READ-sub]). Compute per-step option lists from the card and never make
  entity IDs an option list.
- **Ariadne's two failed experiments match published effects.** Rewriting before
  retrieval hurts questions that already matched (Kotte 2026, [READ-sub]). Picking from long
  lists degrades with length and position.
- **A new and important point: a wrong entity passes Ariadne's claim verifier**, because
  the records genuinely support claims about the wrong node. The defence has to sit at
  grounding time.
- **Recommends** a request schema, an error contract (`ok`, `invalid_request`, `empty`,
  `ambiguous_anchor`, `limit_hit`) and five experiments on the paraphrase tiers.

### Report 4 — Ariadne as a callable component

- **Nobody else combines deterministic executors, federation and per-claim verification.**
  Database vendors' MCP servers hand query writing to the caller's model; GraphRAG and memory
  products hide an LLM inside one opaque call. None returns the executed query as a contract.
- **MCP 2026-07-28 covers every requirement:** typed output schemas, progress, long-running
  tasks, and multi-round-trip requests for clarification. A2A and OpenAPI as thin adapters.
- **Callers believe what they're given** (ClashEval, [READ-sub]: 31–63% adoption of wrong
  context), so a confident wrong answer from Ariadne propagates. Ariadne must bind claims to
  records itself, not ask the caller to cite.
- **A warning for the design premise:** a June 2026 preprint (CYGNET, [SNIPPET]) reports
  Gemma 4 31B at 77.6% zero-shot text-to-Cypher accuracy on CypherBench. If it holds, "LLMs
  can't write Cypher" is dated. No comparable figure exists for Gremlin.
- **Recommends** `ariadne_ask` plus about six typed primitives, an `AnswerEnvelope`
  response schema, four cache layers and three speed modes (`fast`, `auto`, `thorough`).

## 2. Where the four agree

Independently, all four arrive at the same core:

1. **Replace the natural-language sub-question with a typed plan.** All four name it the
   most consequential change, and all four say it can be tested **without building a loop**.
   This is confirmed in the code: the Gremlin builder re-reads `task.text` with keyword rules
   (`asks_for_bulk_scan`, `is_definitional_request`, exact-name matching), so the
   deterministic engine is itself parsing language.
2. **Shrink the model's choices.** Lists of valid options from the card, not free arguments.
3. **Errors that teach.** The executor rejects a bad request and lists the valid options; an
   empty result comes back with a diagnosis.
4. **The validator decides when to stop**, and the system abstains with the executed queries
   when the budget runs out.
5. **The database computes sets, counts and totals.** The model never counts rows.
6. **Speed comes from a cascade:** a deterministic fast path first, the loop only on failure.

## 3. Where they are weak or disagree

- **Latency estimates are too pessimistic for today's model.** Reports 1, 3 and 4 assume
  "several seconds per call" and estimate 20–40 s for a six-call loop. The probe measured
  0.7 s per typed tool call with thinking off and 1.2–2.4 s with thinking on (§4.3).
- **Card in the prompt or behind a tool?** Report 3 says the card is small enough to keep
  in the prompt. Report 1 recommends a `get_schema` tool. Both are right at different sizes,
  and a universal system needs both: the whole card in the prompt below a size threshold, a
  schema-slice tool above it.
- **Is text-to-query still the wrong path?** Report 4's CYGNET figure is [SNIPPET] only. Keep
  the typed design. The universality argument (one algebra compiles to every backend) holds
  even if Cypher generation improves, but re-test it on Cypher once a year.
- **Load-bearing evidence that is thin:**
  - the truncation-labelling result (Jeffries, [ABSTRACT], single author);
  - CYGNET ([SNIPPET]);
  - most 2026 sources, which are preprints;
  - a few unfamiliar model names in Chenene et al. ("Qwen3.8-27B", "gpt-6-luna") that nobody
    checked.
- **Nothing was measured on Gremlin, on a federated multi-store setup, or on security
  graphs.** Every transfer to Ariadne is an inference. That is also where the open research is
  (§7).

---

## 4. Your five points

### 4.1 Exact results: the model's view can be bounded, the answer cannot

You are right that GAIFA's 4,000-token cap doesn't transfer. GAIFA can afford to lose rows;
Ariadne cannot. The rule for Ariadne:

> **No shaping step may remove anything that belongs in the answer.** What the controller
> *reads* is bounded; what the composer *returns* is the complete, exact set the plan selects,
> or an explicit `partial` status saying exactly what is missing.

That needs six things.

1. **Two channels.**
   - *Evidence channel:* every row the plan selects, fetched completely into a record store
     under a handle. The composer and verifier read only from here.
   - *View channel:* what the controller reads to decide its next step.

   The two never mix, so truncating the view cannot truncate the answer.
2. **Only lossless reductions in the view.** Exact totals, exact counts grouped by relation,
   label or property value, and database-side set operations (intersect, union, difference) and
   aggregates. "40,880 `USES`/in neighbours: 31,002 Software, 9,878 Group" (illustrative numbers,
   not a measurement) drops nothing; it is the whole set, grouped. A sample of rows appears only as
   an illustration, marked as such.
3. **The row cap becomes a page size, not a result limit.**
   - **Found today:** `utils/specialists/cypher/connector.py` stops reading at
     `max_result_rows` (1,000) and returns the rows **with no flag**, so a 1,001-row result
     reads as complete.
   - Some builders do report a true total (the expand compiler computes `size(members)`), so
     the gap isn't everywhere. But nothing proves every primitive reports it.
   - **The fix:** fetch the full set by keyset pagination (`ORDER BY id`, `WHERE id > $last`,
     `LIMIT $page`), which can't skip or repeat rows the way `SKIP`/`LIMIT` can. Always return
     the exact total and a `complete` flag. Keep one hard ceiling for safety only, and make
     hitting it an explicit `partial` status.
4. **Narrow by exact predicates, never by ranking.** When a hub is too large to read, the
   controller narrows by relation, label or property filter, which is exact. Ranking by
   similarity is allowed only when order *is* the answer ("the most …"), and then it's stated.
5. **When membership needs judgment, cover every member.** "Which of these 300 techniques
   concern cloud identity?" can't be a database predicate. Exact coverage then means classifying
   every member, not reading a sample. That is a decision-model job (§4.2):
   - a probability per member;
   - members above the threshold listed;
   - members in the uncertain band listed separately;
   - nothing dropped.
6. **What exact retrieval cannot protect.** A wrong plan gives a complete list of the wrong
   set (report 2), and a wrong entity passes the claim verifier (report 3). Two defences:
   - show the controller the counts for *every* relation at the anchor, so a missing facet is
     visible;
   - check the interpretation, not just the claims: echo the resolved entity and relation in
     the answer, and ask a decision model whether the plan answers the question.

### 4.2 Decision models: yes, and they fit the 35% problem specifically

GAIFA's `decide` mod already serves one: **d3-lite** (vLLM Semantic Router's Decision 3.0,
0.85B, fine-tuned from Qwen3.5-0.8B, Apache-2.0). It returns a probability for each answer to
a yes/no, choice or score question, with no generated text.

**Why it fits.** The 35% wrong-entity rate came from a *generative* pick: the model named a
candidate and gave no score, so there was nothing to threshold. A decision model gives a
probability per candidate, which turns grounding into a dial:
- accept above a high threshold;
- ask (or return `needs_clarification`) in the middle;
- abstain below.

That is the computed-signal trigger report 3 found works (CLEAR-KGQA asks when entropy over
candidates is high, [READ]), where letting the model decide when to ask did not.

**Probe** (one question, [`probe/RESULTS.md`](probe/RESULTS.md)):
- about **80 ms** per call for two questions, after a 7 s model load;
- the relation choice was right (MITIGATES, p = 0.614);
- the entity match was right (yes, p = 0.791);
- identical probabilities on every repeat.

**Where it goes in the loop:**

| Decision | Question to the decision model | Replaces |
|---|---|---|
| Entity grounding | yes/no per candidate: "does *mention* refer to *candidate + description*?" | The generative pick (35% wrong) |
| Relation choice | choice over the relations valid from the anchor's label, each with its gloss, plus NONE | Keyword rules in the builders; the gloss lexicon |
| Question shape | choice: lookup, enumerate, count, chain, compare, aggregate, other | The MITRE-specific regexes in `utils/planner/intent.py` |
| Membership by meaning | yes/no per member of a large set (§4.1, point 5) | Reading a sample |
| Fast-path gate | "does this plan answer this question?" | Nothing today: the missing interpretation check |
| Stop | "do these records answer the question?" | The model's own "done" |

**It stays universal.** The options come from the card (relations and their glosses), so a
new graph needs glosses at build time and no code. It is the one model component that can sit
in the fast path, because 80 ms is close to deterministic cost.

**Risks:**
- d3-lite is general-purpose and was never trained on graphs.
- Its calibration on our tasks is unknown, and a margin of 0.614 may be typical.
- It shares the GPU with the controller.

Thresholds therefore have to be set from Ariadne's banks: accuracy, calibration error, and
wrong-entity rate at fixed coverage. Never from one probe.

**The research angle:** train one schema-conditioned grounding model once, across many graphs,
and test it on held-out graphs. That is allowed under the plug-and-play rule (pre-trained on
*other* graphs, reused unchanged). It is also the cross-graph machine-learning thesis in the ARA
proposal. See §7, item 3.

### 4.3 How long each step takes

Measured today on the local stack unless marked. One question, warm, single user: these are
per-call costs, not accuracy.

| Step | Deterministic | Decision model (d3-lite) | LLM, thinking off | LLM, thinking on |
|---|---|---|---|---|
| Read the source cards | — | — | in the prompt: 2.5 s cold / **0.6 s cached** at 27k tokens | same |
| Find identifiers in the question | < 1 ms *(estimate)* | — | — | — |
| Candidate entities from the name index | ms *(estimate; inside the 6 ms below)* | — | — | — |
| Choose the entity | compatibility filter, ms *(estimate)* | **~80 ms** | menu pick **0.30–0.41 s** | — |
| Choose the relation | lexicon, ms | **~80 ms** (same call) | menu pick 0.30–0.41 s; tool call **0.66–0.74 s** | tool call **1.16–2.38 s** |
| Enumerate typed plans | ms *(estimate; not built)* | — | — | — |
| Run the query | ms at 10k nodes; **unmeasured on hubs** | — | — | — |
| Envelope counts and facets | one count query, ms *(Neo4j stored degree; Gremlin walks edges, unmeasured)* | — | — | — |
| Decide next step or stop | validator rule, ms | ~80 ms | 0.66–0.74 s | 1.16–2.38 s |
| Compose and verify | ms | — | — | — |
| Prose narration (optional) | — | — | ~1.5 s for 300 tokens *(derived from about 200 tokens/s)* | more |

**Per question:**

| Path | Time | Source |
|---|---|---|
| Deterministic only | **0.006 s** median | `EXP-2026-09-016` A-3 (September tree) |
| Deterministic + two decision-model calls | about **0.2 s** | derived |
| Loop, 4 controller calls, thinking off, cached cards | about **3 s** | derived |
| Loop, 6 calls, thinking on | about **7–14 s** | derived |
| The old "model writes the query" arm | **182.0 s** median | `EXP-2026-09-016` A-3 (different model, big thinking budgets, whole queries) |

**What this changes:**
- The "about 3,000×" gap belongs to the old arm, not to a controller loop.
- The cost now depends on **how many calls**, **whether thinking is on**, and **whether the
  card prefix is cached**, more than on whether a model is used at all.
- **Design rules that follow:**
  - menu picks with thinking off;
  - thinking only for the planning call;
  - cards first in the prompt, in a fixed order;
  - decision models for every classification.

**Caveats:**
- These are speeds, not accuracy: whether thinking-off picks stay *right* on hard tiers is
  unknown.
- The alias now serves `minicpmv47-35b`, the fourth model behind it.
- There was no concurrency, and the decision model and controller share one GPU.

### 4.4 Errors that teach: agreed

The same as GAIFA's `fix` field. Every specialist response is one of the following:
- `ok`;
- `invalid_request`, with the field, the value given, a code, the valid options with glosses,
  and the nearest matches;
- `empty`, with whether the anchor exists, the relations it actually has with counts, and the
  count in the reverse direction;
- `ambiguous_anchor`, with the compatible candidates;
- `partial`, with the exact total and the limit that was hit.

Every option list is computed from the card, so it is generic. The `empty` case matters most:
it is the 77 of 284 questions where the planner retrieved nothing.

### 4.5 Universal by construction: the typed request is the universal part

MITIGATES was only an example value. The request's *fields* are the property-graph model
itself, which every graph has. Their *values* are computed at runtime from whichever card is
loaded:

| Field | Values come from |
|---|---|
| `source` | the cards of the graphs that are online |
| `anchor.id` | the card's identifier property and scheme; candidates from the graph's own name index |
| `anchor.label` | the card's labels |
| `relation`, `direction` | the card's allowed (source label, relation, target label) patterns, filtered to the anchor's label |
| `target_label` | fixed by the pattern |
| `filters[].property` | the target label's properties in the card |
| `join_key` | identifier properties shared across online cards |

So only two things change per graph: **the card** (built automatically) and **the specialist**
(one compiler per backend: Cypher, Gremlin, later SPARQL). That is the goal as you stated it.

**Three things stand between today's code and that goal.**

1. **Code that still reads language.**
   - `utils/planner/intent.py`, `canonical.py` and `lexicon.py` carry MITRE-specific
     patterns (C-010).
   - The builders re-read the sub-question text.
   - Both go away under typed requests plus decision models.
2. **The request algebra must cover the question shapes of any graph.** Today it has
   describe, expand, join, chain and intersect. Still missing:
   - aggregates (count, group, top-k by property, min/max);
   - property filters and ranges (a located defect: filters in the question never reach the
     query);
   - absence ("X with no Y");
   - variable-length and shortest paths;
   - comparisons and superlatives;
   - time.

   Without these, an unfamiliar graph's questions fall outside the algebra and the system
   abstains.
3. **The card must be complete and automatic.** Required:
   - glosses for every label and relation (written once by an LLM, a build step);
   - identifier-scheme detection;
   - detection of name and alias properties;
   - property types and value statistics;
   - per-relation degree statistics (for hub handling).

   The Synapse transfer has already shown what an incomplete card breaks: opaque `node-<hash>`
   IDs defeated an anchor path.

**Proving it needs graphs Ariadne has never seen** (§6, step 7):
- CypherBench's Wikidata-derived property graphs;
- Synapse graphs;
- the same content in two different schemas;
- a gate that a new graph goes in with **zero code changes**.

---

## 5. The revised system

| Layer | What it does | Model | Time |
|---|---|---|---|
| 0. Build, per graph | Card (schema, patterns, glosses, ID scheme, name and alias properties, degree stats); name, alias and description index | LLM once, for glosses | offline |
| 1. Prelude | Find IDs; retrieve candidates; filter them by the planned relation; enumerate typed plans with pre-executed counts | none | ms |
| 2. Grounding | Entity, relation and question-shape decisions with probabilities; accept, ask or escalate | decision model | ~80 ms per call |
| 3. Fast path | All decisions confident and the plan non-empty → run → compose → verify → return | none | ~0.2 s |
| 4. Controller loop | Only on escalation. Typed tools, option lists, teaching errors, cap of 6 calls | LLM | ~0.7–2.4 s per call |
| 5. Evidence channel | Envelopes (exact totals, facets, labelled sample, `complete`, handle with query and snapshot); full sets by keyset pagination | none | ms per page |
| 6. Compose and verify | Deterministic composer; claim verifier; interpretation check (echo entity and relation, "does the plan answer the question?") | decision model for the interpretation check | ms + ~80 ms |
| 7. Interface | MCP: `ariadne_ask` plus typed primitives; `AnswerEnvelope`; `fast` / `auto` / `thorough` | — | — |

The controller sits on the GAIFA loop, with three changes the reports require:
- option lists instead of free arguments;
- the validator, not the model, decides when to stop;
- results arrive as envelopes and never as raw rows.

---

## 6. What to test, where, and why

In dependency order. Each step is pre-registered under the usual contract (`make
new-experiment`, hypotheses in `PROTOCOL.md` before the run). The thresholds are proposals to
pre-register, not results.

| # | Test | Where | Why | Decides on |
|---|---|---|---|---|
| 1 | **Instrument and attribute.** Per-stage timing, and why each of the 77 empty retrievals was empty (Q57) | dev 284 | Every later decision needs the breakdown. No model, cheap | Share of empties caused by entity, relation, direction or algebra gap |
| 2 | **Exactness contract (no model).** Every primitive returns an exact total and a `complete` flag; keyset pages equal the uncapped query; composer count equals database count; synthetic hubs of 10⁵–10⁶ edges in Neo4j and Gremlin | unit + stress graphs | Your exactness requirement, and the silent 1,000-row cut found today | Zero silent truncations; p95 latency on hubs; identical result sets |
| 3 | **Typed boundary, no loop.** The current planner emits typed plans checked against the card; builders stop reading text | paraphrase tiers T0–T5 + dev 284 | All four reports' first experiment. If it recovers most of the loss, the loop is only for the residue | T1 (synonym verb, 0.4667 today) ≥ 0.80; empties (77 today) halve; T0 stays ≥ 0.98; confident-wrong does not rise |
| 4 | **Grounding decisions.** Deterministic filter vs d3-lite vs LLM menu pick vs LLM free pick, for entity and relation | named, paraphrased and description tiers | The 35% wrong-entity problem, and whether decision models can carry the fast path | Wrong-entity rate at fixed coverage (< 10% before enabling); calibration error; latency |
| 5 | **Envelope and completeness.** Truncation labelled vs unlabelled; sample size k ∈ {0, 5, 20, 100}; controller writes the list vs composer renders it | enumeration subset, inflated past k | Whether the view can stay small without losing the answer | Confident-incomplete rate; enumeration recall and precision; next-step correctness |
| 6 | **Loop vs single shot vs cascade**, thinking on and off, three stopping rules | sealed 282 + tiers | Whether the loop earns its seconds | Gold coverage ≥ 0.75 (0.8611 is the authored-plan ceiling); correctness stays ≥ 0.90; p50/p95 latency; pass^5 |
| 7 | **Universality.** CypherBench subset; Synapse graphs; same content in two schemas; zero-code-change gate | unseen graphs | The plug-and-play claim cannot rest on three MITRE graphs | Records-exact on unseen graphs against CypherBench's published baselines; any code change needed counts as a failure |
| 8 | **As a component.** MCP contract tests; do callers honour abstentions?; prompt injection planted in Synapse-extracted descriptions | MCP harness | Embedding is the goal, and callers believe what they get | Zero unverified claims pass; callers' fabrication rate on abstentions |

Steps 1–3 need no model and no loop. If step 3 lands, the remaining loss is small enough to
see what the loop is actually for.

---

## 7. Open research areas

Each is a gap at least one report says no published work fills. The publishable ones are
marked. All of them need the novelty audit in prompt 7 before anything is claimed.

1. **Exact answers under a bounded controller.** *Publishable.* No KGQA system has measured
   the split where the controller sees counts and a sample while the database lists the full
   set, and nobody measures confident-incomplete answers on graph results (report 2). The ground
   truth is constructed: the database knows the full set. This fits Ariadne's measurement record.
2. **Typed query algebra vs text-to-query on unseen property graphs, across Cypher and
   Gremlin.** *Publishable.* No head-to-head exists on unseen schemas (reports 1 and 3), and
   there is no modern Gremlin generation figure at all (report 4). Porting CypherBench to Gremlin
   and Neptune would itself be a resource.
3. **A calibrated grounding model trained once across graphs.** *Publishable, highest risk.*
   "How often do LLMs correctly pick none?" is unmeasured (report 3). Cross-graph foundation
   models cover link prediction, not grounding for question answering (the ARA deep-research
   pass). The entity-linking literature is large, so the novelty check matters most here.
4. **Checking the interpretation, not only the claims.** Wrong-entity and wrong-relation
   answers pass claim verification (report 3). This is a smaller contribution, best as a section
   of 1 or 3.
5. **Federated agents across engines, and hub-scale latency on property graphs.** No published
   evaluation of either exists (reports 1 and 2). This strengthens C-024 more than it stands
   alone.

**My recommendation:** combine 1 and 2 into one paper. *Exact, verifiable retrieval over
million-node property graphs with a bounded controller, across Cypher and Gremlin.*
- It is what you are building anyway.
- Its ground truth needs no human graders.
- It answers the question an engineer asks first: does it return everything, exactly, and fast?

Item 3 is the follow-on, and the ARA proposal's machine-learning aim.

## 8. Follow-up deep-research prompts

| Prompt | Question |
|---|---|
| [5 — decision models](../../../prompts/2026-10-26-agentic-loop-5-decision-models.md) | What decision models and calibrated classifiers exist for grounding and control decisions, how well calibrated they are, and can one be trained once across graphs? |
| [6 — universal coverage](../../../prompts/2026-10-26-agentic-loop-6-universal-coverage.md) | What operators a graph-universal query algebra needs, how to build complete source cards automatically, and which unseen-graph benchmarks to use |
| [7 — novelty audit](../../../prompts/2026-10-26-agentic-loop-7-novelty-audit.md) | A refutation brief against the five candidate claims in §7 |
