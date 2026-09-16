# POINTERS — EXP-2026-09-025

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `scored_anchor_first.json` | `docs/evaluation/variants-2026-09-15/scored_anchor_first.json` | 2,374,888 | `sha256:d88b181a8e6111221de8707f4788c814b7ebf79f3197618566f91b75241a334f` | exposed: anchor_first (control, EXP-2026-09-023) |
| `scored_form_execute.json` | `docs/evaluation/variants-2026-09-15/scored_form_execute.json` | 2,387,416 | `sha256:4f62754def176ea5aaa43ea4d1c78362949776ed5227ab7d5ddb03f0f339bc08` | exposed: form_execute |
| `scored_form_execute_ids.json` | `docs/evaluation/variants-2026-09-15/scored_form_execute_ids.json` | 2,732,766 | `sha256:1c90c239eb60bf535dbefd098a7f667596c4f054ceee38d601f672505660a263` | exposed: form_execute_ids |
| `scored_anchor_first.json` | `docs/evaluation/variants-holdout-2026-09/scored_anchor_first.json` | 578,532 | `sha256:b7282dd7a3179f7b46885c752c94d164723a864a066339be30834087ed5fe056` | sealed: anchor_first (control, EXP-2026-09-023) |
| `scored_form_execute.json` | `docs/evaluation/variants-holdout-2026-09/scored_form_execute.json` | 584,494 | `sha256:36962cf419116bbdb7ca13fce4815451619a354876c38ea7cc1d0fd9a450cfbe` | sealed: form_execute |
| `scored_form_execute_ids.json` | `docs/evaluation/variants-holdout-2026-09/scored_form_execute_ids.json` | 623,174 | `sha256:14cb8bab1002f9f5c0174f1f5c913ecd626f56f17da070252d6e8a712ddb11d4` | sealed: form_execute_ids |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
