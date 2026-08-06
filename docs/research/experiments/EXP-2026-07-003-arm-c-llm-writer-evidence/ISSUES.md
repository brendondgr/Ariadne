# ISSUES — EXP-2026-07-003

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

## 2026-08-04 — The -0.196 delta is not reproducible from this arm's post-fix score

**Impact:** The figure **-0.196** for the cost of LLM planning appears in
`docs/evaluation/experiments/untruncated/root-cause.md` and was inherited by the
research audit. It was computed when this arm scored **0.9620** in an earlier
judge run (109/9/2), before the eight defect fixes.

**Cause:** Two judge runs, one delta, no statement of which run it came from.

**Resolution:** Post-fix this arm scores **0.9690** (110/8/2) and B - C is
**-0.1185**. Both numbers are faithfully recorded in the repository; they are
from different runs. This folder records the post-fix value only.

**Paper implication:** **Do not quote -0.196.** Recompute within a single judge
run before publication. The qualitative finding survives either way: with
extraction and synthesis held constant, LLM planning is still the dominant
single effect. Tracked as a `partial` claim in `../../CLAIMS.md`.
