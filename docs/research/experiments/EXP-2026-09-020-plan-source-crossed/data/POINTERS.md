# POINTERS — EXP-2026-09-020

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — a path alone does not say whether the
directory still holds what it held when the number was computed.

All four cells were written to one root, back to back, on one tree. That is the
whole point of the design: a difference between any two of them cannot be the
repository moving underneath the comparison.

Hashes are over each directory's files in sorted path order, **sidecars
included** — `utils.research_record.hashing.sha256_tree` folds in every file
under the root and performs no exclusion (`EXP-2026-09-019` I-10). None of these
directories has been graded; judging one would change its hash, and the row
would then need re-hashing with the pass named.

| Artifact | Path (repo-relative) | Files | Bytes | SHA-256 | What it is |
|---|---|---:|---:|---|---|
| templates + authored plan | `docs/evaluation/experiments/plan-source-2026-09-14/deterministic/answers` | 284 | 4062854 | `sha256:aec93332e5a99593784a6edbe4637047478850873896878bb45f69e4bac45e81` | 2x2 cell: the shipped engine at the plan source every headline uses |
| primitives + authored plan | `docs/evaluation/experiments/plan-source-2026-09-14/generic_composed/answers` | 284 | 8654457 | `sha256:13697453f6ac7e630c45d8ff14fdf7811db26c7a11166ba93b1ae5b931e0d8e0` | 2x2 cell: EXP-2026-09-018's winning configuration, re-run on this tree |
| templates + real planner | `docs/evaluation/experiments/plan-source-2026-09-14/deterministic_planned/answers` | 284 | 19778759 | `sha256:fb974f4f25df2563e5d258459d99b129950479cd0d0d373570bbc4061386bac4` | 2x2 cell: **what `app.py` actually does** — the cell that did not exist |
| primitives + real planner | `docs/evaluation/experiments/plan-source-2026-09-14/generic_planned/answers` | 284 | 5964491 | `sha256:133324b3f5f0070a99cde90c0edd4c73958062f5f4bdac0207f98e5464f3009e` | 2x2 cell: what `SPECIALIST_GENERIC_ONLY=true` in production would give |
| question bank (input) | `docs/evaluation/composition/bank/bank-dev.json` | 1 | 573495 | `sha256:a4ca6702029cae7784574b0307b9f76d4718a039f3254f2c0ff708a2fa1a4119` | the 284 dev questions, identical across all four cells |

The committed derivative is `data/metrics.json`, built by `data/build_metrics.py`
from the directories above. No number in `RESULTS.md` or `manifest.yaml` is typed
rather than read.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
