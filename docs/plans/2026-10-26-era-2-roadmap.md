# Era-2 roadmap — order, tests and reasons (2026-10-26)

**Status: proposed, for discussion.** Nothing here is scheduled. Each test becomes an experiment
only through `make new-experiment`, with hypotheses written in `PROTOCOL.md` before it runs.

**What this plan is for.** Ariadne becomes an agent that other systems call to read any
knowledge graph and get back correct, complete, cited information, fast. The design and the
evidence behind it are in:
- [`../era-2-expansion/README.md`](../era-2-expansion/README.md) (goal and requirements);
- round one: [`SYNTHESIS.md`](../research/reports/2026-10-26-agentic-loop/SYNTHESIS.md);
- round two: [`ASSESSMENT.md`](../research/reports/2026-10-26-agentic-loop-round-2/ASSESSMENT.md).

## Decisions this plan takes as given

1. **Exact results.** The controller's view may be bounded; the answer may not.
2. **Graph-universal.** Only the source card and the per-backend compiler change per graph.
3. **Many models, never one.** Every test runs across a list of models, and the served model is
   recorded on every call.
4. **Off-the-shelf open-source decision models only.** No model is trained or fine-tuned for
   Ariadne, neither per graph nor once across graphs. (Round two's candidate C-C, a grounding
   model trained once across many graphs, is dropped by the operator's decision of 2026-10-26.)
   If off-the-shelf models all fall short on a step, the step stays with the controller LLM or
   with deterministic code; it does not become a training project by default.
5. **Decision models run on a separate vLLM server**, so their calls batch and run concurrently.
6. **New plans live in `docs/plans/`**, next to the era-1 plans (operator, 2026-10-26).

## The order at a glance

| Phase | What | Needs | Why it sits here |
|---|---|---|---|
| **0** | Foundations: disk check, model registry, timing, exactness fixes, question generator | nothing | Every later number depends on these, and three of them fix known defects |
| **1** | Decision-model bake-off, step by step, across types and sizes | 0 | Your priority. It decides which steps a small model can own before anything is built around it, and needs no loop |
| **2** | Typed boundary and the operator algebra | 0 (runs alongside 1) | The largest measured defect (specialists reading text), and it can be tested without a loop |
| **3** | Grounding pipeline and the fast path | 1, 2 | Combines the Phase 1 winners with typed requests into the millisecond path |
| **4** | Controller loop for what the fast path can't answer | 3 | Built only for the residue Phase 3 leaves, so its size is known before it's built |
| **5** | Universality and the external study (typed vs LLM-written Cypher and Gremlin) | 2, 3, 4 | Needs full operator coverage and working grounding, or the comparison is unfair |
| **6** | The embeddable interface (MCP) | 3–4 | It wraps a working system |

Phases 1 and 2 run in parallel: one is measurement, the other engineering, and they touch
different code.

---

## Phase 0 — Foundations

### 0.1 Disk integrity (before anything)

On 2026-10-26 the kernel log showed btrfs checksum failures on `nvme0n1p3`, with a lifetime
corruption counter of 23,787,109. Three files under `docs/evaluation/experiments/` read back as
I/O errors:
- one tracked (`untruncated-generic/generic/answers/A-CMP-01.json`; git still holds a good copy);
- two untracked, with no copy in git.

`make validate-research` crashes on them. Every measurement in this plan is only as good as the
disk it is read from.
- **Operator actions** (system-level, outside the repository): a backup, a `btrfs scrub`, a SMART
  check of the drive and, if errors persist, a memory test.
- **Repository action afterwards:** restore the tracked file from git; record the two lost files
  in their experiments' `ISSUES.md`.

### 0.2 A model registry and a matrix runner

- **The registry:** one file listing every model a test may use, with endpoint, type, size,
  licence and serving mode:
  - LLMs on the relay;
  - decision models, rerankers, NLI classifiers and embedders on the vLLM server.
- **The runner:** runs any test over a list of models, and writes the served model
  (`scripts/model_identity.py`) into every result row.
- **Why:** requirements 3 and 5. The relay alias has already served four different models, and
  any comparison made through an alias records nothing.
- **Done when:** one existing test (the latency probe) runs across three models from one
  command, and its output names each served model.

### 0.3 Timing and the 77 empty retrievals

- **The work:** per-stage timing on every path, plus a cause for each of the 77 of 284 questions
  where the planner retrieved nothing and the authored plan did (`Q57`). Each gets one cause:
  entity, relation, direction, missing operator, or limit.
- **Why:** this is the breakdown every later phase is judged against. It needs no model.
- **Bank:** dev 284.

### 0.4 Exactness fixes and contract tests

- **The work:**
  - `utils/specialists/cypher/connector.py` stops at 1,000 rows with no flag. Every primitive
    must return an exact total and a `complete` flag.
  - Full sets are fetched by keyset pagination.
  - The safety ceiling becomes an explicit `partial` status.
- **Tests (no model):**
  - every primitive reports totals;
  - paged sets equal uncapped sets;
  - the composer's count equals the database's count;
  - synthetic hubs of 10⁵–10⁶ edges in Neo4j and Gremlin.
- **Why:** requirement 1, and a defect that exists today.
- **Gate:** zero silent truncations; identical result sets; hub p95 within the card's timeout.

### 0.5 The card-driven question generator

- **What it does:** from a source card alone, it writes questions at every paraphrase tier:
  identifier, name, paraphrased name, description only, synonym verb. Each comes with its gold
  entity, relation, plan and records by construction, because the generator executes the typed
  request.
- **What it produces:** separate, sealed tuning and held-out sets, one per decision step.
- **Why:** it is the one piece of infrastructure every later phase uses:
  - Phase 1's labelled test sets for each decision step, with no hand labelling;
  - Phase 1's calibration sets;
  - Phase 5's probe questions for adding a graph;
  - Phase 5's paraphrase tiers on CypherBench, whose questions name entities verbatim.
- **The limit, stated up front:** generated questions are not real users. Every Phase 1 result
  is checked once on the real sealed banks before it is trusted.
- **Gate:** generated questions execute non-empty and match their gold, by construction; a
  sample is read by a person for fluency.

---

## Phase 1 — Decision models, step by step

**The question this phase answers.** For each closed decision in the loop, which off-the-shelf
model types and sizes are reliable enough to:
- run the step alone;
- serve as a gate or second opinion;
- or stay out?

Each step is tested **in isolation**, with correct upstream inputs supplied. A model's error is
then its own, not inherited.

### 1.1 The model roster: types × sizes

All open-source, used unchanged. Verify availability and licence before each is added to the
registry.

| Type | What it returns | Size ladder to test |
|---|---|---|
| Dedicated decision model | A probability per option | d3-lite (0.85B, in GAIFA's `decide` mod), plus any other sizes or families vLLM can serve |
| Cross-encoder reranker | A score per (question, candidate) pair | ~0.6B, ~4B (e.g. Qwen3-Reranker-0.6B and -4B), ~0.5B multilingual (bge-reranker-v2-m3) |
| NLI zero-shot classifier | Entailment probability per label | ~0.4B (a DeBERTa-v3 NLI model) |
| Embedding similarity | A similarity, used **for ordering only**, never for dropping | ~0.5B, ~4B (e.g. BGE-M3, Qwen3-Embedding) |
| LLM scored by option log-probabilities | A probability per option label, from one forward pass | ~4B, ~8–14B, 26–35B (`minicpmv47-35b`, and whichever other models the relay serves healthily) |
| LLM choosing with reasoning (baseline) | A chosen option, with vote share over 3 samples as confidence | the same sizes, thinking on |

Round two's evidence to beat: on entity choice, a pointwise reranker's top pick scored 27 while
an LLM choosing with reasoning scored 77–83 (LELA). Turning reasoning off cut one model from 77
to 54. The roster puts every type against that baseline on Ariadne's own questions.

### 1.2 The steps, in test order

From [`decision-model-tests.md`](../era-2-expansion/decision-model-tests.md), reordered by round
two's evidence:

| Order | Step | Why in this position |
|---|---|---|
| 1 | **D4 relation choice** from the card's menu | Small menus (3–10), the strongest candidate, and it targets the synonym-verb tier (0.4667 today) |
| 2 | **D10 membership by meaning** over large sets | The best fit for batching. Also exercises the vLLM server's throughput |
| 3 | **D2 entity grounding** and **D3 "none of these"** | The largest loss (35% wrong entity) and the hardest step. Tested as a second opinion against the reasoning-LLM baseline, together with the structural none signal |
| 4 | **D1 source routing** | Needed as soon as more than one graph is online |
| 5 | **D7 answer type** | Catches answers that stop one hop short |
| 6 | **D6 property filter** | Untested anywhere |
| 7 | **D9 sufficiency** | A cheap pre-check; the validator keeps the final say |
| 8 | **D12 untrusted-text screening** | Needed before any LLM-built graph goes live |
| 9 | **D5 question shape**, **D8 plan check** | Advisory only, per round two; tested last |

### 1.3 How each step is tested

- **Data:**
  - the Phase 0.5 generated sets (tuning half to set thresholds, held-out half to test them);
  - then, once, the real banks: paraphrase tiers T0–T5, dev 284, sealed 282.
- **Measurements, identical for every step:**
  - accuracy per tier;
  - calibration error;
  - wrong answers at 90%, 70% and 50% coverage;
  - "none" precision and recall;
  - answer changes when options are shuffled;
  - latency, single call and batched on the vLLM server;
  - agreement (κ) with the reasoning-LLM baseline.
- **Run as a matrix:** each step × each model × each size, from the Phase 0.2 runner, with
  treatment and control back to back on one tree.

### 1.4 The rule for assigning a role (to agree before Phase 1 runs)

| Role | Rule (proposed) |
|---|---|
| **Runs the step alone** | On the held-out half: wrong ≤ 5% at ≥ 70% coverage; the threshold set on the tuning half still holds; shuffle flips ≤ 2% |
| **Gate or second opinion** | Lowers the baseline's wrong rate when combined with it, at under a tenth of its latency |
| **Not used** | Neither of the above |

Among models that qualify, take the cheapest within 2 points of the best.

### 1.5 Calibration transfer (one experiment)

Set thresholds on generated questions; apply them unchanged to the real sealed banks.
- **If** the real wrong rate exceeds the target by more than 2 points, generated calibration
  isn't trustworthy alone. The fallback is to make generated sets harder than real traffic, and
  to report every guarantee as "valid for generated questions".

**Phase 1 output:** a table of step × model × size → role, with latency. That table is the
grounding design for Phase 3.

---

## Phase 2 — Typed boundary and the operator algebra

### 2.1 Typed requests

- **The change:**
  - specialists accept only typed requests;
  - per-step option lists are computed from the card;
  - builders stop reading `task.text`;
  - every rejection uses the error contract (`invalid_request`, `empty`, `ambiguous_anchor`,
    `partial`).
- **Test, with no loop:** the current planner emits typed plans.
  - Banks: paraphrase tiers plus dev 284.
  - Gate (from round one): synonym-verb tier ≥ 0.80; empty retrievals (77 today) halve; the
    original tier stays ≥ 0.98; confident-wrong does not rise.
- **Why first in Phase 2:** all four round-one reports put it first. If it recovers most of the
  loss, Phase 4's loop has less to do.

### 2.2 The operator algebra

- **What it needs:** report 6's minimal set, in this order:
  1. property filter;
  2. aggregate;
  3. rank, with ties returned;
  4. verify, with the query as proof;
  5. type scan;
  6. group-by that keeps empty groups.

  Then edge and time filters, union and absence; reach and shortest path last.
- **Semantics to fix in the specification:**
  - deduplicate by identifier;
  - "property present and satisfies" filters;
  - explicit path mode;
  - the card's label mode;
  - per-operator limits (the row cap applies to samples, never to aggregate inputs).
- **First, count CypherBench's question categories from its released data**, to confirm the
  order.
- **Why:** without these operators, the Phase 5 comparison loses on coverage rather than approach.

### 2.3 One compiler per backend, tested against each other

- **The work:** Cypher and Gremlin compilers for every operator.
- **The differential test:** the same data loaded in both, with result sets compared by
  identifier, on every operator instance the generator produces.
- **Gate:** zero disagreements.

Before shipping any builder change, re-run the deterministic path over both banks and diff the
answers against the previous tree.

---

## Phase 3 — Grounding and the fast path

- **Entity:**
  1. exact match;
  2. retrieval (BM25 plus embeddings);
  3. the card's compatibility filter;
  4. an explicit "none" plus the structural none signal;
  5. the Phase 1 roles: second opinion, ask band.

  Only on the slow path does the controller choose, with thinking on.
- **Relation:** the Phase 1 winner over the card's menu. On a near-tie, run both relations.
- **Interpretation check:** compared as a section of this phase. The claim verifier alone,
  against adding round-trip back-translation, a type check, or a decision-model binding check.
  - Inject wrong bindings (sibling entity, sibling relation, reversed direction).
  - Measure confident-wrong answers.
- **Tests:** paraphrase tiers and sealed 282.
  - Measurements: wrong-entity rate at fixed coverage; confident-wrong; abstention precision;
    latency p50/p95 on the fast path.
- **Why here:** this is the path most questions should take; the loop is only its fallback.

## Phase 4 — The controller loop (slow path)

- **Built on GAIFA's loop pattern, with four changes:**
  - typed tools with option lists;
  - envelopes instead of rows;
  - the validator decides when to stop;
  - a cap of six calls.
- **Tests:**
  - single shot vs loop vs fast-path-first;
  - thinking on and off;
  - three stopping rules;
  - across several LLMs;
  - pass^5 for consistency.
- **Gates:** gold coverage ≥ 0.75 (0.8611 is the authored-plan ceiling); correctness stays
  ≥ 0.90; p50/p95 latency reported per path.
- **Completeness study (C-A) in this phase.** Enumeration questions whose answers exceed the row
  cap, with three arms:
  - raw truncated rows;
  - rows plus a truncation label (Jeffries' fix, the baseline to beat);
  - envelope plus composer.

  Measure answer-set recall and the confident-incomplete rate.

## Phase 5 — Universality and the external study

### 5.1 Graphs Ariadne has never seen

- **The CypherBench mirror:** its seven test graphs in Neo4j and a Gremlin server; Neptune, which
  serves openCypher and Gremlin over one copy of the data, when AWS credits allow. The Phase 0.5
  paraphrase tiers are added to its questions.
- **The two-schema pair:** ATT&CK as today, and again in a STIX-style relationship-object model.
- **Synapse graphs.**
- **The zero-code-change protocol for each graph:**
  1. Register it.
  2. Build the card.
  3. Lint the card.
  4. Generate probe questions.
  5. Run them on the deterministic path.
  6. Promote the graph if they pass.

  Any code change needed counts as a failure.

### 5.2 The study (C-B, with C-E as a section)

- **The question:** on the same unseen graphs, with the same models, how do typed requests
  compiled per backend compare with LLM-written Cypher and LLM-written Gremlin?
- **The arms:** free Cypher and free Gremlin, each with a CYGNET-style corrector so the baseline
  is the strongest available, against typed requests compiled to both.
- **Measurements:**
  - records-exact by result set;
  - abstention precision (constraining is known to raise empty answers);
  - wrong entity;
  - latency.
- **Federation (C-E):** cross-source questions, latency split by anchor degree, against a
  merged-store baseline.
- **Before writing anything up:** re-audit C-B and C-E with full reads. Round two's audit was
  abstract-level.

## Phase 6 — The embeddable interface

- **The interface:** MCP with `ariadne_ask` plus the typed primitives, the `AnswerEnvelope`
  response, and `fast` / `auto` / `thorough` modes.
- **Tests:**
  - contract tests on every response;
  - whether calling agents honour abstentions;
  - an injection red team on a Synapse-built graph.

---

## Alongside the phases

- **The era-1 paper.** `docs/research/paper/tmlr/ariadne-tmlr.tex` is a complete draft (last
  edited 2026-09-09) that banks the pre-pitch findings. Submitting it is the operator's call; see
  the note in the next section.
- **The ARA proposal (due 2026-11-04).** Phase 5's study on Neptune is the closest fit to the
  Amazon call. The one-pager's research questions should be re-read against it before submission.
- **Competitor watch, monthly:**
  - Ozsoy / Neo4j (multi-database Text2Cypher);
  - Ant Group / TuGraph (Text2GQL, Gremlin in its framework);
  - text2ql;
  - the SAGA authors.

## The era-1 TMLR draft — what it is and whether it carries over

- **Title:** *Removing the Model from the Query Path: A Deterministic Graph-QA System as a
  Measurement Instrument, and What It Reveals About LLM Graders.*
- **Its findings:**
  - Grading models have a resolution floor near the ceiling, and one local grader inverted the
    ordering of mediocre and good answers.
  - Schema-derived construction beat hand-written templates by +0.1684 judged correctness on 288
    held-out questions.
  - Templates beat a model writing the queries by +0.0822.
  - Federating gave no accuracy over merging, while building the merged store rewrote 1,083 of
    9,138 nodes.
  - Co-authored benchmarks overstate a system.
  - Plus failure localisation, the coverage cliff, and run-to-run variance.
- **Status:** the repository holds no record of a submission. The September venue assessment rated a journal (Semantic Web
  Journal or TMLR) reachable, with TMLR's risk being audience fit.
- **One gap it can't ship with:** it was last edited on 2026-09-09, before `EXP-2026-09-019`
  (2026-09-13) showed that every headline comparison replays an *authored* plan, and that the
  system's own planner costs −0.3814 gold coverage. That has to go into its limitations, and its
  figures have to be re-checked against `CURRENT.md`.
- **Recommendation:** treat it as **era 1's publication, not an era-2 programme.** Finishing it
  is a bounded job (the planner caveat, a figures check, a venue choice) that banks a year of
  work. Era 2's own paper is Phase 5's study. Carrying the TMLR programme into era 2 as live
  research would split effort.
