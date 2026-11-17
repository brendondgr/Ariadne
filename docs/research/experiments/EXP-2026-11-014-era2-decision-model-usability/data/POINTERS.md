# POINTERS — EXP-2026-11-014

The control is EXP-2026-11-013's committed `data/items.jsonl` and `data/runs/*.jsonl`, which
are hashed in that experiment's POINTERS.

**Frozen 2026-11-17, before any model call.** The relation readings were written by a Claude
Opus 5.5 subagent at medium effort.
- **Input:** the brief alone.
- **Checks passed first time:** 63 of 63 readings; nothing was sent back.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| readings | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/readings.json | 6177 | sha256:9e3efd99e779eede8f6e1812c0fb7587a2f15e63b195d9faeb200da8fa517b5f | one plain reading per relation option |
| readings brief | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/readings-brief.md | 9220 | sha256:507df75a5c53f4c3cb4bf008049dabeca6c034241e77fb75be6a7fa86800f4ff | the writer's whole input |

**Run records and built items, 2026-11-17.** Written by `scripts/era2_usability.py build` and `run`, on the decision servers only (amendment 1).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| build.json | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/build.json | 542 | sha256:02b811624cda434901a7c8e3f6509c1cb287951975c4404b9654a3814271d0e4 | summary |
| wording.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/wording.jsonl | 760600 | sha256:592ab5e55e3c5240308f1dfc1ed10e68f5e8f87676db8df58298a00db74f43c0 | 464 built items |
| rulefilter.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/rulefilter.jsonl | 334210 | sha256:829eda61f02c38f99e81236dab18666ce65b9371612e2c896291186335a243a1 | 312 built items |
| shortlist.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/shortlist.jsonl | 1704378 | sha256:93263417997c4108895c4cd64faa6fe1998323abfb4af3c0c50323ec76dc31bd | 1722 built items |
| verifier.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/verifier.jsonl | 968262 | sha256:5f0a44a0d4ee1966f3e11015d0398a679be239693e215cbf64aeb370a4b2e6d0 | 1485 built items |
| drift.json | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/drift.json | 43223 | sha256:23273f5e85ddafa9d0f2bf5cef64da11236058facd773b3bc1ba838145575594 | summary |
| latency.json | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/latency.json | 502 | sha256:e9d0c2d8b20c3716387b3270e1eca6f1abe7cf43ef69b75bb6afe3c67c90d415 | summary |
| runs/rulefilter/d3.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/rulefilter/d3.jsonl | 237043 | sha256:e464cd76d9ed403c366c1b2b90974d08a6d70eb60e442c4f94724fc73f540fc9 | 624 records, two orders |
| runs/rulefilter/pplx.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/rulefilter/pplx.jsonl | 263718 | sha256:94e4818c5cac70f98abd809f497039a7c08c73a017cbef402c8cec1b5dfb2d9e | 624 records, two orders |
| runs/shortlist/d3.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/shortlist/d3.jsonl | 1142501 | sha256:c3d1647c003dff9e11d406b068ff886b8f991d410bca2211023aca2731ca3c68 | 3444 records, two orders |
| runs/shortlist/pplx.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/shortlist/pplx.jsonl | 1231858 | sha256:be39a899a2ce59aad41f9034bfd56bcb107cd8f9347414a6c219e03f1d758fb5 | 3444 records, two orders |
| runs/verifier/d3.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/verifier/d3.jsonl | 744451 | sha256:8f9be2ec83ec047cce0bcb55cdf5bd5d5174ebcaf3cff6d6e88a9c9271072043 | 2970 records, two orders |
| runs/verifier/pplx.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/verifier/pplx.jsonl | 755124 | sha256:d55bd4d9320e4984de627250aefaabdec84554bd95a2a320247a904d744476bb | 2970 records, two orders |
| runs/wording/d3.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/wording/d3.jsonl | 715614 | sha256:e47f0a9017dff0fd62e34ad933d33c37a383a3abbc9e9a71a5ebde7ff8ca31f1 | 928 records, two orders |
| runs/wording/pplx.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/wording/pplx.jsonl | 868829 | sha256:c2011c463be37a58959ecae5bdfd626913c0f6082c4b881c3d690b5497d34c78 | 928 records, two orders |
| runs/wording_yesno/d3.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/wording_yesno/d3.jsonl | 587207 | sha256:757cb2f7d760099e3acaaea0214dd57d2a0ae2b8f833896e6df018a911166e51 | 928 records, two orders |
| runs/wording_yesno/pplx.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/wording_yesno/pplx.jsonl | 744101 | sha256:8f479208c6fb9d65f9026b5e6db12cd19fafcc11039a23dbb60b787d48c47459 | 928 records, two orders |
| runs/yesno/d3.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/yesno/d3.jsonl | 803647 | sha256:6349cbcc24759db8f527c083df5de95dca3e801f7e883b27d99035775215e4f0 | 1722 records, two orders |
| runs/yesno/pplx.jsonl | docs/research/experiments/EXP-2026-11-014-era2-decision-model-usability/data/runs/yesno/pplx.jsonl | 1051576 | sha256:6f56030405105e83f680cc8b9e8e480dd350d69754ee3386da769d95f69c8b83 | 1722 records, two orders |
