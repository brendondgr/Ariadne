# POINTERS — EXP-2026-09-003

| Artifact | Path (repo-relative) | SHA-256 | What it is |
|---|---|---|---|
| post-fix answers | `docs/evaluation/experiments/capec-anchor-2026-09-03/deterministic/answers/` | `sha256:1a1102c400c6fa613b4b3743be6c3c3e3d776e0a03dbdc2b6c95dfc6323c3599` | 37 re-run answer artifacts, the "after" side |
| pre-fix answers | `docs/evaluation/experiments/expansion-2026-09-01/deterministic/answers/` | `sha256:c523e069d0c29f3679810c98e1d1398f252e3b51ac564e0c2866f6ddd74d21d3` | EXP-2026-09-002's artifacts, the "before" side |
| bank | `docs/evaluation/composition/bank/bank.json` | `sha256:ad99afb18934bd7db233c292d235a4350c332114c357ea624123031ff0ab434e` | unchanged since EXP-2026-09-002 preflight |

The two answer sets were produced against graph builds that differ on the ATT&CK
side; every question here is CAPEC-anchored. See ISSUES I-3.

Tree hashes cover the directory's whole contents; regenerate with
`uv run python -m utils.research_record.hashing <path>`.
