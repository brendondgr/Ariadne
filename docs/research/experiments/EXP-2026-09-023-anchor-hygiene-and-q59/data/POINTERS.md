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

Scored arms are appended as they complete (Steps 3 and 4).

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
