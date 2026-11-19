# POINTERS — EXP-2026-11-016

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| variant set | docs/evaluation/experiments/scan-fix-2026-11-19/variants/variants.json | 219487 | sha256:428a23467ecf8aed1f266186504d6f68d0a9d88173cc090149558d078bdea63c | 579 variants + 120 gold (copy of variants-2026-09-15) |
| reference capture | docs/evaluation/experiments/scan-fix-2026-11-19/variants/reference.json | 350660 | sha256:dc1fbf131f49dae6e5ad01c475bb23b0304d296511ecb90fd6835310b6988670 | R reference; reference_check.json is byte-identical |
| arm R | docs/evaluation/experiments/scan-fix-2026-11-19/variants/R.json | 3998126 | sha256:e0470b0994cd9ad468fe67b054137ac7dc19dca38bda45eacfabe61cac3b5db6 | rules-only, 579 variants |
| arm E | docs/evaluation/experiments/scan-fix-2026-11-19/variants/E.json | 6612569 | sha256:3bb8328cd9417cd0bf3db72b278eb229375a1db7bbec939982e8ef60d521cce8 | 699 rows (attempt 4) |
| arm T-lazy | docs/evaluation/experiments/scan-fix-2026-11-19/variants/T-lazy.json | 5201004 | sha256:ee4ad52834360ff3164f2edd7a7140c628c7d3f164e5299f777338477882d842 | 699 rows (attempt 3) |
| arm T-full | docs/evaluation/experiments/scan-fix-2026-11-19/variants/T-full.json | 5677689 | sha256:f2c56767a6aa35d3e704d54ab6754f3308f4ff694adf746c85d965d105062f0b | 699 rows (attempt 3) |
| arm T-lazy-G | docs/evaluation/experiments/scan-fix-2026-11-19/variants/T-lazy-G.json | 4466192 | sha256:8f972d6a5a622ffd65689989105e9033b4007a8a2097f69ca2ebd9e69812d61b | 699 rows, Gemma (attempt 4) |
| identity E | docs/evaluation/experiments/scan-fix-2026-11-19/variants/E.identity.json | 568 | sha256:d793b528fdafa77971830582ac2963b3cc45e686a82eb669851d2200e6610781 | token-id check before and after |
| identity T-lazy | docs/evaluation/experiments/scan-fix-2026-11-19/variants/T-lazy.identity.json | 575 | sha256:e0ea3ef1f5bf9cd3b407c6541212154cefda4d2241870f71abd82ca375ce55a9 | token-id check before and after |
| identity T-full | docs/evaluation/experiments/scan-fix-2026-11-19/variants/T-full.identity.json | 575 | sha256:5521684f259b60bc21b77b6f96a250600ff85588c9427d2df4cb743dbea60218 | token-id check before and after |
| identity T-lazy-G | docs/evaluation/experiments/scan-fix-2026-11-19/variants/T-lazy-G.identity.json | 555 | sha256:6d1d09aec432312f02e92f672d0e41546880e57923485f7e4285ffcf2f5f5d42 | token-id check before and after |
| dev E answers | docs/evaluation/experiments/scan-fix-2026-11-19/dev/planned_llm_english/answers | 12171750 | sha256:bf457f98ae0b3d9e27d06b9a62138f815f2cb68647ab16f933250e304f8a93e6 | 284 answers (gitignored; attempt 2) |
| dev T-lazy answers | docs/evaluation/experiments/scan-fix-2026-11-19/dev/planned_llm_typed_lazy/answers | 6956266 | sha256:5683c862b26647abe0b0cbe0df6b3e08293042a52dcc6c841aad5e3504a1e662 | 284 answers (gitignored; attempt 2) |
| dev T-full answers | docs/evaluation/experiments/scan-fix-2026-11-19/dev/planned_llm_typed_full/answers | 6764653 | sha256:b89c5bccd22c3e3336972a5f56191c8d5582389913d12fa0dd0839833c80669d | 284 answers (gitignored; attempt 3) |
| dev T-lazy-G answers | docs/evaluation/experiments/scan-fix-2026-11-19/dev-gemma/planned_llm_typed_lazy/answers | 6086277 | sha256:6908f2564673c1ac87de129707ece4078e9f577140a0c8654f5fdfab48b43146 | 284 answers, Gemma (gitignored; attempt 2) |
| authored baseline | docs/evaluation/experiments/harness-attribution-qwen-walkfix-2026-11-16/generic_composed/answers | 8653405 | sha256:b09095b78878b8ae18aa5be02bacf221a7f5597d1efee522d2f385ee40b63825 | G2/G4 dev baseline (hashed in EXP-2026-11-009) |

If this experiment reads no raw output outside `docs/research/`, delete the
table and write one line: `No external artifacts: <why>` — the validator
rejects an empty table on a completed experiment.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
