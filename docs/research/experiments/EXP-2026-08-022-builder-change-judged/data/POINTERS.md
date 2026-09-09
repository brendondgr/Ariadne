# POINTERS — EXP-2026-08-022

Answers and judgments live under `docs/evaluation/experiments/`, git-ignored
per `D-007`. Both answer sets are **LLM-free and byte-reproducible**: the
deterministic arm has no model in it, so the two conditions differ only in
builder revision. Each hash is the SHA-256 of the matching files concatenated
in sorted path order; the commands are in [`../RESULTS.md`](../RESULTS.md) §8.

The four answer-directory rows were re-pinned on 2026-09-09 (RESULTS A-1) with
`utils.research_record.hashing` tree hashes, because the validator hashes a
directory as a tree (path + content of every file) and the original rows
recorded a digest over the 30 answer files only. The answer files are
unchanged — their 30-file digests still reproduce, as noted per row. The tree
hashes of the two `bank2026*` directories will move again whenever another
experiment adds a grading pass beside those answers; the judgment-set rows
below (glob paths) are the stable pins for this experiment's own gradings.

`data/metrics.json` was created 2026-09-09 (A-1) from
`scripts/builder_change_judged.py --out` over these files plus the manifest
values.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Answers, bank 19 (tree, re-hashed 2026-09-09, A-1) | `docs/evaluation/experiments/bank20260819/deterministic/answers` | 828548 | sha256:e034f420eb44ffe349146654dae18ce0e172b4e99aa7eff9dbddf9a909323d35 | 30 answers, old builder, pre-9f02dc6, plus 420 judgment sidecars from this and other experiments; the 30 answer files alone still digest to sha256:ecb8c1c2… (505317 B) |
| Answers, bank 19 (tree, re-hashed 2026-09-09, A-1) | `docs/evaluation/experiments/builderiso-b19-newbuilder/deterministic/answers` | 607473 | sha256:e18d54a89e7e0460b5a7de1aad745f80fe25fc7d2f3d1544304b4d8dc8328b3e | 30 answers, new builder, HEAD 2026-08-31, plus this experiment's 120 judgment sidecars; the 30 answer files alone still digest to sha256:c9206758… (505955 B) |
| Answers, bank 20 (tree, re-hashed 2026-09-09, A-1) | `docs/evaluation/experiments/bank20260820/deterministic/answers` | 893664 | sha256:264c26e3ffe0cdc9e2f715cb1ad6d3b5fde1e238d5302d7e695bc74bc8e112fa | 30 answers, old builder, pre-9f02dc6, plus 391 judgment sidecars from this and other experiments; the 30 answer files alone still digest to sha256:1310e640… (588529 B) |
| Answers, bank 20 (tree, re-hashed 2026-09-09, A-1) | `docs/evaluation/experiments/builderiso-b20-newbuilder/deterministic/answers` | 694890 | sha256:ae336a0685fb93fa86dbd11e2b8e2e0f9d76291a0dcbb55e0f7c20bb48cfe624 | 30 answers, new builder, HEAD 2026-08-31, plus this experiment's 120 judgment sidecars; the 30 answer files alone still digest to sha256:b790beb7… (593309 B) |
| Judgments `.bld1` | `docs/evaluation/experiments/bank20260819/deterministic/answers/*.judgment.bld1.json` | — | sha256:667339a7137c21810dd4411f321825fe1c4a5784e21812275190a8c080fb59a7 | bank 19 old, old graded first |
| Judgments `.bld1` | `docs/evaluation/experiments/builderiso-b19-newbuilder/deterministic/answers/*.judgment.bld1.json` | — | sha256:70b838a1dc05b446ef7ffcf1b974b099ca6016cb45602844f122e297ab9e1b2b | bank 19 new, old graded first |
| Judgments `.bld1` | `docs/evaluation/experiments/bank20260820/deterministic/answers/*.judgment.bld1.json` | — | sha256:acf6b1c7c231ae0a9416ffca36dcedfebce535f80939b403c8b47999ca0753e5 | bank 20 old, old graded first |
| Judgments `.bld1` | `docs/evaluation/experiments/builderiso-b20-newbuilder/deterministic/answers/*.judgment.bld1.json` | — | sha256:179f666fc405f076f422faee914b9719ac24df4959c6e578764d61b487de5a15 | bank 20 new, old graded first |
| Judgments `.bld2` | `docs/evaluation/experiments/bank20260819/deterministic/answers/*.judgment.bld2.json` | — | sha256:11e1b8091e2c9816d59041d6063983a4f190d7cf2764481119a26d8cc636719d | bank 19 old, old graded first |
| Judgments `.bld2` | `docs/evaluation/experiments/builderiso-b19-newbuilder/deterministic/answers/*.judgment.bld2.json` | — | sha256:dc3df0eeeaf6672af7c232766056024210bcd58722dad572816ce2d4423e7d25 | bank 19 new, old graded first |
| Judgments `.bld2` | `docs/evaluation/experiments/bank20260820/deterministic/answers/*.judgment.bld2.json` | — | sha256:07987034bb67e5deb40e141ef3c218a2a8c1ab979171d840c5b09f5913b1e9f1 | bank 20 old, old graded first |
| Judgments `.bld2` | `docs/evaluation/experiments/builderiso-b20-newbuilder/deterministic/answers/*.judgment.bld2.json` | — | sha256:9c543d8e382fc661bb1f3264955c1f705b596875d1b98d65cd5f98d6b848c969 | bank 20 new, old graded first |
| Judgments `.bld3` | `docs/evaluation/experiments/bank20260819/deterministic/answers/*.judgment.bld3.json` | — | sha256:9ae5f7ca99d6f0c515dae7124b290e2b0b97ad583fa87d0d7e0c4c8c214dfc8a | bank 19 old, old graded first |
| Judgments `.bld3` | `docs/evaluation/experiments/builderiso-b19-newbuilder/deterministic/answers/*.judgment.bld3.json` | — | sha256:1dd14c07eaec670ea7466c04d9fa51a6bfcfd29d32bcd78309c770580e89f0d6 | bank 19 new, old graded first |
| Judgments `.bld3` | `docs/evaluation/experiments/bank20260820/deterministic/answers/*.judgment.bld3.json` | — | sha256:4d676c14b560cc4482df7a7f525ff35988f5442394dc05ef7186920fff865797 | bank 20 old, old graded first |
| Judgments `.bld3` | `docs/evaluation/experiments/builderiso-b20-newbuilder/deterministic/answers/*.judgment.bld3.json` | — | sha256:ca95fe9c56c8df5b3dd803813974c3848db4534493ad396a30c0219b5f3fe5e2 | bank 20 new, old graded first |
| Judgments `.bldrev` | `docs/evaluation/experiments/bank20260819/deterministic/answers/*.judgment.bldrev.json` | — | sha256:12b96074b1d4c163a8547c85cbb82fdc405454f516934c3f108b7039231cd164 | bank 19 old, NEW graded first (position-effect test) |
| Judgments `.bldrev` | `docs/evaluation/experiments/builderiso-b19-newbuilder/deterministic/answers/*.judgment.bldrev.json` | — | sha256:4157882fbe6dccecb99eef57d1f2738d9048cb16dd5b88ab670c93844e971525 | bank 19 new, NEW graded first (position-effect test) |
| Judgments `.bldrev` | `docs/evaluation/experiments/bank20260820/deterministic/answers/*.judgment.bldrev.json` | — | sha256:29ea7be107b225020258a26fe1e8b6c9be0fff858e6e72fb3c9cbeb7f7c7bb0c | bank 20 old, NEW graded first (position-effect test) |
| Judgments `.bldrev` | `docs/evaluation/experiments/builderiso-b20-newbuilder/deterministic/answers/*.judgment.bldrev.json` | — | sha256:075acdf4bdb3e7bde37db326625b2537f52f65138745a92e262ca0f29e4d0c6e | bank 20 new, NEW graded first (position-effect test) |
