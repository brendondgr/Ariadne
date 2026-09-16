# POINTERS — EXP-2026-09-029

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `summary.json` | `docs/evaluation/experiments/variants-judged-2026-09-15/sealed-form_execute/summary.json` | 770 | `sha256:3c3bf644aa9226a344807882b727ff32765ac1d4f41ce5a7c443b9f32bf62e55` | the bridge's per-tier aggregate over the 160 judgments |
| `scored_form_execute.json` | `docs/evaluation/variants-holdout-2026-09/scored_form_execute.json` | 584,494 | `sha256:36962cf419116bbdb7ca13fce4815451619a354876c38ea7cc1d0fd9a450cfbe` | the answers judged (EXP-2026-09-025) |

The 160 answer files and their judgments sit beside `summary.json` under `form_execute/answers/`, outside git.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
