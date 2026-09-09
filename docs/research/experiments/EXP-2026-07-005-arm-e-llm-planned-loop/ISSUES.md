# ISSUES — EXP-2026-07-005

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

## 2026-07-26 — Reported figures come from the second loop run

**Impact:** Two directories hold Arm E artifacts. `untruncated-loop/` is the
pre-defect-fix run; the figures here come from `untruncated-loop2/`.

**Resolution:** This folder points only at `untruncated-loop2/`. The pre-fix
directory is kept for artifact-level comparison and must never be aggregated
with post-fix arms.

## 2026-09-09 — Audit: artifact commit recorded as an upper bound

**Impact:** `code.commit` now holds `3717442`, the commit that added all 240
artifact files (2026-07-26 19:34 −0400). It bounds the run from above; the run
commit itself was never captured.
**Cause:** The study predates the research record.
**Resolution:** RESULTS A-1 records the derivation.
**Paper implication:** Cite `3717442` as the artifact commit, not the run.
