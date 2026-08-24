# POINTERS — EXP-2026-08-019

| Artifact | Path (repo-relative) | Bytes | SHA-256 |
|---|---|---:|---|
| metrics-seeded-w16.json | `docs/evaluation/determinism-2026-08-24/metrics-seeded-w16.json` | 301313 | sha256:b1821eede2561197b337887edba58237c61effca7e07ed6df159efa8d778b067 |
| metrics-seeded-w32.json | `docs/evaluation/determinism-2026-08-24/metrics-seeded-w32.json` | 332107 | sha256:4890defe2f564e01ee15bdb20a0dde07870924c718f2153898dd1711f758562e |
| condition A (reused) | `docs/evaluation/composer-2026-08-24/metrics.json` | 421786 | sha256:6cdbc906b8fe9f36b6fce68f0671a6258c169ed6619277fb1fc9183bab4583cd |

`data/metrics.json` here holds conditions B and D in one object. **Condition A is
not duplicated** — it is EXP-2026-08-018's LLM arm, reused because it ran before
the seed landed, and is pinned above by the same hash that experiment records.

## Reproducing

```bash
uv run python scripts/composer_arm_sweep.py --out docs/evaluation/determinism-2026-08-24 \
  --repeats 3 --arms llm_claims --workers 16 --tag seeded-w16
uv run python scripts/composer_arm_sweep.py --out docs/evaluation/determinism-2026-08-24 \
  --repeats 3 --arms llm_claims --workers 32 --tag seeded-w32
```

**It will not reproduce these numbers exactly** — that is the subject of the
experiment. What should reproduce is the *direction*: higher concurrency raises
per-request latency and timeout-induced fallbacks on this stack.
