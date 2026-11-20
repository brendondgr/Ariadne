# POINTERS — EXP-2026-11-017

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| variant set | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/variants.json | 219487 | sha256:428a23467ecf8aed1f266186504d6f68d0a9d88173cc090149558d078bdea63c | 579 variants + 120 gold (copy of variants-2026-09-15) |
| reference capture | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/reference.json | 350660 | sha256:dc1fbf131f49dae6e5ad01c475bb23b0304d296511ecb90fd6835310b6988670 | R reference; reference_check.json is byte-identical |
| arm R | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/R.json | 3998116 | sha256:9d39ebf481636900f62e9e84a55890833f9fe17ab3812a6a98f04826e98ce7fe | rules-only, 579 variants |
| arm E | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/E.json | 6304765 | sha256:d87da9d289575710d527b97657a3a974180eba11a1552612d5e845ad2bd022dd | 699 rows (sitting 1, attempt 1) |
| arm T-lazy | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/T-lazy.json | 5123430 | sha256:8ca16a577a35a9f766370f374b8531f741a14b229295e4a0f0700eec8c10d81d | 699 rows (sitting 1, attempt 1) |
| arm T-full | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/T-full.json | 5646800 | sha256:e2862ed9ba56257b26ad6cca1950658958775ec92dc39df66e2a55838b87d947 | 699 rows (sitting 2, attempt 3; ISSUES) |
| arm T-lazy-G | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/T-lazy-G.json | 4465712 | sha256:b0d9a72473c21a9759deeaeadc69498819761fd5ca8a30aa5a6855a38623c1c5 | 699 rows, Gemma (sitting 1, attempt 1) |
| identity E | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/E.identity.json | 568 | sha256:37932d1badd5dbf0428174cbab3e28d2008306a049ad88e4e0c2ca07fd7c3346 | token-id check before and after |
| identity T-lazy | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/T-lazy.identity.json | 575 | sha256:b52fa3f4ed95e664c784290e275d0d7bb1fe8a7c497f13038c583f9b275248e9 | token-id check before and after |
| identity T-full | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/T-full.identity.json | 574 | sha256:3369777b401a3342281bb76ce8e4b15364c03e6afa856b3de49a5fc4bb5f231a | token-id check before and after |
| identity T-lazy-G | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/T-lazy-G.identity.json | 555 | sha256:4fbfb6f6b1e13462ed60cd59e83cce2ce5997d3010c6b35b6373e82fafa9113e | token-id check before and after |
| dev E answers | docs/evaluation/experiments/bridge-guard-2026-11-19/dev/planned_llm_english/answers | 13317734 | sha256:a66dbfa0cf61e604c48696d8d201f9c73f09bb0399706ef485b7f6e95b5fb21c | 284 answers (gitignored; sitting 2) |
| dev T-lazy answers | docs/evaluation/experiments/bridge-guard-2026-11-19/dev/planned_llm_typed_lazy/answers | 6016026 | sha256:fa5779b02f4c8074b0c8de9df8a7d4a44e9c9e464a9e9c49e535e13b2d5d37f0 | 284 answers (gitignored; sitting 2) |
| dev T-full answers | docs/evaluation/experiments/bridge-guard-2026-11-19/dev/planned_llm_typed_full/answers | 7241656 | sha256:e284336fd4ca402d92465117395c1aef2cde6ceffe4016cff2f9ee2bdd14e6f2 | 284 answers (gitignored; sitting 2) |
| dev T-lazy-G answers | docs/evaluation/experiments/bridge-guard-2026-11-19/dev-gemma/planned_llm_typed_lazy/answers | 6736876 | sha256:529b23fc7c11ea66a873a233a4d7c059dd3ce53f41a11743658e7296f6c59400 | 284 answers, Gemma (gitignored; sitting 1) |
| authored baseline | docs/evaluation/experiments/harness-attribution-qwen-walkfix-2026-11-16/generic_composed/answers | 8653405 | sha256:b09095b78878b8ae18aa5be02bacf221a7f5597d1efee522d2f385ee40b63825 | G2/G4 dev baseline (hashed in EXP-2026-11-009) |

If this experiment reads no raw output outside `docs/research/`, delete the
table and write one line: `No external artifacts: <why>` — the validator
rejects an empty table on a completed experiment.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
