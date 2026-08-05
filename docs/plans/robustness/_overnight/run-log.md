# Overnight run log — Plan 01

What was done, in order, with timestamps. Written as the run proceeded.

## Starting state

- **Timestamp:** 2026-08-04T23:48:47-04:00
- **Starting commit:** `45ac6e53556e47b0085e2189b0e0dcebb77c49ed`
  (`Documentation Accuracy Purge (7/7): docs-accuracy regression test`)
- **Branch:** `claude/robustness-overnight-safe-work-a20faf`, a worktree branch
  created from `main` at the same SHA.

`git status --short` in the primary checkout (`/home/bdgr/Agents/Ariadne`) at
start:

```
 M .gitignore
 M utils/evaluation/experiment_untruncated.py
 M utils/specialists/cypher/builder.py
 M utils/specialists/cypher/normalizer.py
 M utils/specialists/gremlin/builder.py
?? docs/pitch/
?? docs/plans/branch-a-publication-readiness-plan.md
?? docs/plans/robustness/
```

### Note on where the work happened

The uncommitted Arm G work lived in the **primary checkout**, not in the
worktree this session was given. The four modified files and the four untracked
paths were copied into the worktree verbatim and the diff was verified identical
to the primary checkout's, hunk for hunk, before anything was committed:

```
diff <(grep -v '^diff --git a/.gitignore' main.diff) worktree.diff   # empty
```

The one deliberate exception is the `.gitignore` hunk, which is recorded as
**Q1** in `questions.md` and was not carried across. See that entry for why.

Two of the untracked paths — `docs/plans/robustness/` (this plan) and
`docs/plans/branch-a-publication-readiness-plan.md` (its parent) — are not
mentioned by any task, but Task 11 writes into both and §2 requires
`_overnight/` to be committed, so they are committed alongside the Task 1 work.

---

## Task log

### Setup — 2026-08-04T23:48

Created `docs/plans/robustness/_overnight/` with `run-log.md` and
`questions.md`. Starting SHA and status recorded above. `numbers.json` is
written by Task 4 and `verification.md` by Task 12, so neither is created empty
here.

Committed as `Overnight (0/12)` — `ed9ce8d`.

Baseline test suite started in the background before any file was touched, run
as `ORCH_MAX_HOPS=5 .venv/bin/python -m pytest -q` (the repository `.env` pins
`ORCH_MAX_HOPS=1`, under which one orchestration event-order test fails for
reasons unrelated to anything here). Result recorded under Task 8.

### Task 1 — Commit the untracked Arm G work — 2026-08-04T23:52

Verified before committing:
`docs/evaluation/experiments/untruncated-generic/generic/` holds 120
`answers/*.json`, 120 `answers/*.judgment.json` and a `manifest.json` reporting
`count: 120`, `ok: 120`, `wall_s: 914.8` — 241 files, matching the plan.

Committed 245 files: the four modified Python files exactly as found (no edits)
plus the 241 artifacts. Two deviations recorded in `questions.md` rather than
resolved: **Q1** (an uncommitted `.gitignore` hunk that would have hidden the
artifacts — not committed) and **Q2** (`cypher/normalizer.py` is a fourth
modified file the plan did not list — committed, with reasoning).

Commit `a509f63`.

### Task 2 — Track docs/pitch/ — 2026-08-04T23:54

One file, `docs/pitch/checkin-pitch.md`, 278 lines, committed verbatim.
Commit `a9e514f`.

### Task 3 — MITRE attribution NOTICE — 2026-08-04T23:58

Retrieved both terms pages live and used them verbatim, so no `TODO` marker was
needed:

- `https://attack.mitre.org/resources/legal-and-branding/terms-of-use/`
- `https://capec.mitre.org/about/termsofuse.html`

Dataset versions and SHA256 values read from `data/versions.json`
(ATT&CK 19.0, 52,680,865 bytes; CAPEC 3.9, 3,849,998 bytes; snapshot
2026-07-23); source URLs read from `utils/download/downloader.py:25-37`.
`README.md` gains a *Data attribution* section and a Documentation-table row.

Confirmed no `LICENSE` file exists and no `license` field was added to
`pyproject.toml` or `web/package.json`. Commit `7cbc7c0`.

### Task 4 — Recompute every arm figure — 2026-08-05T00:05

Wrote `_overnight/recompute.py` and ran it over every arm directory under
`docs/evaluation/experiments/*/`; output is `_overnight/numbers.json`. No figure
was carried in from prose. All seven of the plan's sanity-check values
reproduce:

| Arm | Directory | Plan expects | Recomputed |
|---|---|---|---|
| A | `untruncated-fixed/deterministic` | 0.9972, 1.6 s, 1,061 | 0.997250, 1.6 s, 1,061 |
| F | `untruncated-goldloop/gold_loop_llm` | 0.9957 | 0.995667 |
| D | `untruncated-claimnarr/gold_llm` | 0.9917 | 0.991667 |
| C | `untruncated-fixed/gold_llm` | 0.9690 | 0.969000 |
| E | `untruncated-loop2/llm_loop` | 0.8560 | 0.856000 |
| B | `untruncated-fixed/llm` | 0.8505 | 0.850500 |
| G | `untruncated-generic/generic` | 0.6388, 64/14/42 | 0.638833, 64/14/42 |

`untruncated/` and `untruncated-loop/` are in a separate `superseded` block.
Two further arms (`untruncated-claimnarr/deterministic`,
`untruncated-claimnarr2/gold_llm`) carry answers but no judgments and so report
`n: 0` with null means, matching the existing index's note that they were
superseded before judging.

One labelling discrepancy, recorded as **Q6**: the plan's "F − G delta (−0.357)"
is signed as G − F. F − G is +0.356834.

Commit pending below.
