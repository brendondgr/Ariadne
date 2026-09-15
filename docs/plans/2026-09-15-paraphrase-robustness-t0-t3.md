# Paraphrase robustness at T0–T3

*Created 2026-09-15. Append-only: corrections go in a new dated plan, never in place.*

## 1. Introduction

The workbench is measured at 1.0000 on the gold questions themselves and at
0.4667 on the same questions with the verb changed. `EXP-2026-08-020` recorded
that cliff across six rewording tiers, and `EXP-2026-09-014` reproduced its shape
two weeks later. The operator's requirement is that the system work for questions
that keep the entity and change the wording — tiers **T0 (verbatim), T1 (same
identifier, new verb), T2 (same identifier, restructured) and T3 (exact name, no
identifier)** — at a bar of roughly **0.9 per tier**. T4 (paraphrased name) and
T5 (description only) are explicitly out of scope for this plan and are carried
only as a fidelity guard.

Three facts make this worth measuring before it is worth engineering. First,
`EXP-2026-08-020`'s Arm 0 ran at `0ae78c19`, **before** the change that resolves a
named entity ahead of the template ladder landed at `9f02dc6b` — so T3's 0.0990
is stale and has never been re-measured, and neither has any tier since the
`EXP-2026-09-018` repair. Second, the rewrite stage built for exactly this problem
moved T3 from 0.2745 to 0.4706 and was shelved because its ship rule required
T4 **and** T5 above 0.25 — a gate scored on tiers outside this plan's scope.
Third, the variant bank has only ever been run on the hand-written template
router; the schema-derived primitives route on labels and declared relations
rather than surface verbs, which is the T1/T2 failure mode, and nobody has run
them against it.

The plan therefore measures before it builds: re-baseline the bank on the shipped
tree, test the engine hypothesis, re-gate the rewrite stage on the tiers that
matter, and only then decide whether new relation-ranking work is needed. Every
step is pre-registered with a prediction and a falsifier before it runs.

## 2. Gaps & Unanswered Questions

- **Which metric carries the 0.9 bar.** `records_exact` demands the returned
  record set match gold exactly; the same T1 runs score `records_recall` 0.5790
  against `records_exact` 0.4667, and judged correctness would read higher than
  both. *Assumption*: `records_exact` is the **primary** metric because it is what
  the existing record is denominated in and it cannot flatter us;
  `records_recall` and `recall|no-dump` are reported beside it at every tier. A
  judged pass is scoped as optional Step 6 and is the only metric that answers
  "does the analyst get a correct answer". **Confirm the bar is on
  `records_exact` before Step 5 spends engineering effort against it.**
- **Pooled versus per-tier.** The variant bank over-samples the paraphrase tiers
  on purpose, so a pooled T0–T3 figure is an artifact of the sampling and T0's
  1.0000 would flatter it. *Assumption*: the bar is **per tier**; no pooled
  number is produced or quoted.
- **Whether a live model may sit in the shipped path.** The rewrite stage's T3
  gain requires a model call per question. `EXP-2026-09-016` prices the LLM
  planner at ~12 s/question; the rewrite call is smaller but non-zero. *Human
  intervention is needed to answer this question* — Step 4 measures the latency
  and states the trade, but whether the workbench may call a model on the
  critical path is a product decision, not a measurement.
- **Is 0.9 at T1/T2 reachable at all.** No measured intervention has ever moved
  T1 or T2: rewrite off 0.4921, deterministic fill 0.4921, model rewrite 0.4921,
  and T2 fell slightly. *Assumption*: this plan does not promise 0.9; it
  establishes the true current baseline, tests two cheap hypotheses, and — if
  both fail — scopes the engineering that would be required, with the gap stated
  honestly rather than a projected figure. `EXP-2026-09-020` `A-3`/`A-4` is the
  standing warning against reasoning a coverage number instead of measuring one.
- **Reference stability.** Every variant is scored against its own gold
  question's captured behaviour, so a reference that is not byte-reproducible
  makes every downstream figure meaningless. *Assumption*: capture twice and diff
  before any comparison run, as `EXP-2026-08-020` did.

## 3. Hierarchical Step-by-Step Instructions

### Step 1: Pre-register the experiment and prove the reference reproduces

- **Locations**: `make new-experiment SLUG=paraphrase-robustness-t0t3`,
  `docs/research/experiments/EXP-2026-09-021-paraphrase-robustness-t0t3/PROTOCOL.md`
  and `manifest.yaml`; `scripts/variant_harness.py` `capture`;
  `docs/evaluation/variants-2026-09-15/`.
- **Rationale**: the hypotheses, their thresholds and the fidelity guard must be
  written before any tier figure is seen — the same discipline that let
  `EXP-2026-09-018`'s kill gate fire honestly. The reference capture is the
  instrument: variants are scored against their own gold question's behaviour, so
  a capture that does not reproduce byte-for-byte invalidates everything after
  it. Capture twice, diff, and record the hash.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Paraphrase Robustness (1/6)
  Complete: hypotheses pre-registered and the reference capture proved
  reproducible.

### Step 2: Re-baseline the bank on the shipped tree

- **Locations**: `scripts/variant_harness.py` `compare` (`--rewrite off`),
  `docs/evaluation/variants-2026-09-15/scored_baseline.json`, the experiment's
  `data/metrics.json` and `RESULTS.md`.
- **Rationale**: every tier figure in the record predates both the name-resolution
  reorder (`9f02dc6b`) and the `EXP-2026-09-018` repair. Until the bank is re-run
  on the tree that actually ships, no number describes the current system, and
  the two hypotheses after this step have nothing to be measured against.
  **Pre-registered prediction**: T0 ≥ 0.99; T1 0.45–0.55; T2 0.40–0.50; T3
  **≥ 0.25**, up from 0.0990, because the reorder targets exactly "exact name, no
  identifier". **Falsifier**: T3 below 0.15 means the reorder did not reach this
  path and T3 depends entirely on Step 4.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Paraphrase Robustness (2/6)
  Complete: the shipped tree re-baselined per tier against the stale August
  figures.

### Step 3: Test the engine hypothesis — primitives against paraphrase

- **Locations**: `SPECIALIST_GENERIC_ONLY` read by
  `utils/specialists/cypher/builder.py` `_generic_only` and
  `utils/specialists/gremlin/builder.py` `_generic_only`;
  `scripts/variant_harness.py` `compare`;
  `docs/evaluation/variants-2026-09-15/scored_primitives.json`.
- **Rationale**: T1 keeps the identifier, so entity resolution is not the failure
  — template selection from surface phrasing is. The primitive engine selects on
  labels and declared relations and never reads a verb, so if the T1/T2 loss is
  routing-by-vocabulary it should be smaller here. This has never been run: every
  variant figure on record is the template router. **Pre-registered prediction**:
  primitives beat templates by ≥ 0.10 at T1 and T2. **Falsifier**: within ±0.05
  of the Step 2 baseline means engine choice is not the T1/T2 lever, and Step 5
  becomes the only remaining route. Report `catalogue_dump` beside every tier —
  primitives raised empty answers from 55 to 85 on the dev bank and the failure
  mode here may be dumping rather than missing.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Paraphrase Robustness (3/6)
  Complete: the primitive engine measured against paraphrase for the first time.

### Step 4: Re-gate the rewrite stage on T0–T3

- **Locations**: `utils/planner/rewrite_llm.py`, `utils/planner/canonical.py`,
  the `REWRITE_ENV` flags in `scripts/variant_harness.py` (`--rewrite model`),
  `docs/evaluation/variants-2026-09-15/scored_rewrite.json`.
- **Rationale**: `EXP-2026-09-014` refused this stage on a rule requiring T4 and
  T5 above 0.25, and it failed there at 0.0880/0.1635. On T3 it gained +0.1961
  and it *improved* fidelity (`wrong_entity` 0.1111 → 0.0556, `catalogue_dump`
  0.1111 → 0.0371). A gate scored on tiers this plan excludes cannot decide a
  question this plan asks, so the stage is re-gated — not re-tuned — against a
  rule written in Step 1. **Pre-registered ship rule**: T3 ≥ Step-2 baseline
  + 0.10, **and** no tier T0–T2 below its Step-2 baseline − 0.02, **and**
  `wrong_entity` ≤ 0.0950 and `catalogue_dump` ≤ 0.0915 (the `EXP-2026-09-018`
  shipped reference). Record the per-question latency the stage adds; it is the
  input to the product decision named in §2.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Paraphrase Robustness (4/6)
  Complete: the rewrite stage re-gated on the tiers in scope, with its latency
  priced.

### Step 5: Scope the T1/T2 gap that survives

- **Locations**: `utils/specialists/cypher/builder.py` `CypherQueryBuilder.build`
  (the template ladder), `utils/specialists/schema/` (declared relations per
  label), `utils/planner/canonical.py` (the intent triple), a new scoring path
  under `utils/specialists/` with tests beside it.
- **Rationale**: if Steps 3 and 4 leave T1/T2 short of the bar, the remaining
  mechanism is intent selection from surface vocabulary, and `A-3`'s measurement
  says the candidate set is small enough to rank rather than classify: 26 distinct
  predicates across the whole bank, a median of 5 declared relations per anchor,
  most labels declaring one or two. The intervention is to score the question
  against the relations the **resolved anchor actually declares** instead of
  matching a verb to a template. `EXP-2026-09-020` `A-4` is the binding caution:
  walking every declared relation *replaced* `describe`, which often already
  carried the answer, and cost −0.0187 — so this must rank and keep the fallback,
  never union. Scope only; implementation is gated on Steps 2–4 leaving a gap
  worth the work, and on the metric question in §2 being settled.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Paraphrase Robustness (5/6)
  Complete: the residual T1/T2 gap scoped against measurement rather than
  estimate.

### Step 6: Record, decide, and state the honest position

- **Locations**: the experiment's `RESULTS.md`, `manifest.yaml`, `data/metrics.json`;
  `docs/research/CLAIMS.md`, `DECISIONS.md`, `OPEN_QUESTIONS.md`;
  `make index`, `make validate-research`, `make check-docs`; `README.md` if a
  default changes.
- **Rationale**: `EXP-2026-08-020`'s tier table is the figure a reader meets on
  this question, and it is now stale in both directions — it predates the repair
  and it predates any of this. Whatever the outcome, the record must carry the
  current tier table, the ship/no-ship decision for each lever with its reason,
  and — if the bar is not met — the gap stated as a number rather than softened.
  An optional judged pass on the T0–T3 slice is the only thing that converts
  `records_exact` into the metric the use case actually cares about; it is scoped
  here and run only if the operator confirms the bar belongs there.
- **Action**: Undergo the verification/tests/validation process for this phase.
  Once validated, push changes to GitHub stating: Paraphrase Robustness (6/6)
  Complete: the tier table refreshed, every lever decided with its reason, and
  the residual gap recorded.

## 4. Deliverables Table

| Deliverable | Description | Location (File/Path) |
| --- | --- | --- |
| Experiment record | Pre-registered protocol, per-tier results, manifest, machine-readable metrics | `docs/research/experiments/EXP-2026-09-021-paraphrase-robustness-t0t3/` |
| Reference capture | The 120 gold questions' behaviour, captured twice and proved identical | `docs/evaluation/variants-2026-09-15/reference.json` |
| Baseline scoring | Shipped tree, all six tiers, `--rewrite off` | `docs/evaluation/variants-2026-09-15/scored_baseline.json` |
| Primitive-engine scoring | Same bank under `SPECIALIST_GENERIC_ONLY=true` | `docs/evaluation/variants-2026-09-15/scored_primitives.json` |
| Rewrite-stage scoring | Same bank under `--rewrite model`, re-gated on T0–T3 | `docs/evaluation/variants-2026-09-15/scored_rewrite.json` |
| Tier comparison table | Baseline vs primitives vs rewrite, per tier, with fidelity columns | `.../EXP-2026-09-021-.../tables/tiers.md` |
| Tier figure | Generated from `data/metrics.json`, never hand-edited | `.../EXP-2026-09-021-.../figures/` |
| Relation-ranking tests | Small-subset tests for the Step 5 selector: ranking preserves the `describe` fallback, and a known anchor's declared relations rank correctly | `utils/specialists/tests/test_relation_ranking.py` |
| Harness regression test | Asserts the tier scorer reports per-tier and refuses a pooled figure | `utils/evaluation/tests/` |
| Decision entries | Ship/no-ship per lever with the rule each was judged against | `docs/research/DECISIONS.md` |
