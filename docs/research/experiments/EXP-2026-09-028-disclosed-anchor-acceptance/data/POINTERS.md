# POINTERS — EXP-2026-09-028

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `scored_form_execute.json` | `docs/evaluation/variants-2026-09-15/scored_form_execute.json` | 2,387,416 | `sha256:4f62754def176ea5aaa43ea4d1c78362949776ed5227ab7d5ddb03f0f339bc08` | exposed: form_execute |
| `scored_disclosed.json` | `docs/evaluation/variants-2026-09-15/scored_disclosed.json` | 2,451,859 | `sha256:1cff3fa2af15e4e5450f96f9ae380756be722df58bed7ff5aed9d6f6f7c6c9b4` | exposed: disclosed |
| `scored_form_execute.json` | `docs/evaluation/variants-holdout-2026-09/scored_form_execute.json` | 584,494 | `sha256:36962cf419116bbdb7ca13fce4815451619a354876c38ea7cc1d0fd9a450cfbe` | sealed: form_execute |
| `scored_disclosed.json` | `docs/evaluation/variants-holdout-2026-09/scored_disclosed.json` | 606,095 | `sha256:128a28eee58e679404957b0e7e5be9fd7d91167dd3d7351aff9a6d40f28da222` | sealed: disclosed |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
