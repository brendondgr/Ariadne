# PROTOCOL — EXP-2026-09-014 Hybrid rewrite stage

> Written and committed **before** any arm is run. The ship rule below is
> pre-registered: it was confirmed by the operator on 2026-09-08, before a
> single scored number existed, and it is quoted verbatim in RESULTS.md.

## Question

The deterministic engine scores 1.0000 on the 120 gold questions and **0.0000**
on 208 paraphrased variants at T4 and T5, across every arm ever tried
(EXP-2026-08-020). Does putting one stage in front of it — which rewrites the
analyst's question into a canonical tier-0 form in the source card's own
vocabulary, deterministically where the shipped machinery can bind a slot and
otherwise by a model **choosing from candidate lists it cannot add to** — recover
record identity at T4/T5 without raising the confident-and-wrong rates the
project exists to avoid?

It has an answer that could come out either way. Step 1 already found one way it
comes out badly: a rewrite that discards words the raw question carried can score
*worse* than no rewrite, and the T1 case "How do I defend against T1047?"
canonicalises to a bare description because the shipped intent classifier does
not read `defend` as remediation.

## Hypothesis

1. **T4/T5 move off the floor.** Record identity rises from 0.0000 to somewhere
   under the measured anchor ceiling (tune half, Step 3: T4 0.4528, T5 0.5660).
2. **T6 does not move.** An invented identifier has nothing to find, and the
   candidate lists contain nothing that matches it, so the gate abstains.
3. **T0–T2 are at risk, not safe.** The deterministic rewrite can lose
   information the raw question carried. If R1 falls below R0 at T0/T1/T2, that
   is the finding, not an anomaly.
4. **Within-model variance is small but non-zero.** Every graded call is
   temperature 0 and seeded; the residual is batch-shape reduction on the server.

## Setup

The real pipeline, planner included, with **no language model in planning,
query building or synthesis** in any arm. The only variable is the rewrite
stage. Flags: `ARIADNE_REWRITE`, `ARIADNE_REWRITE_MODEL`, both stated
explicitly in every arm rather than inherited from `.env` (D-029).

- **R0** — rewrite off. Must reproduce `reference_2026-09-08.json` exactly.
- **R1** — deterministic fill only. No model, no network, byte-reproducible.
- **R2** — model fill, `default-model` on `:9090`, **3 runs**, cache cleared
  between them so what is measured is model variance and not cache variance;
  then a 4th run from cache to show the cache reproduces run 3.
- **R3** — model fill, `default-model-2` on `:9090`, same protocol.
  **R3 is a cross-instance repeatability arm, not a model comparison.** The
  operator confirmed on 2026-09-08 that `default-model` and `default-model-2` are
  two instances of the same checkpoint (`qwen38-27B-v2`) on different GPUs, and
  both probes returned the same `system_fingerprint`. Any claim from R2-vs-R3 is
  about serving instances, not about models. See ISSUES.md.
- **R4** — the 572-question expansion bank, dev and holdout, rewrite off / det /
  model, one run, with whichever instance R2–R3 ranked first.

Model identity is re-probed **at run time** for every arm, from a response
envelope and never from the alias, because `default-model-2` demonstrably flaps
(ISSUES.md) and an alias is not a model (D-028).

## Data

- **Variant bank**: `docs/evaluation/variants-2026-08-29/variants.json`, 579
  variants over the 120 gold questions, frozen 2026-08-29. Tiers T1–T6; T0 is the
  gold questions themselves, from `reference_2026-09-08.json`.
- **Split**: `split.json`, 301 tune / 278 report. Everything below is run on the
  **tune half first**. The `report` half was spent once, on the name-index margin
  threshold; it is disclosed as "seen once before, for a different mechanism" and
  is read exactly once at the end.
- **Expansion bank**: `docs/evaluation/composition/bank/bank.json`, 572
  questions, dev and holdout apart. `bank-holdout.json` has been seen by nothing
  in this stage and is the clean report set.
- **Understanding-gold**: `slot_gold.json`, 120 records, built from question
  metadata and raw-source answers and never from system behaviour — which is why
  it can score this stage without defining the incumbent as correct. It does not
  specify the federated bank (ISSUES.md): 40 of 120 records carry only an anchor.

Selection bias: the variant bank over-samples the paraphrase tiers on purpose,
so a pooled figure across tiers is meaningless and is never quoted. Every number
is per tier.

## Metrics

Over the variant bank, per tier, against each variant's own gold question's
captured behaviour (never a hand-written expectation):

- **`records_exact`** — the set of entity identifiers retrieved is identical to
  the gold question's. **Primary.** A variant reaching them through a different
  query is a success: outcome, not interpretation.
- **`records_recall`** and **`records_recall_no_dump`** — fraction of the gold's
  identifiers retrieved, pooled and with catalogue dumps removed. The second is
  the honest one; the first credits answers found by returning everything.
- **`wrong_entity`** — returned records and **none** is one the gold found.
  Nothing downstream catches this: every claim is genuinely grounded in a
  genuinely retrieved record, and all of them are about the wrong thing.
- **`catalogue_dump`** — ≥50 records and ≥10× the gold's count, or any large
  result where the gold returned none.
- **`abstained`** — no records, or an explicit abstention.
- **Slot accuracy** — per slot (`slot_anchor`, `slot_anchor_label`,
  `slot_target_label`, `slot_relation`) and `form_exact`, against `slot_gold`.
  This is what separates *understanding* from *retrieval*: a right form that
  renders to a sentence the engine mishandles is a renderer defect, and a wrong
  form that still retrieves the gold by dumping is the I-11 failure class.
  Neither is visible in `records_exact`.
- **Provenance** — `rung` (off | deterministic | model | abstain),
  `model_consulted`, `cache_hit`, `served_model`, latency.

Spread is the **population standard deviation across the three runs of an arm**,
not a confidence interval. Three runs is three runs.

## Baselines

- `reference_2026-09-08.json` — the 120 gold questions with every LLM seam off,
  captured at Step 0 on the graphs these arms run against. R0 must reproduce it.
- **Not** the shipped `reference_arm6.json`: 0 of 120 cases differ on
  `entity_ids`, but 60 differ on `queries`, 15 on `claims` and 11 on abstention
  wording, because of shipped changes and an ATT&CK 19 refresh since 2026-08-29
  (ISSUES.md). Record comparisons against the published Arm 0–6 figures remain
  valid; query comparisons against them do not and are not made.
- On the expansion bank the control is **`rewrite_off`**, not `deterministic`.
  `deterministic` replays the authored plan and never runs the planner, which is
  where the stage under test lives; comparing against it would measure
  gold-replay-versus-planner and call it the rewrite.

## Ship rule (pre-registered)

> **Ship** — flip `ARIADNE_REWRITE` and `ARIADNE_REWRITE_MODEL` on by default —
> **only if T4 and T5 `records_exact` are both > 0.25, AND every T6 metric is no
> worse than Arm 6: `wrong_entity` ≤ 0.1000 and `catalogue_dump` ≤ 0.0667.**

The T6 half is a **gate, not a trade**. An arm that raises T6 `wrong_entity`
above 0.1000 or T6 `catalogue_dump` above 0.0667 does not ship regardless of how
much T4/T5 improve. Confident-and-wrong is the failure this project exists to
avoid, and no amount of recovered recall buys it.

0.25 is roughly half the anchor ceiling Step 3 measured on the tune half
(T4 0.4528, T5 0.5660), so it is demanding without being unreachable.

Confirmed by the operator on 2026-09-08, before any arm was scored.

## Procedure

```bash
# R0 — control. The diff must be empty.
uv run python scripts/variant_harness.py compare \
  --out docs/evaluation/variants-2026-08-29 \
  --reference reference_2026-09-08.json --split tune \
  --rewrite off --name scored_R0.json --metrics metrics_R0.json

# R1 — deterministic fill only.
uv run python scripts/variant_harness.py compare \
  --out docs/evaluation/variants-2026-08-29 \
  --reference reference_2026-09-08.json --split tune \
  --rewrite det --name scored_R1.json --metrics metrics_R1.json

# R2 — model fill, default-model, three runs, cache cleared between them.
uv run python scripts/variant_harness.py compare \
  --out docs/evaluation/variants-2026-08-29 \
  --reference reference_2026-09-08.json --split tune \
  --rewrite model --llm-base-url http://localhost:9090/v1 \
  --llm-model default-model --cache-dir <fresh dir per run> \
  --repeat 1 --name scored_R2.json --metrics metrics_R2.json

# R3 — same, --llm-model default-model-2.

# R4 — the expansion bank.
ORCH_MAX_HOPS=5 uv run python -m utils.evaluation.experiment_untruncated \
  --arm rewrite_off|rewrite_det|rewrite_model --bank <dev|holdout>
uv run python scripts/score_bank.py --rewrite off|det|model
```

## What would falsify this

- **T4/T5 stay at 0.0000** with the model consulted on most of them. The gate
  refuses everything, or the model picks off-list, or recall@5 was the ceiling
  and the chooser cannot use it. The stage does not ship and the recorded reason
  is which of the three.
- **T6 rises.** The stage manufactures a confident wrong answer for an entity
  that does not exist. This is the outcome that kills it outright.
- **T0–T2 fall.** The rewrite discards information the raw question carried. If
  R1 < R0 at T0/T1/T2 the deterministic fill is lossy, and the honest response is
  to report the loss rather than to add a rule that keeps the raw question
  whenever the rewrite would score worse — which would be fitting to the bank.
- **The three runs of R2 disagree materially.** A model seam whose spread is
  comparable to its effect has not been measured, it has been sampled once.
