# Overnight report — 2026-09-07

Driver started **2026-09-07 00:49:19.826761**, deadline **2026-09-07 08:00:00**.
Endpoint: `qwen38-27B-v2` on `:9090`, sharded across **default-model-2 / -3 / -4** at 32 workers each. **`default-model` was reserved by the operator at 01:15 and is untouched from that point.**

> **What did not happen.** The driver exited at 02:49 having completed every step it was given, not at the 08:00 deadline. Its steps finished early because judging completed early. No replacement was scheduled, so between 04:00 and 09:57 nothing ran: three extension seeds generated at ~03:30 sat ungraded, and no 08:00 report was produced. Grading started 09:57. The gap is an operator error, not a tool failure -- there was a watchdog for judging and none for the schedule.

## Steps

| step | outcome | elapsed |
|---|---|---|
| `judge_generic_resume_1` | rc=143 | 17 min |
| `judge_generic_resume_2` | rc=143 | 1 min |
| `judge_generic_resume_3` | ok | 95 min |
| `validate_research` | ok | 0 min |
| `verify_paper_numbers` | ok | 0 min |
| `identity_analysis` | ok | 0 min |
| `report` | ok | 0 min |

## EXP-2026-09-011 — does `generic`'s wording variation move its score?

This is the cell the night was for. `EXP-2026-09-010` established that `generic` words 143 of 276 answers differently on a rerun at the same seed, in the field the grader reads. Whether that reaches the **score** is this measurement.

| seed | block q1 | n | block q2 | n |
|---|---|---|---|---|
| 1729 | 0.6646 | 284 | 0.6394 | 284 |
| 20260906 | 0.6451 | 284 | 0.6444 | 284 |
| 424242 | 0.6468 | 284 | 0.6394 | 284 |

### Extension seeds (EXP-2026-09-011 A-1)

| seed | answers generated | judgments |
|---|---|---|
| 31337 | 284 | 0 |
| 8675309 | 284 | 0 |
| 271828 | 284 | 0 |

**Generated but ungraded.** Three further seeds were generated to turn a three-point spread into something closer to a distribution, and grading was not queued behind the generation. The answers are frozen on disk and can be graded at any time; nothing is lost but the elapsed hours.

**Balanced across-seed spread: 0.0039** (means [0.652, 0.6447, 0.6431]).

- **H2** (SD < 0.03): **holds**
- **H3, as pre-registered** (holdout gap 0.1684 > 3xSD = 0.0116): **holds**
- **H3, same population** (dev gap 0.1623 > 3xSD = 0.0116): **holds**

The pre-registered form of H3 compares a holdout gap against a spread measured on the dev half. That mismatch is in the protocol as written, so it is reported as written *and* alongside the same-population comparison, which is the one that actually tests what H3 means.

Counterbalancing note: both blocks are the **same grader**, so this is position-balanced repeatability, not cross-grader agreement. The second grader family was unavailable (its slot was freed).

## Record

**44 of 45 experiments complete.**

Not complete:
- `EXP-2026-07-010-independent-eval-baseline` — superseded

## Paper number traceability

- traced to a manifest: **86**
- untraced: **0**

This check did not exist before tonight. `OUTLINE.md` and the draft's own appendix both claimed automated enforcement of number→experiment traceability; a readiness audit found no such check. It is a **review list, not a gate**.

---

*Generated 2026-09-07 09:58. Every figure is read from disk at render time; nothing here is carried over from prose.*
