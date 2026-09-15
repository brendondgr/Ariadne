# POINTERS — EXP-2026-09-021

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash** — the validator rejects a pointer without
one, because a path alone does not tell you whether the file still holds what
it held when the number was computed.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `reference.json` | `docs/evaluation/variants-2026-09-15/reference.json` | 350,789 | `sha256:891a26147cc65672c0906572b18a753915acf3f20cdaf82689b24373bdd89c1b` | the 120 gold questions' captured behaviour; every variant is scored against this |
| `variants.json` | `docs/evaluation/variants-2026-09-15/variants.json` | 219,487 | `sha256:428a23467ecf8aed1f266186504d6f68d0a9d88173cc090149558d078bdea63c` | the 579 rewordings, unchanged from EXP-2026-08-020 |
| `scored_baseline.json` | `docs/evaluation/variants-2026-09-15/scored_baseline.json` | 3,999,632 | `sha256:cb82a17a63a7ca3d187fa28235d0d31394e111a54831d0c9167bee4025f026e5` | Step 2: shipped tree, rewrite off |
| `scored_primitives.json` | `docs/evaluation/variants-2026-09-15/scored_primitives.json` | 1,960,946 | `sha256:f0ffceb7f30b8f63a3a40244843b12851604696701fb7ebaa63d97e98be461ed` | Step 3: SPECIALIST_GENERIC_ONLY=true |
| `scored_rewrite.json` | `docs/evaluation/variants-2026-09-15/scored_rewrite.json` | 3,312,302 | `sha256:f856a83302a3bb597378a5dbefc8cb31e49cd233a10e905e6bcc043aa13e5f81` | Step 4: rewrite model rung, ungated |
| `scored_noid.json` | `docs/evaluation/variants-2026-09-15/scored_noid.json` | 3,471,642 | `sha256:bff4dec199bbe4c24b019a3b79fd4370ba94787251bde220c844e185559cbae7` | Step 5: rewrite gated on no identifier cited |
| `scored_noid_anchored.json` | `docs/evaluation/variants-2026-09-15/scored_noid_anchored.json` | 3,992,374 | `sha256:5b6992caf640891f10c7af11893cebce9fcc1e215225686aad114f50b1bc3a9f` | AMENDMENT A-1: the gate plus a refusal to let the model choose the anchor |
| `scored_baseline_recheck.json` | `docs/evaluation/variants-2026-09-15/scored_baseline_recheck.json` | 3,999,627 | `sha256:a5877e957cb946c3989925437541e4a9dd959e9e1825a63f22a76d61caa718f3` | Step 5: flag-off identity re-run, byte-identical to scored_baseline.json |
| `scored_arm0.json` | `docs/evaluation/variants-2026-08-29/scored_arm0.json` | 4,458,400 | `sha256:036705d92ab4d9f661ddc311496c389b661f07db2f91ebaba4a93c3131335267` | EXP-2026-08-020 Arm 0, the August tier table the like-for-like comparison reads |
| `reference.json` | `docs/evaluation/variants-2026-08-29/reference.json` | 323,213 | `sha256:76966f0c7a016c1aaa2c04741f3ac486280bc6dc66959bb99c0aff995e48d469` | the August reference; 51 of its 120 gold entity sets have since moved |

If this experiment reads no raw output outside `docs/research/`, delete the
table and write one line: `No external artifacts: <why>` — the validator
rejects an empty table on a completed experiment.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
