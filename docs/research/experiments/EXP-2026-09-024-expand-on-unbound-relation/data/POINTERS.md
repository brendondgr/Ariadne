# POINTERS — EXP-2026-09-024

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `scored_anchor_first.json` | `docs/evaluation/variants-2026-09-15/scored_anchor_first.json` | 2,374,888 | `sha256:d88b181a8e6111221de8707f4788c814b7ebf79f3197618566f91b75241a334f` | control (EXP-2026-09-023) |
| `scored_expand_unbound.json` | `docs/evaluation/variants-2026-09-15/scored_expand_unbound.json` | 2,576,236 | `sha256:0090af8fa88b78e8d0bb1a6f8161b3c9caf8a875907ebfa087a0c0fddbf3d549` | treatment, exposed bank |
| `scored_anchor_first.json` | `docs/evaluation/variants-holdout-2026-09/scored_anchor_first.json` | 578,532 | `sha256:b7282dd7a3179f7b46885c752c94d164723a864a066339be30834087ed5fe056` | control, sealed bank (EXP-2026-09-023) |
| `scored_expand_unbound.json` | `docs/evaluation/variants-holdout-2026-09/scored_expand_unbound.json` | 584,120 | `sha256:94d0522e2b4c1dd79f0acb9e12cc71e6552d54a8d01838716fdee1be27089537` | treatment, sealed bank |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
