# RESULTS — EXP-2026-09-012 — grader repeatability, from passes already on disk

**Analysed 2026-09-07.** No new judgment was made. Every figure comes from
sidecars that already existed.

---

## Headline

**Re-grading the same frozen answers with the same grader family moves the
reported mean by a median of 0.0066 and up to 0.0242.** Across **22 cells and
117 grading passes**, that variance has never been reported by this project.

Every judged figure here carries a bootstrap interval **over questions**. None
carries one **over grading passes**. A reader assumes the second is negligible.
On the worst cell it is a quarter of the effect the paper's §6 reports.

| | SD across passes |
|---|---|
| minimum | 0.0021 |
| **median** | **0.0066** |
| mean | 0.0093 |
| maximum | **0.0242** |

## By arm — and the ordering is not incidental

| arm | cells | mean SD | max |
|---|---|---|---|
| `llm_query` | 2 | **0.0218** | 0.0234 |
| `merged` | 4 | 0.0151 | 0.0242 |
| `gold_loop_llm` | 2 | 0.0075 | 0.0090 |
| `deterministic` | 7 | 0.0073 | 0.0156 |
| `generic` | 3 | 0.0053 | 0.0084 |
| `generic_composed` | 4 | 0.0047 | 0.0072 |

**The arm with a model in the query path is the least repeatably gradeable**, at
roughly four times `generic_composed`. A plausible reading is that its answers
sit in a quality band where the grader is least decisive — consistent with
`EXP-2026-09-008`, where resolution collapsed on a homogeneous population — but
this experiment cannot establish that and does not claim it.

## Why it matters for what is already published

`C-012`'s holdout margin is **0.0822**. Grader repeatability on `llm_query`
cells is **~0.02**. A single grading pass therefore carries a fifth to a quarter
of that margin as unmodelled noise, on top of the question-sampling interval the
paper does report.

This does **not** overturn the result: `EXP-2026-09-007` graded every cell twice
by position and `EXP-2026-09-006` re-graded across families, so the published
figures are already averages rather than single passes. What it means is that
**the reported interval is narrower than the total uncertainty**, and the paper
should say so.

## What this cannot support

- **Not a correction.** Knowing a pass carries ±0.02 does not say which way any
  particular published pass erred.
- **Not one project-wide number.** The cells differ by population, arm and date;
  the variation between them is the finding.
- **Not generation variance.** These are re-gradings of **frozen answers**.
  `EXP-2026-09-010` and `-011` cover the generation side.
- **An upper bound, not an estimate.** Passes within a family differ in grading
  position, and that effect is measured at ~0.01 three separate times
  (`EXP-2026-08-022`, `-09-009`, `-09-011`). Each SD here **includes** it.

## Two method notes

**The audit read a quarantine bin.** Thirty sidecars under
`outerjoin-holdout/deterministic/_contaminated_run3/` are judgments of
judgments — the failure mode `ariadne-judge-pass-contamination` names. They were
**already found and quarantined by an earlier session**; the defect was that this
audit read them, not that they exist. Included, they inflated one cell to
**0.0774** against a 0.0066 median. Excluded by path and by double suffix.

**142 of 218 computed cells appear in no manifest.** Most are legitimately
intermediate — repeat passes, spot checks after a fix. The number is reported
rather than resolved, because deciding which intermediates deserve a metric is a
judgement this analysis is not entitled to make on its own.

## The recommendation

The paper should state that its intervals cover question sampling and not grader
re-run variance, and quote **0.0066 median / 0.0242 max** as the scale of what is
uncovered. That is cheaper and more honest than widening every interval on an
estimate this coarse.

---

## AMENDMENT A-1 (2026-09-09) — record repair: the manifest was a scaffold with results bolted on

**What was wrong.** `manifest.yaml` carried `status: complete` with
`date_completed: null`, `authors: []`, template prose in `purpose` and
`hypothesis`, `code.entrypoint: "<exact command>"`, `data.*` placeholders with
`n_examples: 0`, `compute.hardware: "<cpu/gpu, ram>"` with
`wall_clock_hours: 0.0`, and a full `llm:` block of placeholders although no
model was in the loop (the template says to delete the block in that case).
`data/POINTERS.md` was the empty template, `data/metrics.json` did not exist,
and `ISSUES.md` was empty although `code.dirty: true` and `seeds: []` /
`n_runs: 1` need saying.

**What is now recorded (old → new), and how each was established.**

| field | was | is | established from |
|---|---|---|---|
| `date_completed` | `null` | `2026-09-07` | `data/recompute-audit.json` mtime 02:53:59; the directory was created and completed in one commit, `b3e4bf5` 02:54 |
| `authors` | `[]` | `[brendondgr]` | git author of `b3e4bf5` |
| `purpose` | template text | filled from PROTOCOL.md §The question / §Method | PROTOCOL.md |
| `hypothesis` | template text | `exploratory — no prior hypothesis`, with the pre-committed aggregation rules named | PROTOCOL.md's own statement that pre-registration does not apply |
| `code.entrypoint` | `<exact command>` | `scripts/recompute_audit.py --json data/recompute-audit.json` for the cell means; the 22-cell aggregation's code is not on record (ISSUES.md) | the script's docstring; no committed script produces the RESULTS table |
| `data.*` | placeholders, `n_examples: 0` | the sidecar tree as of 2026-09-07 02:53 (218 cells, 30 quarantined); 22 cells analysed; `hash: null` because the tree has since changed (A-3) | `data/recompute-audit.json`; PROTOCOL §Method |
| `compute.hardware` | placeholder | `cpu only, local workstation; no model in the loop` | the design |
| `compute.wall_clock_hours` | `0.0` | `null` | not recorded; the two audit JSONs are 79 s apart |
| `llm:` block | placeholders | **deleted** | no model was run; every judgment analysed belongs to another experiment |
| `metrics.values.grading_passes_recomputed_2026_09_09` | absent | `115` | A-2 |
| `metrics.values.sd_deterministic_recomputed_2026_09_09` | absent | `0.0068` | A-2 |
| `related` | `[]` | `[EXP-2026-08-022, EXP-2026-09-007, -008, -009, -010, -011]` | the experiments this RESULTS quotes |

**Pointers.** `data/POINTERS.md` now points at the input — the
`docs/evaluation/experiments` tree — hashed as it stands on 2026-09-09, with
a statement of how that tree differs from the one read on 2026-09-07 (A-3).
**Metrics file.** `data/metrics.json` created with every `metrics.values`
entry, the canonical audit file named, and the 2026-09-09 re-aggregation
(A-2) recorded beside the manifest's figures.

## AMENDMENT A-2 (2026-09-09) — the family-grouping rule as written does not produce the table; the rule that does, and two figures it does not reproduce

PROTOCOL.md §Method (lines 39–41) assigns grader families by suffix —
`g31`/`gem` → gemma, `cross` → cross-model, `qw`/`q`/`pass2`/unsuffixed →
qwen — and says "a suffix matching none is reported under its own name".
Applied literally to `data/recompute-audit.json`, the suffixes `.c015`,
`.c022rev1`, `.c022rev2` and `.bld1`, `.bld2`, `.bld3`, `.bldrev` are each a
singleton family, no such cell reaches three passes, and the result is **16
cells / 93 passes, median 0.0084, and no 0.0242 cell**. The recorded table
(22 cells, median 0.0066, min 0.0021, max 0.0242) is reproduced only when
**`.c015` / `.c022rev*` are pooled as one family and `.bld*` as another** —
a rule that was applied but not written down. Under that rule the 2026-09-09
recomputation (`r012d.py`, verify-b6; also `data/metrics.json`) gives:

| | recorded | recomputed 2026-09-09 |
|---|---|---|
| cells with ≥ 3 passes | 22 | 22 |
| grading passes | **117** | **115** |
| median SD | 0.0066 | 0.0066 |
| mean SD | 0.0093 | 0.0092 |
| min / max SD | 0.0021 / 0.0242 | 0.0021 / 0.0242 |
| `llm_query` cells / mean / max | 2 / 0.0218 / 0.0234 | 2 / 0.0219 / 0.0234 |
| `merged` | 4 / 0.0151 / 0.0242 | 4 / 0.0152 / 0.0242 |
| `gold_loop_llm` | 2 / 0.0075 / 0.0090 | 2 / 0.0075 / 0.0090 |
| `deterministic` | 7 / **0.0073** / 0.0156 | 7 / **0.0068** / 0.0156 |
| `generic` | 3 / 0.0053 / 0.0084 | 3 / 0.0053 / 0.0084 |
| `generic_composed` | 4 / 0.0047 / 0.0072 | 4 / 0.0047 / 0.0072 |

Every headline figure and every per-arm max reproduces; the differences
(mean 0.0093 vs 0.0092; `merged`/`llm_query` means by 0.0001) are rounding.
Two do not: **117 vs 115 passes** and the **`deterministic` arm mean 0.0073
vs 0.0068**. The most likely explanation is that one `deterministic` cell had
two more passes on 2026-09-07 than the stored audit JSON carries — the
aggregation was run in-session and its code was not committed — but that
cannot be established from the stored file. The recorded values stand as
written; the recomputed ones are added to the manifest under
`grading_passes_recomputed_2026_09_09` and
`sd_deterministic_recomputed_2026_09_09`, and the gap is logged in ISSUES.md.
Neither affects the recommendation (0.0066 median / 0.0242 max), which
reproduces exactly.

## AMENDMENT A-3 (2026-09-09) — two audit files, which one is canonical, and how the input tree has moved since

`data/` holds two near-identical outputs of `scripts/recompute_audit.py`.
**`recompute-audit.json`** (02:53:59) is canonical: 218 cells, 142 absent from
every manifest, matching the manifest's `cells_recomputed_total` and
`cells_absent_from_manifests`. **`2026-09-07-recompute-audit.json`** (02:52:40)
is the earlier copy and still contains one cell the method excludes —
`outerjoin-holdout / deterministic / .run2.judgment.run3`, n=30, mean 0.6767,
a judgment-of-a-judgment from the quarantine bin described in §"Two method
notes" — giving 219 cells / 143 unmatched. Nothing in either file said which
was which; this amendment and `data/metrics.json` (`canonical_audit_file`) now
do. The earlier copy is kept as the record of the defect it exposed.

The stored audit is also a **dated snapshot**. EXP-2026-09-011's extension
grading (2026-09-07 10:15–13:00) added 1,704 sidecars under
`seeded-repeats-generic-2026-09-06`, so an independent re-walk of the tree on
2026-09-09 (`r012.py`, verify-b6) reproduces 215 of the 218 (n, mean) pairs
exactly and differs on three: the two `seeded-repeats-generic .q1` / `.q2`
cells now hold 1,704 judgments where the audit saw 852, and
`untruncated-generic-outer (none)` reads 0.9692 vs 0.9693 (float rounding).
`data/POINTERS.md` hashes the tree as of 2026-09-09 and says so.
