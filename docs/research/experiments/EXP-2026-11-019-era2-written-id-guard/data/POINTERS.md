# POINTERS — EXP-2026-11-019

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash.**

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| variant subset | docs/evaluation/experiments/written-id-guard-2026-11-20/variants/variants.json | 4091 | sha256:cf7a6ffd227979860c77fc0319b5a236f1dc7be82964acfee1e0636e407669c4 | 22 items: 10 targets, 12 controls (selection.json beside it) |
| reference capture | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/reference.json | 350660 | sha256:dc1fbf131f49dae6e5ad01c475bb23b0304d296511ecb90fd6835310b6988670 | EXP-2026-11-018's R reference, used unchanged |
| arm T-lazy | docs/evaluation/experiments/written-id-guard-2026-11-20/variants/T-lazy.json | 138573 | sha256:a5416597762f613ee4034f9e5aa65ae56c8fcd85238d5a3eb348c74d1af79cfa | 22 rows, Qwen |
| arm T-lazy-G | docs/evaluation/experiments/written-id-guard-2026-11-20/variants/T-lazy-G.json | 120143 | sha256:b1b026d5371dec985fcb590bbb4d169a1cca679e61d68bd47fb33a749cfdaea3 | 22 rows, Gemma |
| identity T-lazy | docs/evaluation/experiments/written-id-guard-2026-11-20/variants/T-lazy.identity.json | 575 | sha256:ca2431873557c5f3c3e820c173ac171bfbf1a9bf01749eb34982aef5e8986836 | token-id check before and after |
| identity T-lazy-G | docs/evaluation/experiments/written-id-guard-2026-11-20/variants/T-lazy-G.identity.json | 555 | sha256:e127b759bac4b020a69b6f23e5754d7f9c326d9824aa15e34c6c918d55e907f4 | token-id check before and after |
| dev T-lazy answers | docs/evaluation/experiments/written-id-guard-2026-11-20/dev/planned_llm_typed_lazy/answers | 319312 | sha256:ac3fe814233af740e94cde220497a34a58f7e1b4ecff4d4fa318bd86fa858efd | 15 answers (gitignored) |
| dev T-full answers | docs/evaluation/experiments/written-id-guard-2026-11-20/dev/planned_llm_typed_full/answers | 333733 | sha256:96500fde8efb0865ec684847093fbf7d5c90a39ab61bf8df597414154fe2d269 | 15 answers (gitignored) |
| dev T-lazy-G answers | docs/evaluation/experiments/written-id-guard-2026-11-20/dev-gemma/planned_llm_typed_lazy/answers | 303233 | sha256:0fc739298f5074b7e69b1b51989d90e5feef19263ad30918e528e40ee2d15ac7 | 15 answers, Gemma (gitignored) |
| EXP-2026-11-018 runs | docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/T-lazy-G.json | 4618498 | sha256:19153942e47f99ca4861001d86457acd3dd9b1d95116688bf6d50a6716171164 | the before side (as hashed in EXP-2026-11-018; its other arms likewise) |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
