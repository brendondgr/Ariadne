# POINTERS — EXP-2026-08-008

Large artifacts live outside `docs/research/`. **Every entry needs a hash.**

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| REPORT.md | `docs/evaluation/measure-2026-08-19/REPORT.md` | 6423 | sha256:cd94473bec1a6483ea119d45fc6582bd300730d22a28bda8d905483cd4c2efc3 | measurement REPORT |
| state.json | `docs/evaluation/measure-2026-08-19/state.json` | 19298 | sha256:6b4add36c6ef4d87fe99ac80c38e981f7d03147f7db931a163c846872f452d85 | measurement state |
| metrics.json | `docs/evaluation/measure-2026-08-19/metrics.json` | 9471 | sha256:4eb37e01f28ce01af6ecfacd2df3961b1cf5345567475fd34aa4a4ba618e93be | measurement metrics |

Judgment sets live under `docs/evaluation/experiments/` (gitignored). Digest a
set with:

```bash
d=docs/evaluation/experiments/<root>/<arm>/answers
for f in $(ls "$d"/*.judgment.json | sort); do echo "$(basename $f)"; cat "$f"; done | sha256sum
```
| bank20260819/deterministic | `docs/evaluation/experiments/bank20260819/deterministic/answers` | 30 judgments | sha256:ab6126f1eb3da68e3d397d426b2ac571070fdc64e7726f5a985c0b3ead9a755b |
| bank20260819/generic | `docs/evaluation/experiments/bank20260819/generic/answers` | 30 judgments | sha256:7a03a81822ea2d354efb3e4638d28380de19cf5adf6dc87d9591411f1a2f35e9 |
| bank20260819/gold_loop_llm | `docs/evaluation/experiments/bank20260819/gold_loop_llm/answers` | 30 judgments | sha256:c744c418997522ea7302fa4d3e1adf8137aba87861941651ab1a42da47743568 |
| bank20260819/llm_query | `docs/evaluation/experiments/bank20260819/llm_query/answers` | 30 judgments | sha256:668b5bb1f336d754db1ceea9fd2b7db69aaea75b966cf2c9b0c10b19ba057cc4 |
| composerfix-holdout/deterministic | `docs/evaluation/experiments/composerfix-holdout/deterministic/answers` | 30 judgments | sha256:8ff28c96ba0a073e41d17b55c42dc90c55eef29028578db1655948daa16ed67f |
| composerfix-dev/deterministic | `docs/evaluation/experiments/composerfix-dev/deterministic/answers` | 119 judgments | sha256:ee50b56db0ad317731ae250fba2beabe39bc24df73ff635e97257b30fafbdb13 |
