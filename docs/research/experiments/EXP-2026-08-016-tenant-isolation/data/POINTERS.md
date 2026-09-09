# POINTERS — EXP-2026-08-016

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Isolation metrics | `docs/evaluation/isolation-2026-08-23/metrics.json` | 10682 | sha256:82d8fbf8b84e438ac3583bcfe50b598ab8d426df0562d56ad12b2c9d5677ce6a | Per-probe routing and per-source record counts under both selection rules |

`data/metrics.json` here is a copy of that file plus a top-level `manifest_metrics`
object added 2026-09-09 (RESULTS A-2) so the phase-1 gate figures, which were
never a file, are machine-readable; the sweep keys are unchanged and the pointed
file still verifies. **The pointed file is the pre-Q21 run** (14:02 on
2026-08-24): its `comparative.rows.attack_group` still shows the routing
regression that A-1 (17:23) reports repaired. No post-fix sweep output exists;
see ISSUES.

Phase 1's figures are not a file: `score_safety()` computes them from the
committed probe fixtures and the live cards, so they are reproduced by running
it rather than by reading an artifact.

## Reproducing

```bash
uv run python -m utils.specialists.evalset.score_safety
uv run python scripts/tri_compose.py --check
uv run python scripts/isolation_probes.py --out docs/evaluation/isolation-2026-08-23
```

Phase 2 needs all three sources live — `attack` on bolt://localhost:5456,
`capec` on ws://localhost:6455/gremlin, `identity` on bolt://localhost:5459 —
and a current `data-tri` composition. Both phases are deterministic and LLM-free.
