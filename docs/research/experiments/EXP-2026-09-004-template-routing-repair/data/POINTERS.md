# POINTERS — EXP-2026-09-004

| Artifact | Path (repo-relative) | SHA-256 | What it is |
|---|---|---|---|
| post-fix answers | `docs/evaluation/experiments/template-routing-2026-09-03/deterministic/answers/` | `sha256:eedb8ac5977aafe6ec703c32136555460498a704948e0fc8fdd280f6e637cdb0` | 32 re-run answer artifacts, the "after" side |
| pre-fix answers | `docs/evaluation/experiments/expansion-2026-09-01/deterministic/answers/` | `sha256:c523e069d0c29f3679810c98e1d1398f252e3b51ac564e0c2866f6ddd74d21d3` | EXP-2026-09-002's artifacts, the "before" side |
| bank | `docs/evaluation/composition/bank/bank.json` | `sha256:ad99afb18934bd7db233c292d235a4350c332114c357ea624123031ff0ab434e` | unchanged since EXP-2026-09-002 preflight |

Tree hashes cover the directory's whole contents; regenerate with
`uv run python -m utils.research_record.hashing <path>`.

The two answer sets did not see identical ATT&CK graphs — see ISSUES I-5.
