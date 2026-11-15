# POINTERS — EXP-2026-11-007

The replay reads the kill tests' saved-generation caches, which live under the gitignored
`logs/`. Hashes were taken on 2026-11-15, before the replay.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| typed/cache/generate.jsonl | `logs/killtests-2026-11/typed/cache/generate.jsonl` | 652763 | sha256:fbfd574f106e43f039cc8a250483992cd0d27ba06a5c8c7dfe2d23ca2c33e620 | saved replies, one JSON object per line (`key` = qid\|arm\|model) |
| exp005/cache/A-generate.jsonl | `logs/killtests-2026-11/exp005/cache/A-generate.jsonl` | 658117 | sha256:7ec6d8e9e538b128bb2a76739d1460101cbe09da207da1490e0454c60c3090cc | saved replies, one JSON object per line (`key` = qid\|arm\|model) |
| exp005/cache/A-repair.jsonl | `logs/killtests-2026-11/exp005/cache/A-repair.jsonl` | 11785 | sha256:1ef0b77de683630344f931026128cec75a8eee6f85b8b2214e0aa2a6aa20b448 | saved replies, one JSON object per line (`key` = qid\|arm\|model) |
| exp005/cache/B-generate.jsonl | `logs/killtests-2026-11/exp005/cache/B-generate.jsonl` | 2678707 | sha256:65980cfe3e922df75e290e3ca6532a314b005e5e72043ecf4a762dae9202fc2f | saved replies, one JSON object per line (`key` = qid\|arm\|model) |
| exp005/cache/B-repair.jsonl | `logs/killtests-2026-11/exp005/cache/B-repair.jsonl` | 174362 | sha256:c5637e14605b30b394ffb288768fb21144c139b1f11ec1a3c6ed51d2a588eb79 | saved replies, one JSON object per line (`key` = qid\|arm\|model) |
| exp005/cache/B-generate.qwen-xhigh-archive.jsonl | `logs/killtests-2026-11/exp005/cache/B-generate.qwen-xhigh-archive.jsonl` | 293190 | sha256:604335c9048bb2b77583ba7e9e8f3c32d22c5870cf38c1793861f4909ef84fb5 | saved replies, one JSON object per line (`key` = qid\|arm\|model) |
| exp006/cache/A-generate.jsonl | `logs/killtests-2026-11/exp006/cache/A-generate.jsonl` | 1048685 | sha256:af6402578bc54aea0e3cd11a108d7ecbded49b0a50a2e4b2077ba0a69eb591b6 | saved replies, one JSON object per line (`key` = qid\|arm\|model) |
| exp006/cache/A-repair.jsonl | `logs/killtests-2026-11/exp006/cache/A-repair.jsonl` | 827 | sha256:4affa293e66ab59674e0c0edd641223c277dc7f4ece327060b5f73f963ec61bc | saved replies, one JSON object per line (`key` = qid\|arm\|model) |
| exp006/cache/B-generate.jsonl | `logs/killtests-2026-11/exp006/cache/B-generate.jsonl` | 1934206 | sha256:88d7dd78d729569b3910e03ac2be9a1395c344d074c3001abffc442d9c9888cc | saved replies, one JSON object per line (`key` = qid\|arm\|model) |
| exp006/cache/B-repair.jsonl | `logs/killtests-2026-11/exp006/cache/B-repair.jsonl` | 91905 | sha256:e30decbb3381a4d27db5c3ed51e886297a773868dffc767f1f2f280053307861 | saved replies, one JSON object per line (`key` = qid\|arm\|model) |
| exp006/cache/C-generate.jsonl | `logs/killtests-2026-11/exp006/cache/C-generate.jsonl` | 2425698 | sha256:5c667a40317287f6d192c4970253c3a06802ac5dc179ebd6de8b6a2e07d4b8c6 | saved replies, one JSON object per line (`key` = qid\|arm\|model) |
| exp006/cache/C-repair.jsonl | `logs/killtests-2026-11/exp006/cache/C-repair.jsonl` | 224519 | sha256:38bf9d59755572da17d808de10517d635a21f9453a9a7d6f4337f5341ad5b15f | saved replies, one JSON object per line (`key` = qid\|arm\|model) |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
