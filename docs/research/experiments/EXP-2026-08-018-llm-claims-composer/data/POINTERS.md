# POINTERS — EXP-2026-08-018

| Artifact | Path (repo-relative) | Bytes | SHA-256 |
|---|---|---:|---|
| Sweep metrics | `docs/evaluation/composer-2026-08-24/metrics.json` | 421786 | sha256:6cdbc906b8fe9f36b6fce68f0671a6258c169ed6619277fb1fc9183bab4583cd |

`data/metrics.json` here was a byte-identical copy until 2026-09-09; it is now
`{runs: [the four sweep objects, unchanged], manifest_metrics: {...}}` so the
manifest's aggregates are machine-readable (RESULTS A-1). It carries every
per-question row — composer used, fallback reason, claim and unsupported counts,
gold overlap and per-question latency — for all four runs. `wall_s_total` and
the per-row `elapsed_s` are **summed per-question latencies**, not elapsed wall
clock.

## Reproducing

```bash
uv run python scripts/composer_arm_sweep.py \
  --out docs/evaluation/composer-2026-08-24 --repeats 3 --workers 16
```

Needs both graph backends loaded and the LLM relay serving. **It will not
reproduce these numbers exactly**: the composer is nondeterministic, which is
what T4 measures, and this run predates the pinned seed added the same day. Run
EXP-2026-08-019 for the seeded conditions.
