# ISSUES — EXP-2026-07-006

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

## 2026-07-26 — One PARTIAL: the narrator recomputed a count

**Impact:** F-CTM-01, this arm's only non-CORRECT verdict. The narrator said
"five techniques" where the evidence held six.

**Cause:** The narrator recomputes counts rather than reading them off the
verified claims.

**Resolution:** Not resolved; recorded as open work.

**Paper implication:** The 119/120 is one arithmetic slip, not a retrieval
failure. Worth stating precisely if the arm is reported.

## 2026-09-09 — Audit: artifact commit recorded as an upper bound; planner flag in metrics.json is the env value

**Impact:** `code.commit` now holds `9e34b87`, the commit that added all 240
artifact files (2026-07-26 21:20 −0400); the run commit itself was never
captured. `data/metrics.json` `llm_posture.planner: "true"` records the env
flag the harness set, while all 120 answers ran on the injected authored plan
(`run_meta.planner == "gold-plan (injected)"`).
**Cause:** The study predates the research record; the harness overrides the
planner flag by injecting `_GoldPlanAgent` and the posture block copies the env.
**Resolution:** RESULTS A-1 records both; a note field was added to
`metrics.json`. The flag value is left so the file still mirrors the run env.
**Paper implication:** Describe Arm F as authored-plan; cite `9e34b87` as the
artifact commit, not the run; quote the A−F gap as 0.0016.
