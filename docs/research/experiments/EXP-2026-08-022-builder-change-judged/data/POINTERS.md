# POINTERS — EXP-2026-08-022

Answers and judgments live under `docs/evaluation/experiments/`, git-ignored
per `D-007`. Both answer sets are **LLM-free and byte-reproducible**: the
deterministic arm has no model in it, so the two conditions differ only in
builder revision. Each hash is the SHA-256 of the matching files concatenated
in sorted path order; the commands are in [`../RESULTS.md`](../RESULTS.md) §8.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Answers, bank 19 | `docs/evaluation/experiments/bank20260819/deterministic/answers` | 505317 | sha256:ecb8c1c2ccc12a5b97a0a9102c1a405a9fce9802cbf1c505959a36f6d58b055d | 30 answers, old builder, pre-9f02dc6 |
| Answers, bank 19 | `docs/evaluation/experiments/builderiso-b19-newbuilder/deterministic/answers` | 505955 | sha256:c92067583f682ddede7b9e1429de0e5102fee8baf6f1ebe449f34b0ff5c54550 | 30 answers, new builder, HEAD 2026-08-31 |
| Answers, bank 20 | `docs/evaluation/experiments/bank20260820/deterministic/answers` | 588529 | sha256:1310e640db2be15a547303eb6d79ede69858d217088c54e71f5fec84fab2968f | 30 answers, old builder, pre-9f02dc6 |
| Answers, bank 20 | `docs/evaluation/experiments/builderiso-b20-newbuilder/deterministic/answers` | 593309 | sha256:b790beb70f80cd46b4846f467dd0ec925dd5793b005d9e25b7f266dd27de71f3 | 30 answers, new builder, HEAD 2026-08-31 |
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
