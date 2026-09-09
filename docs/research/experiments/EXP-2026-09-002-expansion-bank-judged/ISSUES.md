# ISSUES — EXP-2026-09-002

Everything that is wrong with this experiment, recorded rather than smoothed
over. Each item states what a reader should refuse to conclude because of it.

## I-1 — The tree changed mid-run (`dirty: true`)

The run started at **`54dbfe0`** (2026-09-02T22:55:52Z — the harness commit,
whose timestamp is the run's start time to the second). Two commits landed
*during* the 10.9-hour run:

| commit | when | what |
|---|---|---|
| `003f2cf` | 2026-09-03T05:18Z | `builder_budget_probe.py` — a **new** script; touched no arm |
| `04a5425` | 2026-09-03T09:52Z | `morning_report.py` additions — **after** the final phase |

**What this does not invalidate:** neither commit modified the planner, the
specialists, the gate, the composer, the grader, or any arm. The three arms ran
under `54dbfe0` unmodified.

**What a reader should refuse to conclude:** that the folder is byte-restorable
by checking out one commit. It is not; `54dbfe0` is the arms' commit and the
probe artifact belongs to `003f2cf`.

## I-2 — Two models were in the loop, and only one was identified

- **The grader** was probed at preflight: `skynet -> qwen38-27B-v2`, with the
  relay advertising `'auto'`. This is the good case, and it is what
  audit-2026-08-31 X2 asks for.
- **The `llm_query` arm's builder** was called as `default-model` against
  `http://localhost:9090/v1` and **was not probed**. It is very likely the same
  served model, and that is an inference, not a record.

**Refuse to conclude:** that the arm's builder model is known. Per the local-model
discipline, `skynet` has served three different models; the alias is not evidence.

## I-3 — The arm's reasoning budget was silently wrong, twice

`.env` sets the builder budget to **2048**. The arm never read it and used a
built-in default of **4096**. Neither is enough for a reasoning model whose
chain-of-thought consumes 16 000+ characters before `content` is emitted.

Consequence: **`llm_query`'s 0.3712 is confounded and is not a baseline.** 153 of
284 questions returned an empty query the gate correctly refused. The probe
(`budget-probe.json`) shows a real query appearing at 32768.

Two separate defects here — the ignored `.env` value **and** the too-small
default. Fixing only the first would still produce a blank.

## I-4 — `config.hash` is null

The run's configuration is a prose plan, not a machine-read config file. There
is no config artifact to hash. Recorded as `null` rather than invented; the plan
is pinned by its commit (`46a051d`) instead.

## I-5 — One run per arm, and no significance test

`D-010` is still in force. Each arm answered once; only the **grading** was
repeated (twice, order-counterbalanced). The 0.1642 headline gap is argued from
**magnitude** — 16× the grader's measured 0.0050 spread and 16× the ~0.01 order
effect from EXP-2026-08-022 — not from a test. X8 in audit-2026-08-31 is the fix.

## I-6 — The folder was created a day after the run

The plan (`46a051d`, 2026-09-01) named `EXP-2026-09-002` and the changelog said
results would be recorded under it. Nobody created the folder; the numbers lived
in `docs/reports/` and `docs/evaluation/` for one day, outside the research
record, in violation of the OUTLINE rule *"every number in the paper cites an
`EXP-` ID."*

**This is a process failure, not a data failure** — every number here traces to a
hashed artifact produced by the run. Recorded so the gap is visible in the record
rather than invisible.

## I-7 — 283, not 284

The `llm_query` arm judged **283** cases against the other arms' 284, and 564
judgments against 568. **One case is missing and the cause is unexplained.** It
is 0.35% of the arm and cannot move a 0.1642 gap, but it is not accounted for.

## I-8 — 97 of 334 questions are excluded from the direction contrast

The paired contrast covers only shapes the draw asked from **both** ends: 20
shapes, 237 questions. The other 97 are single-ended and contribute nothing.
The pairing is on **shape**, not on `(shape, anchor)` — pairing on anchor gives
only 2 pairs, because the draw never asks one entity both ways.

**Refuse to conclude:** that −0.0797 covers the whole bank. It covers the paired
subset, which is what makes it unconfounded and also what limits it.

## I-9 — 2026-09-09: seeds and lockfile

`seeds: []` is accurate rather than an omission: the dev/holdout split is
`sha256(spec_id)` parity, the two model-free arms are deterministic, and the
grader and `llm_query` arm ran at temperature 0 with no seed parameter exposed
by the relay. `environment.lockfile` pointed at `env/requirements.lock`, which
was never written; set to `null` in A-1. The dependency set is `uv.lock` at
`54dbfe0`.

## I-10 — 2026-09-09: `score.json` was overwritten after this experiment read it

**Impact:** the POINTERS hash for `docs/evaluation/composition/bank/score.json`
stopped matching on 2026-09-08. The values this experiment quotes from it
(0.4522 / 0.506 / 37 of 61 / dev 0.435 / holdout 0.4683) are unchanged in the
rewritten file's `report` block, and the audit recomputed 37/61 from the
`eeef322` rows.
**Cause:** `a460fa2` (Hybrid Rewrite Stage 6/8) re-ran `scripts/score_bank.py`
over the same answers with new provenance columns and wrote to the same path.
**Resolution:** row re-hashed; the original blob
(`sha256:6fb4eaf1168e7960065f912cdb2a220726ec1a5b035f00fac60c7652aa29e048`,
233,633 B) is recoverable with `git show eeef322:docs/evaluation/composition/bank/score.json`.
**Paper implication:** none.

## 2026-09-09 — the morning report moved into the research record
**Impact:** none on any number. The report this experiment points at,
`2026-09-02-overnight-report.md`, lived in `docs/reports/`, a second report
location outside `docs/research/` (noted above as "outside the research
record"). On 2026-09-09 every file in `docs/reports/` moved to
`docs/research/reports/` and that directory was removed; the POINTERS row's
path is updated and its hash is unchanged.
