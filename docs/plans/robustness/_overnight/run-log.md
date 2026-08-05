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

Commit `1f98e1a`.

### Task 5 — Arm G in both arm tables — 2026-08-05T00:20

Added the Arm G row to the results and cost tables in
`docs/evaluation/2026-07-26/README.md`, a *two deltas side by side* block
(G − F = −0.3568 against B − C = −0.1185, both treated-minus-reference so they
compare directly — losing the templates costs 3.0× what LLM planning costs), and
a paragraph stating precisely what Arm G is and is not.

`docs/evaluation/experiments/README.md`'s code→letter map gained **D** and **G**
and a Directory column, because the letter is not a function of the `--arm` code
alone: C and D both run `gold_llm` and differ only by directory.

Deliberately *not* done: rewriting "seven-arm study" across six documents. Arm G
was run later and moves a variable the original matrix held fixed, so it is
reported as an eighth run beside the study rather than folded into it. That is a
framing call and the plan is decision-free; the narrower phrasing avoids it.

Commit `feb9298`.

### Task 6 — Arm A cost correction — 2026-08-05T00:35

`README.md`, `docs/evaluation/2026-07-26/README.md` (×2), `docs/pitch/checkin-pitch.md`
and `docs/research/audit-2026-08-03.md` (×2). The audit is dated, so both
figures stay in place there with dated correction notes beside them.

Arithmetic, recomputed rather than trusted:

```
pre-fix   1,019.7 / 2.6 = 392.19   -> the recorded 392x
post-fix  1,019.7 / 1.6 = 637.31   -> 637x
Arm F       533.4 / 1.6 = 333.37   -> 333x
```

One figure moved beyond the plan's list, recorded as **Q7**: Arm B's coverage
cell was 0.7989, the pre-fix value; post-fix is 0.8074. Arm E's blank coverage
cell is 0.8819.

Commit `a38f424`.

### Task 7 — Template count — 2026-08-05T00:50

`_overnight/derive_templates.py` AST-parses both builders and scans the banks.
Result: **25 distinct template identifiers, of which 19 are exercised by the
120-question bank** (17 Cypher + 11 Gremlin, with `describe`,
`describe_by_name` and `expand` declared in both — which is where every wrong
total came from). Written to `numbers.json` under `templates`; all four markdown
locations updated to state it identically. The fifth location is a docstring and
is Task 8.

Commit `f87d145`.

### Task 8 — Builder docstrings — 2026-08-05T01:05

Docstrings and comments only, verified by parsing both files before and after,
stripping every docstring, and comparing `ast.dump()` — identical trees.
Dead-code markers added above `_node_lookup` and `_capec_lookup` without
deleting either.

Test suite, `ORCH_MAX_HOPS=5 pytest -q`, same invocation both times:

| | failed | passed | skipped |
|---|---|---|---|
| before | 4 | 1308 | 213 |
| after | 4 | 1308 | 213 |

Same four tests both times, none related: two `utils/conversation` graph-order
tests and one setup-wizard test that assert LLM-off behaviour while a local
inference server is reachable on `localhost:4000`, and one evaluation test
needing the live graph subset.

Commit `3e3ebab`.

### Task 9 — `.env.example` — 2026-08-05T01:20

`ORCH_MAX_HOPS` added as a live key set to 1 (**Q8** — that is a shipping-default
decision, and the comment beside it documents both values);
`EVAL_LLM_MAX_TOKENS` aligned 1024 → 32000 with the reasoning-model explanation;
the pipeline comment replaced with the real graph including the
`bundle → assess → (synthesize | replan → specialists)` cycle and the two
caveats — inert at `max_hops=1`, and `ORCH_ASSESS_MODE=llm` degrading because
nothing injects a critic. No code default changed.

Full suite re-run: 4 failed, 1308 passed, 213 skipped — unchanged. The new key
did expose a latent test-isolation bug, recorded as **Q9** and filed as a
follow-up rather than fixed here.

Commit `fa26268`.

### Task 10 — Model identity — 2026-08-05T01:35

`docs/evaluation/README.md` records `skynet` = **Gemma 4 31B**, with
quantisation and served context window written as **unknown** (**Q3**, **Q4**)
and all three prior window figures listed side by side with the distinction that
reconciles them: a client-side `num_ctx` request is not a served
`max_model_len`. `.env` was **not** modified — prohibited, and gitignored
operator state.

Commit `974e85a`.

### Task 11 — Freeze tag — 2026-08-05T01:40

```
git tag -a freeze/holdout-v1 -m "Frozen for the blind holdout. Templates and planner immutable from this point."
```

**`freeze/holdout-v1` → `974e85a494f020e218e8b73f193543c11ea0d292`**

`git describe --exact-match HEAD` confirmed `freeze/holdout-v1` at the time of
tagging. The SHA is written into
`docs/plans/robustness/02-holdout-question-generation.md` §2 and
`docs/plans/branch-a-publication-readiness-plan.md` Step 1.

The tag necessarily precedes those two edits and this log entry — a commit
cannot contain its own SHA. What the tag freezes is the code and the evaluation
record, which is what the holdout is measured against; the audit trail after it
is documentation only.
