# Results — EXP-2026-09-020

Status: **complete**. Every number here is read from `data/metrics.json`, which
`data/build_metrics.py` composes from the run artifacts.

**The finding in one line: the primitive engine's advantage over hand-written
templates is contingent on having a good plan, and production does not have
one.** At the authored plan primitives lead by **+0.2184**; at the real planner
the lead falls to **+0.0261 and is not separable**.

## Why this experiment exists

`EXP-2026-09-018` measured templates against schema-derived primitives and the
primitives won decisively — 0.9005 against 0.5525 judged, on a sealed set. That
comparison, like every headline this programme has published, ran against a
**human-authored plan that is replayed**. `app.py` does not replay a plan:
`api/services/query.py` calls `iter_pipeline`, so the planner executes.

No arm on record was production's configuration. Every `deterministic`-family
arm drives `run_deterministic`, which replays the authored plan. So the question
actually being asked — *should the shipped workbench swap its query-construction
engine* — had one measured cell out of the two that matter.

`deterministic_planned` is `generic_planned` with one flag inverted
(`SPECIALIST_GENERIC_ONLY`). Both drive `run_planned`; both execute the planner;
both load `SynthesisConfig` by the same route. All four cells ran on one tree,
model-free and byte-reproducible, 284/284 each.

## The 2×2

Deterministic gold coverage, 284 development questions, paired per question.

| | **authored plan** | **real planner** *(what `app.py` does)* |
|---|---:|---:|
| **hand-written templates** | 0.6428 | **0.4536** |
| **schema-derived primitives** | **0.8611** | 0.4797 |

Zero-record counts, same order: 22 and **55** for templates, 9 and **85** for
primitives.

### The engine effect — the question that was asked

| Plan source | primitives − templates | SE | Separable |
|---|---:|---:|---|
| authored plan | **+0.2184** | 0.0233 | **yes** |
| real planner | **+0.0261** | 0.0255 | **no** |

**Interaction: −0.1923.** The two variables interact strongly, which is the
opposite of what `EXP-2026-09-019` found for the *model* seam, and it is why the
corner cells are misleading on their own.

### The plan effect — and templates survive it better

| Engine | real planner − authored plan | SE | Retrieved nothing where the other retrieved |
|---|---:|---:|---:|
| templates | **−0.1892** | 0.0241 | 45 |
| primitives | **−0.3814** | 0.0262 | 77 |

**A bad plan costs the primitive engine roughly twice what it costs the
templates.** The mechanism is visible in the zero-record counts: under the real
planner primitives return nothing on 85 of 284 questions against templates' 55,
and on **51 questions templates retrieved records where primitives retrieved
nothing**. A template constrains the shape of the query, so a poor decomposition
still lands on something defensible; a primitive follows the plan literally, so
a poor decomposition becomes a poor traversal. The generality that makes
primitives able to answer anything is the same property that makes them
faithful to a bad instruction.

### The effect changes sign by tier

| Tier | n | primitives − templates, at the real planner |
|---|---:|---:|
| easy | 35 | **−0.1586** |
| adversarial | 36 | **−0.1389** |
| hard | 129 | **+0.0659** |
| medium | 84 | **+0.1127** |

The aggregate +0.0261 is a cancellation, not an agreement. Templates win where
the question is routine or adversarial; primitives win where it is hard or
medium. Reporting only the mean would hide both.

## What this means for `app.py`

**A straight swap is not supported.** Setting `SPECIALIST_GENERIC_ONLY=true` in
the shipped workbench buys +0.0261 coverage that this experiment cannot
distinguish from zero, while raising zero-record answers from 55 to 85 — the
analyst-visible failure mode of "I found nothing" — and losing 51 questions that
templates answered.

**What the evidence does support is routing, not replacement.** The tier table
is a routing rule with the sign of the effect on both sides of it. That is also
the honest form of the generality argument: templates cannot accept a question
nobody wrote a template for, so the primitive path is still what makes the
system open-ended — it is just not, at production's plan source, uniformly
better at the questions templates *can* take.

**The real target is the planner.** It costs −0.1892 to templates and −0.3814 to
primitives, and it is the largest term in every cell of this table. Fixing it
raises both engines and is what would make the swap worth making: the
primitives' +0.2184 at an authored plan is what is available if the planner
reaches that quality.

## What this does not say

- **The metric is retrieval, not correctness.** Gold coverage is deterministic
  and model-free, which is what makes a 284-question 2×2 affordable and immune
  to grading noise; it is not the judged score the 0.9005 headline is. A judged
  pass on the two planner cells is warranted — the engine difference clears the
  0.02 threshold, though barely and not separably — and has not been run.
- **It does not withdraw `EXP-2026-09-018`.** 0.9005 against 0.5525 stands as
  measured, at the plan source it was measured at. This experiment establishes
  that the figure does not transfer across a change of plan source, which is a
  limit on its scope rather than a correction to its value.
- **`Q58`'s confound does not reach the engine comparison.** The self-planning
  arm inherits tighter per-plan bounds (`max_result_rows: 1000`,
  `max_traversal_depth: 3`), which is why `Q58` is open against the *plan*
  effect. Both cells of the engine comparison at the real planner inherit the
  same bounds from the same planner, so that term cancels. It still applies to
  the plan-effect column.

## Amendment A-1 — run both engines instead of choosing one (2026-09-14)

The 2×2 above was read as a choice, and the choice is the wrong frame. Both
engines cost **0.095 s per answer single-user with the planner running**, so
running both costs about a tenth of a second in parallel. Scoring the union of
what they retrieve — a gold id counts as found if *either* engine found it —
against each alone, on the same 284 questions at production's plan source:

| Configuration | Gold coverage | Empty answers |
|---|---:|---:|
| templates only | 0.4536 | 55 |
| primitives only | 0.4797 | 85 |
| **both, evidence merged** | **0.5862** | **34** |
| both, oracle pick-best | 0.5862 | — |

**The merge equals the oracle.** Picking the better engine per question with
perfect foreknowledge scores exactly what merging scores, to four decimals. The
two engines' evidence sets are **complementary rather than competing**, which
means the routing rule I recommended earlier is unnecessary: there is nothing to
predict, because taking both loses nothing against choosing perfectly.

**+0.1064 over the better single engine** — four times the +0.0261 that choosing
between them is worth, and it needs no tier classifier, no held-out validation of
a routing rule, and no model.

Empty answers fall from 55 (templates) and 85 (primitives) to **34**. That is the
analyst-visible failure mode, down 38% against the better single engine.

### A rule that needs no foreknowledge, if merging is too invasive

| Rule | Coverage |
|---|---:|
| prefer primitives, fall back when they retrieved nothing | **0.5713** |
| prefer templates, fall back when they retrieved nothing | 0.5020 |

The first captures 87% of the merge benefit with a one-line condition, and is the
cheaper thing to ship first.

### What this does not establish

- **Merging more evidence is not proven free.** More records reaching the
  composer could raise wrong-entity or catalogue-dump rates; `EXP-2026-09-018`'s
  T6 instrument is the thing that would catch it and has not been run on a merged
  configuration. The coverage gain is measured; the fidelity cost is not.
- **Still retrieval, not judged correctness**, and still at a plan source that
  loses 0.38 to the authored path. Merging raises the floor; it does not reach the
  0.8611 ceiling, and the planner remains the dominant term.
- The 34 questions where **both** engines retrieve nothing are a planner
  diagnostic set, not an engine one.

## Amendment A-2 — two planners are complementary; one planner is not better (2026-09-14)

`A-1` found the two query engines complementary. The same question for the
*planner*, which `A-1` established is the dominant term: `generic_planned_llm` is
`generic_planned` with an LLM drafter and every other seam still off, run against
`gemma-4-26B-it` on the local relay. All 284 questions.

| | Gold coverage | Empty answers |
|---|---:|---:|
| deterministic planner | 0.4797 | 85 |
| LLM planner | 0.4858 | 114 |
| **both planners, evidence unioned** | **0.6596** | **46** |
| oracle pick-best | 0.6596 | — |
| authored plan (ceiling) | 0.8611 | 9 |

**Union − deterministic = +0.1799** (SE 0.0208, n=284, separable by a factor of
nine). It is by a wide margin the largest single improvement measured on this
programme's planning stage.

**The LLM planner is not better.** Alone it is worth **+0.0061**, which is noise.
Every reading that treats "use a model to plan" as the finding here is wrong. The
value is entirely in *complementarity* — and the evidence for that is the same
signature `A-1` found: **union equals oracle pick-best to four decimals**. The two
planners select different correct relations, neither dominates, and taking both
loses nothing against choosing perfectly.

### The complementarity is visible in the tiers

| Tier | n | LLM − deterministic |
|---|---:|---:|
| adversarial | 36 | **−0.3056** |
| easy | 35 | −0.1000 |
| hard | 129 | **+0.0535** |
| medium | 84 | **+0.1108** |

The aggregate +0.0061 is a cancellation of two large opposite effects, which is
exactly the shape `A-1` reported for the engines. A programme that had only read
the aggregate would have discarded the LLM planner as worthless.

### A caution recorded against myself

The first read of this arm, at 73 of 284 answers, reported the LLM planner at
**−0.1637 and separable** — the opposite conclusion. The bank is ordered by tier
and `--limit` takes the first N by name, so that slice was entirely `D6`
cross-catalogue questions, the tier the LLM planner loses worst. The interim
figure was quoted before the run finished. **Partial results from this bank are
not a random sample of it**, and nothing from a `--limit` slice should be read as
an estimate of the whole.

### What this does not establish

- Retrieval, not judged correctness, and the merged configurations have never
  been through the `T6` entity-fidelity instrument. Three unions now stack
  (engines, facets, planners) and every one of them puts more records in front of
  the composer. `EXP-2026-09-018` records `catalogue_dump` at 0.0915 on the
  shipped tree; that is the number a merged configuration has to be held to.
- The LLM planner costs about 12 s per question against the deterministic
  planner's 0.095 s — a live model on the critical path, where every other union
  measured today is free.
- 0.6596 against a 0.8611 ceiling. The union closes 47% of the planner gap and
  leaves the rest.

## Amendment A-3 — the ceiling cannot be replayed, but most of it can be reached without selecting anything (2026-09-14)

**The authored plan cannot be shipped.** `utils/specialists/evalset/spec_bank.py`
builds it from a `spec`, and that same `spec` produces the question text *and*
`ex_gold`. Replaying it hands the system the traversal that defines the correct
answer, so using it in production would require knowing the answer in order to
plan the query. This is recorded as `Q57` and is not an engineering obstacle.

**What the ceiling represents, however, is reachable by a different route.**
0.8611 is what the engine achieves when handed a correct traversal. The planner
has been trying to *select* that traversal from the question text, and three
deterministic selectors and one LLM all fail to clear 55% predicate accuracy. The
measurement below says selection is the wrong goal.

### The candidate set is tiny

| | |
|---|---:|
| distinct predicates in the whole 284-question bank | **26** |
| declared relations per anchor label, median | **5** |
| … mean / max | 8.9 / 19 |
| gold predicate is declared on its anchor | **78.6%** of legs |

Most labels carry one or two relations. `Mitigation`, `Software`, `View` and
`DataComponent` each declare exactly one — for those there is nothing to select.
`AttackPattern` is the outlier at 19.

### So ask them all

| | Coverage | Cost |
|---|---:|---|
| planner today | 0.4797 | 1 query |
| **exhaustive single-hop union (upper bound)** | **0.7350** | median **2** queries, **0.19 s**; worst 38 queries, 3.6 s |
| authored-plan ceiling | 0.8611 | — |

Querying every relation the anchor declares and unioning the results reaches an
upper bound of **0.7350** — 67% of the distance from today's planner to the
ceiling — and it needs no relation selection at all, no model, and a median of a
fifth of a second. On 190 of 284 questions the gold traversal is included **by
construction**.

### What it cannot reach, and why

The remaining 94 questions are **compressed multi-hop triples**: the authored
leg `Analytic -[HAS_TECHNIQUE]-> Tactic` is really
`Analytic -> DetectionStrategy -> Technique -> Tactic`, so `HAS_TECHNIQUE` is not
declared on `Analytic` at all. Reaching those needs two-hop exhaustive expansion,
which squares the fan-out; `utils/specialists/schema/paths.py` already does the
breadth-first search, so the machinery exists, but the cost and the precision
consequence are unmeasured.

### The precision consequence is the real open question

Every union recorded in this experiment — engines (`A-1`), planners (`A-2`), and
now relations — puts more records in front of a composer that enumerates what it
is handed. `EXP-2026-09-018` records `catalogue_dump` at 0.0915 and
`wrong_entity` at 0.0950 on the shipped tree. **No merged configuration has been
through that instrument.** Coverage is a recall measure and cannot fall when
evidence is added, so every figure in this amendment is guaranteed to look good
by construction. T6 is the check that says whether the answers are still about
what was asked, and it must run before any of this ships.

## Amendment A-4 — A-3's bound was wrong, and the mechanism is the opposite (2026-09-14)

`A-3` bounded exhaustive relation union at **0.7350** by assuming that when the
gold relation is among those the anchor declares, walking them all reaches the
authored-plan coverage for that question. **Implemented and measured, it does the
reverse.**

| | Coverage | Empty | Median records |
|---|---:|---:|---:|
| planner, as shipped | 0.4797 | 85 | 1 |
| planner + relation union | **0.4611** | 85 | 1 |

**−0.0187** (SE 0.0109), 6 questions improved and **18 worsened**. The change
did what it was designed to do — `describe` fell from 59 answers to 20 and
`generic_neighbors` rose from 10 to 49, so 39 questions switched from describing
the anchor to walking every declared relationship — and those questions got
worse.

**Why the bound was wrong.** `describe` is not the weak fallback `A-3` assumed.
It returns the anchor's full record *plus a bounded facet block*, and for a
question whose gold is reachable from the anchor's own properties that block
already carries the answer. Replacing it with a neighbour walk over a 19-way
alternation trades a record that contained the gold for neighbour rows that do
not. Coverage is a recall measure, so the only way it can fall on added evidence
is if the added evidence *replaced* rather than extended what was there — which
is exactly what a routing change does.

**The lesson is about the bound, not the feature.** `A-3` reasoned from schema
structure to a coverage number without running anything, and the number was
0.27 too high. Every other union in this experiment (`A-1`, `A-2`) was measured
before it was claimed. This one was not, and it is withdrawn:
`exhaustive_relation_union_upper_bound` 0.7350 does not stand.

The implementation is reverted rather than kept behind its flag. A public
repository carrying a measured-negative routing switch is a trap for the next
reader.

## Amendment A-5 — the merged configuration fails T6 (2026-09-14)

Every amendment above reports a coverage gain, and coverage is a recall measure
that **cannot fall when evidence is added**. `T6` is the instrument that asks the
other question — is the answer still about the entity that was asked for — and it
was run on the merged configuration (`SPECIALIST_ENGINE_MERGE=1`,
`ORCH_CHASE_FACETS=1`, 8 expansions) over the same 579 paraphrase variants.

| | shipped tree | merged | change |
|---|---:|---:|---:|
| `wrong_entity` | 0.0950 | **0.1071** | +0.0121 (+13%) |
| `catalogue_dump` | 0.0915 | **0.1157** | +0.0242 (**+26%**) |
| `abstained` | 0.4663 | 0.5147 | +0.0484 |

**It fails.** `EXP-2026-09-018`'s bar was "not above the reference", and the
merged configuration is above it on both fidelity measures. The worst tiers are
`T3`–`T5`, where `catalogue_dump` reaches 0.2277, 0.2308 and 0.1731.

This is the trade the coverage figures could not show. Merging buys +0.0548 of
recall and spends roughly a quarter again as much catalogue dumping — the failure
mode where an answer contains what was asked for inside a list of everything
else. For an analyst tool those are not equivalent currencies: a dumped catalogue
is an answer a reader cannot act on, and it is the specific complaint
`EXP-2026-09-016` built this instrument to detect.

**Consequence: `SPECIALIST_ENGINE_MERGE` must not ship on by default in its
current form.** It stays off, with this amendment as the reason. The coverage
result stands; what does not stand is the inference from it to a shipping
decision.

What would make it shippable is bounding what reaches the composer rather than
bounding what is retrieved — the merge adds rows the enumeration then lists in
full. That is a composer change, not a retrieval one, and it has not been
attempted.

## Amendment A-6 — the gated rollout: what shipped, and what the gate refused (2026-09-14)

`A-5` refused the merged configuration. `docs/plans/2026-09-14-frontend-prototype-configuration.md`
set the order that follows from it: bound the composer first, then admit each
coverage win only if `T6` holds. Run over the same 579 paraphrase variants,
against the shipped reference of `wrong_entity` **0.0950** / `catalogue_dump`
**0.0915**.

| Configuration | `wrong_entity` | `catalogue_dump` | `abstained` | Verdict |
|---|---:|---:|---:|---|
| shipped reference | 0.0950 | 0.0915 | 0.4663 | — |
| ranked composer only | **0.0950** | **0.0915** | 0.4663 | **passes** |
| ranked + facet chasing | **0.0950** | **0.0915** | 0.5078 | **passes** |
| ranked + engine merge | 0.1088 | 0.1140 | 0.4836 | **fails** |

### The ranked composer is a no-op on T6, which is the right answer

Identical on all three rates. That is what it should be with no merge on: related
sets rarely exceed `MAX_ENUMERATION_IDS`, so nothing is withheld and reordering a
list that is shown in full changes no answer. It earns its place as the gate that
lets the next two steps be *tried*, not as a gain in itself.

### Facet chasing ships

**+0.0358 gold coverage** (separable, 15 questions improved and 0 worsened) at
**no measurable fidelity cost**. The cheapest real gain on record. Abstentions
rise 0.4663 → 0.5078, which the gate does not price: an abstention carries its
executed query as proof and is an honest empty, not a wrong answer.
`ORCH_CHASE_FACETS` now ships `true`.

### The engine merge is refused, and ranking does not rescue it

`0.1088` / `0.1140` against the reference — still failing, and essentially where
it was unranked (`0.1071` / `0.1157`). **This falsifies A-5's proposed remedy.**
`A-5` reasoned that the merge's cost was "the merge adds rows the enumeration then
lists in full", so bounding the enumeration would absorb it. It does not, and the
reason is visible in the numbers: the merge's extra rows arrive as additional
**records**, each of which composes its own claim, and the enumeration bound
governs entries *within* a record's related set rather than the number of records.
The bound that would govern it is `SYNTHESIS_MAX_RECORDS_PER_RESULT`, and lowering
that discards retrieved evidence rather than ranking it.

`SPECIALIST_ENGINE_MERGE` stays off. Its +0.0548 coverage remains real and remains
unshippable on this instrument.

### What the shipped prototype is, after this

Ranked, bounded composition plus facet chasing, with every LLM seam off and
`ORCH_MAX_HOPS` at the 5 every figure was measured with. The merge and the LLM
planner — the two largest coverage wins measured today, +0.0548 and +0.1799 — are
both implemented, both off, and both refused for stated reasons rather than
forgotten.

## Amendment A-7 — what the workbench ships, verified end to end (2026-09-14)

The plan in `docs/plans/2026-09-14-frontend-prototype-configuration.md` was
implemented. What ships, and what the gate refused:

| Change | Status | Evidence |
|---|---|---|
| `ORCH_MAX_HOPS` 1 → 5 | **ships** | every recorded figure used 5; at 1 the loop is inert |
| Ranked, bounded enumeration | **ships** | `T6` unchanged: 0.0950 / 0.0915 |
| Facet chasing | **ships** | +0.0358 coverage, `T6` unchanged |
| Narrator as a per-question toggle | **ships** | 284/284 claims byte-identical (`EXP-2026-09-019` Step 3) |
| Engine merge | **refused** | `T6` 0.1088 / 0.1140, `A-5`/`A-6` |
| LLM planner | **refused** | +0.1799 coverage, but needs a live endpoint at ~12 s/question |

### The defect the frontend work actually found

The composer defaulted to `drafter: "llm"`, with a source comment explaining that
this is what "produces the natural-language final answer". It does — and
`drafter: "llm"` sets the planner, the **specialist** and the synthesis seams
together. So every analyst who wanted a readable answer was silently given query
construction by a model: the baseline that scores **0.5000** where the template
cascade scores **0.9467** on the same unseen questions (`EXP-2026-09-007`).

Nothing in the evaluation record would have caught this. Every arm sets its seams
explicitly, so no arm was ever the configuration the UI shipped. It was found by
reading the component that builds the request.

The two are now separate flags, wired through both `/api/query` and
`/api/conversation-query` — the workbench uses the latter, so a flag added only to
the former would have been a no-op toggle on screen.

### Verified against `:9090` through the running stack

| | `composer` | `narrative_source` | `synthesis_ms` | claims |
|---|---|---|---:|---|
| `narrate: false` | deterministic | deterministic | **12** | 3/3 supported |
| `narrate: true` | deterministic | **llm** | **19,659** | 3/3 supported |

Claim texts identical across both. Full stack preflight green — `attack` 4,369
nodes, `capec` 6,374, super-graph compiled, full smoke query answered — and a
question run through the browser returns `VERIFIED ANSWERS 3/3`.

### What is still open

`Q57` is unchanged by any of this: the workbench runs the real planner, so its
end-to-end answer quality is the **0.4536–0.5156** coverage band, not the 0.9005
the sealed set reports at an authored plan. Step 6 of the plan — a judged pass on
a sealed bank at the shipped configuration — has **not** been run, and until it
has, no figure in this repository describes what an analyst gets from the UI.

## Amendment A-8 — where a chat turn's time actually goes, and what the controls now cost (2026-09-14)

A deterministic turn through the workbench took **43.27 s**. Timed per SSE event
against the running stack, the graph answered at **1.09 s**; everything else was
the conversation wrapper.

| Stage | LLM | Before |
|---|---|---:|
| `router` | yes | ~1.0 s |
| **the pipeline** | **no** | **1.09 s** |
| `validation` (sufficiency) | yes | **~28.6 s** |
| `answer` (writes the reply) | yes | **~10.7 s** |
| thread auto-title | yes | ~2.9 s, at the very end |

No control on screen could stop any of it. `ConversationConfig` resolves
`enabled` from the shared LLM group, so `ARIADNE_LLM_ENABLED=true` switched the
layer on implicitly, and `with_llm_enabled()` was **one-way** — it could turn the
layer on and never off. The composer read "Drafter: deterministic" while four
model calls ran at a 4,096-token thinking budget.

### After: the four control corners, measured end to end

`ORCH_MAX_HOPS=5`, `:9090`, same question, per-event timings.

| Corner | Verify | Prose | Total |
|---|---|---|---:|
| **A — the default** | off | off | **0.25 s** |
| B | **on** | off | 28.56 s |
| C | off | **on** | 32.20 s |
| D | **on** | **on** | 78.87 s |

**The default path is 0.25 s against 43.27 s — 170× faster**, and the thread is
titled at **0.02 s** rather than at the end. D runs long because validation
judged the evidence insufficient and drove a retry, which is the loop working.

### Two defects the measurement caught rather than confirmed

**Titling ran last and was a dependency of nothing.** `title_for` reads the
question and nothing else, so its position at the end of `_persist_turn` was
incidental: it cost ~2.9 s at the tail and left the sidebar reading "New
conversation" until after the answer was on screen. Moved to turn-open on a
worker. Writing the test for that then caught a second fault — when the titler
raises anything but `LLMUnavailable`, the fallback calls the **same failing
client**, and the exception propagated: the stream ended in `error` rather than
`done`, **losing an answer that had already been composed and verified over a
thread's name.**

**Declining to disable is not the same as enabling.** The first run of these four
corners had `verify: on` finishing in **0.08 s** — the control silently did
nothing, because the environment had the conversation LLM off and `verify` merely
left the agent to the config. The toggle on screen is now authoritative in both
directions. Had the corners not been measured, this would have shipped as a
control that looked wired and was not.

### What is unchanged

`router` and `orchestration` still run in every mode — routing and reference
resolution are what make a thread conversational, and the router costs ~1 s. The
**deterministic claim verifier is untouched and unconditional**: `Verify` governs
the LLM sufficiency agent, which is a second opinion, not the guarantee.
