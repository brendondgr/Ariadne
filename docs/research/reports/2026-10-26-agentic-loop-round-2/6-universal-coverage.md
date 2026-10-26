# Making Ariadne Graph-Universal: Question Shapes, a Typed Operator Set, Multi-Backend Compilation, Automatic Source Cards and a Universality Test Suite

Ariadne can be made graph-universal, but only if its typed algebra grows from five operators to about twelve: property filters, aggregates, superlatives with ties, boolean verify, anchorless type scans, group-by with zero groups, edge-property (temporal) filters, union and absence. Most of the measurable benchmark mass sits in the first eight. Path operators matter for graph-native workloads but barely appear in KGQA benchmarks. The source card can be built automatically from the live store, except for meaning (glosses, cardinality, entailment), which no evidence shows can be derived reliably. And no public Gremlin or Neptune QA benchmark exists, so Gremlin universality has to be tested on suites you build yourself.

## TL;DR

- **Shapes and operators.** Lookups dominate the benchmarks with published counts. In GrailQA, 83.2% of questions use no function and 68.9% use one relation [READ]. The tail is count (5.4%), superlatives (6.4%) and comparatives (5.0%) [READ]. KQA Pro adds count (11.5%), superlative-among (4.6%) and multi-hop (73.7% of questions) [READ]. CypherBench, Spider and Text2GQL-Bench add group-by, optional match, time-sensitive and union shapes, plus variable-length paths. Ariadne's current algebra (describe, expand, join, chain, intersect) covers roughly the "no function, no literal filter" slice. Add filter, count/aggregate, argmax/sort with ties, verify, type scan, group-by, edge-property filter, union and difference to cover essentially all published benchmark shapes. Bounded reachability and shortest path come last.
- **Backends.** One IR (intermediate representation) can compile to several graph languages, but the evidence on correctness is weak. GraphQ IR claims "lossless" compilation to SPARQL, KoPL, lambda-DCS and Cypher [ABSTRACT]. Cypher-for-Gremlin is the only large Cypher-to-Gremlin translator. At v1.0.0, openCypher's GitHub release notes (March 2019) report 669/886 (76%) openCypher TCK M10 scenarios passing with plain Gremlin and 815/886 (92%) with server extensions; the final release, v1.0.4, reports 91.75% [SNIPPET]. It is unmaintained. The divergences that will bite Ariadne are bag vs set results, missing-property handling, default path semantics (openCypher uses trail; ISO GQL defaults to walk), single vs multiple labels, and tie handling under LIMIT. Ariadne should own a small compiler per backend and test it differentially, rather than adopt a general translator.
- **Cards and testing.** Labels, (source, rel, target) patterns with counts, property types, value statistics, degree percentiles, identifier and name properties, and join keys can all be computed deterministically (B: one automatic build step per graph). Neptune now exposes label triples and property types through a schema API [READ]. LLM-written glosses are only a ranking aid; their accuracy evidence comes from SQL columns and is mixed. For testing, use CypherBench's seven unseen test graphs (result-set scoring), ZOGRASCOPE, Text2GQL-Bench and GrailQA-style surface forms. Build your own Gremlin mirror and a "same content, two schemas" pair, because no public suite separates schema difficulty from content difficulty for property graphs.

## Key Findings

1. **Benchmark frequencies are generator artefacts, not user distributions.** GrailQA's skew comes from crowdsourced paraphrases of sampled logical forms. CypherBench is deliberately "balanced" across 12 patterns.\[1\]\[2\] KQA Pro samples 9 asking strategies at roughly 10% each.\[3\] A "95% coverage" target is therefore benchmark-specific. The defensible target is 100% coverage of each benchmark's logical-form *types*, weighted by Ariadne's own query logs once they exist.
2. **The operator gap is smaller than the entity-linking gap.** Ariadne scores 0.0000 on paraphrased-name and description-only tiers, so grounding, not the algebra, is the bigger current loss. CypherBench intentionally preserves entity names verbatim in its questions "to avoid introducing the additional complexity of entity linking" [READ].\[1\]\[2\] CypherBench will therefore overstate Ariadne's real-world accuracy. GrailQA's mined surface forms ("Obama", "FDA") are the better grounding test [READ].\[4\]
3. **Gremlin is the risk, not Cypher.** Text-to-GQL results show that dialect matters enormously for LLMs: ISO-GQL zero-shot execution accuracy is at most 4% versus about 50% with 3-shot prompting [READ, Text2GQL-Bench v1]. The v2 abstract (arXiv 2602.11745v2) adds that "fine-tuning an 8B model reaches or exceeds zero-shot large models, indicating unfamiliarity – rather than model capacity – is the primary barrier" [ABSTRACT]. Ariadne avoids this by never letting the LLM write queries, which is the right call. But it moves the risk into the hand-written compiler, and no public Gremlin QA benchmark exists to check it.
4. **Several brief assumptions conflict with universality.** These are: max traversal depth 3 (blocks variable-length and shortest-path operators); max rows 1000 (must apply only to the *sample*, never to aggregates); and a single label per node (TinkerPop allows only one label; Neo4j allows several).

## 1. Question-shape taxonomy with frequencies

Definitions used below:
- **S-expression**: GrailQA's prefix-notation logical form, e.g. `(AND Theater (JOIN staged_here …))`.
- **KoPL**: KQA Pro's "Knowledge-oriented Programming Language", a sequence of 27 functions such as Find, Relate, FilterConcept and Count, composed as a tree.\[5\]
- **lambda-DCS**: Liang's lambda dependency-based compositional semantics, a variable-free logical form with join, intersection, aggregation and argmax.

### Unified taxonomy

| # | Shape | Example | Notes |
|---|---|---|---|
| 1 | Lookup / attribute | "What platform is Beats of Rage for?" | one relation or property from an anchor |
| 2 | Multi-hop chain | "Lakes in countries the Natara flows through" | 2–4 relations |
| 3 | Intersection (AND) | "Cyclone that affected Palau and Hong Kong" | two anchors |
| 4 | Union (OR) | | |
| 5 | Negation / absence / difference | "Techniques with no mitigation" | |
| 6 | Count | "How many titles share genre with X?" | |
| 7 | Other aggregate (sum/avg/min/max) | "Average lifespan of taxa that feed on Leporidae" | |
| 8 | Group-by (incl. zero groups) | "Each ATR model with its accident count" | needs outer join |
| 9 | Superlative / argmax / sort-limit | "Season with most rushing yards" | ties matter |
| 10 | Comparative / numeric or date range filter | "Engines with fewer than 3 chambers" | |
| 11 | Comparison between named entities | KQA Pro SelectBetween | |
| 12 | Verify / boolean | "Is X's height > 180 cm?" | |
| 13 | Qualifier / edge-property / temporal validity | "Population in 2010", "drafted in 2003" | |
| 14 | String operation | "K-pop bands starting with T" | |
| 15 | Global (no named entity) | "List all teams" | type scan |
| 16 | Two-intention / multi-output | "Team of Messi and how many matches?" | |
| 17 | Variable-length reachability | "Funds flowing back to Alice via transfers" | |
| 18 | Shortest path | | |

### Frequencies per benchmark (only where counted in text)

| Benchmark | Graph(s) | Counted shares | Read status |
|---|---|---|---|
| GrailQA (WWW 2021, peer-reviewed), 64,331 Qs, Freebase | 86 domains | Functions: none 53,526 (83.2%), count 3,463 (5.4%), superlative 4,111 (6.4%), comparative 3,231 (5.0%). Relations: 1 = 44,340 (68.9%), 2 = 16,610 (25.8%), 3 = 3,254 (5.1%), 4 = 127 (0.2%). Answer cardinality >1: 20,287 (31.5%) | [READ]; percentages computed by me from the counts\[4\] |
| GrailQA zero-shot dev (GrailQA++ paper, IJCNLP-AACL 2023) | Freebase | one-hop reasoning path = 78.5% of zero-shot samples; 3-hop = 0.53%\[6\] | [SNIPPET] (lead) |
| KQA Pro (ACL 2022, peer-reviewed), 117,970 Qs, Wikidata subset | 16,960 entities, 363 predicates, 846 attributes\[5\] | 9 asking types; SelectAmong 4.6%, Count 11.5%, others "more or less than 10%". Multi-hop 73.7%; ≥5 hops 4.7%\[3\] | [READ]; the other per-type shares exist only as a chart image (confirmed by the subagent) |
| LC-QuAD 2.0 (ISWC 2019, peer-reviewed), 30,000 Qs, Wikidata/DBpedia | 21,258 entities, 1,310 relations\[7\] | 10 types (single fact, single fact with type, multi-fact, fact with qualifiers, two intention, boolean, count, ranking, string operation, temporal aspect) over 22 templates;\[8\] **no per-type counts in text** | [READ] (via subagent); a later study (Ferguson et al., arXiv 2206.02737) found "no direct correspondence" between the 10 types and the released metadata [READ via subagent]\[9\] |
| MetaQA (AAAI 2018, peer-reviewed), WikiMovies KG | 43k entities, 9 relations, 135k triples | 1-hop / 2-hop / 3-hop test sets of 9,947 / 14,872 / 14,274 questions; pure chains, template-generated | [SNIPPET] (lead); one study reports 21% of 2-hop and 56% of 3-hop test labels wrong [SNIPPET] (lead)\[10\]\[11\] |
| CypherBench (ACL 2025; arXiv 2412.18702), 11 property graphs, 7.8M entities | 4 train + 7 test graphs | 12 match patterns (7 basic: all isomorphisms with one answer node and ≤2 edges; 5 special: comparison, grouping, optional match, time-sensitive, union) × 6 RETURN templates (NAME, PROPERTY, SORT, WHERE, AGGREGATE, ARGMAX). Test 2,488 Qs.\[1\]\[2\] **Per-category shares only in Fig. 4 (image)** | [READ]; the HF release shows 10,882 rows vs the paper's 11,305 (unresolved)\[12\] |
| Spider (EMNLP 2018), 10,181 Qs, 200 DBs | relational | ORDER BY 1,335, GROUP BY 1,491, nested 844, HAVING 388 | [SNIPPET] (lead; unit, question vs SQL, unclear)\[13\] |
| Spider / BIRD dev (EMNLP 2023 analysis) | relational | LIMIT 1 in 16% of Spider dev and 16% of BIRD dev queries (tie-sensitive) | [SNIPPET] (lead)\[14\] |
| Text2GQL-Bench (arXiv 2602.11745, preprint) | v1: 34 DBs, 13 domains, Cypher + ISO-GQL, 178,184 (question, query) pairs. v2 (Aug 2026, retitled "Text2GraphQuery-Bench") adds SQL/PGQ, with "267,276 (Question, Graph Query) pairs across 34 databases and 13 domains" [ABSTRACT] | Difficulty: Easy 21.39%, Medium 43.62%, Hard 30.23%, Extra Hard 4.76%; explicitly includes variable-length and reachability queries | [SNIPPET] for the difficulty table (lead); v1 design [READ] |
| Spider 2.0, BIRD, Neo4j Text2Cypher 2024 | | **No published per-shape frequency found.** Text2Cypher 2024 has 44,387 instances; CypherBench reports 49% of them are not linked to any database\[1\]\[2\] | [SNIPPET] |

**Interpretation.** In the only benchmark with full counts (GrailQA), Ariadne's current algebra covers at most the 83.2% "no function" slice, less the questions with literal constraints, which need property filters. Adding count, argmax/argmin and comparison filters reaches 100% of GrailQA's logical-form types *by construction*: GrailQA's grammar contains nothing else. KQA Pro adds verify, qualifiers, union and between-entity comparison. CypherBench adds group-by with zero counts, time-sensitive edge properties and union. Path operators (17–18) appear essentially only in graph-native suites (Text2GQL-Bench, FinBench-derived queries). I found **no** published frequency for negation/absence in any KGQA benchmark above. DBLP-QuAD has "Negation" and "Double Negation" template classes [SNIPPET],\[15\] and Spider uses NOT IN/EXCEPT, but I have no share for either. For a security graph, "techniques with no detection" is probably far more common than benchmarks suggest; that is an inference, not evidence.

## 2. Operator sets in existing intermediate representations

| IR / tool set | Type | Covers | Does not cover |
|---|---|---|---|
| KoPL (KQA Pro) | 27 functions; trained parser (T) | Find, Relate (with direction), FilterConcept, FilterStr/Num/Year/Date with =, ≠, <, >; qualifier filters; And/Or; Count; SelectAmong (argmax/argmin); SelectBetween; Verify; QueryAttr/QueryRelation/qualifier queries\[3\]\[5\] | no group-by, no negation, no paths [READ] |
| S-expressions (GrailQA) | AND, JOIN, R (reverse), COUNT, ARGMAX/ARGMIN, LT/LE/GT/GE | chains to 4 relations, intersection, count, superlative, comparative [READ]\[16\] | no union, negation, group-by, paths |
| lambda-DCS | join, intersection, union, negation, aggregation, superlatives | broadest classical logical form | no paths; never tied to property graphs |
| SPARQL algebra | BGP (basic graph pattern) join, OPTIONAL (left outer join), UNION, FILTER, MINUS/NOT EXISTS, GROUP BY + aggregates, property paths (reachability only; paths cannot be returned), bag semantics [SNIPPET, G-CORE] | essentially complete for 1–16 | no shortest path; property paths return endpoints only\[17\] |
| Cypher | MATCH patterns, OPTIONAL MATCH, WHERE incl. pattern predicates (`NOT (a)-[:R]->()`), WITH aggregation (implicit grouping), UNION, ORDER BY/LIMIT, variable-length `*m..n`, shortestPath | all 18 | default trail semantics on variable-length paths |
| Gremlin | step pipeline: V/E, has, out/in/both, where, not, and/or, union, coalesce/optional, group/groupCount, count/sum/mean/min/max, order/limit, dedup, repeat/until/emit, simplePath, path | all 18 in principle | evaluates by homomorphism/arbitrary paths [SNIPPET, G-CORE]; idioms differ sharply from declarative patterns\[17\] |
| Middleware KB tools (EMNLP 2024) | 7 tools; LLM agent loop (P) | get_relations, get_neighbors, get_attributes, intersection, count, argmax/argmin, comparator filters [SNIPPET] | no union, negation, group-by, paths\[18\]\[19\] |
| QueryAgent PyQL (ACL 2024) | Python-wrapped SPARQL builder; LLM writes code (P) | covered in the earlier pass; mirrors SPARQL constructs | — |

**Minimal operator set for ~95% (my synthesis, not a measured result).** No paper reports a minimal operator set that covers 95% across these benchmarks. I found no union-of-benchmarks coverage study. From the counted data, {anchor, expand, chain, intersect, filter, count, argmax/argmin} covers 100% of GrailQA by grammar. Adding {verify, union, attribute/qualifier filter, between-entity compare} covers KQA Pro's 9 types. Adding {group-by with outer join, type scan, other aggregates, sort} covers CypherBench's 12 patterns × 6 templates. That union of 12–13 operators is the minimal set. Paths and absence are needed for graph-native and security use but are not measured by these benchmarks.

**Hard operators for Gremlin specifically:**
- *Group-by with zero groups*: needs `coalesce`/`optional` or `project().by(out().count())`.
- *Absence*: `not(out('R'))` is easy for a single edge, but harder for "no path of type R1/R2".
- *Union as sets*: `union()` yields bags, so `dedup()` must be added explicitly.
- *Missing properties*: `values('p')` silently drops elements that lack the property, so averages and counts over properties differ from Cypher's null-based semantics. This is a well-known Gremlin behaviour; I did not re-verify it against current TinkerPop docs in this pass.
- *Shortest path*: idiomatically `repeat(...).until(...)` with `simplePath()`, `path()` and `limit(1)`, which is only "shortest" under breadth-first evaluation. I did not verify whether Neptune supports TinkerPop's OLAP `shortestPath()` step; treat it as unsupported until tested.
- *Ties in argmax*: `order().by(p, desc).limit(1)` drops ties, as SQL LIMIT 1 does.

## 3. One algebra, many backends

**Systems:**
- *GraphQ IR (EMNLP 2022, peer-reviewed).* Natural-language-like IR; a trained neural parser maps text→IR (T); a deterministic compiler maps IR→SPARQL, KoPL, lambda-DCS and Cypher. Evaluated on KQA Pro, Overnight, GrailQA and MetaQA-Cypher "under standard i.i.d., out-of-distribution, and low-resource settings", with "a maximum 11% accuracy improvement" over prior work (Nie, Cao, Shi et al., arXiv 2205.12078) [ABSTRACT]. "Losslessly compiled" is the authors' claim; I found no independent check of translation correctness. The paper notes that its design "still require[s] non-trivial manual efforts" [SNIPPET].\[20\] A transpiler package (graphq-trans) exists.\[21\]
- *Text2GQL-Bench Graph-IR (preprint, 2026).* Parses Cypher ASTs into a Graph-IR and emits ISO-GQL. It also converts BIRD SQL→Cypher→GQL using open-source tools [READ].\[22\] No translation-correctness rate is reported separately from the benchmark's quality checks.
- *Cypher for Gremlin (openCypher, software; deterministic, no per-graph step).* At release 1.0, 669/886 TCK M10 scenarios (76%) passed with plain Gremlin and 815/886 (92%) with Gremlin server extensions (openCypher v1.0.0 release notes). The final v1.0.4 release reports "Passing: 879, Failing: 79, Coverage: 91.75%". Translation was verified on Neptune, Cosmos DB, JanusGraph and TinkerGraph [SNIPPET]. It is no longer maintained [SNIPPET].\[23\] openCypher's own "Cypher for Gremlin" slides list as "Major limitations" that "Multiple labels and label modification are not supported", since "TinkerPop graph elements have a single, immutable string label", with "No plans for a workaround". They also list length, nodes, percentileCont, percentileDisc, properties, relationships, size, toBoolean, toFloat, toInteger and toString as needing the server plugin [SNIPPET]. Neptune cannot load such plugins, so the 76% figure is the realistic ceiling there.
- *SPARQL→Gremlin (Gremlinator, arXiv 1801.02911).* Covers SPARQL basic graph patterns and modifiers. REGEX is unsupported because TinkerPop Gremlin lacked it [SNIPPET].\[24\]

**Where the languages differ in ways that change answers:**
- *Bag vs set semantics.* A bag keeps duplicates; a set does not. Cypher MATCH, SPARQL [SNIPPET] and Gremlin traversers all produce bags, one row per match. CypherBench's gold queries use `WITH DISTINCT n` on the node before projecting names. The paper found that the main error on its simplest pattern was "incorrect deduplication — merging distinct entities that have the same name" [READ].\[1\]\[2\] Rule for Ariadne: dedup on the **identifier**, never on the display name.
- *Path semantics.* Cypher 9 uses no-repeated-edge (trail) semantics; Gremlin follows arbitrary-path semantics [SNIPPET, G-CORE].\[17\] ISO GQL (ISO/IEC 39075:2024, the first ISO property-graph query language) makes the choice explicit through restrictors (WALK, TRAIL, SIMPLE, ACYCLIC) and selectors (ANY SHORTEST, ALL SHORTEST, SHORTEST k). WALK requires a selector to avoid infinite results, which gives 27 meaningful path modes [SNIPPET].\[25\]\[26\] One engine reports that GQL's WALK default against openCypher's TRAIL default caused 9 of its 10 divergences in a GPML conformance suite [SNIPPET; GitHub issue, low authority].\[27\] Ariadne's path operator must therefore carry an explicit mode, defaulting to ACYCLIC for reachability, and every compiler must implement exactly that mode.
- *Null and missing properties.* Cypher returns null for missing properties and uses three-valued logic in WHERE. Gremlin `has`/`values` treat absent properties as non-matching and drop them. This changes `avg`, `count(prop)`, `NOT (p = x)` and range filters. Ariadne should define filter semantics as "property present and satisfies the predicate", with absence as its own operator.
- *Ordering and ties.* No backend guarantees order without an explicit sort. LIMIT 1 is tie-sensitive in 16% of Spider/BIRD dev queries [SNIPPET].\[14\] The argmax operator should return **all** tied rows plus a tie count in the envelope.
- *Labels.* Neo4j nodes can carry several labels; TinkerPop allows one; Neptune supports multi-labels through a delimiter, with "basic multiple-label support" in Cypher-for-Gremlin [SNIPPET].\[28\]\[29\] The card must record a label mode.
- *ISO GQL as a target.* Few engines implement it fully, and LLM generation of GQL is poor zero-shot. As a *compiler target* it is attractive, since its path modes match Ariadne's needs exactly, but there is no evidence yet on engine conformance at scale.

**Recommendation.** Do not adopt a general Cypher→Gremlin translator. Write one compiler per backend for the ~13 typed operators only (a few hundred lines each). Prove equivalence by **differential testing**: run every operator instance on the same data loaded in both Neo4j and a TinkerGraph/Neptune mirror, and compare result *sets* keyed by identifier. This is the same execution-equivalence idea CypherBench uses, applied to the compiler.\[1\]

## 4. Recommended operator set (ranked by coverage evidence)

| Rank | Operator (typed fields) | Evidence of need | Cypher | Gremlin | Notes |
|---|---|---|---|---|---|
| 1 | **anchor**(source, label, id \| name-candidate-set) | every anchored Q; GrailQA 1-relation 68.9% | `MATCH (n:L {idProp:$id})` | `g.V().has(L,idProp,id)` | exists today (describe) |
| 2 | **expand**(rel-set, direction, target label) | all chain Qs | `-[:R1\|R2]->(m:T)` | `out('R1','R2').hasLabel(T)` | allow a relation *set* for LLM-built duplicate relations |
| 3 | **filter**(property, op ∈ {=,≠,<,≤,>,≥,between,prefix,contains,in}, typed value) | GrailQA comparatives 5.0%; KQA Pro literal filters; CypherBench WHERE; LC-QuAD string ops | `WHERE n.p < $v` | `has('p', lt(v))`; `TextP.startingWith` | the brief's top gap; value type comes from the card |
| 4 | **chain** (compose 2–4 expands) | GrailQA ≥2 relations 31.1%; KQA Pro multi-hop 73.7% | multi-segment pattern | step sequence | exists today |
| 5 | **intersect**(set A, set B) on id | GrailQA AND; KQA Pro And | two patterns sharing a variable | `where(within)` or `match()` | exists today (two-anchor) |
| 6 | **aggregate**(fn ∈ {count, count-distinct, sum, avg, min, max}, property?) | GrailQA count 5.4%; KQA Pro count 11.5%; CypherBench AGGREGATE | `count(DISTINCT n)`, `avg(n.p)` | `dedup().count()`, `values(p).mean()` | always computed in the DB; never capped by the 1000-row limit |
| 7 | **rank**(property \| aggregate, asc/desc, k, ties=all) | GrailQA superlatives 6.4%; KQA Pro SelectAmong 4.6%; CypherBench SORT/ARGMAX | `ORDER BY … LIMIT` + tie query | `order().by(...)` + tie filter | return ties explicitly |
| 8 | **verify**(sub-plan, predicate) → boolean + witness | KQA Pro Verify; LC-QuAD boolean | `RETURN EXISTS {…}` | `hasNext()` / `count().is(gt(0))` | witness = the executed query and record |
| 9 | **scan**(label, filters) | CypherBench global queries; GrailQA superlatives without a topic entity | `MATCH (n:L)` | `g.V().hasLabel(L)` | needs hub and size guards from the card |
| 10 | **group**(key path, aggregate, include-empty) | CypherBench grouping and optional match; Spider GROUP BY | `OPTIONAL MATCH … WITH n, count(m)` | `project('k','c').by(...).by(out(R).count())` | include-empty is the Gremlin trap |
| 11 | **edge-filter**(rel property, op, value; validity interval) | KQA Pro qualifiers; CypherBench time-sensitive; LC-QuAD temporal | `-[r:R]->` `WHERE r.start <= $t < r.end` | `outE(R).has('start',lte(t))…inV()` | needs relationship properties in the card |
| 12 | **union**(A, B) on id | KQA Pro Or; CypherBench union | `UNION` | `union(a,b).dedup()` | set semantics |
| 13 | **difference / absence**(A, minus pattern) | DBLP-QuAD negation; Spider NOT IN/EXCEPT (no shares found) | `WHERE NOT (n)-[:R]->()` | `not(out('R'))` | high value for security graphs |
| 14 | **compare**(entity A, entity B, property) | KQA Pro SelectBetween | two lookups | two lookups | can compose from 1+3 |
| 15 | **reach**(rel-set, min..max hops, mode=ACYCLIC) | Text2GQL-Bench "graph-native"; FinBench | `-[:R*1..k]->` | `repeat(out(R)).times/until… simplePath()` | conflicts with depth cap 3; make the cap per-operator |
| 16 | **shortest**(A, B, rel-set, max hops) | none in KGQA benchmarks | `shortestPath(...)` | BFS `repeat…until…path().limit(1)` | lowest priority; verify Neptune support |

The controller chooses only operator names and enumerated field values from per-step menus. That keeps the existing "choose from a short list" design.

## 5. Automatic source-card pipeline (B: one-time automatic build per graph)

| Field | Derivation | Cost on millions of nodes | Failure on LLM-built graphs |
|---|---|---|---|
| Labels, rel types | Neo4j `db.labels()`, `db.relationshipTypes()`; Gremlin `g.V().label().groupCount()`; Neptune graph summary API (node/edge labels with counts; engine ≥1.2.1.0) [SNIPPET]\[30\] | cheap via catalogue; full scan in Gremlin | near-duplicate labels ("Malware"/"MalwareFamily"); case and plural variants\[31\] |
| (source, rel, target) patterns with counts | exact aggregation over edges, batched; Neptune "Property graph schema" returns label triples and property data types, "designed for LLM query generation" [READ]; Neptune detailed summary gives nodeStructures/edgeStructures [SNIPPET]; CypherBench used `db.schema.visualization` and `apoc.meta.data` [SNIPPET]\[1\]\[31\]\[32\] | one edge scan | spurious patterns from extraction errors; keep counts so that rare patterns (e.g. count < 5) can be flagged\[31\] |
| Property names, types, fill rate | Neo4j `db.schema.nodeTypeProperties()`; sample plus full type check; Neptune schema API types | scan or sample | mixed types in one property (string "2019" vs int); CypherBench had to convert types and units by hand in its RDF→PG engine [READ]\[1\]\[2\] |
| Value statistics | min/max/percentiles for numerics and dates; top-k values and distinct ratio for strings | scan | units embedded in strings; CypherBench puts units in property names (e.g. `runtime_minute`) [READ]\[1\]\[2\] |
| Identifier property and scheme | distinct ratio = 1.0 and non-null; regex induction over values (e.g. `T\d{4}(\.\d{3})?`, `CWE-\d+`) | scan | opaque UUIDs or hash ids carry no scheme; then join keys must come from value overlap |
| Cross-source join keys | inclusion test on value sets between identifier-like properties of different cards (standard data profiling; no KGQA-specific source found) | hashed sets | ids reformatted by the extractor ("CWE-79" vs "79") break joins; normalise via the induced regex |
| Name and alias properties | string, high distinct ratio, short, natural-language tokens; list-of-string properties as aliases | scan | names missing or duplicated across distinct nodes (the CypherBench dedup error) |
| Degree statistics | per (label, rel, direction): p50/p95/p99/max degree; flag hubs above a threshold | one pass | MetaQA's KG is long-tailed (median 4, max 4,431 triples per entity) [SNIPPET]; LLM graphs create giant hubs such as "Organization" or "Attack" nodes\[33\] |
| Cardinality, participation, entailment | **not derivable reliably**: CypherBench determined these manually "due to the presence of missing data" [READ]\[1\]\[2\] | — | estimate from data as *soft* hints only |
| Glosses (one line per label and relation) | LLM from name plus sampled triples (B). Evidence is from SQL only: generated column descriptions improved text-to-SQL accuracy but models "struggle with columns that exhibit inherent ambiguity" [ABSTRACT]; an automatic description method gained 0.93% on BIRD, "37% of human-level" [ABSTRACT] | a few LLM calls per label | glosses inherit extraction confusion; use only to rank menu options, never as constraints\[34\]\[35\] |
| Safety limits | depth, rows and timeout from degree statistics; per-operator caps | — | — |

**Large schemas (hundreds of relation types).** Do not put the whole schema in the prompt. Three tested ideas fit Ariadne:
- GrailQA's vocabulary pruning keeps only schema items "reachable by at least one of the anchor entities within 2 hops" [READ].\[4\]
- Middleware's `get_relations(entity)` exposes only the relations present at the current node [SNIPPET].\[19\]
- CypherBench splits Wikidata (over 12,000 relation types) into small domain views [READ]. It notes at least six overlapping "start time" relations in Wikidata [READ].\[1\]\[2\]

For Ariadne, compute each step's menu from the anchor's *actual* outgoing (rel, target-label) pairs with counts. Schema size then stops mattering.

**LLM-extracted graphs.** EDC (Extract-Define-Canonicalize, EMNLP 2024; P: LLM prompting) canonicalises relations by LLM-written definitions plus embedding similarity [SNIPPET].\[36\]\[37\] One vendor anecdote reports "seventeen variations of 'Phase III trial'" as entity types [SNIPPET; marketing blog, low weight].\[38\] Recommendation: the card builder clusters label and relation names (normalisation plus embedding similarity) into **alias groups** that the expand operator can take as a relation set. It never rewrites the data. Each group is flagged for review, since a false merge silently changes answers.

**"Zero code change" protocol for adding a graph:**
1. Register the endpoint and backend.
2. Run the card builder. It writes a versioned card with statistics and a hash.
3. Run the card linter. It flags missing id or name properties, mixed types, hubs, alias groups and low-count patterns.
4. Auto-generate probe questions from the card: one per pattern × operator, CypherBench-style templates instantiated on sampled non-empty subgraphs [READ].\[1\]\[2\]
5. Run the probes on the deterministic path and check executable rate and non-empty rate.
6. Promote the card if both pass thresholds; otherwise the lint output tells the operator what is ambiguous. No code, rules or labels change.

## 6. Universality test suite

| Suite | Graphs | Scoring | Status |
|---|---|---|---|
| **CypherBench** test split | 7 unseen Wikidata-derived property graphs (company, fictional character, flight accident, geography, movie, nba, politics); full-scale | Execution accuracy by result-table equivalence up to row/column permutation; PSJS (provenance-subgraph Jaccard) [READ] | primary universality test. gpt-4o EX 60.18%, claude3.5-sonnet 61.58%, models <10B under 20% [READ].\[1\]\[2\] Names are verbatim, so grounding is understated |
| **ZOGRASCOPE** (Findings EMNLP 2025) | Neo4j Pole crime graph, 17 relation types; about 3.7k manually annotated Cypher queries; iid, compositional and length splits [SNIPPET] | execution | graph size reported inconsistently (">13k nodes" in SPOT vs 61.5k nodes / 105.8k edges in CypherTurn) [SNIPPET]; verify locally\[39\]\[40\]\[41\] |
| **Text2GQL-Bench** (preprint) | 34 DBs, 13 domains; v1 covers Cypher + ISO-GQL and includes path and reachability queries and BIRD-derived graphs [READ]; v2 (Aug 2026, "Text2GraphQuery-Bench") adds SQL/PGQ, 267,276 pairs and 8 LLMs, and reports that "schema aliasing has minimal impact" [ABSTRACT] | execution plus grammar | the only multi-language suite; data partly LLM-synthesised |
| **GrailQA** (+ GrailQA++) | Freebase | answer F1 / EM | hard to host; best test of surface-form grounding and zero-shot schema |
| **KQA Pro** | Wikidata subset (16,960 entities)\[3\]\[5\] | answer accuracy | tests verify, qualifiers, union; convert to a property graph with qualifiers as edge properties |
| **Neo4j Text2Cypher 2024** | 16+ graphs | text metrics only for half | only about half of its rows have database access [SNIPPET];\[42\] use the database-backed subset only\[2\] |
| **Gremlin / Neptune** | **none found** | — | EICopilot used 150 real queries and 418 training pairs from Baidu's enterprise graph;\[43\] there is no public execution benchmark [SNIPPET]. Build a mirror: load CypherBench graphs into TinkerGraph/Neptune and score by the same result sets |
| **Same content, two schemas** | none for property graphs | — | closest: Dr.Spider (Chang et al., ICLR 2023), with 17 perturbations on databases, questions and SQL including schema-synonym, schema-abbreviation and DBcontent-equivalence; "even the most robust model suffers from a 14.0% performance drop overall and a 50.7% performance drop on the most challenging perturbation" [ABSTRACT]. Also the Freebase→Wikidata migrations (WebQSP-WD, SimpleQuestions-WD), which change content too [SNIPPET] |

**Build your own two-schema pair.** Re-model 2–3 CypherBench graphs (rename labels and relations, reify one relation into a node, move a property onto an edge, split a label). Also load ATT&CK/CAPEC/CWE twice: once as today, once in a different modelling such as STIX-style relationship objects. Run the same gold questions on both. The accuracy gap is schema difficulty; the residual error is content difficulty.

**Metrics:**
- records-exact (result-set equality on identifiers);
- PSJS-style provenance Jaccard;
- abstention precision (an abstention is correct only when the gold set is empty or the question is unsupported);
- confident-wrong rate;
- wrong-entity rate (gold anchor ≠ chosen anchor);
- latency p50/p95, split by fast path and loop;
- for multi-backend graphs, cross-backend agreement.

**Paraphrase tiers.** Reuse Ariadne's tiers (synonym verb, name instead of id, paraphrased name, description only) on every suite. They expose grounding failures that CypherBench by design does not.\[1\]

## Recommendations

1. Implement operators 3, 6, 7, 8, 9 and 10 first. They close every gap the brief lists except paths, and they cover all GrailQA and most CypherBench shapes.
2. Make limits per-operator. The depth cap applies to expand chains, not to `reach`. The row cap applies to envelope samples, never to aggregate inputs.
3. Write a separate compiler per backend for the operator set. Gate releases on a differential Neo4j-vs-Gremlin result-set test over the CypherBench mirror.
4. Build cards deterministically. Treat LLM glosses and alias groups as ranking hints that a person can review, not as schema.
5. Adopt CypherBench (unseen graphs) plus the paraphrase tiers as the primary universality gate. Add the self-built Gremlin mirror and the two-schema pair. Report schema-gap and content-gap separately.

## Caveats

- Per-category frequencies for CypherBench, LC-QuAD 2.0 and most KQA Pro types exist only as chart images. Exact values require counting the released data: CypherBench `match_category` and `return_pattern_id` fields; KQA Pro's final KoPL function.\[12\] Their numbers are absent here by choice, not estimated.
- Spider, MetaQA, Text2GQL-Bench difficulty, Cypher-for-Gremlin TCK, GQL path-mode and Neptune summary figures are [SNIPPET] leads. Dr.Spider, GraphQ IR and the column-description results are [ABSTRACT] leads. None should be cited as measured until read in full.
- Gremlin null/missing-property behaviour and shortest-path support on Neptune come from my background knowledge, not from sources read in this pass.
- No evidence exists for: a cross-benchmark minimal operator set; LLM gloss accuracy on graph labels and relations (as opposed to SQL columns); public Gremlin or Neptune QA benchmarks; property-graph "same content, two schemas" benchmarks.

## Bibliography (method class; venue; read status)

- Feng, Papicchio, Rahman. CypherBench. arXiv 2412.18702 (ACL 2025). https://arxiv.org/abs/2412.18702 — baseline P; [READ]
- Cao et al. KQA Pro. ACL 2022. https://arxiv.org/abs/2007.03875 — KoPL parser T; [READ]
- Gu et al. Beyond I.I.D. (GrailQA). WWW 2021. https://arxiv.org/abs/2011.07743 — T; [READ]
- Dubey et al. LC-QuAD 2.0. ISWC 2019. https://jens-lehmann.org/files/2019/iswc_lcquad2.pdf — dataset; [READ via subagent]
- Ferguson et al. LC-QuAD 2.0 type analysis. arXiv 2206.02737 — [READ via subagent]
- Lyu et al. Text2GQL-Bench. arXiv 2602.11745 (preprint). https://arxiv.org/abs/2602.11745 — fine-tuned T, prompting P; [READ, partial]
- Nie et al. GraphQ IR. EMNLP 2022. https://arxiv.org/abs/2205.12078 — T parser plus deterministic compiler; [ABSTRACT]
- Gu et al. Middleware for LLMs. EMNLP 2024. https://arxiv.org/abs/2402.14672 — P; [SNIPPET]
- openCypher. Cypher for Gremlin. https://github.com/opencypher/cypher-for-gremlin — deterministic, no per-graph step; [SNIPPET]
- Thakkar et al. SPARQL querying of property graphs using Gremlin. arXiv 1801.02911 — deterministic; [SNIPPET]
- Angles et al. G-CORE. arXiv 1712.01550 (SIGMOD 2018) — [SNIPPET]
- PathFinder: Returning Paths in Graph Queries. arXiv 2306.02194 — [SNIPPET]
- Amazon Neptune. Graph schema and metadata (property graph schema API). https://docs.aws.amazon.com/neptune/latest/userguide/graph-schema-metadata.html — B; [READ]
- Amazon Neptune. Graph summary API. https://docs.aws.amazon.com/neptune/latest/userguide/neptune-graph-summary.html — B; [SNIPPET]
- Yu et al. Spider. EMNLP 2018. https://aclanthology.org/D18-1425.pdf — [SNIPPET]
- Pourreza & Rafiei. Evaluating Cross-Domain Text-to-SQL Models and Benchmarks. EMNLP 2023. https://arxiv.org/abs/2310.18538 — [SNIPPET]
- Chang et al. Dr.Spider. ICLR 2023. https://arxiv.org/abs/2301.08881 — [ABSTRACT]
- Synthetic SQL Column Descriptions. arXiv 2408.04691 — B; [ABSTRACT]
- Gao et al. Automatic database description generation for Text-to-SQL. arXiv 2502.20657 (preprint) — B; [ABSTRACT]
- Zhang & Soh. EDC: Extract, Define, Canonicalize. EMNLP 2024. https://aclanthology.org/2024.emnlp-main.548.pdf — P; [SNIPPET]
- Cazzaro et al. ZOGRASCOPE. Findings EMNLP 2025. https://arxiv.org/abs/2503.05268 — [SNIPPET]
- Cazzaro et al. SPOT. Findings ACL 2025. https://aclanthology.org/2025.findings-acl.524.pdf — automatic synthetic data plus parser training (B+T); [SNIPPET]
- Ozsoy et al. Text2Cypher (Neo4j Text2Cypher 2024 dataset). GenAIK 2025. https://aclanthology.org/2025.genaik-1.11.pdf — T; [SNIPPET]
- Zhang et al. MetaQA (Variational Reasoning for QA with KGs). AAAI 2018 — [SNIPPET via secondary sources]
- Banerjee et al. DBLP-QuAD. ECIR 2023 — [SNIPPET]
- GrailQA++ (Designing harder benchmarks…). IJCNLP-AACL 2023. https://aclanthology.org/2023.ijcnlp-main.58.pdf — [SNIPPET]
- EICopilot. arXiv 2501.13746 (preprint) — ICL P plus fine-tuned T; [SNIPPET]
- samyama-graph issue #1642 (GQL WALK vs Cypher TRAIL divergences). GitHub — [SNIPPET; low authority]

## Sources

1. <https://aclanthology.org/2025.acl-long.438.pdf>
2. [CypherBench: Towards Precise Retrieval over Full-scale Modern Knowledge Graphs in the LLM Era](https://arxiv.org/html/2412.18702)
3. [KQA Pro: A Dataset with Explicit Compositional Programs for Complex Question Answering over Knowledge Base](https://arxiv.org/html/2007.03875v4)
4. <https://arxiv.org/html/2011.07743v6>
5. <https://arxiv.org/pdf/2007.03875v4>
6. [GrailQA++: A Challenging Zero-Shot Benchmark for ...](https://aclanthology.org/2023.ijcnlp-main.58.pdf)
7. [(PDF) Template-based Question Answering analysis on the LC-QuAD2.0 Dataset](https://www.researchgate.net/publication/349782685_Template-based_Question_Answering_analysis_on_the_LC-QuAD20_Dataset)
8. <https://jens-lehmann.org/files/2019/iswc_lcquad2.pdf>
9. <https://arxiv.org/pdf/2206.02737>
10. [TransferNet: An Effective and Transparent Framework for Multi-hop Question Answering over Relation Graph](https://arxiv.org/pdf/2104.07302)
11. [Querying Knowledge via Multi-Hop English Questions](https://arxiv.org/pdf/1907.08176)
12. [megagonlabs/cypherbench · Datasets at Hugging Face](https://huggingface.co/datasets/megagonlabs/cypherbench)
13. [Spider: A Large-Scale Human-Labeled Dataset for ...](https://aclanthology.org/D18-1425.pdf)
14. [Evaluating Cross-Domain Text-to-SQL Models and Benchmarks](https://arxiv.org/pdf/2310.18538)
15. [DBLP-QuAD: A Question Answering Dataset over the DBLP Scholarly Knowledge Graph](https://www.inf.uni-hamburg.de/en/inst/ab/lt/publications/2023-banerjee-bir-ecir-2023-dblpquad.pdf)
16. [TIARA: Multi-grained Retrieval for Robust Question ...](https://aclanthology.org/2022.emnlp-main.555.pdf)
17. [G-CORE: A Core for Future Graph Query Languages](https://arxiv.org/pdf/1712.01550)
18. [Middleware for LLMs: Tools Are Instrumental for Language ...](https://aclanthology.org/2024.emnlp-main.436.pdf)
19. [AgentTuning: Enabling Generalized Agent Abilities for LLMs](https://arxiv.org/pdf/2310.12823)
20. [GraphQ IR: Unifying the Semantic Parsing of Graph Query Languages with One Intermediate Representation](https://arxiv.org/pdf/2205.12078)
21. [GitHub - Flitternie/GraphQ\_Trans: A Graph Query Language Transpiler · GitHub](https://github.com/Flitternie/GraphQ_Trans)
22. [Text2GQL-Bench: A Text to Graph Query Language Benchmark \[Experiment, Analysis & Benchmark\]](https://arxiv.org/html/2602.11745v1)
23. [GitHub - opencypher/cypher-for-gremlin: Cypher for Gremlin adds Cypher support to any Gremlin graph database. · GitHub](https://github.com/opencypher/cypher-for-gremlin)
24. [A Stitch in Time Saves Nine -- SPARQL querying of Property Graphs using Gremlin Traversals](https://arxiv.org/pdf/1801.02911)
25. [What Is GQL? Features & Syntax](https://www.puppygraph.com/blog/what-is-gql)
26. [Semantic Web 0 (0) 1 1 IOS Press 1 1 2 2 3 3 4 4 5 5 6 6 7 7 8 8 9 9 10 10 11](https://www.semantic-web-journal.net/system/files/swj3930.pdf)
27. [The default path mode is TRAIL; ISO GQL's default is WALK, and it costs 9 of our 10 divergences in the conformance map · Issue #1642 · samyama-ai/samyama-graph · GitHub](https://github.com/samyama-ai/samyama-graph/issues/1642)
28. [Releases · opencypher/cypher-for-gremlin · GitHub](https://github.com/opencypher/cypher-for-gremlin/releases)
29. [Cypher for Gremlin](https://www.slideshare.net/slideshow/cypher-for-gremlin-99744176/99744176)
30. [Getting a quick summary report about your graph - Amazon Neptune](https://docs.aws.amazon.com/neptune/latest/userguide/neptune-graph-summary.html)
31. [Graph schema and metadata - Amazon Neptune](https://docs.aws.amazon.com/neptune/latest/userguide/graph-schema-metadata.html)
32. [GraphSummary - Neptune Analytics](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/query-APIs-graph-summary.html)
33. [Knowledge Graph-extended Retrieval Augmented Generation for Question Answering](https://arxiv.org/pdf/2504.08893)
34. [\[2502.20657\] Automatic database description generation for Text-to-SQL](https://arxiv.org/abs/2502.20657)
35. [\[2408.04691\] Synthetic SQL Column Descriptions and Their Impact on Text-to-SQL Performance](https://arxiv.org/abs/2408.04691)
36. [LLM-Empowered Knowledge Graphs](https://www.emergentmind.com/topics/llm-empowered-knowledge-graph-construction)
37. [Extract, Define, Canonicalize: An LLM-based Framework ...](https://aclanthology.org/2024.emnlp-main.548.pdf)
38. [Knowledge Graph with LLMs: Enterprise AI Guide](https://www.tigergraph.com/blog/how-to-build-knowledge-graph-with-llms-for-enterprise-ai/)
39. [(PDF) ZOGRASCOPE: A New Benchmark for Property Graphs](https://www.researchgate.net/publication/389694640_ZOGRASCOPE_A_New_Benchmark_for_Property_Graphs)
40. [SPOT: Zero-Shot Semantic Parsing Over Property Graphs](https://aclanthology.org/2025.findings-acl.524.pdf)
41. [CypherTurn: A Multi-Turn Benchmark for Conversational Text-to-Cypher Evaluation and the Autonomy Divergence](https://arxiv.org/html/2609.36987v1)
42. [Introducing the Neo4j Text2Cypher (2024) dataset - Neo4j Graph Intelligence Platform](https://neo4j.com/blog/developer/introducing-neo4j-text2cypher-dataset/)
43. [EICopilot: Search and Explore Enterprise Information over Large-scale Knowledge Graphs with LLM-driven Agents](https://arxiv.org/pdf/2501.13746)
