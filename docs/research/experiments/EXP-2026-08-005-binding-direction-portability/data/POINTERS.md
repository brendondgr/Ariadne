# POINTERS — EXP-2026-08-005

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This table was blank until 2026-09-09 (RESULTS A-1). Every hash below
was computed that day with `uv run python -m utils.research_record.hashing`
(directories: tree hash over relative path + per-file SHA-256). All four run
directories are gitignored, hold only answer files + `manifest.json` (no
judgment files, then or now), and are dated 2026-08-18 15:08–15:09.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Blind, after | `docs/evaluation/experiments/binding-fix-holdout/deterministic` | 636600 | sha256:fbddbbc25bcb9c1a476800301be91974a729444b7d8d54c6931faadebc54b4a2 | 30 answers + `manifest.json` (30/30 ok, 1.1 s). The 0.8952 headline |
| Blind, before | `docs/evaluation/experiments/binding-baseline-holdout/deterministic` | 375506 | sha256:d4d4c9e4fbafa38329f633e5e15c4b75bb1cf029df2a77ea3aad29dd342d2525 | 30 answers + `manifest.json` (30/30 ok, 0.9 s), run from a worktree at `ec01fe7`. The 0.7688 baseline |
| Development, after | `docs/evaluation/experiments/binding-fix-dev/deterministic` | 3259655 | sha256:bb25f8f957852d35dec764de2724d10cf431b885c26e81eed8e604c8c0d8d069 | 120 answers + `manifest.json` (120/120 ok, 1.9 s). 1061 records |
| Development, before | `docs/evaluation/experiments/binding-baseline-dev/deterministic` | 3259639 | sha256:74d8a9b2c1ecb5d07e480cdfe0a7ae0320b298c2c358ba8c6850317409fa64e4 | 120 answers + `manifest.json` (120/120 ok, 2.4 s), from the `ec01fe7` worktree. 1061 records |
| Blind bank | `utils/specialists/tests/golden/holdout_questions.json` | 51152 | sha256:cee87ec0e229f200d4052cb41899cb56bcbdf4e91ff9f358eba1f127b6232be0 | The 30 blind questions; unchanged since `ce3a2d2` (2026-08-09) |

**Not pointed at — the development bank.** The two development runs read the
three golden bank files (`attack_questions.json`, `capec_questions.json`,
`federated_questions.json`) as they stood at `8ac1049`. Thirty-five minutes
after the run, `c10caaa` (2026-08-18 15:43, `EXP-2026-08-006`) modified
`capec_questions.json` and `federated_questions.json`, and later commits have
changed them again, so a hash of the current files would not pin what ran.
The bank as run is `git show 8ac1049:utils/specialists/tests/golden/<file>`;
see ISSUES 2026-09-09.

**Not pointed at — the binding audit.** The §3 inventory (615 task shapes,
670 bindings, 242 mismatches; 16 repairable over 5 templates before, 3 after)
was produced by `utils.specialists.audit.binding_audit` driving both builders
live and wrote no artifact; it is reproducible only from a tree at `ec01fe7`
(before) and `8ac1049` (after).
