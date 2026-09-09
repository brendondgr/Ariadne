# POINTERS — EXP-2026-09-006

Filled 2026-09-09 (A-1); the table was the unfilled template until then. This
experiment ran no pipeline: it wrote grading sidecars beside 510 frozen answers
and rolled them up. Every directory below is gitignored raw output; the roll-up
and state files are committed in this folder. Directories carry a tree hash
over their **whole** contents (`utils/research_record/hashing.py::sha256_tree`)
— including sidecars from other experiments (`.judgment.json`, `.c015`,
`.cross`, `.qwen38*`, `.bld*`, `.c022rev*`) that share the directories — so a
later grading pass anywhere in a directory will move its hash; the description
says which files this experiment wrote and which it read. Regenerate with
`uv run python -m utils.research_record.hashing <path>`.

This experiment **wrote** 1,320 sidecars: `.judgment.g31.json` + `.g31p2`
(gemma4-31B-mtp, positions 1 and 2) beside all 510 answers, and
`.judgment.q38b.json` + `.q38bp2` (qwen38-27B-v2) beside the 150 composerfix
answers. Its qwen figures for the two banks **read** the five
`.judgment.qwen38{,r2,r3,r4,r5}.json` sidecars EXP-2026-08-021 wrote; the
historical column reads the unsuffixed `.judgment.json` and `.c015` sidecars
from August (`rollup.json` → `graders`).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---:|---|---|
| bank19 deterministic | `docs/evaluation/experiments/bank20260819/deterministic/answers` | 828548 | `sha256:e034f420eb44ffe349146654dae18ce0e172b4e99aa7eff9dbddf9a909323d35` | 30 answers; wrote `.g31`/`.g31p2` (30 + 30); read `.qwen38*` ×5 |
| bank19 generic | `docs/evaluation/experiments/bank20260819/generic/answers` | 853113 | `sha256:0219150fb82b5233e0425e5d4ab4279cc47ae5bafa533f95cd3498615b1a0d73` | as above |
| bank19 generic_composed | `docs/evaluation/experiments/bank20260819/generic_composed/answers` | 827843 | `sha256:62fc5212910b62d4cce9fe6a96d38eb864c8cff6e4319975269a2bf4b2140e5d` | as above (`.qwen38r3` has 29 + 1 `.error.txt`, a pre-existing dropout) |
| bank19 gold_loop_llm | `docs/evaluation/experiments/bank20260819/gold_loop_llm/answers` | 750191 | `sha256:d88e7df454711e8a75a4830c98c708dee068fa3647e1df8712558715da7b7302` | as above |
| bank19 llm_query | `docs/evaluation/experiments/bank20260819/llm_query/answers` | 419976 | `sha256:4034e67964f33bbdbd99f4b85874ff82fbff13e48527d4a1b9722241f78b806a` | as above |
| bank19 merged | `docs/evaluation/experiments/bank20260819/merged/answers` | 782507 | `sha256:0ce6f296098c29a3cebfbab77bee3b85e44e3d92e29ffd38cb83d820a2acb4ec` | as above (C-022's merged side) |
| bank20 deterministic | `docs/evaluation/experiments/bank20260820/deterministic/answers` | 893664 | `sha256:264c26e3ffe0cdc9e2f715cb1ad6d3b5fde1e238d5302d7e695bc74bc8e112fa` | 30 answers; wrote `.g31`/`.g31p2`; read `.qwen38*` (no `r4` in this cell) |
| bank20 generic | `docs/evaluation/experiments/bank20260820/generic/answers` | 883220 | `sha256:f7c6a193a8ea997e77805b4cd4dc555d71009b48435ba2a58b4bc40052c6fd61` | as above |
| bank20 generic_composed | `docs/evaluation/experiments/bank20260820/generic_composed/answers` | 854072 | `sha256:ba89f20e3a52b2be2e41840ab6dc4f94982c5798eba78cc647e1c0d415838ea5` | as above; the reversed pair's second member (I-7) |
| bank20 gold_loop_llm | `docs/evaluation/experiments/bank20260820/gold_loop_llm/answers` | 823306 | `sha256:ca5947c6a5e9d58352f9203b47e269a63f341306ed0d9a6c228c9ed0299ced36` | as above; the reversed pair's first member (I-7) |
| bank20 llm_query | `docs/evaluation/experiments/bank20260820/llm_query/answers` | 387875 | `sha256:3f4fdcd80e603c65009cb80dab818f19c4252ea65a2283efab1f1f54b95fe461` | as above |
| bank20 merged | `docs/evaluation/experiments/bank20260820/merged/answers` | 873769 | `sha256:ff221cf6fbaeb37fb37e00c7dbfab00fbb831be5dd17cf82daee2314006ceeb5` | as above |
| composerfix-dev (catalogue, 120) | `docs/evaluation/experiments/composerfix-dev/deterministic/answers` | 3845977 | `sha256:d15b78a1b1c2e55cd5311f062c8f34742a954fb5cb5db91c143b9a01175766a2` | 120 answers; wrote `.g31`/`.g31p2`/`.q38b`/`.q38bp2` (120 each; 1 `.g31.error.txt` from the I-2 400, cleared); read the August `.judgment.json` (119 + 1 `.error.txt`, I-3) |
| composerfix-holdout (blind, 30) | `docs/evaluation/experiments/composerfix-holdout/deterministic/answers` | 784141 | `sha256:86490c6e63cab7fb27dbc515f5f82666f25d4acb6da24e4c8b02ac941570eaf6` | 30 answers; wrote the same four suffixes (30 each; `H-SUB-01.judgment.q38b.error.txt` remains beside the retried `.q38b.json`, I-2 / A-1) |
| dev llm_query, gemma (not in the 510) | `docs/evaluation/experiments/llm-query-split-2026-09-05/llm_query/answers` | 3108206 | `sha256:9bc9d4c721705de9fcff67ccc21193ed8f16b94cad745462a2beadada0cf0fba` | `regrade-state-gemma.json` records the gemma track also grading these 284 dev `llm_query` answers (`.gemma`/`.gemma2`, 284 + 284) in the same window. **Not part of this experiment's rollup**; consumed by EXP-2026-09-007 A-2's dev gemma figures. Listed because the state file names it |
| regrade driver | `scripts/cross_family_regrade.py` | 14321 | `sha256:a2c771c2f21e75526586f2b41938a21be5ac9b85df2f7c4e574229a90050d021` | writes the sidecars; one state file per track after I-4 (as at HEAD) |
| rollup script | `scripts/cross_family_rollup.py` | 19009 | `sha256:0ba73a6280227cc52d7646c8c52ed4329d1a6105c423f9067771f0b93fbd22c7` | reads sidecars only, never a state file; the audit re-ran it on 2026-09-09 and reproduced `rollup.json` with no differences (as at HEAD) |
| rollup (committed) | `docs/research/experiments/EXP-2026-09-006-cross-family-august-regrade/data/rollup.json` | 16482 | `sha256:c50f0ebd37bf805f04383668b7b7873b26c3df87fc28c9b98a1018ff9ab025f7` | every manifest value; last updated `2bddfd9` |
| state, gemma track (committed) | `docs/research/experiments/EXP-2026-09-006-cross-family-august-regrade/data/regrade-state-gemma.json` | 2708 | `sha256:3a33bd1c9081be5d0086bad3ec90940beb07e17a133bd6eb99040cdaa0839271` | 6 cells, started 12:22, last finished 13:36 |
| state, qwen track (committed) | `docs/research/experiments/EXP-2026-09-006-cross-family-august-regrade/data/regrade-state-qwen.json` | 1812 | `sha256:499ec8cf04851fdd4e6494cf52dee668d2754e1d99dbcce803e647f778005200` | 4 cells, started 12:06; three report `attempted: 0` because the sidecars pre-dated the per-track file (I-4, I-8) |
