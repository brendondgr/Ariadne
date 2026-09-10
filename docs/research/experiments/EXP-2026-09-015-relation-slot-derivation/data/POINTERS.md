# POINTERS — EXP-2026-09-015

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Flag-off reference | `docs/evaluation/variants-2026-08-29/reference_2026-09-08.json` | 319,942 | `sha256:d36411e12851049b3c4a957898d61cdcf47580ea3476daa30ec9f728dda98a68` | the captured behaviour every arm is scored against |
| A2 run 1 scored rows | `docs/evaluation/variants-2026-08-29/A2_run1` | 2,012,403 | `sha256:e36e798104aea8304d0f94a035279179023eed5f45cfbb4eddd7b87fd53404f8` | per-question rows for instance A run 1; the rung and refusal counts read from here |
| A4 ablation scored rows | `docs/evaluation/variants-2026-08-29/A4_ablation` | 2,105,967 | `sha256:507502243c6cc37c12180419661b92c40887a3507d3919b9c440d7c95764f9d0` | the same cached picks with the derivation off; the controlled comparison |
| Understanding-gold | `docs/evaluation/variants-2026-08-29/slot_gold.json` | 36,224 | `sha256:36aa52df72f75c6af3c107d171e5d94ed13f731ec2fbf5711f4813d6dc626648` | the answer key the slot metrics grade against; ISSUES I-1 is about this file |

If this experiment reads no raw output outside `docs/research/`, delete the
table and write one line: `No external artifacts: <why>` — the validator
rejects an empty table on a completed experiment.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```


Run output larger than this table lives in the session scratchpad and is **not**
retained: the per-run metric files it produced are committed under `data/`, and
every number in `RESULTS.md` is read from those.
