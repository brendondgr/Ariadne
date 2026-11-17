# POINTERS — EXP-2026-11-013

**Everything this experiment read and wrote is committed in this folder.** It is about 9 MB of
JSON lines. The items and every model call stay beside the scores, so each number can be
recomputed without the servers.

- **The banks it reads** are the Sonnet-worded tuning banks, `card-sonnet-2026-11-16-*-tuning`.
  They are hashed in EXP-2026-11-012's POINTERS. The sealed held-out banks were not read.
- **Each hash below is of the file as scored.** A mismatch later means a run was appended to,
  or edited.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| items | `docs/research/experiments/EXP-2026-11-013-era2-decision-models/data/items.jsonl` | 2,684,596 | `sha256:5e5be419b99d2f3825d0a27c67bad52dd696f31d09be2147b0169da684d07680` | 1,883 decision items, Phases A–C |
| `qwen_reason` runs | `docs/research/experiments/EXP-2026-11-013-era2-decision-models/data/runs/qwen_reason.jsonl` | 1,212,335 | `sha256:5c7f8d1933337eea0a2add3931f6e175d6c91bfab382c10ac3774a9d7ec9371f` | 1,883 calls, first option order |
| `qwen_prob` runs | `docs/research/experiments/EXP-2026-11-013-era2-decision-models/data/runs/qwen_prob.jsonl` | 1,852,562 | `sha256:71efa85948c4088e83e6976ff48aa439cf160ce889793ef51225b12bf07937e2` | 3,766 calls, two option orders |
| `pplx` runs | `docs/research/experiments/EXP-2026-11-013-era2-decision-models/data/runs/pplx.jsonl` | 1,861,185 | `sha256:ed30a71b53abb0a5521427e9c9d58bfa944e55759bb627b61f7ca6feff92e722` | 3,766 calls, two option orders |
| `d3` runs | `docs/research/experiments/EXP-2026-11-013-era2-decision-models/data/runs/d3.jsonl` | 1,604,388 | `sha256:6569a70c1136e685668cb3b4b534bfb57c92c4320d4626fa14b6fdb7f462bca7` | 3,766 calls, two option orders (10 refused, ISSUES) |
