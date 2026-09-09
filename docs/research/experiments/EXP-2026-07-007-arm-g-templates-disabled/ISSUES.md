# ISSUES — EXP-2026-07-007

## 2026-08-06 — Back-filled; provenance partially unrecoverable

**Impact:** This experiment folder was created on 2026-08-06 from a run
performed on 2026-07-26, before the research record existed. Four manifest
fields could not be recovered and are recorded as unknown rather than guessed:

| Field | Status |
|---|---|
| `code.commit` | **unknown** — no per-arm commit was captured at run time. |
| `code.dirty` | recorded `false` but **unverified** for the same reason. |
| `seeds` | **empty** — seeds were never recorded for any arm of this study. |
| `environment.lockfile` | **null** — no per-arm lock snapshot was taken. |

**Cause:** The study predates the record. Capture at write-time is exactly what
the record now exists to enforce.

**Resolution:** Not resolvable retrospectively. Any number from this arm that
reaches a paper should be re-run under the current protocol first — see
`OPEN_QUESTIONS.md`.

**Paper implication:** This arm must be reported as a **single run** (n=1) with
no seed variance. Do not present it as a mean over seeds.

## 2026-07-26 — Single-run design; no variance recoverable

**Impact:** `n_runs: 1` for every arm. Every metric is a point estimate, and the
inter-arm deltas the study reports carry no confidence interval.

**Cause:** The study was scoped as a one-pass factorial over seven
configurations; a repeated design would have multiplied both wall clock and the
840-agent judging cost.

**Resolution:** Not resolved. Recorded as an open question rather than papered
over.

**Paper implication:** No arm-to-arm delta in this study can be given a p-value
as recorded. `statistical_test` is null and must stay null until the arms are
re-run.

## 2026-07-26 — Arm G is a later run, not a cell of the original design

**Impact:** Arm G moves a fourth variable — whether the hand-written templates
exist at all — that the seven-arm 2x2x3 design held fixed.

**Resolution:** Reported in the same tables but read as a **control against Arm
F**, not as a cell of the matrix.

**Paper implication:** Do not describe the study as an eight-arm factorial.

## 2026-08-04 — Delta sign convention

**Impact:** `docs/plans/robustness/01-overnight-safe-work.md` labels this
contrast the "F - G delta (-0.357)". F - G is **+0.356834**; the figure quoted
is G - F and the letters in that label are the wrong way round.

**Resolution:** This record uses treated-minus-reference throughout, so the
template effect is **G - F = -0.3568** and the planning effect is
**B - C = -0.1185**. Both negative, both directly comparable.

## 2026-09-09 — Audit: run date unsupported; arm described with the wrong planner; artifact commit recorded

**Impact:** `date_started` / `date_completed: 2026-07-26` cannot be supported.
The artifacts and the `generic` arm code first entered git in `a509f63` on
2026-08-04 23:50 −0400 as previously untracked work (241 files per
`01-overnight-safe-work.md` Task 1; run-log Task 1 at 2026-08-04T23:52), and
no artifact carries a timestamp. The run lies between 2026-07-26 21:20 (Arm
F's commit, which introduced the shared driver) and 2026-08-04 23:50. The dates
are left as recorded because no exact date can be established. `code.commit`
now holds `a509f63`, the artifact commit — an upper bound, not the run commit.
Separately, the arm was recorded as LLM-planned; all 120 answers carry
`run_meta.planner == "gold-plan (injected)"` (see RESULTS A-1 §1).

**Cause:** The run was performed outside the committed history and its
description was inherited from the arm tables rather than read from the
harness or the artifacts.

**Resolution:** RESULTS A-1 records the bounds, the corrected description and
the supersession by EXP-2026-08-001. The manifest `purpose` was corrected in
place; PROTOCOL.md:12 is left as written.

**Paper implication:** Describe Arm G as authored-plan + generic primitives;
give its date as "between 2026-07-26 and 2026-08-04"; do not quote −0.3568 as
the cost of templates (C-003 is refuted; C-023 is the current claim).
