# Round two — what the decision-model, universality and novelty reports change (2026-10-26)

**Status: Draft.** Reads across reports 5, 6 and 7 in this folder, which answer prompts 5–7 in
`docs/prompts/2026-10-26-agentic-loop-*.md`. Round one and its synthesis are in
[`../2026-10-26-agentic-loop/`](../2026-10-26-agentic-loop/SYNTHESIS.md). Report figures keep
their read-status tags; [ABSTRACT] and [SNIPPET] figures are leads, not evidence.

## 1. What each report found, in a paragraph

**Report 5 — decision models.** Small decision models (d3-lite) suit cheap, high-volume
judgments: checking every member of a large set, quick yes/no gates, and a second opinion. They
are the wrong final judge for the hardest decision, choosing the entity.
- In the best head-to-head (LELA, on ZESHEL, [READ]), a pointwise reranker's top pick scored
  27.15, against 76.79–83.11 for a 24–30B model choosing with reasoning.
- Turning reasoning off cut Qwen3-30B-A3B from 76.79 to 54.23.
- "None of these" is weak everywhere: LLM selectors almost always pick something.
- Calibrated thresholds need about 1,000 labelled items, and labels from LLM-written questions
  do not guarantee anything about real users, because the two come from different distributions.

**Report 6 — universal coverage.**
- **The algebra.** It must grow from five operators to about thirteen. Highest value first:
  - property filter;
  - aggregate (count, sum, avg, min, max);
  - rank, with ties returned;
  - verify (yes/no plus the query as proof);
  - type scan (no anchor);
  - group-by that keeps zero groups.

  Then edge-property and time filters, union, and absence. Paths come last.
- **Limits** become per-operator. The row cap applies to samples only, never to what an
  aggregate reads.
- **Compilers:** write one per backend and prove them equal by running every operator on the
  same data in Neo4j and Gremlin, comparing result sets by identifier. Don't adopt a general
  Cypher-to-Gremlin translator: the only large one is unmaintained and passes about 76% of the
  openCypher conformance tests without server plugins, which Neptune can't load.
- **Cards:** every field can be built automatically except meaning (glosses, cardinality),
  which should only rank options, never constrain them.
- **No public Gremlin or Neptune question-answering benchmark exists.** We'd build one by
  mirroring CypherBench.
- **The bigger loss is grounding, not the algebra.** CypherBench keeps entity names verbatim
  on purpose, so it will overstate Ariadne's real accuracy unless the paraphrase tiers are added.

**Report 7 — novelty audit.** Nothing is clear. Every candidate survives only as "first to
*measure* X on property graphs", never "first to *build* X".

| Claim | Verdict | What kills or narrows it |
|---|---|---|
| C-A Exact answers under a bounded controller | Narrowed | Jeffries (2026) measured misleading truncation in document search; Wikidata Search Traces built the bounded view for a graph, but reports accuracy, not completeness |
| C-B Typed requests vs LLM-written queries | Narrowed; the "no Gremlin measurement" half **killed** | EICopilot (2025) measured LLM Gremlin generation; Text2GQL-Bench showed dialect collapse; text2ql has a typed IR for SQL/GraphQL only |
| C-C Calibrated cross-graph grounding | Narrowed | KG-R1 transfers a trained policy across KGs (no calibration); selective QA under domain shift is established |
| C-D Interpretation verification | Mechanism **scooped**; measurement narrowed | Google's PVLDB 2026 text-to-SQL verification; SAGA's type checks; CYGNET shows schema checks catch 0% of valid-but-wrong property swaps |
| C-E Federated agents across engines, hub latency | Narrowed | Data Agent Benchmark (four DBMSs, no graph engines); AgCyRAG (demonstration only); Ozsoy's multi-database roadmap (announced future work) |

## 2. How much weight the audit can bear

- **It was shallow next to August's.** About 18 searches and one subagent pass, against 95
  queries and 41 full reads on 2026-08-26. Most 2026 items were read at abstract level.
  "Not found" is weak evidence for C-A (on graphs), C-C, and C-E's latency half.
- **LELA's ZESHEL numbers are normalized accuracy** (gold always among the candidates) on
  Wikia text, not security descriptions. The direction transfers; the numbers may not.
- **d3-lite's p = 0.614 and 0.791 are one question each.** They are not a mean and not an
  accuracy, as report 5 suspected. They say nothing about calibration.
- **Vendor figures:** d3-lite's 13.6 ms and 518 requests/s are on an AMD MI325X.

## 3. Our own errors this round exposed

1. **Round-one synthesis §7 said no modern Gremlin generation figure exists.** Wrong, and
   our own record already said so: `RELATED_WORK.md` carries EICopilot (`[F-EICO]`, 82.14%
   execution correctness, deployed at Baidu), conceded in the 2026-08-26 audit. I relied on
   round-one report 4 instead of checking the record. EICopilot's figure is an expert rating
   with partial credit, from a trained, hand-exemplified system on one graph. So a same-graph,
   result-set comparison on unseen graphs is still open, but "no measurement exists" is not.
2. **Prompt 7's brief described Ozsoy (2026) as a federated security-graph agent.** Also
   wrong. `RELATED_WORK.md` has it right (`[F-OZSOY]`): a Neo4j position paper on multi-database
   Text2Cypher that owns the problem statement, with seven hand-made questions. It is also the
   group most likely to publish overlapping work.
3. **Round-one report 2 filed KG-Guard as an under-enumeration paper.** Its abstract frames
   it as hallucinated-answer-node detection. Don't cite it for under-enumeration.
4. **Round-one report 4 described CYGNET as a text-to-Cypher accuracy result.** It is a
   pre-execution validation gate. Its own generation-accuracy deltas are −0.01 to +1.35 points.
   The 77.6% Gemma figure is unverified and should not be quoted.

## 4. What this changes

### 4.1 The research direction

All five candidates become **measurements**, each with the strongest existing fix as a
baseline (truncation labels for C-A, a CYGNET-style corrector for C-B, round-trip critique for
C-D).

**Recommended spine: C-B.**
- *The question:* on the same unseen property graphs, with the same models, do typed requests
  compiled per backend beat LLM-written Cypher and LLM-written Gremlin? Is the typed path's
  accuracy the same on both backends while free generation drops on Gremlin?
- *Why it leads:* it tests Ariadne's central design decision directly, and it has the clearest
  gap.
- *Why now:* there are active competitors (Ant Group/TuGraph advertises Gremlin in its
  multi-language framework; text2ql has "full-set evaluation planned"; Ozsoy/Neo4j).
- *The setup:* Amazon Neptune serves openCypher and Gremlin over one copy of the data, which
  removes data confounds and fits the ARA proposal.

**C-A and C-E as sections of the same study.** They reuse its graphs and harness:
- C-A: enumeration questions whose answers exceed the row cap, with three arms: raw truncated
  rows, rows plus a truncation label, and envelope plus composer.
- C-E: cross-source questions, with latency split by anchor degree.

**C-C is the follow-on** (it needs training and a cross-graph corpus). **C-D is a section**,
not a paper.

**A prerequisite the reports reveal together:** C-B can't be run fairly until the typed algebra
covers CypherBench's shapes (grouping, optional match, time-sensitive, union). A five-operator
typed arm would lose on coverage, not on approach. Report 6's first six operators come first.
And the record's `[T-OZS]` entry warns of the trade: constraining raised execution success from
63.8 to 86.7% while empty predictions rose from 11 to 36. The typed arm will abstain more, so
abstention precision has to be reported beside accuracy.

### 4.2 Grounding the entity

The earlier proposal to let d3-lite decide entities is withdrawn. Staged design:

1. **Exact match** on identifier or name (deterministic, milliseconds; already 1.0 on the
   original tier).
2. **Retrieval:** BM25 plus embeddings over names and build-time glosses.
3. **Schema-compatibility filter** from the card: the candidate's label must take part in a
   pattern the question needs, and it must actually have the relation.
4. **An explicit "none of these"**, plus a *structural* none signal (no candidate has the
   required relation). Never rely on the selector's own pick to say "none".
5. **Slow path only:** the controller chooses from at most ten options with thinking on and
   three samples. d3-lite gives an independent yes/no on the chosen candidate.
6. **Ask** when two candidates survive with close scores. When Ariadne is embedded, "ask"
   returns the candidate list to the caller.

**Speed.** The 0.7 s thinking-off figure from the probe applies to menu picks, not to hard
entities. LELA spent 11.7–44.4 s per mention with 3–10 samples on its hardware. Ours is
unmeasured, but expect the hard-entity slow path to cost seconds to tens of seconds. The fast
path (steps 1–4) stays in milliseconds.

### 4.3 Where decision models fit (revises `decision-model-tests.md`)

| Step | Round-two verdict |
|---|---|
| D1 source routing | Keep as a candidate; a wrong route fails visibly and falls back |
| D2 entity grounding | **Second opinion only**, never the final judge (LELA: pointwise top-1 27 against 77–83 for an LLM with reasoning) |
| D3 "none" | Combine with structural signals; no selector is good at it |
| D4 relation choice | Strong candidate: menus are small (3–10). On a near-tie, run both relations (two cheap queries) and let the results decide |
| D5 question shape | **Router only, no authority.** Shape should follow from the typed request the controller builds |
| D6 property filter | Candidate; untested anywhere |
| D7 answer type | Candidate; catches answers one hop short |
| D8 plan check | **Advisory only.** Running the plan judges it better; for the binding, compare round-trip back-translation (C-D) |
| D9 sufficiency | Cheap pre-check, loose threshold; the validator keeps the final say |
| D10 membership by meaning | **Best fit.** d3-lite on every member, embeddings for ordering only, controller re-judges the uncertain band plus a 2–5% audit. Adopt if agreement with the controller is κ ≥ 0.8 at under a tenth of its time |
| D11 ask or guess | Derived from D2/D4 margins |
| D12 untrusted text | Keep. All model classes are steerable by injected text, so identity must never rest on description text alone |

**On "decision models beat LLMs on speed and accuracy".**
- *Speed:* yes, measured (80 ms against 300–700 ms here; 518 requests/s batched on the vendor's
  GPU). This supports the vLLM batching server.
- *Accuracy:* not shown, and for entity choice the evidence points the other way.

So the tests matter more than the hypothesis.

### 4.4 Calibration

1. **Generate calibration sets from each card** (a build step): sample anchors and patterns,
   write questions at every paraphrase tier, and know the gold by construction. Make them harder
   than real traffic.
2. **Measure once** how far thresholds set on synthetic questions drift on the real sealed
   banks.
3. **Report every guarantee as "valid for the synthetic distribution"**, never for real users.

How many items the guarantee needs ("rule of three"): about 300 accepted, error-free items to
certify a 1% wrong-entity rate, about 60 for 5%, and about 30 for 10%.

### 4.5 Algebra, compilers and cards

- **Operators,** in order: filter, aggregate, rank-with-ties, verify, scan, group-with-zeros;
  then edge filter, union, absence; then reach and shortest path.
- **Semantics to fix in the specification:**
  - deduplicate on identifier, never on display name;
  - argmax returns every tied row plus a tie count;
  - filters mean "property present and satisfies the predicate", with absence as its own
    operator;
  - paths carry an explicit mode, defaulting to acyclic;
  - the card records whether nodes can carry one label or several.
- **Per-operator limits:** the depth cap of 3 applies to expand chains, not to `reach`. The
  1,000-row cap applies to samples, never to aggregates. This independently backs the exactness
  rule.
- **Cards:** built deterministically, then linted (missing id or name properties, mixed types,
  hubs, near-duplicate labels). Glosses and alias groups are hints a person can review.
- **The zero-code-change protocol for adding a graph:**
  1. Register it.
  2. Build the card.
  3. Lint the card.
  4. Generate probe questions per pattern and operator.
  5. Run them on the deterministic path.
  6. Promote the graph if they pass.

### 4.6 Tests (revises the round-one order, still unscheduled)

- **The Gremlin mirror is now required, not optional.** Load CypherBench's seven test graphs
  into Neo4j and Gremlin (Neptune when credits allow). It is the C-B harness, the compiler
  differential test and the first public Gremlin result-set benchmark in one.
- **Add the paraphrase tiers to CypherBench questions,** since its names are verbatim.
- **Two-schema pair:** ATT&CK as today and in a STIX-style relationship-object model. That
  separates schema difficulty from content difficulty.
- **Count CypherBench's categories from the released data** (`match_category`,
  `return_pattern_id`) before choosing operator priorities. Report 6 could only see them as a
  chart.

### 4.7 The ARA proposal (deadline 2026-11-04)

C-B and C-E on Neptune, which serves openCypher and Gremlin over the same data, are a closer
fit to the Amazon call than the one-pager's current research questions. RQ1–RQ5 should be
re-read against §4.1 before submission.

## 5. What else could be done

| Option | What it buys | Cost |
|---|---|---|
| A deeper novelty audit on C-B and C-E only, with full reads | Brings the two priority claims up to August's standard before anything is written | One deep-research run |
| A card-driven question generator | Serves calibration (§4.4), probe questions (§4.5), paraphrase tiers on CypherBench (§4.6) and the C-B harness. The single highest-leverage piece of infrastructure | Days |
| The CypherBench mirror in Neo4j and a Gremlin server | The C-B harness and the compiler test | Days, plus storage for 7.8M entities |
| The six-operator algebra extension | Removes the coverage handicap before C-B | Weeks |
| A competitor watch on Ozsoy/Neo4j, Ant Group/TuGraph (Text2GQL), text2ql and the SAGA authors | Early warning for C-B and C-E | Minutes a month |
