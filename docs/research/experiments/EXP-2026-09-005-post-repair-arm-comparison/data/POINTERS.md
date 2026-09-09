# POINTERS — EXP-2026-09-005

**Re-hashed 2026-09-09 (A-2).** The two answer directories were pinned on
2026-09-03 with 852 files each (284 answers + 284 `.judgment.json` + 284
`.judgment.pass2.json`). Later experiments wrote gemma grading sidecars into
the same directories — `.judgment.gemma.json`, `.gemma2`, `.gemma_r3` …
`.gemma_r10` (EXP-2026-09-008 / EXP-2026-09-012) — so the tree hash moved. The
original 852 files in each directory are **unchanged**: a tree hash restricted
to them reproduces the 2026-09-03 hashes exactly (`sha256:5c0e8d63…` and
`sha256:a41681361…`; verified 2026-09-09). Tree hashes cover the directory's
whole contents (`utils/research_record/hashing.py::sha256_tree`); regenerate
with `uv run python -m utils.research_record.hashing <path>`.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| deterministic answers + judgments (gitignored) | `docs/evaluation/experiments/post-repair-2026-09-03/deterministic/answers/` | 24872613 | `sha256:e3db4bb1c730efd64183249f8ac4d849d1777a1c026b5573e45208ea4f46440f` | 3,692 files: the original 852 (284 answers, 568 qwen judgments, two counterbalanced passes — recompute 0.4946 exactly) + 2,840 later gemma sidecars (2,839 `.judgment.gemma*.json` + 1 `.gemma_r6.error.txt`) not used here. Was `sha256:5c0e8d63bca98dd9a220625288b57345cbcea3bf9a7ed60297c05e175e1aea1e` over the 852 |
| generic answers + judgments (gitignored) | `docs/evaluation/experiments/post-repair-2026-09-03/generic/answers/` | 9286482 | `sha256:3863fe3a81521bd5e3bbfc4d5f45ba6de6f6e2e9572e15e0cb54ad279cb6efd5` | 3,408 files: the original 852 (recompute 0.6569 exactly) + 2,556 later gemma sidecars not used here. Was `sha256:a41681361ddd2a5243bb5121ab203781455fb15eb5af44da87541f2b02fc09bc` over the 852 |
| judged rollup | `docs/evaluation/composition/bank/post-repair-judged.json` | 263 | `sha256:3c628d27da79620b4703d9f2872a90b1923bab9b6cfd9efbdad6b172c48e0161` | per-arm mean correctness, per-pass means, denominators |
| model-free scores, deterministic | `docs/evaluation/composition/bank/post-repair-deterministic.json` | 125775 | `sha256:4d3a79c715742f7e16563dd8b2ae9e52a40fd24c17cf5ef6e8570a4191550277` | recall by tier, split, direction, register, width, shape. Its `recall_before` column equals `recall` and does **not** carry the pre-repair values (A-2 §2) |
| model-free scores, generic | `docs/evaluation/composition/bank/post-repair-generic.json` | 124459 | `sha256:1be6d7bf70fafe76209d60070d39a9cbf188ec0246d43c5c8c86f01eb8fdd14a` | the same, for the generic arm |
| pre-repair recall baseline | `docs/research/experiments/EXP-2026-09-007-holdout-spend/data/recall-summary.json` | 4904 | `sha256:dcd633ec5aeb4d2faf9c607caf846f7176b7ea4f09d0192fb8cc1545d28ae389` | `pooled.dev_pre` **0.4492**, `dev_post` 0.5176, `dev_delta` 0.0684; `reweighted.dev_pre` 0.5170 — the only place the 0.4492 behind `deterministic_recall_move_vs_prerepair` is stored (A-2 §2, ISSUES I-8). Computed by `scripts/score_bank.py --rescore-property-gold @ 96a72d4` over `expansion-2026-09-01` (pre) and this experiment's `post-repair-2026-09-03` (post) |
| pre-repair answers (gitignored) | `docs/evaluation/experiments/expansion-2026-09-01/deterministic/answers/` | 47007195 | `sha256:c523e069d0c29f3679810c98e1d1398f252e3b51ac564e0c2866f6ddd74d21d3` | the 572 model-free answers the 0.4492 was re-scored from |
| bank (dev half) | `docs/evaluation/composition/bank/bank-dev.json` | 573495 | `sha256:a4ca6702029cae7784574b0307b9f76d4718a039f3254f2c0ff708a2fa1a4119` | the 284 questions both arms answered |
| bank | `docs/evaluation/composition/bank/bank.json` | 1188163 | `sha256:ad99afb18934bd7db233c292d235a4350c332114c357ea624123031ff0ab434e` | unchanged since the EXP-2026-09-002 preflight |
