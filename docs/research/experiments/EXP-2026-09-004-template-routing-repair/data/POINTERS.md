# POINTERS — EXP-2026-09-004

Every hash below was re-verified on 2026-09-09 (A-1) and matches; the table
gained a Bytes column. Tree hashes cover the directory's whole contents
(`utils/research_record/hashing.py::sha256_tree`); regenerate with
`uv run python -m utils.research_record.hashing <path>`.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| post-fix answers (gitignored) | `docs/evaluation/experiments/template-routing-2026-09-03/deterministic/answers/` | 4568210 | `sha256:eedb8ac5977aafe6ec703c32136555460498a704948e0fc8fdd280f6e637cdb0` | 32 re-run answer artifacts, the "after" side |
| pre-fix answers (gitignored) | `docs/evaluation/experiments/expansion-2026-09-01/deterministic/answers/` | 47007195 | `sha256:c523e069d0c29f3679810c98e1d1398f252e3b51ac564e0c2866f6ddd74d21d3` | 572 answer files from the 2026-09-02 model-free run (EXP-2026-09-001 A-5; EXP-2026-09-002 read the same run), the "before" side |
| bank | `docs/evaluation/composition/bank/bank.json` | 1188163 | `sha256:ad99afb18934bd7db233c292d235a4350c332114c357ea624123031ff0ab434e` | unchanged since EXP-2026-09-002 preflight |

The two answer sets did not see identical ATT&CK graphs — see ISSUES I-5.
