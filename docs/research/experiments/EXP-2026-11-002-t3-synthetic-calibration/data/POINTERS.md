# POINTERS — EXP-2026-11-002

Run outputs live under `logs/killtests-2026-11/` (gitignored); the small summaries are copied into this folder. Run of 2026-11-13 19:01–19:45 from tag `killtests-run` (eb676358).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `entities.json` | `logs/killtests-2026-11/t3/entities.json` | 126,601 | `sha256:7893008c55fdc5d0494d6f350915de3bc71db37d7a70e187561ee718ba8d9517` | sampled entities (copied to data/) |
| `reword.json` | `logs/killtests-2026-11/t3/reword.json` | 600,316 | `sha256:b941c37faf6d6a9bf736f175b69297f9ce32021bf747f8244fc312d38aa7801f` | paraphrase/description rewordings with leak checks |
| `questions.json` | `logs/killtests-2026-11/t3/questions.json` | 844,111 | `sha256:390fa5a029489ad92eb529ab4c82e0d6052141adf8639ae92999a57e15e29564` | synthetic questions with tier and distance |
| `score.json` | `logs/killtests-2026-11/t3/score.json` | 1,935,556 | `sha256:91059617f480942967677f5fe4e6f2a39089d65558896e94acf4eab904baa172` | decider probabilities per synthetic question |
| `evaluate.json` | `logs/killtests-2026-11/t3/evaluate.json` | 15,819 | `sha256:08cc86a42dc35ac92f0af8c2d0c93dbfab243a72442431e7f93de7f689c141ce` | calibration and evaluation (copied to data/) |
| `decide.json` | `logs/killtests-2026-11/t2/decide.json` | 732,572 | `sha256:45931be0dd208f658ede60b048c3350775a764da298fad00ea25f851c0a8ab3c` | real-question scores (shared with EXP-2026-11-001) |
| `preconditions.json` | `logs/killtests-2026-11/preconditions.json` | 697 | `sha256:44cb3f553ca1ee84d626508254ecb9370e5f3bce774ea2404bb42aeebf474a34` | served models, graph counts, commit at launch |
| `report.json` | `logs/killtests-2026-11/report.json` | 1,157 | `sha256:9409e3edb9e27506c00dbd65b6b916894b5892015aa0c06007308d13d9720a78` | kill-rule verdicts |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
