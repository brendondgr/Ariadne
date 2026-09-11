# PROTOCOL — EXP-2026-09-018 Correctness repair: six located defects, measured against a concurrent control

**Written 2026-09-11, before any repair code was changed.** The mechanism table
this rests on is `EXP-2026-09-017` `A-2`; the measurement discipline is
`EXP-2026-09-017`'s own falsification clause, which says an intervention chosen
on a dataset needs a concurrent control and a freshly sealed set before it can
be claimed. Steps and hypothesis numbers match
`docs/plans/2026-09-11-correctness-repair-programme.md`.

## Question

The `generic` arm scores **0.6569** on the 284 development questions, and
**0.9675** on the 67 of them where none of six located defects fires. Do
repairs to those six defects move the judged mean, and does the movement survive
a concurrent control, a grader-drift control, and a set nothing in the selection
touched?

## Hypothesis

Each defect is a coding error with an identified location, not a capability
limit, so repairing it should raise the judged mean on the questions it owns and
leave the others alone. The bound, if every affected question rose only to the
single-hop ATT&CK mean of 0.797, is about **+0.20** on the development mean.
That bound is not predicted; it is stated so that a smaller result is not
re-described afterwards as the expected one.

## Setup

**System under test:** `generic` — schema-derived primitives, LLM planner
replan, LLM specialist seam, LLM narrator, facet loop. It carries `C-023` and
the pitch's headline.

**Run beside it in every measurement:**

| Arm | Why it is here |
|---|---|
| `generic_composed` | the model-free twin: same primitives, deterministic composition. Byte-reproducible, and the answer contract must hold *without* a narrator to be a construction property `C-017` can rest on. |
| `deterministic` | the regression control. Must stay byte-identical throughout. |

**Held constant.** Gold-plan protocol as in `EXP-2026-09-005`: the bank's
authored plan is injected, and it carries the ordered graph vocabulary, seed ids
and limits and **nothing else** — no filter, no requested property, only the
first relationship token of a chain. The requested property, the filter and the
chain are derived at run time from the ordered `entities` list and the
sub-question text against the card's declared vocabulary, so the shipped path,
which receives an LLM-drafted plan of the same shape, benefits identically. The
plan schema is **not** extended. If that decision is reversed the change must be
run for all three arms and disclosed as a protocol change.

**Budgets.** `SYNTHESIS_LLM_TIMEOUT_S=600` with the `degraded()` health check of
`scripts/generic_identity_rerun.py`; `SPECIALIST_LLM_TIMEOUT_S=4096`;
`ORCH_MAX_HOPS=5`; 24 workers for generation. These match
`scripts/holdout_run.py` and `EXP-2026-09-016` `A-1`, so cost figures stay
comparable to the published cost table.

**Judge.** `qwen38-27B-v2` on `:9090`, two counterbalanced positions per answer,
`max_tokens 32768`, 16 workers per healthy instance. `gemma4-31B` grades a
second pass for **ordering only**; its scores are never averaged with qwen's
(`EXP-2026-09-009`). Q48's abstention-boilerplate artefact is left in place for
comparability with the published runs and is reported separately.

## Data

| Set | n | Role |
|---|---:|---|
| `bank-dev.json` | 284 | selection and the paired control (Steps 5–6) |
| `bank-holdout.json` | 288 | **spent** — regression only, never new evidence |
| `bank-fresh-<date>.json` | 288 | minted at a new seed, SHA-256 sealed before any arm sees it; the only set that can replace 0.6546 on a slide (Step 7) |

The holdout's spent status is recorded in `data/holdout_seal_prerepair.json`:
`scripts/holdout_seal.py` reports `sealed: false`, `generic` and `llm_query`
listed as unsanctioned arms, and 1,152 judgments per arm from
`holdout-spend-2026-09-05`. That file is the pre-repair state, so any later
holdout answer is attributable to this experiment.

## Metrics

- **Judged correctness** — the qwen judge's `correctness` in [0, 1], averaged
  over the two counterbalanced positions, then over questions. The population is
  named with every figure: whole bank, tier, or mechanism slice from
  `EXP-2026-09-017/data/mechanisms.csv`.
- **Mechanism slice mean** — the same, restricted to the questions one mechanism
  owns under `A-2`'s first-match assignment. Slice membership is fixed at the
  pre-repair commit and never recomputed after a repair, or the denominator
  moves with the intervention.
- **Gold coverage** — `deterministic_scores.coverage.coverage`, model-free, for
  the reference diffs in Steps 1–4.
- **Requested-value rendering** — the share of D1 property questions whose
  evidence carries the requested value and whose *claims* also carry it.
  Deterministic, computed without a judge.
- **Out-of-filter leakage** — the count of enumerated records violating a bound
  filter on D5. Success is zero.
- **Narrator fallback rate** — fallbacks divided by **answers**, never files
  (`EXP-2026-09-016` `A-8`). Healthy reference 0.14, degraded 0.70.
- **`fabricated_mapping`** — from the deterministic verifier, not the judge.
- **T6 wrong-entity and catalogue-dump rates** — `scripts/variant_harness.py`.
- **Single-user latency** — 20 questions, one worker, at the shipped 120 s
  narrator budget *and* at 600 s, because `Q37` says a stage that adds latency
  inside a bounded pipeline cannot be reported without naming the budget.

## Baselines

Three, and the first is the one that matters.

1. **The reference-commit arm, run concurrently.** `generic` and
   `generic_composed` at the pre-repair commit, in the same session, on the same
   live graphs, against the repaired arms. `Q46` documents a 0.0503 move between
   sessions with near-zero within-session spread, so a baseline read from a
   different session is not a baseline for a changed builder.
2. **Unchanged answers as a grader-drift control.** In the frozen-evidence
   comparison, answers whose claims did not change are graded in both passes.
   Their paired difference must fall within the grader-repeatability SD of
   0.0066 (`EXP-2026-09-012`) or the judge moved, not the system.
3. **The model-free references captured at the pre-repair commit** —
   `deterministic` and `generic_composed` over both banks, under
   `data/reference/`. Every model-free diff in Steps 1–4 is against these.

## Pre-registered hypotheses

All on the development half, paired, same session.

| | Claim | Pre-registered threshold |
|---|---|---|
| **H1** | chained walk | `chain` + D6 generic mean rises by **≥ 0.10** |
| **H2** | namespace | zero-record rate on non-D0 Category/View anchors falls from **21 of 23 to 0** |
| **H3** | Q45 allowlist | the 34-question `capec` slice rises from **0.4287 to ≥ 0.60** |
| **H4** | answer contract | on the frozen-evidence re-composition, the requested value appears in the claims on **100%** of D1 property questions whose evidence carries it, and the judged mean on those questions rises |
| **H5** | filter | on D5, records outside a bound filter are **absent** from the claims, and the judged mean rises |
| **H6** | no regression | `deterministic` byte-identical on both banks; `fabricated_mapping` 0 on every arm; T6 wrong-entity and catalogue-dump rates do not rise; repaired `generic` single-user latency at the shipped budget within **2x** its Step 0 reference |

`H2`'s denominator is 23 and not 25 because `A-2` assigns two of the 25 non-D0
Category/View questions to the `capec` mechanism, which is repaired first.

## Kill gate

**Any rise in `fabricated_mapping`, or in the variant bank's T6 wrong-entity
rate, means the change does not ship regardless of the mean.** A run whose
narrator fallback rate over answers exceeds 0.14 is discarded and re-run, never
reported.

## Procedure

```bash
# Step 0 — record, correct, pre-register, capture references (no model)
.venv/bin/python docs/research/experiments/EXP-2026-09-017-correctness-improvement-diagnostic/data/mechanisms.py
.venv/bin/python docs/research/experiments/EXP-2026-09-016-arm-cost-and-latency/data/fallback_audit.py
.venv/bin/python scripts/holdout_seal.py > docs/research/experiments/EXP-2026-09-018-correctness-repair/data/holdout_seal_prerepair.json
# model-free references for both banks at the pre-repair commit -> data/reference/

# Steps 1-4 — repairs, unit tests, model-free regression only (no model)
.venv/bin/python -m pytest utils/specialists/tests utils/synthesis/tests utils/planner/tests utils/kg_builder/tests -q
.venv/bin/python scripts/catalogue_regression.py

# Step 5 — frozen-evidence composition comparison (server, ~2 h)
.venv/bin/python scripts/recompose_frozen.py

# Step 6 — concurrent paired control on the dev half (server, one night)
.venv/bin/python scripts/model_identity.py --json
.venv/bin/python scripts/repair_control_run.py

# Step 7 — freshly sealed set, run once (server, one night plus authoring)
# Step 8 — write-up and gates
make validate-research && make index && make check-docs
```

## What would falsify this

- **H1–H5 individually:** the slice mean does not move, or moves by less than
  the grader-repeatability SD, against the concurrent reference arm. A repair
  that changes records but not the judged mean is recorded as a null result and
  the mechanism's share in `A-2` is re-read as a mis-attribution.
- **The whole programme:** if the `none` bucket's 0.9675 does not hold on the
  freshly sealed set, the mechanism decomposition was an artefact of the dev
  half and the defect list is not the explanation for 0.6569.
- **Step 5 falsifies Step 4 specifically.** If the judged mean does not move on
  D1 and D5 when the *same* evidence is recomposed, the answer contract is wrong
  and must not be carried into Step 6.
- **The grader-drift control falsifies everything downstream of it.** If
  unchanged answers move by more than 0.0066, the session's judge is not the
  published one and no comparison in this experiment is admissible.

## Disclosure

`EXP-2026-09-005` repaired the *template* arm before comparing. Everything here
repairs the *generic* arm and therefore widens a gap `C-023` already reports in
its favour. This must appear in the first paragraph of RESULTS, and `C-023`'s
evidence column is amended rather than replaced. Scoring corrections (`Q44`,
`Q48`) are reported apart from capability gains.
