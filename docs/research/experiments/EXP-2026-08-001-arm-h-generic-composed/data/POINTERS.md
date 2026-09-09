# POINTERS — EXP-2026-08-001

Raw run output — one answer file per question — stays under
`docs/evaluation/experiments/`. It is not copied here: `docs/research/` must
stay cloneable in seconds.

There are **no judgment files** in the Arm H directory, and there still were
none on 2026-09-09. This arm was scored mechanically from the answer artifacts
alone; see `RESULTS.md` §1 and `ISSUES.md`. (Arm H *was* judged later, in
`EXP-2026-08-007`, but on the outer-join artifacts of `EXP-2026-08-004`, not on
these — RESULTS A-2.) The reference directory carries Arm G's 120
`*.judgment.json` files from `EXP-2026-07-007` (dated 2026-08-05), which are
part of its hash.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Arm artifacts | `docs/evaluation/experiments/untruncated-generic-fixed/generic/` | 4806684 | sha256:f7e2c0121320847c5ce210455b3a44f53252234597058631e73f73bd48371a11 | 120 answer files + `manifest.json` (answer + full retrieved evidence + executed queries + per-stage traces). Re-hashed 2026-09-09 with the tree method (RESULTS A-1); the previously recorded `sha256:8170724a…` is the `find\|cat` recipe below and still reproduces — content unchanged |
| Reference arm | `docs/evaluation/experiments/untruncated-generic/generic/` | 4878680 | sha256:de75c852934ff7b0b9db827bb1cd6c38cf22a1357bc161fc05fd24d96aac1ed9 | Arm G's artifacts (120 answers + 120 judgments + `manifest.json`), the paired baseline every delta here is computed against. Tree method; unchanged |

Both rows are now hashed the same way: the tree hash of
`uv run python -m utils.research_record.hashing <dir>` (relative path + per-file
SHA-256, folded in sorted order), which is what the validator checks. The
recipe `RESULTS.md` §8 documents —
`find <dir> -type f -name '*.json' | sort | xargs cat | sha256sum` — gives a
different digest for the same content (`8170724a…` for the Arm H directory)
and is kept there as a second, independent check.
