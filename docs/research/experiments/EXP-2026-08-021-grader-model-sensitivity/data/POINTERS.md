# POINTERS — EXP-2026-08-021

Raw judgments live beside the answers they grade, under
`docs/evaluation/experiments/`, which is git-ignored per `D-007`. Each hash is
the SHA-256 of every judgment file for that pass, concatenated in sorted path
order; the command that reproduces it is in [`../RESULTS.md`](../RESULTS.md) §8.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Pass 1 | `docs/evaluation/experiments/{bank20260819,bank20260820}/*/answers/*.judgment.qwen38.json` | 302307 | sha256:6d76678149e381d326a8d20c93e3fd1a52c7450a5b03344cdbaf6da4a16752e8 | 360 judgments, 0 errored |
| Pass r2 | `docs/evaluation/experiments/{bank20260819,bank20260820}/*/answers/*.judgment.qwen38r2.json` | 301819 | sha256:22a5a86821acbf469eed33d366807d5e8ea7f04c5a754053ad4eafb4c6c5e776 | 359 judgments, 1 errored |
| Pass r3 | `docs/evaluation/experiments/{bank20260819,bank20260820}/*/answers/*.judgment.qwen38r3.json` | 299688 | sha256:a1004f44918745963ff52e236dbfd0a3beab4950681941943b8bc5bec2b6abb0 | 357 judgments, 3 errored |
| Pass r4 | `docs/evaluation/experiments/{bank20260819,bank20260820}/*/answers/*.judgment.qwen38r4.json` | 299539 | sha256:b1ceba83379cf8e792f74aa7f64f9956aaad05ecd00de01fcdf19b8f3f6ac2b7 | 358 judgments, 2 errored |
| Pass r5 | `docs/evaluation/experiments/{bank20260819,bank20260820}/*/answers/*.judgment.qwen38r5.json` | 304419 | sha256:42e2f439ae035fbb3ebc99934ffa259219b71b11279fb78888673d14cead0608 | 360 judgments, 0 errored |

**Reference passes compared against**, both produced 2026-08-19..21 by an
**unidentified** model (`Q12`): `.judgment.json` (base) for the four
`EXP-2026-08-008` arms, `.judgment.c015.json` for the `EXP-2026-08-009` pair.
Each has **n = 1**. RESULTS.md §3 describes its offsets as five-sample means
against a single sample; they are in fact the **pass-1** candidate-minus-reference
offsets (RESULTS A-2, `data/metrics.json` › `h5_offsets` carries both bases).

`data/metrics.json` was created 2026-09-09 (A-2) from `scripts/grader_repeats.py
--out` over the files above, plus the calibration and H5 offsets recomputed from
the sidecars, plus the manifest values.

**Preserved before this experiment ran:** the Ornith-era calibration artifacts at
`docs/evaluation/experiments/holdout-v1/deterministic/answers/*.judgment.local.pre-qwen38.json`
(30 files). `calibrate()` hardcodes `force=True` and would have overwritten them;
they are the only evidence behind the recorded r = 0.9275. See `ISSUES.md` I-1.
