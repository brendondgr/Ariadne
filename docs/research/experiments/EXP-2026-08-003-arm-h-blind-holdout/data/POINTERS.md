# POINTERS — EXP-2026-08-003

Raw run output stays under `docs/evaluation/experiments/`. **No judgment files
exist for Arm H in this directory** (re-checked 2026-09-09: 30 answers +
`manifest.json`, nothing else) — it was scored mechanically from the answer
artifacts. Arm H was later judged in `EXP-2026-08-007`, on the outer-join
artifacts of `EXP-2026-08-004`, not on these (RESULTS A-2).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Arm H artifacts | `docs/evaluation/experiments/holdout-v1-generic/generic/` | 644640 | sha256:8d799d5d3ff7a6e3fc755cf8815a5b118499297b84a1e46e26b201540cdf83dc | 30 answer files + `manifest.json` (answer + retrieved evidence + executed queries + traces). Re-hashed 2026-09-09 with the tree method (RESULTS A-1); the previously recorded `sha256:e1009d3a…` is the `find\|cat` recipe in `../RESULTS.md` §8 and still reproduces — content unchanged |
| Blind bank | `utils/specialists/tests/golden/holdout_questions.json` | 51152 | sha256:cee87ec0e229f200d4052cb41899cb56bcbdf4e91ff9f358eba1f127b6232be0 | The 30 blind questions, unmodified for this run |

Arm A and Arm F artifacts and judgments are `EXP-2026-08-002`'s and are pointed
at from that experiment (since 2026-09-09), not duplicated here.

The directory hash is the tree hash of
`uv run python -m utils.research_record.hashing <dir>` (relative path +
per-file SHA-256, folded in sorted order), which is what the validator checks.
The recipe in `../RESULTS.md` §8 — every `*.json` concatenated in sorted path
order — gives a different digest (`e1009d3a…`) for the same content and is
kept there as an independent check.
