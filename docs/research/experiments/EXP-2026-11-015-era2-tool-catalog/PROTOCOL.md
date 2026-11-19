# PROTOCOL — EXP-2026-11-015 Era 2 Step 8: the tool catalog, generated from the card

Written 2026-11-18, before anything is built or run. The operator agreed the four pass bars
the same day ("Agree, write protocol"). This protocol pins how each bar is measured.

## What was looked at before writing

**From the record** (no new runs):
- **The synonym-tier figure, 0.4667.** This is T1 ("id + synonym", 120 variants) in
  EXP-2026-08-020. It was produced by the rules-only pipeline (`scripts/variant_harness.py`,
  which forces `PLANNER_LLM_ENABLED=false`). The harness cannot run the language-model planner
  today.
- **"Original wording."** T0 is the 120 golden questions, scored against the system's own
  reference capture. In the harness it is a determinism control and is 1.0000 by
  construction.
- **The 77 of 284 empty retrievals.** These come from EXP-2026-09-019's rules planner against
  the authored plan (`scripts/planner_cost_score.py`: authored records > 0, planner records =
  0).
  - **Today's Qwen planner already loses 45** (EXP-2026-11-009 A-2, after the walk fix
    5d1b93e2).
  - **The agreed bar of ≤ 38 is therefore a cut of 7** from today's same-tree figure, not a
    halving. Amendment 1 tightens G2 to half of today's control, at the operator's
    direction.
- **"Confidently wrong" is not computed** in EXP-2026-09-019 or EXP-2026-11-009. It is defined
  below.
- **Code survey** (2026-11-18):
  - There are 17 reads of `task.text` in the two builders: 8 in Cypher, 9 in Gremlin. There
    are 3 more upstream in `utils/specialists/resolve/`.
  - The typed request format and compilers live in `utils/killtests/typed/`.
  - Cards come in two formats: `SourceCardView` for ATT&CK and CAPEC, and kill-test schema
    dicts for the benchmark graphs.
  - The ATT&CK card has no `allowed_edge_patterns`. Its directions come from the schema
    registry.
  - Gremlin stores relation names in screaming snake case (`gremlin_edge_label`).
  - Plain readings exist for ATT&CK and CAPEC only: 63 keys, frozen in EXP-2026-11-014.
- **Models, operator 2026-11-18:**
  - `:9090 default-model` is Gemma 4 31B and `default-model-2` is Qwen 3.8 27B, each allowed
    16 concurrent requests.
  - The registry still maps `qwen38-27b` to `default-model`, which now serves Gemma. Step 4's
    script requires `qwen38-27b` and calls `default-model`, so it would now run Gemma.
  - The decision model is one setting, pplx-decider by default (D-039).

## Question

Does handing the specialists a **typed** request generated against a card-derived tool
catalog, instead of English text, meet the four agreed bars? The four bars are synonym
robustness, empty retrievals, original wording and confidently-wrong answers. Can the catalog
be generated for every loaded card with no per-graph code?

## What gets built (Phase 1, no model calls)

1. **`utils/agent/catalog.py`: card to tool catalog.**
   - It takes either card format through one adapter, which normalizes it to labels, relations
     with (subject, object) direction facets, properties with value types, glosses, aliases
     and readings.
   - It emits OpenAI-style function specs with JSON Schema enums for these tools: `find_schema`,
     `resolve_entity`, `describe`, `expand`, `filter`, `aggregate`, `group`, `rank`, `set_op`,
     `count`, `verify`, `not_expressible`, `ask_caller` and `finish`.
   - **Option rules** (`x-options`) say which relations a label has, in which direction and to
     which target, and which properties take which operators and value types.
   - **Relation options carry a plain reading** for each (relation, direction, target):
     - **ATT&CK and CAPEC:** the frozen EXP-2026-11-014 readings.
     - **Other cards:** a deterministic template reading, "the {target} that this {label}
       {relation gloss}" (inverted for `in`). This is marked `reading_source: template`.
   - **Relation names for a Gremlin store** go through the store's edge-label map
     (`gremlin_edge_label`), not the card's spelling.
   - **Depth** is a typed argument on any repeating relation, checked against the card's
     limit. There is no fixed-depth template.
2. **`utils/agent/coerce.py`.** It fixes near-miss names (edit distance ≤ 2, or a unique case-
   or separator-insensitive match), case in enums, `"8"`→8, and numbers stored as text (from
   the card's value types). Every fix is recorded with `filled_by`.
3. **`utils/agent/errors.py`.** One envelope, `{code, detail, fix, problems[]}`, with these
   codes:
   - `invalid_request`;
   - `empty`, with `view.diagnose_empty`'s reason and fix;
   - `ambiguous_anchor`;
   - `partial`;
   - `not_in_card`;
   - `repeated_call`.
4. **The tools are thin wrappers** over `exact.fetch`, `HandleStore`, `view.build_view` and
   `view.diagnose_empty` (Step 5). They do not re-implement retrieval.
5. **The text boundary.**
   - `SpecialistTask` gains typed fields: `anchors` (ids), `relation`, `direction`,
     `target_label`, `depth`, `filters`, `answer`, `bulk_scan`, `definitional` and
     `requested_slots`.
   - Every builder read of `task.text` (the 17), and the 3 resolver reads, move upstream. The
     rules planner, or the typed plan, computes those signals once and passes them as fields.
   - The builders and resolver then read no English.
6. **The planner's typed mode.**
   - The planner is given the catalog. It may call `find_schema`, `describe` and
     `resolve_entity`, at most 4 calls in total, then emits one typed plan.
   - The plan is validated against the option rules and coerced. It gets **one** repair turn,
     carrying the error envelope, if it is refused.
   - It then executes with `task.text` blanked.
   - This is a single plan, not a loop; the loop is Step 11.
7. **Harness support.**
   - `scripts/variant_harness.py` gains planner arms. The English control arm sets
     `PLANNER_LLM_ENABLED=true` with today's English hand-off. The typed arms are described
     below.
   - The dev-bank runner gains the same typed arm, through `experiment_untruncated`.
8. **The registry.** `qwen38-27b` is re-pointed to `default-model-2`, and a `gemma-4-31b`
   entry is added on `default-model`. Both are confirmed by token id before and after every run
   (Qwen ends on 248046, Gemma on 106).

## Arms (Phase 2)

All arms run on one commit, back to back, with thinking at `reasoning_effort=medium` for
Qwen. Gemma runs at its default.

| Arm | Planner model | Hand-off | Card in prompt |
|---|---|---|---|
| **E** (control) | Qwen 3.8 27B | English sub-questions; builders read text (today) | today's prompt |
| **T-lazy** (primary) | Qwen 3.8 27B | typed plan through the catalog | names only; detail through `find_schema` and `describe` |
| **T-full** | Qwen 3.8 27B | typed plan through the catalog | the whole card |
| **T-lazy-G** (replication) | Gemma 4 31B | as T-lazy | as T-lazy |
| **R** (reference) | none | the rules-only pipeline, re-captured today | — |

**The gates are judged on T-lazy against E.** T-full answers the plan's
"loading only what's needed" question. Gemma is reported but does not gate. R re-anchors the
historical 0.4667 on today's tree.

## Data

- **Variant set:** `docs/evaluation/variants-2026-09-15/variants.json`, 579 variants:
  - T1 120, T2 120, T3 101, T4 104, T5 104, T6 30.
  - T0 is the 120 golden questions of `utils/specialists/tests/golden/{attack,capec,federated}_questions.json`.
  - Variants are scored against the reference capture (`reference.json`) made by R today, and
    checked twice for identity.
- **Dev bank:** `docs/evaluation/composition/bank/bank-dev.json`, 284 questions, scored
  against the authored plan's records (`generic_composed`, committed at
  `docs/evaluation/experiments/harness-attribution-qwen-walkfix-2026-11-16/generic_composed/answers`).
- **Catalog generation:**
  - ATT&CK and CAPEC (`data/source_cards/`);
  - the 11 CypherBench schemas;
  - the Text2Cypher graphs (movies, northwind, fincen);
  - the Mind the Query graphs (wwc, healthcare, er).

  A card that needs a live store for introspection is generated only if that store is loaded,
  and any skipped card is reported.
- **Not used:** the sealed held-out banks of Step 6.

## Metrics

From `variant_harness.score()`, per tier with no pooling, unless stated:
- **`records_exact`:** the variant's entity-id set equals the reference's for its gold
  question.
- **`wrong_entity`:** records were returned, and none is in the reference set.
- **`abstained`:** an abstention, or no records.
- **Empty retrieval (dev bank):** the authored plan has records > 0 and the arm has records = 0
  (`planner_cost_score.lost`). `both_empty` and `gained` are reported too.
- **Confidently wrong:**
  - **On variants:** `wrong_entity` and not `abstained`.
  - **On the dev bank:** the arm returns records, the authored plan returns records, and the
    two sets do not overlap.
  - The variant count and the dev count are reported separately.
- **Typed-path health** (T arms):
  - share of plans valid at first emission;
  - share fixed by coercion, then by the repair turn;
  - share still refused (which counts as abstained);
  - catalog tool calls per question;
  - prompt tokens.
- **Paired uncertainty:** each arm minus E on the same items, with 2,000 bootstrap resamples
  over cases (seed 20261118).

## Hypotheses: the agreed bars

| | Bar | Measured as | Falsified if |
|---|---|---|---|
| **G1** synonym tier | ≥ 0.80 | T-lazy `records_exact` on T1 (120) | below 0.80 |
| **G2** empty retrievals | ~~halve from 77, so ≤ 38~~ at most half of E's same-tree count (amendment 1) | T-lazy lost count on the dev bank (284) | above ⌊E / 2⌋ |
| **G3** original wording | ≥ 0.98 | T-lazy `records_exact` on T0 (120) | below 0.98 |
| **G4** confidently wrong | does not rise | T-lazy against E, the variant (T0–T5) and dev counts each | either count above E's |

**Reported, not gated:**
- E, R and T-full on every bar.
- **G2's stronger reading:** whether T-lazy's lost count is at most half of E's, measured on
  the same tree.
- T2–T6 per tier.
- **G4's interval:** the paired interval on each confidently-wrong difference.

## Engineering checks (Phase 1; each must pass before Phase 2 runs)

| | Check | Pass |
|---|---|---|
| **E1** text boundary | new `utils/specialists/tests/test_typed_boundary.py`: a typed task whose `text` is replaced by nonsense gives identical queries and records, for every golden question through the rules pipeline | 120 of 120 identical |
| **E2** catalog generation | every loaded card's catalog validates as JSON Schema (Draft 2020-12); every enum equals the card's set; a grep of `utils/agent/` for graph and label names from any card finds none | all three |
| **E3** error contract | a 1,000-call fuzz (seeded) of invalid tool calls over the ATT&CK and CAPEC catalogs; every refusal has a non-empty `fix` naming at least one valid option | 1,000 of 1,000 |
| **E4** coercion | unit cases, plus a replay of the kill tests' invalid typed requests (EXP-2026-11-006), counting how many coercion fixes and how many it fixes wrongly | reported; 0 wrong fixes |
| **E5** recorded answers | `scripts/era2_exact_check.py` over both 30-question banks and the 284 dev questions, deterministic and `generic_composed`, against committed baselines | 30/30, 30/30, 284/284 unchanged |

E5 is the check on moving the text reads upstream: the fast path must not change.

## Procedure

```bash
# Phase 0 — stores and models
uv run main.py --dataset attack --graph verify && uv run main.py --dataset capec --graph verify
uv run python scripts/killtests_t1_model.py          # token-id identity of both aliases
# Phase 1 — build, then E1–E5 (commands fixed when the code lands; recorded in RESULTS §8)
# Phase 2 — reference capture twice (R), then arms E, T-lazy, T-full, T-lazy-G
uv run python scripts/variant_harness.py capture --out <exp>/data/variants --name reference.json --workers 8
uv run python scripts/variant_harness.py capture --out <exp>/data/variants --name reference_check.json --workers 8
uv run python scripts/variant_harness.py compare --out <exp>/data/variants --arm {E,T-lazy,T-full,T-lazy-G} --workers 16
uv run python -m utils.evaluation.experiment_untruncated --arm {planned_llm_english,planned_llm_typed,...} \
    --bank docs/evaluation/composition/bank/bank-dev.json --root <exp>/data/dev --workers 16
uv run python scripts/era2_catalog_score.py --data <exp>/data     # metrics.json + tables
```

**Concurrency** is 16 per model, as the operator allows. Qwen and Gemma arms may run at the same
time, since they are separate backends.

**Calls:** about 700 variant and 284 dev questions per planner arm, with up to 5 planner turns
each (4 catalog calls plus 1 repair). That is at most about 5,000 calls per arm and 20,000 in
all.

## Decision rules

- **All of G1–G4 pass:** the typed hand-off ships as the default for the planned path. Step 9
  builds the operators on this catalog.
- **G1 or G2 fails while E1–E5 pass:** the catalog ships for the agent loop. The planned path
  keeps the English hand-off. The failure is diagnosed per question (wrong relation, wrong
  anchor, refused plan, empty), and the plan is revised before Step 9.
- **G3 fails:** the typed path loses on original wording, and it does not ship.
- **G4 fails:** it does not ship, whatever G1–G3 say. Accuracy outranks coverage.
- **T-full beats T-lazy on G1 by more than 0.05:** the prompt loads the whole card for cards
  under a size to be set by amendment.

## Threats, stated in advance

- **The T1 variants are all ATT&CK, CAPEC or federated.** The synonym bar says nothing about
  other graphs. Step 14 covers unseen graphs.
- **The reference is the rules pipeline's own capture of each gold question.** A typed arm can
  be right where the reference is wrong and still score as "not exact". T0 bounds this (G3).
- **The readings for ATT&CK and CAPEC were written knowing these relations.** Template readings
  are used only for other cards, which are not scored here.
- **One run per arm.** Order and nondeterminism are not repeated. The arms run back to back on
  one commit, because a mid-run commit has changed answers before.
- **The aliases have swapped before.** Identity is checked by token id before and after every
  arm, and a mismatch voids the arm.
- **The repair turn and the 4 catalog calls make T-lazy a small loop.** It is reported as
  "typed plan with up to 5 planner turns", not as a single call.

## Amendment 1, 2026-11-18, before anything is built or run: G2 is tightened to half of the control

**Operator, 2026-11-18:** G2 gates on half of the control arm's count on the same tree, not on
≤ 38. The reason is that today's Qwen planner already loses only 45 (EXP-2026-11-009 A-2), so
≤ 38 would ask for a cut of 7.

| | Bar | Measured as | Falsified if |
|---|---|---|---|
| **G2** empty retrievals | at most half of E's | T-lazy's lost count on the dev bank (284), against arm E's lost count from the same commit and run session | T-lazy's count is above ⌊E / 2⌋ |

- **The old reading becomes a report.** ≤ 38 (half of the historical 77) is reported, not gated.
- **E is measured, not assumed.** If E's count is not 45, the bar follows the measured E.
- **The paired interval** on T-lazy minus E (2,000 bootstrap resamples over the 284 cases) is
  reported beside it.
- **Nothing else changes.** G1, G3, G4, E1–E5 and the decision rules stand.


## Amendment 2, 2026-11-18, after Phase 1 and before any Phase 2 call: what was built differs from what was written

Phase 1 is built, and E1–E5 pass (RESULTS will carry the figures). Ten points in the build
differ from the protocol as written. Each is fixed here before any arm runs.

1. **Arm names.** The dev-bank typed arm is two arms, `planned_llm_typed_lazy` and
   `planned_llm_typed_full`. The Gemma arm is `planned_llm_typed_lazy --model gemma4-31b`.
   The English control is `planned_llm_english`.
2. **Planner turns.** A typed plan takes **up to 6** model turns, not 5:
   - up to 4 catalog calls, spread over turns (a 5th call in a turn is refused for budget, and
     later turns get no tools);
   - 1 emission;
   - 1 repair.
3. **The model settings are made equal across arms.** As built, arm E ran
   `generic_planned_llm`'s 4,096-token cap and the `.env` thinking budget of 512, while the
   typed arms used the registry client at 16,384 tokens. Arm E now sets
   `PLANNER_LLM_MAX_TOKENS` to the registry's value and `PLANNER_LLM_THINKING_BUDGET=0`. Both
   arms then run Qwen at `reasoning_effort=medium`, 16,384 tokens and no thinking budget,
   checked at the resolver. The hand-off is the only difference.
4. **The pipeline deadline.** Every planner arm, E included, runs at `PIPELINE_TIMEOUT_S=900`,
   not the `.env` 120 s. Otherwise six planner turns would use up the retrieval deadline and
   be scored as empty retrievals. E's lost count may therefore differ from EXP-2026-11-009's
   45. Amendment 1 already gates on the measured E.
5. **Engines differ by harness.** The variant arms run the reference's own setting (the
   template cascade, `SPECIALIST_GENERIC_ONLY=false`), and typed steps run ahead of the
   cascade. The dev arms run the generic engine, as `generic_planned_llm` does. Within each
   harness, every arm uses the same engine setting.
6. **The planner's catalog tools have no store attached.** `describe` of an entity id is
   refused, and `resolve_entity` answers from the entity index.
7. **Step 9's operators are not in typed steps.** These are set operations other than "what
   every anchor links to", aggregate, group and rank. Questions that need them become
   `unsupported` parts. The step `filter` is single-valued equality on the last label.
8. **Two reads of the request remain on the typed path,** neither in a builder or the
   resolver:
   - `federation.request_seeds(plan.request)`, for a consumer whose producer yielded nothing;
   - the planner's intent classifier, which is off in every arm (`PLANNER_INTENT_LLM_ENABLED=false`).
9. **The paired bootstrap.** Variants are resampled with each gold question and its variants
   as one cluster. Dev questions are resampled one by one. Both use 2,000 resamples, seed
   20261118.
10. **Bridged steps lose their typed path.** A joined Gremlin step that walks the declared
    join edge, or that is anchored on another graph's ids, runs on the engine's bridge. Its
    stated direction and target are not used, and these are counted in the typed-path health
    figures.

**The authored baseline for G2 and G4** is the committed
`harness-attribution-qwen-walkfix-2026-11-16/generic_composed/answers`. A same-tree
`generic_composed` run on 2026-11-18 agreed with it on records > 0 for 284 of 284 questions.

**Unchanged:** the gates G1–G4 (G2 as in amendment 1), the arms' roles and the decision rules.
