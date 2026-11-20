# POINTERS — EXP-2026-11-021

Large artifacts live outside `docs/research/`. **Every entry needs a hash.**

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| typed-query snapshot | docs/evaluation/algebra-2026-11/typed-query-snapshot.jsonl | 1183139 | sha256:e32afae12d940a6bcf2abecbafce0d1689ff7670186c8b1e80fdeff112c6d06e | builder drafts of 1,121 distinct recorded steps, taken before Phase D's move |
| differential, final | docs/evaluation/algebra-2026-11/engine-check/after-amendment4/summary.json | 12067 | sha256:0036001fa6208bd3e80feea5f1d50da9b8a680ab84f5ab8889f5267e535f1190 | 9,391 instances, 0 disagreements, 424/424 cells |
| differential instances | docs/evaluation/algebra-2026-11/engine-check/after-amendment4/instances.jsonl | 4670218 | sha256:50b9304c9acd8bb6658a4d48b41c5335d821d2f3d1be30d7cbc22c7a5a694316 | one row per instance: tree, both results, agreement |
| today's shapes (H3) | docs/evaluation/algebra-2026-11/engine-check/after-amendment4/h3-summary.json | 3657 | sha256:d0cecfd5aec0c442b8b211a553639f1c9afa259bf0fe8f242adad77312adc135 | 864 rows: 853 equal, 11 documented, 0 unexplained |
| H3 rows | docs/evaluation/algebra-2026-11/engine-check/after-amendment4/h3.jsonl | 520096 | sha256:a699a836e7cf0f7ef91e95511087c75bd5be819a9fae1acd7c227958358fd84c | per-row comparison |
| part-1 differential | docs/evaluation/algebra-2026-11/engine-check/final/summary.json | 17155 | sha256:139df1fed957ef9ff87b22ad828f6b84762a8e5153656e058c2c080ac8b6f5b1 | before amendment 4: 8,611 instances, 479 disagreements |
| store-fix regression | docs/evaluation/algebra-2026-11/store-fix/before-after-diff.json | 3678 | sha256:e90857e0012cb9e880aae3c98fd8fc1c80f4174225a09da6b1a790872998978f | today's answers before and after the storage change |
| Phase F regression | docs/evaluation/algebra-2026-11/phase-f/tree-vs-tree-diff.json | 649 | sha256:192d3ba107214386bae9250d5d20a070d3acfea5c8ed6e8e3d39ca72149b0d5c | this tree against be673ec3 on the same stores |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
