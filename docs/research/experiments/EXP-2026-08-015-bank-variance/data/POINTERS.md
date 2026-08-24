# POINTERS — EXP-2026-08-015

## Committed

| Artifact | Path (repo-relative) | Bytes | SHA-256 |
|---|---|---:|---|
| catalogue metrics | `docs/evaluation/variance-2026-08-23/catalogue/metrics.json` | 6979 | sha256:c23abf96e78b511e5617514d41457586e0628fc2d5ad71b71e9a78e3bda7e167 |
| identity metrics | `docs/evaluation/variance-2026-08-23/identity/metrics.json` | 4431 | sha256:893aa1a2c49539ea2961a7e1c96dfc8cdcce813e7061793d694a8b418b255e44 |
| catalogue `banks/bank9*/bank.json` (set digest, 10 files) | `docs/evaluation/variance-2026-08-23/` | — | sha256:6ac87b79c9a5aad6ab5dd9ce834f735e87e1f55657daa7fb8a2abae8c4baefe6 |
| identity `identity/bank9*/bank.json` (set digest, 10 files) | `docs/evaluation/variance-2026-08-23/` | — | sha256:f1b8bf7551132e1e4c9785299024a42976e7addf91f7be69ed08e90b792a11ea |

`data/metrics.json` here is both populations in one object.

The **banks are committed** — they are the experiment's input and what a re-run
must reproduce. Their set digests (filenames sorted, then name+contents
concatenated) pin the *set* rather than one file, and are folded into the table
above.


## Not committed

The per-question run trees — `catalogue/runs/**` and
`identity/bank9*/sweep_state.json`, ~9 MB across 20 bank-runs — are gitignored,
matching how `docs/evaluation/experiments` is already handled. They are
regenerable: both arms are LLM-free and byte-reproducible given a bank.

## Reproducing

```bash
uv run python scripts/variance_sweep.py --population catalogue --out docs/evaluation/variance-2026-08-23
uv run python scripts/variance_sweep.py --population identity  --out docs/evaluation/variance-2026-08-23
```

Needs ATT&CK on bolt://localhost:5456, CAPEC on ws://localhost:6455/gremlin and
the identity tenant on bolt://localhost:5459, all loaded and verified. Add
`--skip-runs` to re-score existing run trees without re-running.

**Redrawing the banks will not reproduce these questions** — the Author is
nondeterministic. It *will* reproduce the anchors: draws are seeded and
`utils/specialists/evalset/drawn_anchors.json` is committed.
