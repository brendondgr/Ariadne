# ISSUES — EXP-2026-07-001

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

## 2026-07-26 — 120/120 splices two judge runs

**Impact:** Arm A's verdict count combines 118 verdicts from the pre-scan-fix
judge run with 2 re-judged cases.

**Cause:** A scan-related fix landed mid-study; re-judging all 120 was avoided.

**Resolution:** Justified only because the other 118 artifacts were verified
materially identical between the runs. Recorded here so the splice is visible.

**Paper implication:** State that Arm A's verdicts are not from a single judge
pass if the 120/120 figure is reported.

## 2026-08-04 — Cost row previously reported pre-fix figures

**Impact:** The Arm A cost row previously read **2.6 s / 1,840 records**. Those
are the *pre-fix* `untruncated/` figures, spliced next to post-fix correctness.

**Cause:** Two runs of the same arm, mixed in one table.

**Resolution:** Recomputed from the committed post-fix artifacts: **1.6 s /
1,061 records**. This folder records the post-fix values. Related-neighbour
count (839) and coverage (1.0000) are identical across both runs.

**Paper implication:** Never mix rows across the pre- and post-fix runs.

## 2026-09-09 — Audit: artifact commit recorded as an upper bound; judge-run splice unverifiable

**Impact:** `code.commit` now holds `33e38ac`, the commit that added all 240
artifact files (2026-07-26 14:31 −0400). It bounds the run from above; the
commit the harness actually ran at was never captured and remains unknown.
The 118 + 2 splice recorded above (2026-07-26) cannot be confirmed: every
judgment file arrived in that single commit and none was changed later, so
git shows one judge pass, not two.

**Cause:** The study predates the research record; no per-arm commit or judge-run
identifier was written into the artifacts.

**Resolution:** Not resolvable retrospectively. RESULTS A-1 records what was
established and how.

**Paper implication:** Cite the artifact commit, never a run commit. Keep the
"not from a single judge pass" caveat: the record cannot prove it either way.
