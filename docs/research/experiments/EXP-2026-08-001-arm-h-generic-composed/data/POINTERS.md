# POINTERS — EXP-2026-08-001

Raw run output — one answer file per question — stays under
`docs/evaluation/experiments/`. It is not copied here: `docs/research/` must
stay cloneable in seconds.

There are **no judgment files**. This arm was scored mechanically from the
answer artifacts alone; see `RESULTS.md` §1 and `ISSUES.md`.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Arm artifacts | `docs/evaluation/experiments/untruncated-generic-fixed/generic/` | 4806684 | sha256:8170724a59b2b4aa76313bf312c1fe299d6023c71befe3c4fb6e0085a5d68b27 | 120 answer files (answer + full retrieved evidence + executed queries + per-stage traces) |
| Reference arm | `docs/evaluation/experiments/untruncated-generic/generic/` | 4878680 | sha256:de75c852934ff7b0b9db827bb1cd6c38cf22a1357bc161fc05fd24d96aac1ed9 | Arm G's artifacts, the paired baseline every delta here is computed against |

Each directory hash is the SHA-256 of every `*.json` under that path,
concatenated in sorted path order. The command that reproduces it is in
[`../RESULTS.md`](../RESULTS.md) §8, kept there rather than here so this file
stays a pure artifact manifest.
