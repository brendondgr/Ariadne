# Deep-research prompt — the controller loop (2026-10-26)

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

## Your task: the controller loop

Find the published agent designs that retrieve from knowledge graphs or databases by
iterating (an LLM decides, a tool executes, the LLM reads the result and decides again),
and work out which design fits a controller that must drive deterministic executors.
Cover 2023-2026, including text-to-SQL agents where the lesson transfers. Methods to
start from, not to stop at: Think-on-Graph and ToG-2, StructGPT, KG-Agent,
Interactive-KBQA, Plan-on-Graph, Generate-on-Graph, Graph-CoT, KnowAgent, EffiQA,
FiDeLiS, ReKnoS, ODA, QueryAgent/ERASER, KBQA-o1, RoG, MAC-SQL, CHESS, ReFoRCE, and the
agent baselines on Spider 2.0 and BIRD. Find newer ones.

Questions:

1. **Action space.** For each method: what can the LLM emit? Free query text, a typed
   function call over primitives, a relation or entity choice from a list, a logical
   form, or code? Is there any head-to-head evidence comparing these action spaces on
   the same benchmark? Which designs keep the executor deterministic?
2. **Control pattern.** ReAct-style step by step, plan-then-execute, plan-execute-replan,
   beam or tree search, or a cascade that only enters the loop on failure. Report LLM
   calls per question, tokens, latency and accuracy where measured, and on which
   graph (Freebase, Wikidata, property graph, unseen schema).
3. **Deciding when to stop.** How do these agents judge they have enough evidence? What
   failure rates are measured for stopping too early, looping, or answering from the
   model's own memory instead of the retrieved records?
4. **Recovering.** How does each loop respond to an empty result, a type or schema
   violation, a wrong entity, or too many results? Edit-on-failure, relaxation,
   backtracking, asking the user. What does each cost?
5. **One agent or several.** For this task specifically, what evidence compares a single
   controller against planner/executor/critic teams? Include the general agent
   literature only where it was measured on retrieval or tool-heavy tasks.
6. **Small local controllers.** What breaks when the controller is a 7-32B open model?
   Tool-call format errors, lost state over many steps, premature answers. What
   mitigations are measured (grammar-constrained tool calls, fewer tools, tool loading
   on demand, step caps, repeated-call guards, compaction)?
7. **Grounding the plan in the schema.** How do agents that read a schema description
   (rather than having it trained in) use it to plan? How large a schema fits before
   accuracy falls, and what do they do when it does not fit (schema retrieval, schema
   exploration tools)?

## Deliverables

1. TL;DR (one paragraph) and a one-page table: method, action space, control pattern,
   class (P/B/T), LLM calls per question, best measured result and where, read status.
2. Findings for each question above.
3. A recommended loop for Ariadne: the tools the controller should have (name, inputs,
   what it returns), the control pattern, the stopping rule, the recovery rules, and the
   step budget. Say which of Ariadne's measured failures each element targets.
4. Methods that look right but fail the constraints (need training, write query text,
   or cost too many calls), and why.
5. Three to five experiments to run on Ariadne's own paraphrase-tier and sealed banks,
   each with the measurement that would show it worked or failed.
6. Bibliography with links and read status.

Keep it under about 7,000 words. Say plainly where no evidence exists.
```
