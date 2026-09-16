# POINTERS — EXP-2026-09-023

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `predictions.jsonl` | `docs/evaluation/experiments/portable-candidate-discovery-2026-09-15/predictions.jsonl` | 12,696,589 | `sha256:09b5b6d19afa408964e4da2cbda7507d7299114049ee5a643b34a90a5abc7ddf` | EXP-2026-09-022's recorded candidate lists and gold groups; Step 0 reads its pooled arm and gold groups |
| `variants.json` | `docs/evaluation/variants-2026-08-29/variants.json` | 219,487 | `sha256:428a23467ecf8aed1f266186504d6f68d0a9d88173cc090149558d078bdea63c` | the exposed bank, 579 variants |
| `slot_gold.json` | `docs/evaluation/variants-2026-08-29/slot_gold.json` | 36,224 | `sha256:36aa52df72f75c6af3c107d171e5d94ed13f731ec2fbf5711f4813d6dc626648` | exposed-bank understanding gold (anchors per case) |
| `reference.json` | `docs/evaluation/variants-2026-09-15/reference.json` | 350,789 | `sha256:891a26147cc65672c0906572b18a753915acf3f20cdaf82689b24373bdd89c1b` | exposed-bank reference on the shipped tree (EXP-2026-09-021 Step 1) |
| `gold.json` | `docs/evaluation/variants-holdout-2026-09/gold.json` | 18,183 | `sha256:df479c6024930a78cbed70027dab30892dc976e84e087dcc22bf36201f83c9f8` | sealed bank: 40 entity-held-out gold questions |
| `variants.json` | `docs/evaluation/variants-holdout-2026-09/variants.json` | 66,541 | `sha256:f50ddaa628f892ee2498c19662a4a42bf1c4589dad6361d4003233011ab578ce` | sealed bank: 160 variants, T3-T6 |
| `slot_gold.json` | `docs/evaluation/variants-holdout-2026-09/slot_gold.json` | 12,684 | `sha256:d96fa70688f78635ffd988db3bf599df5dc8d5a055e7b2557eea5910ae2a209f` | sealed bank: anchors per case, from the composition spec |
| `reference.json` | `docs/evaluation/variants-holdout-2026-09/reference.json` | 87,169 | `sha256:2ab12ae417ff15b4831d17a551bfebbdeb30312c333d325d8d7cd8ec42e6f917` | sealed bank reference, byte-identical across two captures |

| `scored_noid_anchored.json` | `docs/evaluation/variants-2026-09-15/scored_noid_anchored.json` | 3,992,374 | `sha256:5b6992caf640891f10c7af11893cebce9fcc1e215225686aad114f50b1bc3a9f` | exposed baseline: EXP-2026-09-021's shipped arm (D-034 + D-035), 600 s budgets |
| `scored_hygiene.json` | `docs/evaluation/variants-2026-09-15/scored_hygiene.json` | 2,348,253 | `sha256:82e7582a846cd7ba0efff6ab1545c5815a3e1e66f26690b073ca5f422402a206` | exposed: A-1 + unanchored-relation guard (hygiene arm), 600 s budgets |
| `scored_anchor_first.json` | `docs/evaluation/variants-2026-09-15/scored_anchor_first.json` | 2,374,888 | `sha256:d88b181a8e6111221de8707f4788c814b7ebf79f3197618566f91b75241a334f` | exposed: hygiene + Q59 anchor-first routing, 600 s budgets |
| `scored_baseline.json` | `docs/evaluation/variants-holdout-2026-09/scored_baseline.json` | 1,660,225 | `sha256:dbe0c210ebe8e6a4b1aeead8212f5c928ff09246eaa276b0f811550b30823339` | sealed baseline: model_noid_anchored, flags off |
| `scored_distinct.json` | `docs/evaluation/variants-holdout-2026-09/scored_distinct.json` | 1,862,387 | `sha256:35a69ed81a770b0f6273a070add55f77b79052128f9c9cd7b6b78367699c3f4c` | sealed: A-1 alone (no dump guard); the reading that exposed the scans |
| `scored_hygiene.json` | `docs/evaluation/variants-holdout-2026-09/scored_hygiene.json` | 562,188 | `sha256:f541d78bc5c97b5b4de4b8f62d08d6c66598e38a10c751f7f21f675a3fba7cc7` | sealed: hygiene arm |
| `scored_anchor_first.json` | `docs/evaluation/variants-holdout-2026-09/scored_anchor_first.json` | 578,532 | `sha256:b7282dd7a3179f7b46885c752c94d164723a864a066339be30834087ed5fe056` | sealed: anchor_first arm |

`docs/evaluation/variants-2026-09-15/scored_distinct.json` exists on disk and is deliberately not pointed to: ISSUES.md records its timeout contamination.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
