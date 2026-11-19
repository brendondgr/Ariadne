# POINTERS — EXP-2026-11-015

Phase 2 output, written 2026-11-18 on commit 67607f55, from 20:56 to 23:42 EST. It lives under
`docs/evaluation/experiments/tool-catalog-2026-11-18/`.
- **The variant files are committed.** These are the reference capture, R, and the four
  model arms. The same convention was used for `docs/evaluation/variants-2026-09-15/`.
- **The dev answer folders are gitignored.** They are hashed here as trees.
- **Each arm folder also holds `identity.json` and `manifest.json`.** The token-id check is in
  `identity.json`.

The Phase 1 checks (E5 diffs, smoke runs, pytest logs) are in `data/phase1/`. The scored
figures are in `data/metrics.json`.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| reference | docs/evaluation/experiments/tool-catalog-2026-11-18/variants/reference.json | 350660 | sha256:dc1fbf131f49dae6e5ad01c475bb23b0304d296511ecb90fd6835310b6988670 | rules-only capture of the 120 gold questions |
| reference check | docs/evaluation/experiments/tool-catalog-2026-11-18/variants/reference_check.json | 350660 | sha256:dc1fbf131f49dae6e5ad01c475bb23b0304d296511ecb90fd6835310b6988670 | second capture; byte-identical |
| variant set | docs/evaluation/experiments/tool-catalog-2026-11-18/variants/variants.json | 219487 | sha256:428a23467ecf8aed1f266186504d6f68d0a9d88173cc090149558d078bdea63c | the 579 variants (same hash as the manifest's data) |
| R | docs/evaluation/experiments/tool-catalog-2026-11-18/variants/R.json | 3998117 | sha256:c108fe276d67cb12c521c6cb44e554f880eb3dd5383cc7a188a7ce0403e5238e | rules-only, 579 variants scored |
| E | docs/evaluation/experiments/tool-catalog-2026-11-18/variants/E.json | 6369150 | sha256:ce98f6ea8c9018a0c5c12f91fbf507689f8c4eab5c48cbc616206810de77002f | Qwen, English hand-off, 699 rows |
| T-lazy | docs/evaluation/experiments/tool-catalog-2026-11-18/variants/T-lazy.json | 6239642 | sha256:54185b0971e17295bf075ce2b381ffff20febe975e7cb2fe31895cf256c7c062 | Qwen, typed, names-only card, 699 rows |
| T-full | docs/evaluation/experiments/tool-catalog-2026-11-18/variants/T-full.json | 6112881 | sha256:4b1eb3eca6077549d430668f9965785caf2eda3f95bf3578c78ce2dba51f7d82 | Qwen, typed, whole card, 699 rows |
| T-lazy-G | docs/evaluation/experiments/tool-catalog-2026-11-18/variants/T-lazy-G.json | 4791569 | sha256:83bb84cb97c8f8ff7e97477244e37bb6c4784e621b2784f9d23c10a4a5e75cb0 | Gemma, typed, names-only card, 699 rows |
| dev E answers | docs/evaluation/experiments/tool-catalog-2026-11-18/dev/planned_llm_english/answers | 12031099 | sha256:52843ca8b289b6353ae6b87f6e32fbe4642f44ac27d0bc3e02d0a4cb0f32b1c8 | 284 answers (gitignored) |
| dev T-lazy answers | docs/evaluation/experiments/tool-catalog-2026-11-18/dev/planned_llm_typed_lazy/answers | 11068890 | sha256:7ff99a459f760f8305594422ebcfbad04043c8e59098de006bc42825622d1dfe | 284 answers (gitignored) |
| dev T-full answers | docs/evaluation/experiments/tool-catalog-2026-11-18/dev/planned_llm_typed_full/answers | 8537973 | sha256:ee6bb8f3aceaa16499a7b0048cee9807cff8aa7dc7e303c617fcd4c220d2d8b5 | 284 answers (gitignored) |
| dev T-lazy-G answers | docs/evaluation/experiments/tool-catalog-2026-11-18/dev-gemma/planned_llm_typed_lazy/answers | 9292325 | sha256:be33c4b5d65664cfa01d4af9992f694b96d9d7a840564e12407523d62d4fa7ad | 284 answers, Gemma (gitignored) |
| authored baseline | docs/evaluation/experiments/harness-attribution-qwen-walkfix-2026-11-16/generic_composed/answers | 8653405 | sha256:b09095b78878b8ae18aa5be02bacf221a7f5597d1efee522d2f385ee40b63825 | G2/G4 dev baseline (hashed in EXP-2026-11-009) |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
