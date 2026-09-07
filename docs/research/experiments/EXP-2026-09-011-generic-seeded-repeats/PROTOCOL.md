# PROTOCOL — EXP-2026-09-011 — how much does the primary result move across seeds?

**Written 2026-09-06, before any run.** Pre-registered. Append AMENDMENTS.

---

## Why this exists

`EXP-2026-09-010` amendment A-2 established, from the artifacts rather than from
assumption, that the `generic` arm **composes its answers with a language
model** (`run_meta.synthesis: "llm (claim-grounded)"`). Only its *query* path is
model-free.

`scripts/holdout_run.py` drives the same harness. So the paper's primary
result — **`generic` 0.6546 on the holdout, and the `+0.1684` gap over
`deterministic`** (`EXP-2026-09-007`) — was produced by answers a language model
wrote, from a single draw, with no variance estimate.

That is the largest unmeasured quantity in the record, and it sits directly
under the headline number.

**What its sibling experiments do and do not cover:**

| Experiment | Question | Covers `generic`'s spread? |
|---|---|---|
| `EXP-2026-09-009` | Does `llm_query` hold its sign across seeds? | No — different arm |
| `EXP-2026-09-010` (`deterministic`) | Is it identical across runs? | No — different arm; and it is, 284/284 |
| `EXP-2026-09-010` re-run (`generic`) | Does a rerun **at one fixed seed** reproduce? | Partially — reproducibility, not seed sensitivity |
| **This experiment** | How far does the number move when the seed changes? | **Yes** |

The re-run and this experiment answer different questions and **both are needed**.
A byte-identical rerun at seed 1729 would show the published figure is
reproducible; it would say nothing about how much the choice of 1729 mattered.

---

## Design

Identical to `EXP-2026-09-009` except the arm, so the two are directly
comparable.

**Arm.** `generic`.

**Population.** Expansion-bank dev half, n=284, sha256 `a4ca6702029cae77…` — the
same file as `EXP-2026-09-002`, `-005`, `-009` and `-010`.

**Runs.** Three, `LLM_SEED` ∈ {1729, 20260906, 424242} — the same three seeds as
`EXP-2026-09-009`, so any seed-specific effect is visible across arms. Seed 1729
is the configuration every recorded run used.

**Narrator.** Pinned to `:9090/default-model` (`qwen38-27B-v2`), probed at
launch. `.env` points at `:4000/skynet`; that route was **timing out on
2026-09-06** and is what invalidated `EXP-2026-09-010`'s first `generic` attempt.
The operator confirms both routes reach the same backend. Recorded as a
deliberate deviation.

**Configuration**, matching the recorded runs: `ORCH_MAX_HOPS=5`,
`--llm-max-tokens 32768`, no thinking cap (`EXP-2026-09-008` closed it),
workers 32.

**Grading.** Both families, counterbalanced across the seed axis exactly as in
`EXP-2026-09-009` — each seed occupies position sum 2, so the ~0.01 position
effect (`EXP-2026-08-022`) cancels in the balanced estimate. **H2 is adjudicated
on the balanced estimate only**; per-family SDs carry the confound.

---

## Pre-registered hypotheses

**H1 — the ordering survives.** `generic > deterministic` in all three runs under
both grader families, against `deterministic`'s fixed figure (0.4946,
`EXP-2026-09-005`), which needs no repeat because that arm is verified identical
across runs (`EXP-2026-09-010`).
*Falsified by:* any run/family cell in which the ordering does not hold.

**H2 — the spread is small relative to the gap.** Across-seed SD of `generic`
judged correctness, on the balanced estimate, is **below 0.03**.
*Falsified by:* SD ≥ 0.03.

**H3 — the gap survives its own spread.** The `+0.1684` holdout gap exceeds
three times the across-seed SD measured here.
*Falsified by:* SD ≥ 0.0561.

## What each outcome means, decided now

| Outcome | Consequence |
|---|---|
| H1–H3 hold | The primary result is robust to narration variance. The paper quotes the SD beside the gap and limitation 5 narrows to `llm_query` alone. |
| H2 fails, H3 holds | The gap survives but the arm is noisier than the record implies. Every `generic` figure gets an interval, and `n_runs: 1` is no longer defensible for it. |
| **H3 fails** | **The primary result is not separable from its own run-to-run noise.** `C-023`'s judged figures cannot be quoted as point estimates, §5 of the paper is rewritten around retrieval rather than judged correctness, and replication becomes mandatory before submission. |
| H1 fails | The ordering itself is seed-dependent. That is a finding about the field, not just this system, and it is reported as one. |

The third and fourth rows are the expensive ones. It is recorded here, before the
data exists, that they will be reported rather than re-run until they go away.

---

## Guards

Every guard from `EXP-2026-09-009`, plus the two whose absence invalidated
`EXP-2026-09-010`'s first attempt:

- Stores asserted at pinned counts before any request.
- `served_model` asserted per generation and per grading pass; a pass reporting a
  string not in the record is discarded, not reconciled.
- **The narrator endpoint is probed**, not merely the grading endpoints.
- **`fallback_reason` is read after every run.** A capture with it non-null
  anywhere is degraded — the arm has reported it could not narrate — and is
  discarded and retried rather than graded. Grading a degraded capture would
  measure endpoint availability and call it narration variance.
- A run writing fewer than 284 answers is `not_run`.

## What this does not do

- It does not re-open the holdout. The seeds move on the dev half; the holdout is
  spent.
- It does not separate *narration* variance from *retrieval* variance. If the
  arm moves, a follow-up must localise where. `EXP-2026-09-010`'s re-run is the
  start of that: at fixed seed, retrieval should not move at all.
- Three runs gives a spread, not a distribution. `RESULTS.md` must say so.

---

# AMENDMENTS

## A-1 (2026-09-07) — three further seeds

**Extension, not a correction.** The completed experiment's own limits say
"three seeds gives a spread, not a distribution." This adds three more:
`LLM_SEED` ∈ **{31337, 8675309, 271828}**, chosen before the extension ran, as
the first three were.

**Everything else is held.** Same arm, same 284-question bank at sha256
`a4ca6702029cae77…`, same `ORCH_MAX_HOPS=5`, same 32,768-token budget, same
narrator pinned to a probed `qwen38-27B-v2`, same two counterbalanced grading
blocks giving every seed position sum 2.

### What it can and cannot change

- It **cannot** revise the reported figures. The pre-registered three-seed
  result — balanced SD **0.0039** — is what H1–H3 were adjudicated against, and
  it stands as reported whatever six seeds show.
- It **can** show that spread was optimistic. If the six-seed SD is materially
  larger, that is reported as a finding and the paper quotes the six-seed
  figure with the three-seed one beside it. **Recorded before the data exists.**
- Grading uses a **separate state file** (`judge-state-extension.json`) so the
  extension cannot overwrite the record of the pre-registered run.

### Status

Generation completed 2026-09-07 ~03:30 — 284 answers per seed, all three.
**Grading did not follow.** It was not queued behind generation, and the
endpoints were down when it was finally started at 09:57. The answers are frozen
on disk; grading is queued against `default-model-2`.

**This is recorded because the gap is the interesting part.** An extension whose
answers exist and whose judgments do not is indistinguishable, in a manifest,
from one that never ran. `n_runs` stays at **3** and the manifest carries the
pre-registered result alone until the extension is graded and written up.

### Two defects this amendment exposed

1. `scripts/seeded_repeats_judge.py` hardcoded the pre-registered seed list, so
   a run launched to grade the extension examined the original seeds, found
   every sidecar present, and would have **exited reporting success having done
   nothing**. Fixed with `--seeds preregistered|extension`.
2. `answers_present()` globbed `*.json`, counting judgment sidecars as answers —
   a fully graded seed read as **852** against an expected 284, so the guard
   that refuses to grade a short seed could never fire. Fixed to count answer
   files only.

Both were visible in a single line of the run's own output and neither raised an
error.
