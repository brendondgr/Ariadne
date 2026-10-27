# Deep-research prompt — where to publish era 2's results (2026-10-27)

Paste everything inside the block into a deep-research tool and bring the report back to the
Ariadne session. The study it describes is planned, not run: see
[`docs/plans/2026-10-26-era-2-roadmap.md`](../plans/2026-10-26-era-2-roadmap.md), Phase 5.

```text
You are advising a research group on where to submit a paper. Today is 2026-10-27. The
results do not exist yet, so map each likely outcome to venues. Separate A-level venues
(CORE A* and A) from B-level venues (CORE B), and state the CORE ranking year you used.
Verify every ranking and deadline from the official source, and say when you could not.

## The planned study

Ariadne answers questions over live knowledge graphs in graph databases (Neo4j/Cypher,
TinkerPop/Gremlin, Amazon Neptune). No language model writes a query. A controller sends
typed, schema-constrained requests that deterministic per-backend compilers turn into queries.
The paper's main comparison: on the same unseen property graphs (CypherBench's test graphs,
mirrored into Gremlin), with the same open models, typed compiled requests vs LLM-written
Cypher vs LLM-written Gremlin, scored by result-set match, with paraphrased entity names.
Possible secondary sections:
- complete answers to "list every X" questions when the model only sees a bounded view;
- one agent across unmerged stores on different engines, with latency by hub-node degree;
- a public Gremlin version of CypherBench, as a resource.

Ground truth is computed from the databases, so no human grading. A prior novelty audit found
the mechanisms are published; the contribution is the measurements.

## Outcomes to map

1. Typed requests win clearly on both Cypher and Gremlin.
2. Typed requests win on Gremlin but tie on Cypher.
3. Typed requests tie or lose, but abstain correctly where free generation answers wrongly.
4. The main result is the Gremlin benchmark resource itself.

## What to find

For each outcome: the best-fitting A-level venues and B-level venues, each with:
- its community (databases, NLP, semantic web, IR/web, ML, security);
- deadlines between 2026-11 and 2027-12;
- page limits;
- whether it takes negative or null results;
- what reviewers there require: baselines, human evaluation, artifacts, a second domain;
- acceptance rate.

Include dataset and benchmark tracks (for example NeurIPS Datasets and Benchmarks, PVLDB EA&B,
SIGIR resource track, ISWC resource track), Findings tracks, and the relevant workshops
(GRADES-NDA, RAGE-KG). Name groups publishing close work at each venue, especially Neo4j
(Ozsoy) and Ant Group/TuGraph (Text2GQL).

## Deliverable

A table per outcome (venue, tier and CORE year, community, next deadline, fit, what would get
it rejected), then one recommended sequence (first target, fallback) for each outcome. Keep it
under about 3,000 words.
```
