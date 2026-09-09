# POINTERS — EXP-2026-08-004

Raw run output stays under `docs/evaluation/experiments/`. When this experiment
ran (2026-08-10) **no judgment files existed for either run** — both were
scored mechanically. Since **2026-08-19** both directories also hold the
judgment files `EXP-2026-08-007` wrote when it judged Arm H on exactly these
artifacts (30 and 120 `*.judgment.json`, plus one `*.judgment.error.txt` each).
The answer files are unchanged (RESULTS A-2). Hashes below are the tree hash of
`uv run python -m utils.research_record.hashing <dir>`, computed 2026-09-09
over the directories as they now stand, sidecars included.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Blind, outer join | `docs/evaluation/experiments/holdout-v1-generic-outer/generic/` | 683755 | sha256:055240fdaf44eee9ee1099bfbe5bf01502c8e9b383d919283ff78dec44c112cf | 30 answer files + `manifest.json` (2026-08-10, 657289 bytes of `*.json` excluding sidecars — the originally recorded size) + 31 `EXP-2026-08-007` judgment sidecars (2026-08-19) |
| Development, outer join | `docs/evaluation/experiments/untruncated-generic-outer/generic/` | 4953549 | sha256:ba22ed41fdabbb07fac2ae20a5a8b508c570d94dd2a563474e431ebab6eb4916 | 120 answer files + `manifest.json` (2026-08-10, 4850928 bytes excluding sidecars) + 121 `EXP-2026-08-007` judgment sidecars (2026-08-19) |

The originally recorded digests — `sha256:e24f8d9e…` (blind) and
`sha256:8e15ac27…` (development) — are the recipe in `../RESULTS.md` §8 and
still reproduce **when the sidecars are excluded**:

```bash
find <dir> -type f -name '*.json' ! -name '*.judgment*' | sort | xargs cat | sha256sum
```

Use that to confirm the answers themselves are untouched; use the table
above to confirm the directory as a whole has not changed since 2026-09-09.

The inner-join runs this is compared against belong to `EXP-2026-08-001`
and `EXP-2026-08-003`; Arm F's judgments belong to `EXP-2026-08-002`. None are
duplicated here.
