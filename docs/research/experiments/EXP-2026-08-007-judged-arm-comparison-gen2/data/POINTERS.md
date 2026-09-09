# POINTERS — EXP-2026-08-007

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

## Committed run artifacts

These are in the repository under `docs/evaluation/overnight-2026-08-19/`, so a
plain file hash is the right check.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Run report | `docs/evaluation/overnight-2026-08-19/REPORT.md` | 10507 | sha256:6fb24d3eb5c66089bafd547f7d4a7eaf590c7c77152badb0cf23f0652d2b9431 | The generated morning report — the human-readable form of every figure here |
| Run state | `docs/evaluation/overnight-2026-08-19/state.json` | 21065 | sha256:bed814326832b21a6ba624f625fa0042b2e2133309efcdc0cf4a577438d6d993 | Per-phase status, wall time, roll-ups, and the post-run corrections |
| Roll-up metrics | `docs/evaluation/overnight-2026-08-19/metrics.json` | 4189 | sha256:709b75274c0ba5fe6c14f789822ac8c9eea5798f50af35d6b005cbb7836d1318 | Arm roll-ups and grader pass means, as the sweep emitted them |
| Calibration | `docs/evaluation/overnight-2026-08-19/calibration.json` | 5768 | sha256:675d55787882cc0ed6ed62856fd6bc94f70b8513b7140407ab5b69283330609c | Per-case local-vs-Sonnet comparison behind the r = 0.9275 figure |

## Judgment sets (local only — `docs/evaluation/experiments/` is gitignored)

These are the ~450 graded answers every number is computed from. They are not in
the repository. **Re-hashed 2026-09-09** (RESULTS A-2): the rows below are tree
hashes over each `answers/` directory as it is on 2026-09-09, computed with
`utils.research_record.hashing`, so the validator can check them. Until
2026-09-09 this table carried a different digest (sorted `*.judgment.json`
names + contents piped to `sha256sum`); those six digests still verify (audit
2026-09-09) and are preserved in A-2. Nothing has been added to these six
directories since the record was committed on 2026-08-19 12:29 — the
`.judgment.run2/.run3` passes (00:31–00:44) and the four `.judgment.error.txt`
files were all written during the run.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Cascade, blind | `docs/evaluation/experiments/outerjoin-holdout/deterministic/answers` | 721089 | sha256:1af3a518d4ee77e2da58ddfb6efbcb8fa39537164c245be5b3599cab006dbfeb | 30 answers (2026-08-18 15:43, EXP-2026-08-006's run) + 30 `.judgment.json` (pass E1, the 0.8367 headline and the "after" side of the paired repair delta) + 30 `.judgment.run2.json` (E2a, 0.8417) + 30 `.judgment.run3.json` (E2b, 0.8400) |
| Arm H, blind | `docs/evaluation/experiments/holdout-v1-generic-outer/generic/answers` | 676557 | sha256:d97c1d3d67313db7326980a0caf569ad9b91115250dbe8855078bbc368f3af6c | 30 answers (2026-08-10) + 30 `.judgment.json` + 1 `.judgment.error.txt` (H-SW-02 first attempt, ISSUES §3). The 0.8483 figure |
| Cascade, catalogue | `docs/evaluation/experiments/outerjoin-dev/deterministic/answers` | 3389243 | sha256:4370c6296a5bb0545a8aec8722331b4c8066a9541e5a5e968b30efc60198dcae | 120 answers + 120 `.judgment.json`. The 0.9839 figure and the co-authorship gap's upper term |
| Arm H, catalogue | `docs/evaluation/experiments/untruncated-generic-outer/generic/answers` | 4928605 | sha256:dc4b659bc5ecdac43b4a3f57ebf2725efdc6ac0a02d05e942a899e12524fa41c | 120 answers + 120 `.judgment.json` + 1 `.judgment.error.txt`. The 0.9692 figure and the 11-of-20 abstention-proof rate |
| Arm F gen-2, blind | `docs/evaluation/experiments/gen2-armf-holdout/gold_loop_llm/answers` | 755155 | sha256:84725efd1535bc99ba5a81d747de1d6ba4911a9d50591fd2ab67f65b56c07704 | 30 answers (2026-08-19 01:23–01:29) + 30 `.judgment.json`. The 0.9157 figure |
| Arm F gen-2, catalogue | `docs/evaluation/experiments/gen2-armf-dev/gold_loop_llm/answers` | 3664124 | sha256:8f182b5c5839ab9c782f7aa3efda893d33f2c2d5227e7c3a0e29907c725d0f4f | 120 answers + 120 `.judgment.json` + 2 `.judgment.error.txt`. The 0.9852 figure and the 19-of-120 hallucination count |
| Cascade, blind, **before** the repair (paired delta and calibration) | `docs/evaluation/experiments/holdout-v1/deterministic/answers` | 457952 | sha256:1a6c09120864d64751e538c7bb346b4cfa7f36b16b34f0c3180f1190142603ca | 30 pre-fix answers (2026-08-09) + 30 `.judgment.json` (the committed Sonnet judgments, EXP-2026-08-002) + 30 `.judgment.local.json` (**overwritten 2026-08-31 by EXP-2026-08-021's `qwen38-27B-v2` regrade — no longer this experiment's data**) + 30 `.judgment.local.pre-qwen38.json` (**the E0 calibration pass this experiment used**, copied aside 2026-08-31 11:03 before the overwrite). See ISSUES §9 |

**The "before" side of the paired repair delta and the calibration** (0.7200,
+0.1167 with CI 0.0333–0.2167, 10/3/17, r = 0.9275, mean delta +0.031,
agreement 0.70) reproduce from the 30 `*.judgment.local.pre-qwen38.json`
files only. Their set hash, computed with
`utils.research_record.hashing.sha256_tree(root, "*.judgment.local.pre-qwen38.json")`
(30 files, 26542 bytes), is
`sha256:639dbf46593b846d3527580caa9cb5336e212f5dccbb0954acd1ff23f0267b36`.
The current `*.judgment.local.json` set (30 files, 24830 bytes,
`sha256:28346f56b6ec1c2ea37b0a77a93954bd3ad4a138987a6fa8dff915a160ddafa1`)
gives 0.7100 / +0.1267 / 13-6-11 / r = 0.9612 and is **not** what this
experiment reported. The committed
`docs/evaluation/overnight-2026-08-19/calibration.json` independently records
r = 0.9275 and local mean 0.72.

**One caveat on the six digests.** They describe the sets *after* the four
oversized cases were recovered (ISSUES §3) and after the contaminated third pass
was quarantined (ISSUES §4), i.e. the corrected sets the results use, not the
sets as they stood mid-run.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
