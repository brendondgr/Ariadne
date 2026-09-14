# Frontend prototype: what to ship, and what has to change first

**Status:** plan only. Nothing in it has been implemented.
**Date:** 2026-09-14
**Evidence base:** `EXP-2026-09-020` (`A-1`–`A-5`), `EXP-2026-09-018`, `EXP-2026-09-019`.

---

## 1. Introduction

Today's measurements produced a clean and uncomfortable result. Three independent
changes each raise retrieval coverage at the plan source the workbench actually
runs — merging the two query engines (**+0.0548**), chasing counted facets
(**+0.0358**), and unioning the deterministic and LLM planners (**+0.1799**) —
and together they take the shipped frontend from **0.4536** to roughly **0.66**.
Then `T6`, the entity-fidelity instrument, failed the merged configuration:
`catalogue_dump` rose from **0.0915 to 0.1157** and `wrong_entity` from **0.0950
to 0.1071**.

That is not a contradiction; it is the same fact seen twice. Every union adds
records, coverage is a recall measure that cannot fall when records are added, and
the composer enumerates whatever it is handed. **The coverage gains are real and
the fidelity cost is real, and they are the same change.** So the plan below does
not choose between them. It separates *retrieval breadth* from *presentation
breadth*: retrieve widely, because that is cheap and raises recall, then make the
composer rank and bound rather than list, so an analyst gets the answer instead of
the catalogue it was found in. Only after that gate passes does any merge become
a shipping default.

The ordering is deliberate. Steps 1–3 are prerequisites that make the repository
honest and the composer safe; Steps 4–6 turn on the measured wins one at a time,
each behind its own `T6` re-run; Step 7 is the usability work that makes this
worth publishing.

---

## 2. Gaps & Unanswered Questions

- **The shipped `.env` pins `ORCH_MAX_HOPS=1`, which makes the retrieval loop
  inert.** Every arm on record used `5`. *Assumption*: this is a leftover, not a
  deliberate throttle, and Step 1 changes it to `5` and measures the consequence
  rather than assuming it is free.
- **`T6`'s bar is "not above the reference".** That was chosen for a repair
  experiment, where the job was to avoid regression. A prototype might rationally
  accept slightly worse `catalogue_dump` for materially better recall.
  ***Human intervention is needed to answer this question:*** what is the
  shipping bar — no regression, or a stated budget (e.g. `catalogue_dump` ≤ 0.10)?
- **The LLM planner is the largest single win (+0.1799) and needs a live model
  endpoint at ~12 s per question.** A public repository cannot assume one.
  *Assumption*: it ships **off by default**, documented, and the default path stays
  model-free. If the project wants it on, that is a product decision, not a
  technical one.
- **Which metric the product optimises is not settled.** Coverage and fidelity
  now trade against each other with measured exchange rates.
  ***Human intervention is needed to answer this question.*** The plan assumes an
  analyst tool should prefer a *correct narrow answer over a broad one containing
  it*, and Step 2 is built on that assumption.
- **No merged configuration has ever been judged**, only scored on retrieval and
  `T6`. *Assumption*: a judged pass is required before any public claim about
  answer quality, and it is scheduled as Step 6 rather than skipped.
- **The 2-hop compressed-triple gap** (94 of 284 questions, `A-3`/`A-4`) has no
  measured fix. *Assumption*: out of scope here; recorded as follow-on work.

---

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Make the shipped default honest and measurable

- **Locations**: `.env` (`ORCH_MAX_HOPS`), `utils/orchestration/config.py`
  (`OrchestrationConfig`, `_env_flag`), `README.md` (the "What Actually Runs"
  table's retrieval-loop row), `utils/evaluation/experiment_untruncated.py`
  (a `shipped_default` arm that reads the committed environment rather than
  overriding it).
- **Rationale**: every figure in the research record was produced at
  `ORCH_MAX_HOPS=5`, and the committed `.env` ships `1`. Until the default and
  the measured configuration are the same thing, no number in the repository
  describes what a visitor actually runs. This step exists so that everything
  after it is measured against a real baseline rather than an aspirational one.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Frontend Prototype (1/7)
  Complete: the shipped default runs the retrieval loop it was measured with, and
  a `shipped_default` arm pins it.

### Step 2: Make the composer rank and bound instead of enumerate

- **Locations**: `utils/synthesis/composer.py` (`_enumeration_text`,
  `_enumerated_nouns`, `_mapping_noun`), `utils/synthesis/config.py`
  (`SynthesisConfig.max_enumeration_ids`, `max_enumeration_claims`),
  a new ranking helper beside `composer.py` scoring each candidate record against
  the question's resolved entities and requested properties.
- **Rationale**: this is the gate the whole plan turns on. `A-5` established that
  the merge's cost is not in what is retrieved but in what is *listed* — the
  composer enumerates every record handed to it, so wider retrieval becomes a
  longer list rather than a better answer. Ranking by relevance to the resolved
  task and bounding the enumeration is the only change that lets retrieval breadth
  and answer precision move in the same direction. It must land before any merge
  is enabled, or each merge simply re-spends the same fidelity budget.
- **Rationale, second half**: the bound must be *stated in the answer*. The
  existing contract already refuses silent truncation (`truncated` flags, honest
  abstentions carrying the executed query); a ranked enumeration that hides what it
  dropped would violate it.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Frontend Prototype (2/7)
  Complete: the composer ranks and bounds its enumeration and says what it
  withheld.

### Step 3: Re-run T6 against the bounded composer, with no merges on

- **Locations**: `scripts/variant_harness.py` (`compare`),
  `docs/evaluation/variants-2026-08-29/`, a new amendment in
  `docs/research/experiments/EXP-2026-09-020-plan-source-crossed/RESULTS.md`.
- **Rationale**: Step 2 changes what every answer says, so it is itself a
  regression risk and must be measured before anything is stacked on it. The
  reference is the shipped tree's `wrong_entity` 0.0950 / `catalogue_dump` 0.0915.
  A bounded composer should *improve* both; if it does not, the ranking is wrong
  and Steps 4–5 must not proceed.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Frontend Prototype (3/7)
  Complete: T6 re-measured against the bounded composer and recorded as the new
  reference.

### Step 4: Enable the engine merge, gated on T6

- **Locations**: `utils/specialists/base.py` (`_engine_merge`, `_row_key`, the
  `engine-merge` trace), `utils/specialists/cypher/builder.py` and
  `utils/specialists/gremlin/builder.py` (`build(..., generic=)`), `.env`.
- **Rationale**: the merge is already implemented and measured at **+0.0548**
  coverage with empty answers falling 55 → 38. What it lacked was a composer that
  could absorb the extra rows. With Step 2 in place its fidelity cost should
  shrink; this step turns it on *only if* `T6` holds at or below the Step 3
  reference, and leaves it off otherwise with the measurement recorded.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Frontend Prototype (4/7)
  Complete: the engine merge ships or is refused, on the T6 evidence either way.

### Step 5: Enable facet chasing, gated on T6

- **Locations**: `utils/orchestration/config.py` (`chase_facets`,
  `max_facet_expansions`), `utils/orchestration/main.py` (the re-plan node),
  `utils/orchestration/agents/assess/facets.py` (`relevant_facets`), `.env`.
- **Rationale**: **+0.0358**, separable, with **15 questions improved and 0
  worsened** — the cleanest of the three wins. Raising `max_facet_expansions` past
  4 changes nothing, so the constraint is `relevant_facets` deciding what is worth
  chasing, not the budget; this step leaves the budget alone and does not attempt
  to widen the filter, which is unmeasured.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Frontend Prototype (5/7)
  Complete: facet chasing ships or is refused, on the T6 evidence either way.

### Step 6: Judge the shipped configuration

- **Locations**: `utils/evaluation/judge_answers.py`,
  `scripts/paired_control_score.py`, a fresh sealed bank via
  `scripts/build_bank.py` and `scripts/fresh_seal.py`.
- **Rationale**: every figure driving this plan is retrieval coverage or `T6`.
  Neither says whether an analyst gets a *correct* answer, and the project's
  headline numbers are judged. Before anything is claimed publicly, the shipped
  configuration needs a judged pass on a bank it has not seen — sealed first, as
  `EXP-2026-09-018` Step 7 did, because the dev half has now selected this
  configuration and cannot carry a headline for it.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Frontend Prototype (6/7)
  Complete: the shipped configuration judged on a sealed bank.

### Step 7: Make it usable, and make the repository honest about it

- **Locations**: `web/` (the answer view — an engine/planner provenance badge, the
  executed query already on the SSE contract, a "explain in plain language" control
  that calls the narrator on demand), `api/services/query.py` (surface the
  `engine-merge` trace and the narrator as an explicit opt-in event),
  `utils/synthesis/factory.py` (narrator fallback path), `README.md` (Results and
  "What Actually Runs"), `docs/commands.md`, `.env.example`.
- **Rationale**: this is the step that makes publication defensible. Three things
  a visitor must be able to see without reading the research record: **what the
  system actually ran** (which engine, which planner, which query), **what it is
  and is not** — 0.90 is retrieval-and-composition given a correct plan, not an
  answering capability (`Q57`) — and **that the prose layer is optional and cannot
  change a fact** (284/284 claims byte-identical, `EXP-2026-09-019` Step 3). The
  narrator belongs behind a button at ~20 s, never on the critical path at 0.095 s.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Frontend Prototype (7/7)
  Complete: the workbench shows what it ran, the README says what the numbers mean,
  and the narrator is opt-in.

---

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Ranked, bounded enumeration | Composer ranks candidate records against the resolved task and states what it withheld. | `utils/synthesis/composer.py`, `utils/synthesis/config.py` |
| Ranking unit tests | Small fixed record sets asserting rank order and that the withheld count is stated. | `utils/synthesis/tests/test_enumeration_ranking.py` |
| Engine-merge gate tests | Assert the second engine's failure leaves the primary result byte-identical, and that `engine-merge` traces record rows added. | `utils/specialists/tests/test_engine_merge.py` |
| `shipped_default` arm | An arm that reads the committed environment instead of overriding it, so the default is measurable. | `utils/evaluation/experiment_untruncated.py` |
| T6 gate runner | One command that scores a configuration against the Step 3 reference and exits non-zero above the bar. | `scripts/t6_gate.py` |
| Provenance badge + narrator control | Answer view shows engine, planner and executed query; narrator is an explicit opt-in. | `web/`, `api/services/query.py` |
| Sealed judged pass | Fresh bank, sealed before use, judged in both counterbalanced positions. | `scripts/build_bank.py`, `scripts/fresh_seal.py`, `utils/evaluation/judge_answers.py` |
| Experiment amendments | `A-6` (bounded composer), `A-7` (gated merges), `A-8` (judged pass). | `docs/research/experiments/EXP-2026-09-020-plan-source-crossed/RESULTS.md` |

---

## 5. What this plan deliberately does not do

- **It does not ship the merged configuration as measured today.** It fails `T6`,
  and `SPECIALIST_ENGINE_MERGE` stays off until Step 4's gate passes.
- **It does not pursue exhaustive relation union.** Implemented and measured at
  **−0.0187** (`A-4`); the 0.7350 bound that motivated it was reasoned rather than
  run, and is withdrawn.
- **It does not attempt the 2-hop compressed-triple gap** (94 of 284 questions),
  which has no measured approach.
- **It does not make the LLM planner a default**, despite being the largest single
  win, because it requires a live endpoint at ~12 s per question and this is a
  public repository.
