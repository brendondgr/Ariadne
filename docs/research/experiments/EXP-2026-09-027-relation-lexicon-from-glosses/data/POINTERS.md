# POINTERS — EXP-2026-09-027

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `scored_form_execute.json` | `docs/evaluation/variants-2026-09-15/scored_form_execute.json` | 2,387,416 | `sha256:4f62754def176ea5aaa43ea4d1c78362949776ed5227ab7d5ddb03f0f339bc08` | exposed: form_execute |
| `scored_paraphrases.json` | `docs/evaluation/variants-2026-09-15/scored_paraphrases.json` | 2,474,064 | `sha256:b21c58c7b09cb5811d9a49b10b905d702aa981f5d553f86491fea1ac25f01880` | exposed: paraphrases |
| `scored_form_execute.json` | `docs/evaluation/variants-holdout-2026-09/scored_form_execute.json` | 584,494 | `sha256:36962cf419116bbdb7ca13fce4815451619a354876c38ea7cc1d0fd9a450cfbe` | sealed: form_execute |
| `scored_paraphrases.json` | `docs/evaluation/variants-holdout-2026-09/scored_paraphrases.json` | 590,409 | `sha256:3658473653b9dcef95cfd06034a0ae50d5c815b59248ba5d128b43c83d96bc66` | sealed: paraphrases |
| `attack.relation_lexicon.json` | `data/source_cards/overlays/attack.relation_lexicon.json` | 5,234 | `sha256:ce2136d92868c277c7088dff9940606a406064520defa2e3ae2ce97576abbed1` | the generated lexicon, kept and dropped words |
| `capec.relation_lexicon.json` | `data/source_cards/overlays/capec.relation_lexicon.json` | 10,968 | `sha256:67af64853c628687cc6314b830e9ad9dc76ad8672e8965b2721d75e4d4497584` | the generated lexicon, kept and dropped words |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
