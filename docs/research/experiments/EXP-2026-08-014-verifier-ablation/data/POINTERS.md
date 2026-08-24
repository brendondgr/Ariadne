# POINTERS — EXP-2026-08-014

Large artifacts live outside `docs/research/`. This file is the only link
between this experiment and its raw run output, and every entry carries a hash.

## Committed run artifacts

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Sweep metrics | `docs/evaluation/ablation-2026-08-23/metrics-deterministic.json` | 6151 | sha256:cf76868ee0ff726f50aa2dbbabe39f9c1e0ca820b12813dc934b66f6f434d7eb | Per-bank and per-gate counts for all five conditions, as the sweep emitted them |
| Residual | `docs/evaluation/ablation-2026-08-23/residual-deterministic.json` | 3 | sha256:37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570 | The ambiguous claims a judge would have ruled on. Empty (`[]`) — no gate cut anything, so there is nothing to judge and the deferred half is closed rather than pending |

`data/metrics.json` in this folder is a byte-identical copy of the first row, so
the experiment is readable without leaving `docs/research/`.

## Reproducing

```bash
uv run python scripts/ablation_sweep.py \
  --out docs/evaluation/ablation-2026-08-23 --composer deterministic
```

Requires both graph backends loaded and verified
(`uv run main.py --dataset attack --graph verify`, likewise `capec`). No LLM and
no network beyond the local graph stack: the path is byte-reproducible, so a
re-run reproduces these files exactly.
