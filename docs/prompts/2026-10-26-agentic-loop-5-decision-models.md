# Deep-research prompt — decision models for grounding and control (2026-10-26)

Second-round prompt on the agentic retrieval loop, written from the first round's
synthesis ([SYNTHESIS.md](../research/reports/2026-10-26-agentic-loop/SYNTHESIS.md)); the
full set is listed in [2026-10-26-agentic-loop-README.md](2026-10-26-agentic-loop-README.md).
Paste everything inside the block into a deep-research tool and bring the report back to
the Ariadne session.

```text
You are a research analyst. Today is 2026-10-26. Prefer evidence over claims. For every
figure you cite, tag how you read it: [READ] full text read, [ABSTRACT] abstract only,
[SNIPPET] search excerpt only. A figure tagged [ABSTRACT] or [SNIPPET] is a lead, not
evidence, and must not be presented as what a paper measured. Classify every method:
P = plug-and-play with an off-the-shelf model; B = needs only an automatic one-time build
step per graph; T = needs training or fine-tuning on the target graph or task. Say which.
Peer-reviewed or preprint: say which.

## The system: Ariadne

Ariadne answers natural-language questions over live knowledge graphs held in graph
databases: Neo4j (Cypher) and Gremlin/TinkerPop today, Amazon Neptune planned. Current
graphs are MITRE ATT&CK, CAPEC and CWE (about 10,000 nodes, 34 edge types), plus graphs
built by an LLM extraction pipeline from documents. Target graphs reach millions of
nodes, with high-degree hub nodes. Graphs stay in their own stores (federated, never
merged) and are joined on shared identifiers.

Each graph is described by a "source card": node labels, relationship types, the allowed
(source label, relation, target label) patterns, node properties, the identifier property
and its scheme, safety limits (max traversal depth 3, max rows 1000, timeout), connection
endpoint and backend, and a one-line description per label.

Specialists: one per store. Each builds a bounded, read-only, schema-validated query from
a small set of primitives (describe a node, expand along a relation, join projection
across sources, chained composition, two-anchor intersection) and runs it. This path is
deterministic and fast: 120 questions in 1.6 s end to end. LLM-written queries cost about
3,000x more wall-clock time, and on Gremlin in particular LLM-written traversals are
usually wrong even with instructions (a 2B model produced 0 working drafts of 17; free
text-to-Cypher by gpt-4o reaches about 60% execution accuracy on CypherBench's unseen
graphs). The design decision is fixed: the specialists stay deterministic and no
language model writes query text.

Current interface defect: the planner hands each specialist a natural-language
sub-question (text plus entity names, seed identifiers, limits, a join key), and the
deterministic builder re-reads that text with keyword rules to find names and to detect
request types. So any wording outside the vocabulary the rules expect breaks retrieval.

## What the system's own measurements show

- Given a correct plan, answers are accurate: judged correctness 0.9005 on 282 sealed
  questions, with no language model in the answer path.
- When the system plans for itself, gold coverage falls from 0.8611 to 0.4797 (-0.3814,
  n=284). On 77 of 284 the planner retrieved nothing where the correct plan retrieved
  records; never the reverse. Worst on chained and cross-source questions (about -0.50
  and -0.55).
- Wording sensitivity, records-exact by paraphrase tier: original 1.0000; synonym verb
  ("How do I defend against T1176?") 0.4667; entity named instead of given by
  identifier 0.0990 (0.3762 after deterministic fixes); paraphrased name 0.0000;
  description only 0.0000.
- Already tried and failed or mixed: an LLM-written relation lexicon from glosses (mixed;
  the synonym tier got worse); an LLM choosing an entity from a reranked candidate list
  (picked the wrong entity 35% of the time); a gated LLM rewrite stage before planning
  (lifted the hardest tiers to 0.088 and 0.164 but doubled confident-wrong answers).
- Not yet tried: an iterative agent loop in which an LLM controller calls the
  deterministic specialists as tools and reads their results; typed plan enumeration;
  edit-on-failure (Readi-style); a schema-compatibility filter on entity candidates.
- An earlier research pass already covered single-shot plug-and-play KGQA: plan
  enumeration and ranking (Pangu), Readi's edit-on-failure (1.55 edit calls on
  average), build-time relation lexicons, failure-gated cascades, and entity selection
  behind a compatibility filter with a "none" option. Do not re-survey those as
  stand-alone methods; cite them only where they fit inside the loop described below.

## The target design (what this research is for)

One LLM controller in a single tool-calling loop, modelled on Claude Code: call the
model, run its tool calls, append the results, repeat until it answers. It reads the
source cards of the graphs that are online, plans, calls the deterministic specialists
as tools, reads shaped results, decides whether it needs more or must adjust, and
iterates. When it has enough it drafts an answer, a validation step checks every claim
against the retrieved records (abstaining with the executed query as proof when nothing
holds), and the answer is returned. The whole thing must be embeddable: other systems
call Ariadne as an agent or tool and get correct, cited information back.

Priorities, in order: accuracy, then speed, then robustness. Plug-and-play: add a graph
by building its source card automatically; no per-graph training, no hand-written rules
or templates, no hand-labelled data. The controller runs on a local reasoning model in
the 27-35B class on one GPU (per-call times are measured below); hosted frontier models are a
comparison point, not the default.

## What a first research round settled (2026-10-26)

Four earlier deep-research reports (controller loop, observations, vocabulary boundary,
embedding) converged on a design; do not re-argue it, build on it:
- The controller never sends natural language to a specialist. It sends typed requests
  whose fields are the property-graph model (source, anchor id and label, relation,
  direction, target label, property filters, join key) and whose allowed values are
  computed per step from whichever source card is loaded. The design must be
  graph-universal: only the source card and the per-backend compiler change per graph.
- Choosing from a short list of valid options beats free generation, especially for small
  models (Middleware, EMNLP 2024). Executor-produced diagnostics beat self-critique
  (QueryAgent/ERASER, ACL 2024). The validator, not the model, decides when to stop.
- Answers must be exact. The controller reads bounded "envelopes" (exact totals, exact
  facet counts, a labelled sample, a completeness flag, a handle); the database computes
  the full set and a deterministic composer lists it. Nothing that belongs in the answer
  may be dropped by any shaping step.
- A wrong entity passes Ariadne's claim verifier, because the records genuinely support
  claims about the wrong node. Grounding must be defended when it happens.
- Speed comes from a cascade: deterministic fast path first, LLM loop only on failure.

Measured on the local stack on 2026-10-26 (one question, warm, single user):
- one typed tool call from the local controller model: 0.66-0.74 s with thinking off,
  1.16-2.38 s with thinking on; a pick from a four-option menu: 0.30-0.41 s;
- a decision model (d3-lite, 0.85B, returns a probability per answer to yes/no, choice or
  score questions, no generated text): about 80 ms per call; it picked the right relation
  with p = 0.614 and the right entity with p = 0.791;
- the deterministic path: 0.006 s median per question.

## Your task: decision models for grounding and control

A "decision model" here is a model that answers a closed question about an input (yes/no,
one of several options, or a score) with a probability per answer and no generated text.
d3-lite (vLLM Semantic Router, "Decision 3.0", fine-tuned from Qwen3.5-0.8B) is one. The
proposal is to make every classification in Ariadne's loop a decision-model call: is this
candidate the entity the user meant; which of these relations answers the question; what
shape is the question (lookup, enumerate, count, chain, compare, aggregate); does this
plan answer the question; do these records answer it; does each member of a large set
satisfy a judgment the database cannot compute. Probabilities make thresholds possible:
accept above one, ask the user between, abstain below.

Questions:

1. **What exists.** Decision models and their neighbours: d3-lite and the vLLM Semantic
   Router family, LLM-as-classifier via label log-probabilities, cross-encoder rerankers,
   NLI-based zero-shot classifiers, reward and verifier models, small judge models,
   bi-encoder entity linkers (BLINK, ReFinED and successors), LLM-based entity
   disambiguators. For each: what it outputs, size, latency, licence, and whether it is
   P, B or T in the sense above.
2. **Accuracy on grounding tasks.** Entity disambiguation against a candidate list with
   descriptions, relation or schema-item selection given glosses, NIL ("none of these")
   detection. How do small decision models and cross-encoders compare with generative LLM
   picks on the same task? Find head-to-head numbers.
3. **Calibration.** How well calibrated are these models' probabilities out of the box,
   on unseen domains? What recalibration methods work with a small labelled set
   (temperature scaling, isotonic, conformal prediction), and how many labels do they
   need? Conformal methods that give a guaranteed error rate for "accept" decisions are of
   particular interest.
4. **Selective prediction.** Coverage-risk curves for entity linking and KGQA grounding:
   how much coverage must be given up to bring wrong-entity rates below 10%, 5%, 1%?
5. **Trained once, used on unseen graphs.** Has anyone trained a schema-conditioned
   grounding or linking model across many knowledge graphs (with synthetic questions
   generated from each graph's schema) and evaluated it on graphs it never saw? Include
   zero-shot entity linking (Wikia, ZESHEL), cross-schema text-to-SQL schema linking,
   and KG foundation models (ULTRA, KG-ICL and successors) as the nearest work. What
   training data would such a model need, and how much?
6. **Batch classification over large sets.** Cost and accuracy of classifying every member
   of a 100-10,000 item set against a judgment ("concerns cloud identity"), by decision
   model, embedding filter, or LLM map-reduce. Throughput figures on one GPU.
7. **Failure modes.** Position and order bias in option lists, sensitivity to option
   wording, long-description truncation, adversarial or misleading descriptions (graph
   content is untrusted text).

## Deliverables

1. TL;DR and a comparison table: model or method, output, size, latency, class (P/B/T),
   best grounding evidence, calibration evidence, read status.
2. Findings for each question above.
3. A recommendation for each decision in Ariadne's loop (entity, relation, question shape,
   plan check, sufficiency, set membership): which model type, how to calibrate it, and
   how to set the accept/ask/abstain thresholds.
4. Whether a cross-graph grounding model is an open research question, what the nearest
   work is, and what an experiment to answer it would look like.
5. Three to five experiments on Ariadne's paraphrase-tier banks, each with the measurement
   that decides it (wrong-entity rate at fixed coverage, calibration error, latency).
6. Bibliography with links and read status.

Keep it under about 6,000 words. Say plainly where no evidence exists.
```
