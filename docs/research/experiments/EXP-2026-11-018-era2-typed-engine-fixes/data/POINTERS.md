# POINTERS — EXP-2026-11-018

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| variant set | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/variants.json | 219487 | sha256:428a23467ecf8aed1f266186504d6f68d0a9d88173cc090149558d078bdea63c | 579 variants + 120 gold (copy of variants-2026-09-15) |
| reference capture | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/reference.json | 350660 | sha256:dc1fbf131f49dae6e5ad01c475bb23b0304d296511ecb90fd6835310b6988670 | R reference; reference_check.json is byte-identical |
| arm R | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/R.json | 3998124 | sha256:ab57b15e7589a8f5932a6534f2d5b0ad7212c7cd3550768115fbe3515db35c5a | rules-only, 579 variants |
| arm E | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/E.json | 6573901 | sha256:5a12ed8b9fa648bdc16cff4b413df7751457ac20565a8a2660d890e8e0670bbc | 699 rows (attempt 1) |
| arm T-lazy | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/T-lazy.json | 5351551 | sha256:52f70d7ba117634df0ed2af70e8f82982aaa4bbcd8758277a6eaf9972a2e8c97 | 699 rows (attempt 1) |
| arm T-full | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/T-full.json | 5554284 | sha256:c8abbfabe176cefa377be3f3385b371057d2c39dd87da248f4ee04f0157ebd61 | 699 rows (attempt 1) |
| arm T-lazy-G | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/T-lazy-G.json | 4618498 | sha256:19153942e47f99ca4861001d86457acd3dd9b1d95116688bf6d50a6716171164 | 699 rows, Gemma (attempt 1) |
| identity E | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/E.identity.json | 568 | sha256:9b7d4c59d65076b80ea50909b691b63dc514c84fe360b29d152f23e7a3c0fcc0 | token-id check before and after |
| identity T-lazy | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/T-lazy.identity.json | 575 | sha256:56f403402825386ed06d78dc0ced238d856847a45fe787c1629ae5cd137c7ad6 | token-id check before and after |
| identity T-full | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/T-full.identity.json | 575 | sha256:3b20ecbafa4b4be8e60e33d6659d32dc289357fe4e31552b0714c5b12e0a41bd | token-id check before and after |
| identity T-lazy-G | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/T-lazy-G.identity.json | 555 | sha256:9e35028d4471fc38defc02b201036a1614734401bb2d21cfcc796d639fd21c17 | token-id check before and after |
| dev E answers | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/dev/planned_llm_english/answers | 12662765 | sha256:3af5ecf5efbc5fea688447df15231aabc1846cb9b2442c38dc9bb795ec997eed | 284 answers (gitignored) |
| dev T-lazy answers | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/dev/planned_llm_typed_lazy/answers | 7467854 | sha256:d78669deb577a547e144686daf2eef24e122f747c707e57674162b6130d0cf01 | 284 answers (gitignored) |
| dev T-full answers | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/dev/planned_llm_typed_full/answers | 7947329 | sha256:c06466b2db2678e6dd275c782e9aa0144e2808fb5bc29375d501b6d61bb26c1c | 284 answers (gitignored) |
| dev T-lazy-G answers | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/dev-gemma/planned_llm_typed_lazy/answers | 7086517 | sha256:d7193a768c935c5117dc7633789ee583ed99003d6927e76ff45916190a502046 | 284 answers, Gemma (gitignored) |
| authored baseline | docs/evaluation/experiments/harness-attribution-qwen-walkfix-2026-11-16/generic_composed/answers | 8653405 | sha256:b09095b78878b8ae18aa5be02bacf221a7f5597d1efee522d2f385ee40b63825 | G2/G4 dev baseline (hashed in EXP-2026-11-009) |
| EXP-2026-11-017 runs | docs/evaluation/experiments/bridge-guard-2026-11-19/variants/T-lazy.json | 5123430 | sha256:8ca16a577a35a9f766370f374b8531f741a14b229295e4a0f0700eec8c10d81d | paired baseline (as hashed in EXP-2026-11-017; its other arms likewise) |

If this experiment reads no raw output outside `docs/research/`, delete the
table and write one line: `No external artifacts: <why>` — the validator
rejects an empty table on a completed experiment.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
