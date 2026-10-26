# Deep-research prompt — plug-and-play question understanding and adaptive retrieval (2026-10-20)

Paste everything inside the block into a deep-research tool. Bring the report back to the
Ariadne session for discussion. The failure figures in the brief are quoted from
`docs/research/CURRENT.md` and the experiments it indexes.

```text
You are a research analyst. Today is 2026-10-20. Find the published methods that would let
a knowledge-graph question-answering system understand a user's question against a graph
it has never seen, retrieve the right records, and recover when it retrieves the wrong
ones, WITHOUT training a model on that graph. Report what works, what it costs per
question, and what evidence supports it. Prefer evidence over claims, and say when a
method needs training.

## The system

Ariadne answers natural-language questions over live knowledge graphs held in graph
databases (Neo4j/Cypher, Gremlin/TinkerPop; Amazon Neptune planned). Each graph is
described by a "source card": node labels, relationship types, allowed
(source label, relation, target label) patterns, node properties, the identifier
property and scheme, safety limits, and a one-line gloss per label and relation. The
pipeline:
1. Planner: classifies intent, finds the anchor entity, chooses relations, and splits
   the question into per-source sub-questions with join keys. Today intent comes from a
   closed regex taxonomy, partly written for MITRE ATT&CK and CAPEC vocabulary.
2. Query builders: derive bounded, read-only, schema-validated queries from the card.
   This part is schema-derived and needs no per-graph code.
3. A deterministic retrieval loop: assess sufficiency, then re-plan up to 5 hops.
4. Composer and verifier: claims are built from retrieved records and checked against
   them; when nothing holds, the system abstains and shows the executed query.

## What the system's own measurements show (the failures to target)

- Given a correct retrieval plan, answers are accurate: judged correctness 0.9005 on
  282 sealed questions, with no language model in the answer path.
- When the system plans for itself, gold coverage falls from 0.8611 to 0.4797
  (-0.3814, n=284). On 77 of 284 questions the planner retrieved nothing where the
  correct plan retrieved records; the reverse never happened. The loss is worst on
  chained (two-hop) and cross-source questions (about -0.50 and -0.55).
- Wording sensitivity, records-exact by paraphrase tier: original question 1.0000;
  same identifier with a synonym verb ("How do I defend against T1176?") 0.4667;
  entity named instead of given by identifier 0.0990 (later raised to 0.3762 by
  deterministic fixes); paraphrased name 0.0000; description only 0.0000.
- Choosing an entity from a reranked candidate list answered more questions but picked
  the wrong entity 35% of the time on one bank, so it ships disabled.
- Located defects: two-hop requests collapse to the shortest schema path; property
  filters in the question never reach the query; the intent form has one relation slot,
  so it cannot express a cross-source chain.
- Cost: LLM-written queries cost about 3,000x the deterministic path in wall-clock time.
  An LLM narrator costs about 1,340x the deterministic composer.

## The constraint: plug-and-play

ALLOWED per new graph: automatic, one-time build steps, such as introspecting the
schema, building name and alias indexes, having an LLM write glosses or synonyms once,
generating synthetic example questions once, or selecting few-shot examples.
NOT ALLOWED per new graph: gradient training or fine-tuning, hand-written rules or
templates, hand-labelled training data.
A model pre-trained once on OTHER graphs and reused unchanged is allowed. Say so when a
method falls in that class.

For EVERY method you report, classify it: (P) plug-and-play as defined; (B) needs only
an automatic build step; (T) needs per-graph training; (H) needs per-graph hand work.

## Questions

1. Schema linking and question understanding on unseen schemas
   - Text-to-SQL is the most mature cross-schema literature (Spider, BIRD). Which
     schema-linking methods transfer to unseen databases, and what do they cost per
     question? Cover, e.g., DIN-SQL, MAC-SQL, CHESS, RSL-SQL and their successors.
   - Relation and entity linking in KGQA without per-graph training: zero-shot relation
     linking, lexicon induction from schema labels and glosses, embedding retrieval
     over schema elements.
   - Methods that map a synonym or paraphrase onto a schema relation reliably. What
     closes the gap between "defend against" and a relation named MITIGATES?
2. Planning and decomposition over a typed schema graph
   - Intermediate representations and program induction (query graphs, KoPL,
     S-expressions, multi-target IRs such as text2ql) and how they are grounded to an
     unseen schema.
   - Enumerate-then-rank approaches: generate candidate schema paths or plans from the
     schema, then rank or select. Evidence that this beats free generation.
   - Agentic KGQA: Think-on-Graph, ToG-2, Plan-on-Graph, KG-Agent, StructGPT,
     Interactive-KBQA, Readi, KBQA-o1, RoG, ChatKBQA and newer. For each: P/B/T/H,
     accuracy on zero-shot or unseen-schema splits, LLM calls per question, latency.
   - Multi-hop and cross-source chains: how do methods keep intermediate entities and
     direction, and check that each hop produced the input the next hop needs?
3. Detecting failure and adapting
   - Execution-guided refinement: using query results (including empty results) as
     feedback. Cover Guo et al. (EMNLP 2023), SQL self-debugging and correction, and
     KGQA path editing on failure.
   - The classic empty-answer problem: query relaxation, cooperative answering and
     why-not questions in databases and SPARQL. Which of these are deterministic and
     usable without a model?
   - Answerability and sufficiency detection: deciding when retrieval is wrong or
     incomplete versus when the answer is truly empty (e.g. GrailQAbility).
   - Clarification: when candidates stay ambiguous, ask the user instead of guessing.
     What is the evidence on when to ask?
4. Entity resolution against a graph never seen before
   - Training-free entity linking: name and alias indexes, BM25, rerankers, LLM
     selection among enumerated candidates, using the requested relation and
     neighbourhood compatibility to choose. Report correct-entity AND wrong-entity
     rates where available, not recall alone.
5. Speed without losing accuracy
   - Cascades and routing: a cheap deterministic or small-model path first, escalating
     to an LLM only on detected failure. Evidence on accuracy kept and cost saved.
   - Caching plans by question shape, small models for linking, constrained decoding.
6. Evaluation of plug-and-play claims
   - Benchmarks with held-out schemas or zero-shot splits: GrailQA's i.i.d. /
     compositional / zero-shot levels, CypherBench's unseen graphs, Spider/BIRD
     cross-database, KQA Pro, robustness suites such as Dr.Spider. Which best measure
     "new graph, no training"?
   - Reported gaps between seen-schema and unseen-schema performance, and what closes
     them.

## Output format

1. One page: the five most promising plug-and-play techniques for the failures listed
   above, ranked by expected accuracy gain, each with its P/B/T/H class, cost per
   question, and the strongest evidence for it.
2. A section per question group, with comparison tables: method, class, benchmark and
   split, reported accuracy, LLM calls per question, latency, code available.
3. A table mapping each listed Ariadne failure to the methods that address it.
4. A table of methods that look good but fail the plug-and-play constraint, and why.
5. A bibliography. For each citation: authors, year, venue, link, and a read-status tag:
   [READ] (full text read), [ABSTRACT] (abstract only), [SNIPPET] (search result only).
   Never cite an [ABSTRACT] or [SNIPPET] source for what a paper measured.

Rules: separate peer-reviewed papers from preprints and blog posts. Prefer 2023-2026
sources, but include older database work (query relaxation, cooperative answering) where
it is still the reference point. If a question cannot be answered, say so; do not fill
the gap with a guess.
```
