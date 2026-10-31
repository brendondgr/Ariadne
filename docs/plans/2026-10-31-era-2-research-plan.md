# Era 2 — research plan, step by step toward paper 2 (2026-10-31)

**Status: proposed, for discussion.** Nothing here runs until the operator says go. Each
measurement becomes an experiment only through `make new-experiment`, with its hypotheses and
gates written in `PROTOCOL.md` before it runs.
**What it is built from:** the [era-2 roadmap](2026-10-26-era-2-roadmap.md), which holds the
order and the reasons, laid out here as steps to work from. Behind it are round one's
[`SYNTHESIS.md`](../research/reports/2026-10-26-agentic-loop/SYNTHESIS.md) and round two's
[`ASSESSMENT.md`](../research/reports/2026-10-26-agentic-loop-round-2/ASSESSMENT.md).
**Git:** commit at every step with a `docs/changelog.jsonl` entry; never push.

---

## 1. Introduction

Era 2 makes Ariadne an agent that other systems call to read any knowledge graph and get back
correct, complete, cited information, fast. No language model writes a database query. A
controller sends typed requests, whose options come from each graph's source card, and a
deterministic compiler per backend turns them into Cypher or Gremlin. Only the card and the
compiler change from one graph to the next.

Era 2 ends in **paper 2**, a study measured on graphs Ariadne has never seen. On CypherBench's
test graphs, mirrored into Gremlin, with the same open models in every arm, it compares three
ways of querying:
- typed requests compiled per backend;
- a model writing Cypher;
- a model writing Gremlin.

Answers are scored by whether the exact records come back, with entity names reworded. The
databases compute the right answers, so no grading model is involved. The paper answers these
questions:

| | Research question | Answered in |
|---|---|---|
| **RQ1** (main) | On unseen property graphs, do typed requests compiled per backend return the exact records more often than model-written Cypher and model-written Gremlin? Do they abstain correctly where free generation answers wrongly? | Step 12 |
| **RQ2** | Can "list every X" answers be complete when the controller only sees a bounded view of the results? | Step 10 |
| **RQ3** | Across separate databases on different engines, what does one agent cost in accuracy and latency against a merged store, by how connected the busiest node is? | Step 12 |
| **RQ4** | A public Gremlin version of CypherBench, as a resource | Step 11 |

The steps before the study build what it needs and measure each part on its own, so the study
compares approaches, not missing pieces. Two of those measurements become sections of the
paper's method: which decisions off-the-shelf decision models can own (Step 6), and how much a
typed hand-off recovers over today's English one (Step 7). The paper is then written in its own
frozen repository, the way paper 1 is.

**Decisions this plan takes as given** (operator, 2026-10-26):
1. **Exact results.** The controller's view may be bounded; the answer may not.
2. **Graph-universal.** Only the source card and the per-backend compiler change per graph.
3. **Many models, never one.** Every test runs across a list of models, and the served model is
   recorded on every call.
4. **Off-the-shelf open-source decision models only.** Nothing is trained or fine-tuned for
   Ariadne. A step no off-the-shelf model can own stays with the controller LLM or with
   deterministic code.
5. **Decision models run on a separate vLLM server**, so their calls batch and run concurrently.
6. **Plans live in `docs/plans/`.**

---

## 2. Gaps & Unanswered Questions

- **The disk.** The operator reports that one application was the cause. The kernel log still
  shows checksum errors: 161 since the restart on 2026-10-30, across 13 files from different
  programs, most of them last written in September. That fits old damage being read again
  rather than new damage, but the log alone can't confirm it. *Human intervention is needed to
  answer this question:* a scrub's result, or the confirmed cause. No measurement step runs
  until then.
- **The role rule for decision models** (Step 6): wrong ≤ 5% at ≥ 70% coverage, threshold
  holding from tuning to held-out, and shuffled options flipping ≤ 2% of answers. *Human
  intervention is needed to answer this question:* agree it, or set another, before Step 6
  runs.
- **The typed-request gates** (Step 7):
  - synonym-verb tier ≥ 0.80, from 0.4667 today;
  - empty retrievals halve, from 77 of 284;
  - original wording stays ≥ 0.98;
  - confident-wrong answers don't rise.

  *Human intervention is needed to answer this question:* agree them before Step 7's protocol
  is written. Gates set after the numbers are seen aren't gates.
- **The vLLM server.** *Human intervention is needed to answer this question:* which machine
  and GPU serves the decision models, and what it can hold at once.
- **Neptune.** It needs AWS credits, which the ARA proposal (due 2026-11-04) asks for.
  *Assumption:* the study runs on local Neo4j and a Gremlin server, with Neptune added when
  credits allow. RQ1 doesn't depend on Neptune.
- **CypherBench's licence.** *Assumption:* its released test graphs and questions may be
  mirrored, and the Gremlin copy released. Step 11 checks before downloading or publishing
  anything.
- **The sealed banks.** The sealed rewording bank (`docs/evaluation/variants-holdout-2026-09/`)
  has been opened once per hypothesis, and its T4 and T5 rows are now seen. *Human intervention
  is needed to answer this question:* whether era 2's final checks need a freshly sealed bank of
  real-style questions. Generated questions are not real users.
- **The free-generation arms.** *Assumption:* each gets a CYGNET-style corrector, so the
  baseline is the strongest available. Beating a weak baseline would prove nothing.
- **The venue.** *Assumption:* it is chosen from the study's outcome. The venue prompt maps
  each outcome to venues, so it can run now for deadlines and again when the results are in.
- **Where paper 2 is written.** *Assumption:* era 2 is frozen at a tag once the study is done
  and copied to `~/Papers/Ariadne-Era2`, as era 1 was, so later work can't move its figures.

---

## 3. Hierarchical Step-by-Step Instructions

### Step 1 — Settle the disk (roadmap 0.1)

- **What:**
  - Confirm the cause, and that no new damage is appearing.
  - List every damaged file.
  - Restore `untruncated-generic/generic/answers/A-CMP-01.json` from git.
  - Record the two lost run artifacts in their experiments' `ISSUES.md`.
- **Locations:** system level for the operator (backup, `btrfs scrub`, a SMART check). In the
  repository: `ISSUES.md` of `EXP-2026-09-010`, `EXP-2026-09-012` and `EXP-2026-09-018`,
  appended rather than edited.
- **Rationale:** every later number is read from this disk. A file that reads back wrong looks
  exactly like a defect in the system.
- **For paper 2:** nothing in it is trustworthy until this is settled.

> *Action: Undergo the verification/tests/validation process for this phase (`make
> validate-research` runs without an I/O error; the kernel log shows no new checksum errors over
> a full read of the repository). Once validated, commit (do not push) stating: Era 2 (1 / 14)
> Complete: the disk is settled and its losses are recorded.*

### Step 2 — A model registry and a matrix runner (roadmap 0.2)

- **What:**
  - **A registry:** one file listing every model a test may use, with its endpoint, type, size,
    licence and serving mode. LLMs are on the relay; decision models, rerankers, NLI
    classifiers and embedders are on the vLLM server.
  - **A runner:** any test runs over a list of models from one command, and every result row
    names the model that actually served it.
- **Locations:** new `utils/llm/registry.py` and `utils/llm/models.yaml`; new
  `scripts/matrix_run.py`; `scripts/model_identity.py` (reused); round one's
  `docs/research/reports/2026-10-26-agentic-loop/probe/latency_probe.py` as its first client.
- **Rationale:** the relay's alias has already served four different models. A comparison made
  through an alias records nothing about what was compared.
- **For paper 2:** "the same open models in every arm" is only checkable with this.

> *Action: Undergo the verification/tests/validation process for this phase (the latency probe
> runs across three models from one command, and its output names each served model). Once
> validated, commit (do not push) stating: Era 2 (2 / 14) Complete: the model registry and
> matrix runner work across three models.*

### Step 3 — Timing, and a cause for each empty retrieval (roadmap 0.3)

- **What:**
  - Per-stage timing on every path.
  - One cause for each of the 77 of 284 questions where the planner retrieved nothing and the
    authored plan did: entity, relation, direction, missing operator, or limit.
  - Model-free, on dev 284.
- **Locations:** `utils/orchestration/main.py` (`iter_pipeline`, stage timers); a new
  experiment `empty-retrieval-causes`; `docs/research/OPEN_QUESTIONS.md` (`Q57`, `Q58`).
- **Rationale:** this is the breakdown every later step is judged against. It says where the
  planner's −0.3814 loss lives before anything is built to fix it.
- **For paper 2:** the latency method, and the baseline the typed hand-off is compared with.

> *Action: Undergo the verification/tests/validation process for this phase (`make
> validate-research`; every one of the 77 has exactly one recorded cause; the model-free posture
> asserted at the socket). Once validated, commit (do not push) stating: Era 2 (3 / 14) Complete:
> per-stage timing recorded and every empty retrieval given a cause.*

### Step 4 — Exact answers (roadmap 0.4)

- **What:**
  - Every primitive returns an exact total and a `complete` flag.
  - Full sets are fetched by keyset pagination.
  - The safety ceiling becomes an explicit `partial` status. Today the Cypher connector stops
    at 1,000 rows with no flag.
- **Locations:** `utils/specialists/cypher/connector.py`, `gremlin/connector.py`;
  `utils/specialists/primitives/expand.py` (`paginate`), `describe.py`;
  `utils/synthesis/composer.py` (counts come from the database, never from rows).
- **Rationale:** requirement 1, and a defect that exists today.
- **For paper 2:** RQ2 needs it, and scoring by result set is meaningless if a set is silently
  cut.

> *Action: Undergo the verification/tests/validation process for this phase (zero silent
> truncations; paged sets equal uncapped sets; the composer's count equals the database's;
> synthetic hubs of 10⁵–10⁶ edges in Neo4j and Gremlin answer within the card's timeout at
> p95). Once validated, commit (do not push) stating: Era 2 (4 / 14) Complete: every primitive
> returns exact totals and never truncates silently.*

### Step 5 — A question generator that works from the card alone (roadmap 0.5)

- **What:**
  - **The questions:** from a source card alone, it writes questions at every rewording tier:
    identifier, name, reworded name, description only, and a synonym for the verb.
  - **The answers:** each question comes with its gold entity, relation, plan and records, by
    construction, because the generator executes its own typed request.
  - **The sets:** separate sealed tuning and held-out sets for each decision step.
- **Locations:** new `utils/specialists/evalset/card_generator.py`, reusing `render.py` and
  `make_bank.py`; sets written as `<dir>/<bankname>/bank.json`.
- **Rationale:** it is the one piece every later step uses:
  - Step 6's labelled sets and calibration sets;
  - Step 11's probe questions for a new graph;
  - the reworded names for CypherBench, whose questions name entities verbatim.
- **For paper 2:** the reworded-name condition in RQ1 comes from here.

> *Action: Undergo the verification/tests/validation process for this phase (generated
> questions execute non-empty and match their gold; tuning and held-out sets share no anchors,
> measured pairwise; a person reads a sample for fluency). Once validated, commit (do not push)
> stating: Era 2 (5 / 14) Complete: questions with gold answers are generated from a card
> alone.*

### Step 6 — Which decisions can off-the-shelf decision models own? (roadmap Phase 1)

- **What:** each closed decision is tested in isolation, with correct upstream inputs supplied,
  so a model's error is its own.
  - **Model types:**
    - dedicated decision models (d3-lite and whatever else vLLM can serve);
    - cross-encoder rerankers;
    - NLI classifiers;
    - embedding models (ordering only, never dropping);
    - LLMs scored by option probabilities;
    - LLMs choosing with reasoning, as the baseline to beat.
  - **Sizes:** from under 1B up to 35B, where each type has them.
  - **Decisions, in test order:**
    1. relation choice (D4);
    2. membership by meaning over large sets (D10);
    3. entity grounding and "none of these" (D2, D3);
    4. which graph to ask (D1);
    5. whether the answer is the right kind of node (D7);
    6. property filter (D6);
    7. sufficiency (D9);
    8. screening untrusted text (D12);
    9. question shape and plan check (D5, D8), advisory only.
  - **Measurements, the same for every step:**
    - accuracy per tier;
    - calibration error;
    - wrong answers at 90%, 70% and 50% coverage;
    - "none" precision and recall;
    - answer changes when options are shuffled;
    - latency, single and batched;
    - agreement with the baseline.
  - **One calibration-transfer test:** thresholds set on generated questions, applied
    unchanged to the real banks.
- **Locations:** `docs/era-2-expansion/decision-model-tests.md` (the step definitions); new
  `utils/decision/` (one client per model type, served from the vLLM server); GAIFA's `decide`
  mod on `:5107` for d3-lite; one experiment per decision.
- **Rationale:** it decides which steps a small model can own before anything is built around
  it, and it needs no loop. On entity choice, round two's evidence favours an LLM with
  reasoning (LELA: 77–83 against a reranker's 27), so that step is tested as a second opinion.
- **Output:** a table of decision × model × size → role (alone, gate, or not used), with
  latency.
- **For paper 2:** this table is the grounding design, and a section of the method.

> *Action: Undergo the verification/tests/validation process for this phase (per decision: `make
> validate-research`; the served model recorded on every call; treatment and control back to back
> on one tree; the agreed role rule applied to the held-out half). Once validated, commit (do not
> push) stating: Era 2 (6 / 14) Complete: every decision has a measured role across model types
> and sizes.*

### Step 7 — Typed requests instead of English sub-questions (roadmap 2.1)

- **What:**
  - **Requests:** the specialists accept only typed requests, whose option lists are computed
    from the card.
  - **No text:** the Cypher and Gremlin builders stop re-reading the sub-question's English.
    Today they read `task.text` 17 times with keyword rules.
  - **Errors that teach:** every rejection uses the error contract, which lists the valid
    options:
    - `invalid_request`;
    - `empty`, with a diagnosis;
    - `ambiguous_anchor`;
    - `partial`.
  - **The test:** today's planner emits typed plans, and the same tree is run with the English
    hand-off and with the typed one.
  - **Banks:** the rewording tiers and dev 284.
- **Locations:** new `utils/specialists/request.py`; `utils/specialists/contracts.py`
  (`SpecialistTask`), `errors.py`; `utils/planner/cards.py`, `canonical.py` (`IntentForm`),
  `form_plan.py`, `drafter.py`, `gate.py`; `utils/specialists/cypher/builder.py`,
  `gremlin/builder.py`.
- **Rationale:** every round-one report put this first, and it can be tested without a loop.
  If it recovers most of the planner's loss, Step 10's loop has less to do. If not, Step 3's
  causes say where the loss lives.
- **For paper 2:** this defines the typed arm, and its result is a section of the method.

> *Action: Undergo the verification/tests/validation process for this phase (a contract test
> that replaces each typed task's text with nonsense and gets identical queries and records; the
> agreed gates; the deterministic path re-run over both banks and diffed against the previous
> tree, excluding clock keys). Once validated, commit (do not push) stating: Era 2 (7 / 14)
> Complete: the specialists take typed requests and never read text.*

### Step 8 — The operator set, compiled to both backends (roadmap 2.2, 2.3)

- **What:**
  - **First, count** CypherBench's question categories from its released data, to confirm the
    order below.
  - **Then the operators, in order:**
    1. property filter;
    2. aggregate;
    3. rank, with ties returned;
    4. verify, with the query as proof;
    5. type scan;
    6. group-by that keeps empty groups;
    7. edge and time filters, union and absence;
    8. reach and shortest path, last.
  - **Semantics fixed in writing first:**
    - deduplicate by identifier;
    - a filter means the property is present and satisfies it;
    - explicit path mode;
    - the card's label mode;
    - per-operator limits (the row cap applies to samples, never to an aggregate's inputs).
  - **One compiler per backend**, Cypher and Gremlin.
  - **A differential test:** the same data in both stores, with result sets compared by
    identifier on every operator instance the generator writes.
- **Locations:** new `scripts/count_question_shapes.py`; new `utils/specialists/algebra/`
  (one module per operator, plus `differential.py`); new `utils/specialists/cypher/compile.py`
  and `utils/specialists/gremlin/compile.py`; `docs/era-2-expansion/operator-algebra.md`.
- **Rationale:** today's requests can only describe, expand, join, chain and intersect.
  Without the rest, an unfamiliar graph's questions fall outside what a request can say, and
  the typed arm would lose on coverage rather than on approach.
- **For paper 2:** RQ1 is a fair comparison only after this step.

> *Action: Undergo the verification/tests/validation process for this phase (per operator:
> unit tests on a fixture graph; zero disagreements between Cypher and Gremlin; exact totals).
> Once validated, commit (do not push) stating: Era 2 (8 / 14) Complete: the operator set
> compiles to Cypher and Gremlin with zero disagreements.*

### Step 9 — Grounding, and the fast path (roadmap Phase 3)

- **What:**
  - **Entity:**
    1. exact match;
    2. retrieval (BM25 plus embeddings);
    3. the card's compatibility filter;
    4. an explicit "none", plus the structural none signal;
    5. Step 6's roles: second opinion, and when to ask.
  - **Relation:** Step 6's winner over the card's menu; on a near-tie, run both relations.
  - **Interpretation check:** the claim verifier alone, against adding round-trip
    back-translation, a type check, or a decision-model binding check. Tested by injecting
    wrong bindings (sibling entity, sibling relation, reversed direction).
  - **Banks:** the rewording tiers and the sealed 282.
- **Locations:** `utils/specialists/schema/namesearch.py`, `rerank.py`;
  `utils/specialists/resolve/resolver.py`, `binding.py`; `utils/planner/gate.py`;
  `utils/synthesis/verifier.py`.
- **Rationale:** most questions should take this millisecond path; the loop is only its
  fallback.
- **For paper 2:** reworded entity names are part of RQ1, and this is how the typed arm finds
  the entity.

> *Action: Undergo the verification/tests/validation process for this phase (wrong-entity rate at
> fixed coverage; confident-wrong answers; abstention precision; fast-path latency p50 and p95,
> all recorded). Once validated, commit (do not push) stating: Era 2 (9 / 14) Complete:
> grounding and the fast path are measured.*

### Step 10 — The controller loop, and complete answers (roadmap Phase 4; RQ2)

- **What:**
  - **The loop:** GAIFA's loop pattern, with four changes:
    - typed tools with option lists;
    - summaries with exact totals ("envelopes") in place of raw rows;
    - the validator decides when to stop;
    - a cap of six calls.
  - **Tests:**
    - single shot against the loop against fast path first;
    - thinking on and off;
    - three stopping rules;
    - several LLMs;
    - five repeats for consistency.
  - **Complete answers (RQ2):** enumeration questions whose answers exceed the row cap, with
    three arms:
    - raw truncated rows;
    - rows plus a truncation label (the baseline to beat);
    - envelope plus composer.
- **Locations:** new `utils/controller/`, modelled on `~/Agents/GAIFA/services/agent`;
  `utils/orchestration/main.py`; `utils/synthesis/composer.py`.
- **Rationale:** it is built only for what the fast path leaves, so its size is known before it
  is built.
- **For paper 2:** RQ2's section.

> *Action: Undergo the verification/tests/validation process for this phase (gold coverage ≥ 0.75
> against the authored-plan ceiling of 0.8611; correctness ≥ 0.90; latency per path; for RQ2,
> answer-set recall and the confident-incomplete rate per arm). Once validated, commit (do not
> push) stating: Era 2 (10 / 14) Complete: the loop and complete answers are measured.*

### Step 11 — Graphs Ariadne has never seen (roadmap 5.1; RQ4)

- **What:**
  - **The CypherBench mirror:** its seven test graphs, loaded into Neo4j and a Gremlin server
    (Neptune when credits allow), with Step 5's reworded names added to its questions.
  - **The two-schema pair:** ATT&CK as today, and again in a STIX-style relationship-object
    model. That separates schema difficulty from content difficulty.
  - **Synapse graphs.**
  - **The zero-code-change protocol for each graph:**
    1. register it;
    2. build its card;
    3. lint the card;
    4. generate probe questions;
    5. run them on the deterministic path;
    6. promote the graph if they pass.

    Any code change needed counts as a failure.
- **Locations:** `utils/graph_loader/`, `utils/kg_builder/`; `utils/specialists/schema/build.py`
  (cards and the lint); new `scripts/cypherbench_mirror.py`; the released Gremlin copy in a new
  `docs/evaluation/cypherbench-gremlin/`, licence permitting.
- **Rationale:** universality is a claim about graphs the system was not built on. This makes it
  measurable.
- **For paper 2:** the study's test bed, and the RQ4 resource itself.

> *Action: Undergo the verification/tests/validation process for this phase (every graph passes
> the protocol with no code change, or the change is recorded as a failure; the Gremlin copy's
> answers match the Neo4j copy's by identifier). Once validated, commit (do not push) stating:
> Era 2 (11 / 14) Complete: the unseen graphs are loaded, carded and probed.*

### Step 12 — The study (roadmap 5.2; RQ1, RQ3)

- **What:**
  - **The question:** on the same unseen graphs, with the same models, how do typed requests
    compiled per backend compare with model-written Cypher and model-written Gremlin?
  - **The arms:**
    - free Cypher, with a CYGNET-style corrector;
    - free Gremlin, with the same corrector;
    - typed requests compiled to both.
  - **The models:** at least three, from the registry.
  - **Measurements:**
    - exact records by result set;
    - abstention precision, since constraining is known to raise empty answers;
    - wrong entity;
    - latency.
  - **Federation (RQ3):** cross-source questions, with latency split by the anchor's degree,
    against a merged store.
  - **Before writing anything:** re-audit the novelty of RQ1 and RQ3 with full reads. Round
    two's audit was abstract-level.
- **Locations:** a new experiment `typed-vs-free-query`, pre-registered before any arm runs;
  a new arm runner in `utils/evaluation/`; `docs/research/CLAIMS.md` and
  `docs/research/RELATED_WORK.md`; the paper-extraction service (`~/Tools/PubMedExtraction`)
  for full texts.
- **Rationale:** this is the paper. Every earlier step exists so that it compares approaches
  and nothing else.
- **For paper 2:** the main result and the federation section.

> *Action: Undergo the verification/tests/validation process for this phase (`make
> check-record`; every arm on one tree, back to back; the served model on every call; the
> pre-registered analysis followed, with deviations recorded). Once validated, commit (do not
> push) stating: Era 2 (12 / 14) Complete: the typed-vs-free study is measured and recorded.*

### Step 13 — The interface other systems call (roadmap Phase 6)

- **What:** an MCP server with `ariadne_ask` plus the typed primitives. It returns the
  `AnswerEnvelope` and offers `fast`, `auto` and `thorough` modes. Tested three ways:
  - contract tests on every response;
  - whether calling agents honour abstentions;
  - a red team that plants instructions in a Synapse-built graph's text.
- **Locations:** new `utils/mcp/`, wrapping `utils/orchestration/`; the response contracts in
  `utils/synthesis/contracts.py`.
- **Rationale:** it wraps a working system, so it comes last. It is era 2's product goal
  rather than something paper 2 needs, so it runs alongside the write-up.
- **For paper 2:** at most a short section on how other agents use it.

> *Action: Undergo the verification/tests/validation process for this phase (contract tests on
> every response; the abstention and red-team results recorded). Once validated, commit (do not
> push) stating: Era 2 (13 / 14) Complete: Ariadne is callable over MCP.*

### Step 14 — Paper 2

- **What:**
  1. Run the venue prompt with the actual outcome, and pick the venue from it.
  2. Run a field refresh for paper 2, as for paper 1: prompts sharing one brief of the
     findings, re-run before submission, with full texts fetched for every citation.
  3. Freeze era 2 at a tag, and copy it to its own repository (`~/Papers/Ariadne-Era2`).
  4. Write the paper there.
- **Locations:** `docs/prompts/2026-10-27-paper-2-venue-selection.md`; new field-refresh
  prompts in `docs/prompts/`; the frozen copy, with its own `FREEZE.md` and `CLAUDE.md`, as in
  `~/Papers/Ariadne-Era1`.
- **Rationale:** paper 1 showed that writing from a tree that keeps changing moves the
  figures under the draft.
- **For paper 2:** the paper.

> *Action: Undergo the verification/tests/validation process for this phase (every figure in the
> draft quoted from `CURRENT.md`; `make check-docs`; every citation read in full). Once validated,
> commit (do not push) stating: Era 2 (14 / 14) Complete: paper 2 is drafted from a frozen tree.*

### Running it in order

| Track | Steps | Waits for |
|---|---|---|
| Foundations | 1 → 2 → 3 → 4 → 5 | Step 1 before any measurement |
| Decision models (measurement) | 6 | 2, 5; the agreed role rule |
| Typed requests and operators (engineering) | 7 → 8 | 3 (to read Step 7's result), 4, 5; the agreed gates |
| Grounding and the loop | 9 → 10 | 6, 7, 8 |
| Unseen graphs and the study | 11 → 12 | 8, 9, 10 (Step 11's loading can start after Step 4) |
| Interface and paper | 13 alongside 14 | 12 |

Steps 6 and 7–8 run in parallel: one is measurement, the other engineering, and they touch
different code.

**Alongside the steps:**
- **Paper 1** is written in `~/Papers/Ariadne-Era1`, frozen at `era-1-final`, so nothing here
  touches its figures.
- **The ARA proposal** is due 2026-11-04. Step 12 on Neptune is the closest fit to the Amazon
  call.
- **Competitor watch, monthly:**
  - Ozsoy / Neo4j (multi-database Text2Cypher);
  - Ant Group / TuGraph (Text2GQL);
  - text2ql;
  - the SAGA authors.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Disk record | Damaged files listed; tracked file restored; losses recorded | `ISSUES.md` of `EXP-2026-09-010`, `-09-012`, `-09-018` |
| Model registry | Every model a test may use, with endpoint, type, size and licence | `utils/llm/registry.py`, `utils/llm/models.yaml` |
| Matrix runner | Any test across a list of models; served model on every row | `scripts/matrix_run.py` |
| Empty-retrieval causes | One cause for each of the 77; per-stage timing | experiment `empty-retrieval-causes`; `utils/orchestration/main.py` |
| Exact answers | Totals, `complete` and `partial` on every primitive; keyset pagination | `utils/specialists/cypher/connector.py`, `gremlin/connector.py`, `primitives/` |
| Card question generator | Questions at every tier with gold by construction; sealed sets per decision | `utils/specialists/evalset/card_generator.py` |
| Decision-model roles | Decision × model × size → role, with latency | `utils/decision/`; one experiment per decision |
| Typed requests | The request type, the card's option lists and the teaching errors | `utils/specialists/request.py`, `contracts.py`, `errors.py`; `utils/planner/cards.py` |
| Operator set and compilers | Every operator, compiled to Cypher and Gremlin | `utils/specialists/algebra/`; `cypher/compile.py`; `gremlin/compile.py` |
| Grounding fast path | Entity ladder, relation choice, interpretation check | `utils/specialists/schema/`, `resolve/`, `binding.py` |
| Controller loop | Typed tools, envelopes, validator stop, six-call cap | `utils/controller/` |
| CypherBench mirror and Gremlin copy | The study's test bed and the RQ4 resource | `scripts/cypherbench_mirror.py`; `docs/evaluation/cypherbench-gremlin/` |
| The study | Typed vs free Cypher vs free Gremlin; federation section | experiment `typed-vs-free-query` |
| MCP interface | `ariadne_ask`, the typed primitives, `AnswerEnvelope`, three modes | `utils/mcp/` |
| Paper 2 | Venue, field refresh, frozen copy, draft | `~/Papers/Ariadne-Era2` |
| **Test:** registry and runner | Three models in one command on a two-question slice; each row names its served model | `utils/llm/tests/test_registry.py` |
| **Test:** exact totals | Paged sets equal unpaged; totals equal the database's count; no silent cut, on a fixture graph | `utils/specialists/tests/test_exact_totals.py` |
| **Test:** generator | Generated questions on a small fixture card execute and match their gold | `utils/specialists/evalset/tests/test_card_generator.py` |
| **Test:** decision clients | Each model type returns a probability per option on a five-question slice | `utils/decision/tests/test_clients.py` |
| **Test:** text is never read | A typed task with nonsense text gives identical queries and records | `utils/specialists/tests/test_typed_boundary.py` |
| **Test:** operator semantics | Ties returned, empty groups kept, identifier dedup, on a fixture graph | `utils/specialists/algebra/tests/test_semantics.py` |
| **Test:** differential | Cypher and Gremlin agree by identifier on generated instances (live stores; skipped when down) | `utils/specialists/algebra/tests/test_differential.py` |
| **Test:** loop stop and cap | The loop stops on the validator and never exceeds six calls, on a scripted model | `utils/controller/tests/test_loop.py` |
| **Test:** zero-code-change | A small new fixture graph is carded, linted and probed with no code change | `utils/graph_loader/tests/test_new_graph_protocol.py` |
| **Test:** MCP contract | Every response validates against the `AnswerEnvelope` schema | `utils/mcp/tests/test_contract.py` |
