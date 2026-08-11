# POINTERS — EXP-2026-08-003

Raw run output stays under `docs/evaluation/experiments/`. **No judgment files
exist for Arm H** — it was scored mechanically from the answer artifacts.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Arm H artifacts | `docs/evaluation/experiments/holdout-v1-generic/generic/` | 644640 | sha256:e1009d3a412f04dcc54cf1b3c1d5f957339764921bc5f84942f2873fb9b72803 | 30 answer files (answer + retrieved evidence + executed queries + traces) |
| Blind bank | `utils/specialists/tests/golden/holdout_questions.json` | 51152 | sha256:cee87ec0e229f200d4052cb41899cb56bcbdf4e91ff9f358eba1f127b6232be0 | The 30 blind questions, unmodified for this run |

Arm A and Arm F artifacts and judgments are `EXP-2026-08-002`'s and are pointed
at from that experiment, not duplicated here.

Each directory hash is the SHA-256 of every `*.json` under that path,
concatenated in sorted path order; the command is in
[`../RESULTS.md`](../RESULTS.md) §8.
