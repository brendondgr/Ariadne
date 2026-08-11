# POINTERS — EXP-2026-08-004

Raw run output stays under `docs/evaluation/experiments/`. **No judgment files
exist for either run** — both were scored mechanically.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Blind, outer join | `docs/evaluation/experiments/holdout-v1-generic-outer/generic/` | 657289 | sha256:e24f8d9e99f169816c3727a413babecdccd9becdcf9334ec67706b49bccca862 | 30 answer files |
| Development, outer join | `docs/evaluation/experiments/untruncated-generic-outer/generic/` | 4850928 | sha256:8e15ac27a55de80ddfd4a5f813741e32f974b8464e767abad84470c50d33acfb | 120 answer files |

The inner-join runs this is compared against belong to `EXP-2026-08-001` and
`EXP-2026-08-003`; Arm F's judgments belong to `EXP-2026-08-002`. None are
duplicated here.

Directory hashes are the SHA-256 of every `*.json` under the path, concatenated
in sorted path order; the command is in [`../RESULTS.md`](../RESULTS.md) §8.
