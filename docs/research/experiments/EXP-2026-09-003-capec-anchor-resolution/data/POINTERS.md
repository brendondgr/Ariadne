# POINTERS — EXP-2026-09-003

Every hash below was re-verified on 2026-09-09 (A-1) and matches; the table
gained a Bytes column and one corrected label. Tree hashes cover the directory's
whole contents (`utils/research_record/hashing.py::sha256_tree`); regenerate
with `uv run python -m utils.research_record.hashing <path>`.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| post-fix answers (gitignored) | `docs/evaluation/experiments/capec-anchor-2026-09-03/deterministic/answers/` | 4327990 | `sha256:1a1102c400c6fa613b4b3743be6c3c3e3d776e0a03dbdc2b6c95dfc6323c3599` | 37 re-run answer artifacts, the "after" side |
| pre-fix answers (gitignored) | `docs/evaluation/experiments/expansion-2026-09-01/deterministic/answers/` | 47007195 | `sha256:c523e069d0c29f3679810c98e1d1398f252e3b51ac564e0c2866f6ddd74d21d3` | 572 answer files from the 2026-09-02 model-free run (EXP-2026-09-001 A-5's directory), the "before" side. The earlier label "EXP-2026-09-002's artifacts" was imprecise: 002's judged arms wrote to `expansion-judged-2026-09-01`, whose deterministic answers carry identical coverage values for these 37 ids (audit 2026-09-09) — A-1 |
| bank | `docs/evaluation/composition/bank/bank.json` | 1188163 | `sha256:ad99afb18934bd7db233c292d235a4350c332114c357ea624123031ff0ab434e` | unchanged since EXP-2026-09-002 preflight |

The two answer sets were produced against graph builds that differ on the ATT&CK
side; every question here is CAPEC-anchored. See ISSUES I-3.
