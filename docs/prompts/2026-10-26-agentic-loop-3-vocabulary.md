# Deep-research prompt — the language boundary between the controller and the specialists (2026-10-26)

One of four prompts on the agentic retrieval loop; the others are listed in
[2026-10-26-agentic-loop-README.md](2026-10-26-agentic-loop-README.md). Paste everything
inside the block into a deep-research tool and bring the report back to the Ariadne
session. Figures in the brief are quoted from `docs/research/CURRENT.md` and the
experiments it indexes.

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
the 27-32B class on one GPU (several seconds per call); hosted frontier models are a
comparison point, not the default.

## Your task: getting the user's words into the graph's vocabulary

Users say "defend against", "stop", "counter" where the graph has MITIGATES; they name
an entity by a description or a nickname instead of its identifier. The proposal is that
the LLM controller does this translation, and the deterministic specialists receive only
typed requests whose fields are drawn from the source card (a label, a relation, a
direction, an anchor identifier, a property filter), so they never read natural language
at all. Find what is known about making that boundary reliable.

Questions:

1. **Typed requests instead of text.** Which systems have an LLM emit a structured
   request or intermediate representation that a deterministic executor runs (logical
   forms, function calls with schema-derived arguments, query skeletons with slots)?
   What evidence compares that against generating query text, on unseen schemas?
2. **Constrained decoding with schema enums.** JSON-schema and grammar-constrained tool
   calls (llama.cpp grammars, vLLM guided decoding, XGrammar, Outlines) where argument
   values must come from the schema's labels and relations. What happens to accuracy
   and latency with enums of tens, hundreds and thousands of values, and with enums
   that change per step (for example only relations valid from the current node's
   label)? Does constraining the output hurt the model's reasoning, and how is that
   avoided?
3. **Lookup tools for vocabulary.** Tools that let the agent discover the vocabulary:
   search the schema, search entities by name, alias or description, describe a node,
   list relations valid from a label. How do text-to-SQL and KG agents use schema
   exploration tools, and how much does it help compared with putting the schema in the
   prompt?
4. **Rewriting the question.** Normalising or rewriting before planning versus inside
   the loop with execution feedback. Ariadne's rewrite-before-planning stage doubled
   confident-wrong answers; is that a known effect, and what prevents it?
5. **Wrong-entity risk.** When the agent picks the entity, how do published systems keep
   wrong-entity rates low: compatibility with the planned relation, a "none" option,
   asking the user, requiring the entity to have an edge of the planned relation?
   (An earlier pass found ChatEL, LELA and RAISED; go further.)
6. **Error messages that teach.** Validators that reject a malformed or out-of-vocabulary
   request with a message saying what to fix and listing the valid options. Is there
   evidence that executor feedback of this kind improves agent accuracy, and how many
   retries it takes?
7. **Ask or guess.** Ambiguity detection and clarification questions in KGQA and
   text-to-SQL: when asking beats guessing, and how often agents should ask.

## Deliverables

1. TL;DR and a one-page table: technique, class (P/B/T), LLM calls added, evidence,
   read status.
2. Findings for each question above.
3. A recommended request schema for Ariadne's specialists (the fields, which are enums
   from the card, how per-step enums are computed, the error contract), and the lookup
   tools the controller needs.
4. Three to five experiments to run on Ariadne's paraphrase tiers (synonym verb, named
   entity, paraphrased name, description only), with the measurement that decides
   each. Report wrong-entity and confident-wrong rates, not only answered rate.
5. Bibliography with links and read status.

Keep it under about 6,000 words. Say plainly where no evidence exists.
```
