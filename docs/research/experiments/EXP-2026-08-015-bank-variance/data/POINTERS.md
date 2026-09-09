# POINTERS — EXP-2026-08-015

## Committed

| Artifact | Path (repo-relative) | Bytes | SHA-256 |
|---|---|---:|---|
| catalogue metrics | `docs/evaluation/variance-2026-08-23/catalogue/metrics.json` | 6979 | sha256:c23abf96e78b511e5617514d41457586e0628fc2d5ad71b71e9a78e3bda7e167 |
| identity metrics | `docs/evaluation/variance-2026-08-23/identity/metrics.json` | 4431 | sha256:893aa1a2c49539ea2961a7e1c96dfc8cdcce813e7061793d694a8b418b255e44 |
| catalogue banks, tree hash (10 × bank.json + anchors.json + authored.json + CARD.md; re-pinned 2026-09-09, A-2) | `docs/evaluation/variance-2026-08-23/banks` | 621212 | sha256:89c0efc04005655a6dcb3e666359dc38ddf10853a59872bf7cd22c5e41398ee8 |
| identity bank 9101 (re-pinned 2026-09-09, A-2) | `docs/evaluation/variance-2026-08-23/identity/bank9101/bank.json` | 23105 | sha256:e00c6198a1fa90b4231213a7c637751281235bbeb2e11f92d7773e0d9a1052c9 |
| identity bank 9102 (re-pinned 2026-09-09, A-2) | `docs/evaluation/variance-2026-08-23/identity/bank9102/bank.json` | 21857 | sha256:5a268a1344f214b5e8a87d5f5613be16720f24720862ea6f57b63f5a5e8f6085 |
| identity bank 9103 (re-pinned 2026-09-09, A-2) | `docs/evaluation/variance-2026-08-23/identity/bank9103/bank.json` | 15694 | sha256:6023ad61b9aadc1807c4b1b65b9a7b705273326f1e4c9af3f0d41a9a98d32073 |
| identity bank 9104 (re-pinned 2026-09-09, A-2) | `docs/evaluation/variance-2026-08-23/identity/bank9104/bank.json` | 15688 | sha256:ffdaee464cb627039e0de7bbc6bfc99455de14c0f408d8663a3f85ee3f7932a8 |
| identity bank 9105 (re-pinned 2026-09-09, A-2) | `docs/evaluation/variance-2026-08-23/identity/bank9105/bank.json` | 15554 | sha256:674b720fc483f3e67418291d235d09237600b76325987104935e7baca34b43b9 |
| identity bank 9106 (re-pinned 2026-09-09, A-2) | `docs/evaluation/variance-2026-08-23/identity/bank9106/bank.json` | 14828 | sha256:35db495c6d9f0f3ebd2a15a4f7100e21902d2223b957029c0eea54214921559e |
| identity bank 9107 (re-pinned 2026-09-09, A-2) | `docs/evaluation/variance-2026-08-23/identity/bank9107/bank.json` | 16507 | sha256:30d5ac3e8c6e91bc8e494298367d7cef5d6c1a036380ce623024a6a3445853cf |
| identity bank 9108 (re-pinned 2026-09-09, A-2) | `docs/evaluation/variance-2026-08-23/identity/bank9108/bank.json` | 17159 | sha256:6397cc3cae73b47694e2a87ba3512b0f43f276aed22231efc33551b9572b6062 |
| identity bank 9109 (re-pinned 2026-09-09, A-2) | `docs/evaluation/variance-2026-08-23/identity/bank9109/bank.json` | 16124 | sha256:fcb9f51e009a6ca27c983cbc9d462257b4722c4cf5b8bcfc4f7808180c98b081 |
| identity bank 9110 (re-pinned 2026-09-09, A-2) | `docs/evaluation/variance-2026-08-23/identity/bank9110/bank.json` | 16514 | sha256:7df2d59d21e1f947507fdb876751befc14805bb06c456fd0a4e49ce48df01e1b |

`data/metrics.json` here is both populations in one object.

The **banks are committed** — they are the experiment's input and what a re-run
must reproduce. Until 2026-09-09 the two bank rows carried *set digests*
(filenames sorted, then name+contents concatenated: `sha256:6ac87b79…` for the
catalogue set, `sha256:f1b8bf75…` for the identity set) against the directory
path, which the validator re-hashes as a tree and so could never match. They
are replaced by one tree hash over `banks/` (all four files per bank are
committed) and one file hash per identity `bank.json` (the identity bank
directories also hold gitignored `sweep_state.json`, so a tree hash there would
not travel). The bank contents are unchanged; the old digests still reproduce
under their own definition (RESULTS A-2).

`data/metrics.json` carries the pre-fix sweep output plus a `manifest_metrics`
object (added 2026-09-09) holding the current manifest values, including the
post-Q22 catalogue figures for which no sweep artifact survives (ISSUES I-4).


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
