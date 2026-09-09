# POINTERS — EXP-2026-08-008

Large artifacts live outside `docs/research/`. **Every entry needs a hash.**

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| REPORT.md | `docs/evaluation/measure-2026-08-19/REPORT.md` | 6423 | sha256:cd94473bec1a6483ea119d45fc6582bd300730d22a28bda8d905483cd4c2efc3 | measurement REPORT |
| state.json | `docs/evaluation/measure-2026-08-19/state.json` | 19298 | sha256:6b4add36c6ef4d87fe99ac80c38e981f7d03147f7db931a163c846872f452d85 | measurement state |
| metrics.json | `docs/evaluation/measure-2026-08-19/metrics.json` | 9471 | sha256:4eb37e01f28ce01af6ecfacd2df3961b1cf5345567475fd34aa4a4ba618e93be | measurement metrics |

Judgment sets live under `docs/evaluation/experiments/` (gitignored).
**Re-hashed 2026-09-09** (RESULTS A-1): the rows below are tree hashes over each
`answers/` directory as it is on 2026-09-09, computed with
`utils.research_record.hashing`. Until 2026-09-09 they carried set digests over
`*.judgment.json` only (`for f in $(ls "$d"/*.judgment.json | sort); do echo
"$(basename $f)"; cat "$f"; done | sha256sum`); those six digests still verify
(audit 2026-09-09) and are preserved in A-1. Every one of these directories has
since gained grader sidecars from later experiments — listed per row — while
the answer files and the `.judgment.json` sidecars this experiment's numbers
come from are unchanged (mtimes 2026-08-19 19:30–20:25).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| bank20260819/deterministic | `docs/evaluation/experiments/bank20260819/deterministic/answers` | 828548 | sha256:e034f420eb44ffe349146654dae18ce0e172b4e99aa7eff9dbddf9a909323d35 | 30 answers + 30 `.judgment.json` (the 0.9467 cell). Added later: `.cross` (2026-08-20), `.c015` (EXP-2026-08-009), `.qwen38`/`r2`–`r5` (EXP-2026-08-021), `.bld1`–`3`/`.bldrev` (EXP-2026-08-022), `.g31`/`.g31p2` (2026-09-05) |
| bank20260819/generic | `docs/evaluation/experiments/bank20260819/generic/answers` | 853113 | sha256:0219150fb82b5233e0425e5d4ab4279cc47ae5bafa533f95cd3498615b1a0d73 | 30 answers + 30 `.judgment.json` (0.9700). Added later: `.cross` (29 + 1 error), `.c015`, `.qwen38*`, `.g31*` |
| bank20260819/gold_loop_llm | `docs/evaluation/experiments/bank20260819/gold_loop_llm/answers` | 750191 | sha256:d88e7df454711e8a75a4830c98c708dee068fa3647e1df8712558715da7b7302 | 30 answers + 30 `.judgment.json` (0.9773). Added later: `.cross`, `.qwen38*`, `.g31*` |
| bank20260819/llm_query | `docs/evaluation/experiments/bank20260819/llm_query/answers` | 419976 | sha256:4034e67964f33bbdbd99f4b85874ff82fbff13e48527d4a1b9722241f78b806a | 30 answers + 30 `.judgment.json` (0.5000 / 0.5739 and the 19/7/3/1 failure split). Added later: `.cross` (27 + 3 errors), `.qwen38*`, `.g31*` |
| composerfix-holdout/deterministic | `docs/evaluation/experiments/composerfix-holdout/deterministic/answers` | 784141 | sha256:86490c6e63cab7fb27dbc515f5f82666f25d4acb6da24e4c8b02ac941570eaf6 | 30 post-fix holdout-v1 answers + 30 `.judgment.json` (the 0.9350 "after" side of the +0.0983 paired delta). Added later: `.g31*`, `.q38b`/`.q38bp2` (2026-09-05) |
| composerfix-dev/deterministic | `docs/evaluation/experiments/composerfix-dev/deterministic/answers` | 3845977 | sha256:d15b78a1b1c2e55cd5311f062c8f34742a954fb5cb5db91c143b9a01175766a2 | 120 post-fix catalogue answers + 119 `.judgment.json` + 1 `.judgment.error.txt` (C-SCN-01, ISSUES §4) — the 0.9833 cell and the 0.0483 gap. Added later: `.g31*` (120 + 1 error), `.q38b*` (2026-09-05) |

The "before" side of the paired composer-fix delta (0.8367) is
EXP-2026-08-007's pass E1 over
`docs/evaluation/experiments/outerjoin-holdout/deterministic/answers`, hashed in
that experiment's POINTERS.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
