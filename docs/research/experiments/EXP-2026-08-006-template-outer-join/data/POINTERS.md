# POINTERS — EXP-2026-08-006

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

Table filled 2026-09-09 (it was the blank scaffold until then; see RESULTS
AMENDMENT A-1). Hashes are tree hashes over the directory as it is on
2026-09-09. The two `outerjoin-*` directories gained `*.judgment*.json` grader
sidecars on 2026-08-19 (EXP-2026-08-007's judging passes); the 30 + 120 answer
files and the two `manifest.json` files are untouched since 2026-08-18 15:43
and reproduce every number below exactly when the sidecars are excluded.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Blind holdout, after (this arm) | `docs/evaluation/experiments/outerjoin-holdout` | 751040 | sha256:e75d87eced299cc217675812350d3618ad7a73d80ffb38406ed9b1988e41368d | 30 deterministic-arm answers on holdout v1 with outer-join bridges → `blind_gold_in_evidence` 1.0000, 221 records. Also holds 90 `.judgment*.json` sidecars added 2026-08-19 by EXP-2026-08-007 (not used here). |
| Development catalogue, after (this arm) | `docs/evaluation/experiments/outerjoin-dev` | 3414076 | sha256:cec06a7c58a568a51d60ee7a5e4520514e2edfcd03af66b6f22867d56c9de37b | 120 deterministic-arm answers on the development catalogue → `dev_gold_in_evidence` 1.0000, 1079 records. Also holds 120 `.judgment.json` sidecars added 2026-08-19 by EXP-2026-08-007. |
| Blind holdout, before | `docs/evaluation/experiments/binding-fix-holdout` | 636600 | sha256:4354cfb5d12975ce768e9356d25a7b491761915ee3e25e24fba7e576aa24d179 | EXP-2026-08-005's post-binding-fix holdout run (0.8952, 26/30, 216 records) — the paired "before" side. |
| Development catalogue, before | `docs/evaluation/experiments/binding-fix-dev` | 3259655 | sha256:6017994a7433af241b53fd81d6e825e728067122e60bdf5a54a8f2173b229fc0 | EXP-2026-08-005's post-binding-fix development run (1.0000, 1061 records) — the paired "before" side. |
| Template cascade original | `docs/evaluation/experiments/binding-baseline-holdout` | 375506 | sha256:93665fc4b5ada2605c1e3acee6fde90a8f0f9738f9d3660852a6f874a5e41ec6 | Pre-fix cascade on holdout v1 (0.7688, 22/30) — the first row of `progression_blind`. |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```

Recompute the numbers with `utils/evaluation/retrieval_coverage.py`
(`score_case` / `summarize` / `compare`), excluding every file whose name
contains `.judgment` — the committed `score_arm` only excludes names ending in
`.judgment.json`, so a naive re-run today over `outerjoin-holdout` counts
n = 90 (see ISSUES 2026-09-09).
