# ISSUES — EXP-2026-07-002

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

## 2026-08-04 — Coverage cell previously reported a pre-fix figure

**Impact:** Arm B's answer coverage previously read **0.7989**, a pre-fix
`untruncated/` figure.

**Resolution:** Recomputed post-fix as **0.8074**, which is what this folder
records.

**Paper implication:** Quote 0.8074, and name the run.

## 2026-07-26 — 6 of 120 questions finish `partial` on the deadline

**Impact:** Pipeline timeouts, not accuracy failures, account for part of this
arm's loss.

**Resolution:** Not resolved; recorded as open work.

**Paper implication:** The LLM-planned deficit is partly a latency artifact and
should not be attributed wholly to planning quality.

## 2026-09-09 — Audit: two prose counts do not reproduce; artifact commit recorded as an upper bound

**Impact:** The entry above dated 2026-07-26 ("6 of 120 questions finish
`partial`") is wrong on its count: the answer files carry **10**
`run_meta.status == "partial"` cases and `failure_terminus` classes **4** as
`pipeline_timeout`; no reading gives 6. RESULTS §6's "19 of 36" is on the
stale 36 denominator (A-1 corrected it to 28) and has no recomputable basis in
the artifacts. `code.commit` now holds `07e4de4`, the commit at which all 240
artifact files were first on record; the run commit itself is unknown.

**Cause:** Counts quoted from an earlier judge run or from notes, not from the
committed artifacts; no per-arm commit captured.

**Resolution:** RESULTS A-2 records the reproducible counts (10 / 4) and
retires the 19. The entries above are left as written.

**Paper implication:** Quote 10 partial-status answers and 4 timeout termini.
Never quote "19 of 36". Cite `07e4de4` as the artifact commit, not the run.
