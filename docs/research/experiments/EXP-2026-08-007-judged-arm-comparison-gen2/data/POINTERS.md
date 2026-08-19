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
the repository, so a single-file hash is not available. The digest below is
computed over each set deterministically — filenames sorted, then name and
contents concatenated — so it verifies the *set*, not one file.

Recompute with:

```bash
d=docs/evaluation/experiments/<root>/<arm>/answers
for f in $(ls "$d"/*.judgment.json | sort); do echo "$(basename $f)"; cat "$f"; done | sha256sum
```

| Artifact | Path (repo-relative) | Judgments | Bytes | SHA-256 | What it is |
|---|---|---:|---:|---|---|
| Cascade, blind | `docs/evaluation/experiments/outerjoin-holdout/deterministic/answers` | 30 | 26078 | sha256:f975b54428148d9b3143b872640e254907a13c408ade10cb69351ab6031b4549 | The 0.8367 headline and the "after" side of the paired repair delta |
| Arm H, blind | `docs/evaluation/experiments/holdout-v1-generic-outer/generic/answers` | 30 | 26215 | sha256:711d7857a7903d3579027b3543bce4a23ce82be895c1561aa5a674668909d7d1 | The 0.8483 figure — Arm H's first judged result on any bank |
| Cascade, catalogue | `docs/evaluation/experiments/outerjoin-dev/deterministic/answers` | 120 | 100722 | sha256:a931d9a442aeb72f40e2272b716d0c2deb8425edb575709aac347d34816c9639 | The 0.9839 figure and the co-authorship gap's upper term |
| Arm H, catalogue | `docs/evaluation/experiments/untruncated-generic-outer/generic/answers` | 120 | 102581 | sha256:7fe39982499ba016fa1113c802ad647cafc8ff95878aa13e506d6345330e0e34 | The 0.9692 figure and the 11-of-20 abstention-proof rate |
| Arm F gen-2, blind | `docs/evaluation/experiments/gen2-armf-holdout/gold_loop_llm/answers` | 30 | 26727 | sha256:1e2284ae39cbf1e3148a2ab761b83ce1d7cdac357acf42819e799babc0a18aa3 | The 0.9157 figure — closes EXP-2026-08-006's open item |
| Arm F gen-2, catalogue | `docs/evaluation/experiments/gen2-armf-dev/gold_loop_llm/answers` | 120 | 104906 | sha256:582e12cea7347c9f0426368623635d4d999ffccbdb58722f00a723c7acd65cbb | The 0.9852 figure and the 19-of-120 hallucination count |

**Two caveats on these digests.** They are computed *after* the four oversized
cases were recovered (ISSUES §3) and after the contaminated third pass was
quarantined (ISSUES §4), so they describe the corrected sets the results use,
not the sets as they stood mid-run. And the "before" side of the paired repair
delta lives in `docs/evaluation/experiments/holdout-v1/deterministic/answers`
as `*.judgment.local.json` sidecars, alongside the committed Sonnet judgments
it was calibrated against — the two are deliberately kept in one directory and
distinguished by suffix, never overwritten.

Regenerate hashes for committed files with:

```bash
uv run python -m utils.research_record.hashing <path>
```
