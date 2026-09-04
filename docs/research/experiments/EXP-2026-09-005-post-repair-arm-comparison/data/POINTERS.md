# POINTERS — EXP-2026-09-005

| Artifact | Path (repo-relative) | SHA-256 | What it is |
|---|---|---|---|
| deterministic answers + judgments | `docs/evaluation/experiments/post-repair-2026-09-03/deterministic/answers/` | `sha256:5c0e8d63bca98dd9a220625288b57345cbcea3bf9a7ed60297c05e175e1aea1e` | 284 answers, 568 judgments (two counterbalanced passes) |
| generic answers + judgments | `docs/evaluation/experiments/post-repair-2026-09-03/generic/answers/` | `sha256:a41681361ddd2a5243bb5121ab203781455fb15eb5af44da87541f2b02fc09bc` | 284 answers, 568 judgments |
| judged rollup | `docs/evaluation/composition/bank/post-repair-judged.json` | `sha256:3c628d27da79620b4703d9f2872a90b1923bab9b6cfd9efbdad6b172c48e0161` | per-arm mean correctness, per-pass means, denominators |
| model-free scores, deterministic | `docs/evaluation/composition/bank/post-repair-deterministic.json` | `sha256:4d3a79c715742f7e16563dd8b2ae9e52a40fd24c17cf5ef6e8570a4191550277` | recall by tier, split, direction, register, width, shape |
| model-free scores, generic | `docs/evaluation/composition/bank/post-repair-generic.json` | `sha256:1be6d7bf70fafe76209d60070d39a9cbf188ec0246d43c5c8c86f01eb8fdd14a` | the same, for the generic arm |
| bank | `docs/evaluation/composition/bank/bank.json` | `sha256:ad99afb18934bd7db233c292d235a4350c332114c357ea624123031ff0ab434e` | unchanged since the EXP-2026-09-002 preflight |

Tree hashes cover the directory's whole contents; regenerate with
`uv run python -m utils.research_record.hashing <path>`.
