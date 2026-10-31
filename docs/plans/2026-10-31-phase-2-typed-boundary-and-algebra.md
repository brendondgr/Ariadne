# Phase 2 — The typed boundary and the operator algebra (2026-10-31)

**Status: proposed, for discussion.** Nothing here runs until the operator says go. Each
measurement becomes an experiment only through `make new-experiment`, with its hypotheses and
gates written in `PROTOCOL.md` before it runs.
**Parent plan:** [`2026-10-26-era-2-roadmap.md`](2026-10-26-era-2-roadmap.md), Phase 2.
**Git:** commit at every step with a `docs/changelog.jsonl` entry; never push.

---

## 1. Introduction

Today the planner works out what a question means, then writes that meaning back out as an
English sub-question. The Cypher and Gremlin specialists read that English again with keyword
rules (`asks_for_bulk_scan`, `is_definitional_request`, exact-name matching): 17 reads of
`task.text` across `utils/specialists/cypher/builder.py` and `gremlin/builder.py`. So the
"deterministic" engine is itself parsing language. Every round-one report named this the most
consequential defect, and every one said it can be tested without building a loop. Era 1 already
measured where it bites:
- the system's own planner costs −0.3814 gold coverage against an authored plan (`Q57`);
- 77 of 284 questions retrieve nothing under the planner;
- the synonym-verb paraphrase tier falls to 0.4667 (`C-014`).

Phase 2 replaces that English hand-off with a **typed request**: fields whose values come from
the source card. It then widens what a request can say, with an **operator algebra** covering
the question shapes other graphs ask, compiled separately for each backend and checked against
each other. It answers three research questions, in this order:

| | Research question | How it is answered |
|---|---|---|
| **RQ1** | How much of the planner's loss and the paraphrase cliff comes from the specialists re-reading language, rather than from the plan itself? | Experiment A: the same planner, the same tree, a text boundary against a typed one |
| **RQ2** | Which operators does a graph-universal system need, and in what order? | Experiment B: count question shapes in CypherBench's released data and in our banks, before building anything |
| **RQ3** | Can one operator algebra compile to Cypher and Gremlin with identical answers? | Experiment C: a differential test, comparing result sets by identifier, on every operator instance the generator writes |

This phase is engineering with measurement at its seams. It is also the foundation of era 2's
paper: Phase 5's study (typed requests against LLM-written Cypher and Gremlin, `C-B`) is only fair
once the algebra covers what the unseen graphs ask. Without it, the typed arm would lose on
coverage rather than on approach.

---

## 2. Gaps & Unanswered Questions

- **The disk.** The btrfs checksum failures (roadmap 0.1) are not yet reported fixed. A
  measurement read from a failing disk can look like a defect. *Human intervention is needed to
  answer this question:* the scrub, SMART check and backup are the operator's. No measurement
  step below (0, 4, 5, 10) runs until they are done. The specification and code steps can.
- **Phase 0 is not done, and Phase 2 depends on three parts of it.**
  - 0.4 (exact totals, keyset pagination, a `partial` status) is what every operator returns.
  - 0.5 (the card-driven question generator) produces the instances the differential test
    runs on.
  - 0.3 (a cause for each of the 77 empty retrievals) is how Experiment A's result is read.

  *Assumption:* Steps 1–3 and 6 start now; Step 4 waits for 0.3; Steps 7–9 wait for 0.4 and 0.5.
- **The gates.** Experiment A's gates are round one's:
  - synonym-verb tier ≥ 0.80;
  - empty retrievals halve;
  - the original-wording tier stays ≥ 0.98;
  - confident-wrong answers do not rise.

  *Human intervention is needed to answer this question:* agree them, or set others, before
  Step 4's protocol is written. Gates set after the numbers are seen are not gates.
- **Which planner.** *Assumption:* the deterministic drafter is the primary arm. It is
  model-free, and it is the arm behind the −0.3814. An LLM-drafter arm runs second, across at
  least three models through the Phase 0.2 runner, with the served model recorded on every call.
- **The old text path.** *Assumption:* it stays behind a flag until Experiment A is written up,
  because it is the control. Removing it is a decision taken after, recorded in `DECISIONS.md`.
- **MITRE-specific language rules.** `utils/planner/intent.py`, `canonical.py` and
  `lexicon.py` carry ATT&CK and CAPEC patterns (`C-010`). This phase takes them out of the
  **specialists** only. The planner still uses them until Phases 1 and 3 replace grounding.
  *Assumption:* that split is intended. Phase 2 measures the boundary, not the planner.
- **Banks.** *Assumption:* dev 284 and the T0–T5 paraphrase tiers only. The sealed 282 is kept
  for Phase 3, and nothing here spends a holdout.
- **CypherBench's data and licence.** *Assumption:* the released test split from the authors'
  repository is usable for counting and, in Phase 5, for loading. Step 5 checks the licence
  before downloading anything.
- **Neptune.** Shortest path and some text predicates differ on Neptune. *Assumption:* local
  Neo4j and TinkerPop for now; a Neptune check is added when AWS credits allow (roadmap 5.1).
- **Paper 1.** Changing the builders breaks reproduction of era-1 figures in this tree. That is
  why era 1 is frozen in `~/Papers/Ariadne-Era1`; nothing here touches that copy.

---

## 3. Hierarchical Step-by-Step Instructions

### Step 0 — Pre-register Experiment A and record its baseline

- **What:**
  - Scaffold the experiment (`make new-experiment SLUG=typed-boundary`).
  - Write `PROTOCOL.md`: RQ1, the arms, the banks, the metrics, the agreed gates, the stopping
    rule.
  - Tag the tree `pre-phase-2` and run the current system over dev 284 and T0–T5 on it, to
    record the baseline: records-exact per tier, gold coverage, empty retrievals,
    confident-wrong, abstention precision, latency.
- **Locations:** `docs/research/experiments/EXP-…-typed-boundary/` (`PROTOCOL.md`,
  `manifest.yaml`); `utils/evaluation/experiment_untruncated.py` (the existing arm runner);
  the tiered variant bank authored in `EXP-2026-08-020` and re-baselined on one tree by
  `EXP-2026-09-021`.
- **Rationale:** the baseline has to come from the same tree and the same night as the
  treatment. In era 1, a mid-run commit changed 11 of 284 claims and looked like a defect. The
  record's earlier figures are context, not the control.
- **Assert the posture at the socket.** `iter_pipeline`'s `use_llm` overrides every
  `*_LLM_ENABLED`, so a model-free arm is proven model-free by patching the socket, not by
  reading the config (`EXP-2026-09-019` I-1).

> *Action: Undergo the verification/tests/validation process for this phase (`make
> validate-research`, `make check-docs`). Once validated, commit (do not push) stating: Phase 2
> (0 / 10) Complete: Experiment A pre-registered and its baseline recorded on the pre-change tree.*

### Step 1 — Specify the typed request and the error contract

- **What:** one written specification and one type.
  - **Fields** (the property-graph model, so the same for every graph): `source`,
    `anchor.id` / `anchor.label` / name candidates, `relation`, `direction`, `target_label`,
    `filters[]`, `join_key`, `operator`, per-operator `limits`.
  - **Values** are computed at runtime from the loaded card:
    - labels and allowed (source label, relation, target label) patterns;
    - properties and their types;
    - identifier schemes and shared join keys.
  - **The error contract, which teaches:** each rejection names what was wrong and lists the
    valid options, like GAIFA's `fix` field.
    - `invalid_request`: the valid values;
    - `empty`: whether the anchor exists, the relations it actually has with counts, and the
      count in the reverse direction;
    - `ambiguous_anchor`: the compatible candidates;
    - `partial`: the exact total and the limit hit.
- **Locations:**
  - new `docs/era-2-expansion/typed-request-spec.md`;
  - new `utils/specialists/request.py` (`TypedRequest` and its card validation);
  - `utils/specialists/errors.py` (the four error kinds and their option lists);
  - `utils/planner/cards.py` (`SourceCardView` gains the option menus);
  - `utils/planner/canonical.py` (`IntentForm` already holds most of these slots: extend it,
    don't duplicate it).
- **Rationale:** every later step builds on this type. Building it on `IntentForm` keeps the
  path `EXP-2026-09-025` already proved, where a form is executed directly rather than rendered
  to text.

> *Action: Undergo the verification/tests/validation process for this phase (unit tests: every
> field validated against a card; every rejection lists valid options; round-trip to and from
> JSON). Once validated, commit (do not push) stating: Phase 2 (1 / 10) Complete: the typed
> request and its teaching error contract are specified and typed.*

### Step 2 — Carry the request to the specialists, with no text

- **What:**
  - `SpecialistTask` and `SubQuestion` carry an optional `TypedRequest`.
  - `plan_from_form` fills it instead of putting the anchor's identifier in the text.
  - When a request is present, both builders take a typed route that never reads `task.text`.
  - The old route stays behind a flag (`ARIADNE_TYPED_BOUNDARY`) as Experiment A's control.
- **Locations:**
  - `utils/specialists/contracts.py` (`SpecialistTask`, `from_sub_question`);
  - `utils/planner/schema.py` (`SubQuestion`);
  - `utils/planner/form_plan.py` (`plan_from_form`, `_describe_text`);
  - `utils/specialists/cypher/builder.py` and `gremlin/builder.py` (the 17 `task.text` reads);
  - `utils/specialists/resolve/resolver.py`;
  - `utils/config.py` (the flag).
- **Rationale:** this is RQ1's treatment, and the smallest change that isolates it. The planner
  is untouched, so any difference Experiment A measures is the boundary's.
- **The proof that text is not read:** a contract test runs each typed task twice, once with
  its text and once with the text replaced by nonsense, and asserts identical queries and
  records.

> *Action: Undergo the verification/tests/validation process for this phase (the
> nonsense-text contract test; the full `utils/specialists` and `utils/planner` suites; with
> the flag off, the deterministic path re-run over both banks and diffed against `pre-phase-2`
> excluding clock keys, which must be identical). Once validated, commit (do not push) stating:
> Phase 2 (2 / 10) Complete: specialists accept typed requests and never read text when given
> one.*

### Step 3 — The planner emits typed plans

- **What:**
  - **The deterministic drafter** emits a `TypedRequest` for every sub-question it can bind,
    and a plain `UnsupportedPart` for one it can't. It doesn't guess.
  - **The LLM drafter** fills the same request from the card's option menus, not from free
    text.
  - **The gate** validates every request against the card before execution.
- **Locations:** `utils/planner/drafter.py`, `llm_drafter.py`, `gate.py`, `canonical.py`;
  `utils/planner/schema.py` (`Plan`).
- **Rationale:** the roadmap's test is "the current planner emits typed plans, with no loop".
  Changing what the planner hands over, and nothing else about how it decides, keeps RQ1 clean.

> *Action: Undergo the verification/tests/validation process for this phase (planner unit
> tests; every emitted request passes the gate on dev 284; nonsense-text contract test still
> green). Once validated, commit (do not push) stating: Phase 2 (3 / 10) Complete: the planner
> emits typed plans checked against the card.*

### Step 4 — Experiment A: does the typed boundary recover the loss? (RQ1)

- **What:** both arms run back to back on one tree, differing only in the flag.
  - **Arms:** text boundary against typed boundary.
  - **Banks:** dev 284 and T0–T5.
  - **Planners:** the deterministic drafter first. Then the LLM drafter across at least three
    models, through the Phase 0.2 runner.
  - **Measures:**
    - records-exact per tier;
    - gold coverage against the authored-plan ceiling;
    - empty retrievals, each with its Phase 0.3 cause;
    - confident-wrong answers;
    - abstention precision;
    - latency p50 and p95.
  - **Pairing:** every difference is paired per question.
- **Locations:** the experiment folder from Step 0 (`RESULTS.md`, `data/metrics.json`);
  `utils/evaluation/experiment_untruncated.py` (two new arms); the Phase 0.2 matrix runner.
- **Rationale:** this is the decision point for the rest of era 2.
  - **If the typed boundary recovers most of the loss,** Phase 4's controller loop only handles
    the residue, and its size is known before it is built.
  - **If it does not,** the 0.3 causes say where the loss lives: entity grounding (Phases 1 and
    3), a missing operator (Steps 6–9), or limits (`Q58`).
- **Reading the result:** a gate missed is reported as missed. The flag stays off, and the
  write-up says which cause dominated.

> *Action: Undergo the verification/tests/validation process for this phase (`make
> validate-research`; the posture asserted at the socket for every model-free arm; the served
> model recorded on every LLM call). Once validated, commit (do not push) stating: Phase 2
> (4 / 10) Complete: Experiment A measured the typed boundary against the text boundary on one
> tree.*

### Step 5 — Experiment B: count the question shapes before building operators (RQ2)

- **What:**
  - Check CypherBench's licence, then download its released test split.
  - Count its question categories from the data itself (`match_category`,
    `return_pattern_id`), not from the paper's chart.
  - Count the same shapes in our banks, and in the 77 empties' causes.
  - Produce the operator priority table this phase builds from.
- **Locations:**
  - new `scripts/count_question_shapes.py`;
  - new experiment `EXP-…-question-shape-census` (`data/`, `RESULTS.md`);
  - the download goes in its own new directory under `data/`, never next to scripts.
- **Rationale:** report 6's order (filter, aggregate, rank, verify, scan, group, then edge
  filter, union, absence, then reach and shortest path) rests on frequencies it could only see
  as a chart. A day's counting decides weeks of building. This step needs nothing else in the
  phase, so it can run any time after the disk check.

> *Action: Undergo the verification/tests/validation process for this phase (`make
> validate-research`; the counts re-derived from the raw files by the script, never typed in).
> Once validated, commit (do not push) stating: Phase 2 (5 / 10) Complete: question shapes
> counted from CypherBench's released data and our banks; operator order confirmed or revised.*

### Step 6 — Specify the operator algebra

- **What:** one specification, written before any compiler. For each operator:
  - its typed fields;
  - its semantics;
  - its limits;
  - the envelope it returns: exact total, a `complete` flag and a bounded sample.

  **Semantics fixed in writing:**
  - deduplicate on identifier, never on display name;
  - ranking returns every tied row plus a tie count;
  - a filter means "the property is present and satisfies the predicate", with absence as its
    own operator;
  - paths carry an explicit mode, acyclic by default;
  - the card records whether nodes carry one label or several.

  **Limits are per operator:**
  - the depth cap of 3 applies to expand chains, not to `reach`;
  - the row cap applies to samples, never to the inputs of an aggregate.
- **Locations:** new `docs/era-2-expansion/operator-algebra.md`; new package
  `utils/specialists/algebra/` (one module per operator: fields, validation against the card,
  semantics notes); `utils/specialists/request.py` (the `operator` field).
- **Rationale:** the Cypher and Gremlin answers can only be compared against one written
  meaning. Known traps, such as Gremlin dropping empty groups where Cypher's `OPTIONAL MATCH`
  keeps them, are semantics questions. They are settled here rather than discovered in a
  compiler.

> *Action: Undergo the verification/tests/validation process for this phase (unit tests: each
> operator validates its fields against a card and rejects invalid ones with options). Once
> validated, commit (do not push) stating: Phase 2 (6 / 10) Complete: the operator algebra is
> specified, with semantics and per-operator limits.*

### Step 7 — The differential harness, before the first operator (RQ3)

- **What:**
  - **Data:** a small fixture graph loaded identically into Neo4j and TinkerPop.
  - **Inputs:** the Phase 0.5 generator writes operator instances from that graph's card.
  - **The comparison:** each instance runs through both compilers, and the result sets are
    compared by identifier, along with totals and `complete` flags.
  - **Output:** any disagreement is written out with both queries.
- **Locations:** new `utils/specialists/algebra/differential.py`; a fixture in
  `utils/specialists/algebra/tests/fixtures/`; a live-store test
  `utils/specialists/algebra/tests/test_differential.py`, skipped when the stores are down; new
  `scripts/differential_run.py` for the full run.
- **Rationale:** building the harness first means every operator lands already gated. Fixing
  a compiler after the operators pile up is the expensive order.

> *Action: Undergo the verification/tests/validation process for this phase (the harness
> passes on today's `describe` and `expand`, which both backends already serve). Once
> validated, commit (do not push) stating: Phase 2 (7 / 10) Complete: the Cypher-vs-Gremlin
> differential harness runs on generated instances.*

### Step 8 — Operators, batch 1: filter, aggregate, rank, verify, scan, group

- **What:** one operator per commit, each with both compilers. Each is merged only at zero
  differential disagreements and with Phase 0.4's exact totals. `verify` returns the executed
  query and record as its witness. `group` keeps empty groups.
- **Locations:** `utils/specialists/algebra/<operator>.py`; new compilers
  `utils/specialists/cypher/compile.py` and `utils/specialists/gremlin/compile.py`, kept
  separate from the legacy builders so the old path is untouched.
- **Rationale:** round two found these six cover every gap the brief listed except paths, and
  most of GrailQA's and CypherBench's shapes. Step 5 may reorder them.

> *Action: Undergo the verification/tests/validation process for this phase (per operator:
> unit tests; zero differential disagreements; a hub of 10⁵–10⁶ edges within the card's timeout
> for `scan`, `aggregate` and `group`). Once validated, commit (do not push) stating: Phase 2
> (8 / 10) Complete: six operators compile to both backends with zero disagreements.*

### Step 9 — Operators, batches 2 and 3: edge and time filters, union, absence; then reach and shortest path

- **What:** the same procedure as Step 8.
  - **Batch 2:** edge-property and validity-interval filters need relationship properties in
    the card, so the card builder is checked for them first. `union` uses set semantics on
    identifier. Absence is "X with no Y".
  - **Batch 3:** `reach` (variable-length, acyclic) and `shortest`, last because no KGQA
    benchmark measures them.
- **Locations:** as Step 8, plus `utils/specialists/schema/build.py` (relationship properties
  in the card).
- **Rationale:** absence matters most for security graphs ("techniques with no mitigation").
  Paths matter least for coverage, and differ most between backends.

> *Action: Undergo the verification/tests/validation process for this phase (as Step 8, per
> operator). Once validated, commit (do not push) stating: Phase 2 (9 / 10) Complete: the full
> operator set compiles to both backends with zero disagreements.*

### Step 10 — Experiment C: what the algebra now covers, and the write-up

- **What:**
  - **Static coverage:** the share of CypherBench's question shapes the algebra can express,
    counted from Step 5's census.
  - **Measured coverage:** dev 284 and T0–T5 re-run with the full algebra and the typed
    boundary on, against Step 4's typed arm on one tree.
  - **Agreement:** the differential result over every generated instance.
  - **The record:** `RESULTS.md` for Experiments A to C. A `CLAIMS.md` row for what RQ1
    established, and what `C-B`'s Phase 5 comparison inherits. `DECISIONS.md` for removing
    or keeping the text path. `OPEN_QUESTIONS.md` updates to `Q57` and `Q58`.
- **Locations:** new experiment `EXP-…-operator-algebra-coverage`; `docs/research/CLAIMS.md`,
  `DECISIONS.md`, `OPEN_QUESTIONS.md`; `make index` for `CURRENT.md`.
- **Rationale:** Phase 3 (grounding and the fast path) and Phase 5 (the study) both start from
  this phase's numbers, so they have to be in the record, not in a chat.

> *Action: Undergo the verification/tests/validation process for this phase (`make
> check-record`; recorded-answer regression of the shipped default against `pre-phase-2`, every
> difference explained). Once validated, commit (do not push) stating: Phase 2 (10 / 10)
> Complete: the typed boundary and operator algebra are measured and recorded.*

### Running it in order

| Track | Steps | Waits for |
|---|---|---|
| Typed boundary (RQ1) | 0 → 1 → 2 → 3 → 4 | the disk check (0); Phase 0.3 (4); agreed gates (0) |
| Shape census (RQ2) | 5 | the disk check only; can run any time |
| Algebra (RQ3) | 6 → 7 → 8 → 9 | Step 1 (6); Phase 0.4 and 0.5 (7) |
| Write-up | 10 | everything above |

The typed-boundary and algebra tracks touch different files after Step 2, so they can overlap.
Phase 1's decision-model bake-off runs alongside this whole phase, on different code.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Experiment A protocol and baseline | RQ1's hypotheses, gates and pre-change measurements | `docs/research/experiments/EXP-…-typed-boundary/` |
| Typed request specification | Fields, card-derived values, teaching error contract | `docs/era-2-expansion/typed-request-spec.md` |
| `TypedRequest` type | The request and its validation against a card | `utils/specialists/request.py` |
| Teaching errors | `invalid_request`, `empty`, `ambiguous_anchor`, `partial`, each listing valid options | `utils/specialists/errors.py` |
| Card option menus | Labels, patterns, properties and join keys a request may use | `utils/planner/cards.py` (`SourceCardView`) |
| Typed specialist route | Builders take the request and never read `task.text`; old route behind `ARIADNE_TYPED_BOUNDARY` | `utils/specialists/contracts.py`, `cypher/builder.py`, `gremlin/builder.py`, `utils/planner/form_plan.py` |
| Typed planner output | Deterministic and LLM drafters emit typed requests checked by the gate | `utils/planner/drafter.py`, `llm_drafter.py`, `gate.py` |
| Experiment A results | Typed vs text boundary on dev 284 and T0–T5, model-free and across models | the Step 0 experiment folder (`RESULTS.md`, `data/metrics.json`) |
| Question-shape census | Shape counts from CypherBench's data and our banks; operator order | `scripts/count_question_shapes.py`; `EXP-…-question-shape-census/` |
| Operator algebra specification | Fields, semantics and per-operator limits for every operator | `docs/era-2-expansion/operator-algebra.md` |
| Operator package | One module per operator | `utils/specialists/algebra/` |
| Backend compilers | Cypher and Gremlin compilers for every operator | `utils/specialists/cypher/compile.py`, `utils/specialists/gremlin/compile.py` |
| Differential harness | Result-set comparison by identifier between backends | `utils/specialists/algebra/differential.py`, `scripts/differential_run.py` |
| Experiment C results | Static and measured coverage; differential agreement | `EXP-…-operator-algebra-coverage/` |
| **Test:** request contract | Every field validated against a small fixture card; rejections list options; JSON round-trip | `utils/specialists/tests/test_request.py` |
| **Test:** text is never read | Each typed task run with its text and with nonsense text gives identical queries and records | `utils/specialists/tests/test_typed_boundary.py` |
| **Test:** planner emits typed plans | On a ten-question slice, every request passes the gate | `utils/planner/tests/test_typed_plans.py` |
| **Test:** operator semantics | Ties returned, empty groups kept, identifier dedup, filter on a present property, on a fixture graph | `utils/specialists/algebra/tests/test_semantics.py` |
| **Test:** differential | Generated instances on the fixture graph agree across Neo4j and TinkerPop (live-store; skipped when down) | `utils/specialists/algebra/tests/test_differential.py` |
| **Test:** exact totals | Every operator's total equals the database's count, and paged results equal unpaged ones | `utils/specialists/algebra/tests/test_totals.py` |
