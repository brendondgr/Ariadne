# POINTERS — EXP-2026-11-006

Run outputs live under `logs/killtests-2026-11/exp006/`, `logs/killtests-2026-11/mtq/` and `logs/killtests-2026-11/typed-verify-v3/` (gitignored). The small summaries are copied into this folder: `metrics.json`, `killrule.json`, `sensitivity.json`, `miss-sources.json` and `expressibility-sample.json`. The code is at tag `killtests-exp006-run` (f6946de0); the analysis script `utils/killtests/t2c/analysis6.py` was added after the run.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `run_header.json` | `logs/killtests-2026-11/exp006/run_header.json` | 523 | `sha256:cb735e239c48a049f572439bc529cc98f22cf1e91fc32eac828cd64b3c1dbed1` | model identities by token id; reasoning setting; concurrency |
| `gold.json` (C) | `logs/killtests-2026-11/mtq/gold.json` | 5,004,411 | `sha256:704d97d47dbede46d2a6eb797806fac609bf20f93855cc68d6db3a95e1d9a1c0` | the 450 selected Mind the Query questions, gold Cypher, gold rows, exclusion counts |
| `A-generate.json` | `logs/killtests-2026-11/exp006/A-generate.json` | 1,128,759 | `sha256:0470f85b5f9e56245ad4aadd35ecc0c1fb593d14532dd83ae06bb13a0c8ca02b` | part A replies |
| `A-repair.json` | `logs/killtests-2026-11/exp006/A-repair.json` | 893 | `sha256:f00b2be7c520ab721bdac84adf49ded1b99daef6745abba822790c93d2e3042a` | part A repair turns |
| `A-execute.json` | `logs/killtests-2026-11/exp006/A-execute.json` | 1,618,258 | `sha256:c670d69338e41fdd89ecf5a9b4717f291d266ebfa4a98a21eebe7a01cf5d7f71` | part A requests, compiled queries, correctness per backend |
| `A-score.json` | `logs/killtests-2026-11/exp006/A-score.json` | 12,887 | `sha256:cad91d729e35f2da5b426e18b5454dcfb9736a4981c72bf7dd1bf7eb2619a372` | part A scores and paired CIs |
| `B-generate.json` | `logs/killtests-2026-11/exp006/B-generate.json` | 2,088,685 | `sha256:eb58a19b51ef70595b88bca664545623f4dd4e183996fa7976488eb61748ee40` | part B replies |
| `B-repair.json` | `logs/killtests-2026-11/exp006/B-repair.json` | 97,744 | `sha256:85fb8a28129d6903ff841e3020080fab89c138d44b4b92c0c248001ce050a817` | part B repair turns |
| `B-execute.json` | `logs/killtests-2026-11/exp006/B-execute.json` | 2,952,861 | `sha256:56af82bbea78ef889dcb84cacd3c7129dba7523330a8b3f6eda954a4466131c5` | part B execution and correctness |
| `B-score.json` | `logs/killtests-2026-11/exp006/B-score.json` | 12,309 | `sha256:41215877765d88126404f80ca9a92b3c0e7d9d38a0deb3facc0552fa46d03636` | part B scores, by graph and source, paired CIs |
| `C-generate.json` | `logs/killtests-2026-11/exp006/C-generate.json` | 2,597,445 | `sha256:00349257a47f191e0f22b57195a5b02c2db5382647760a768f9da3550dab373f` | part C replies (finish reasons included) |
| `C-repair.json` | `logs/killtests-2026-11/exp006/C-repair.json` | 237,156 | `sha256:7ca26cdfad5ab31c77dd46d5d8a69112eb9aafa01c7983d8ec1e276627689454` | part C repair turns |
| `C-execute.json` | `logs/killtests-2026-11/exp006/C-execute.json` | 3,643,957 | `sha256:afbf71dbcf10aa8e0b96a885dfb8db9cad126d0ab6cb316c47396a35aff4b59c` | part C execution and correctness |
| `C-score.json` | `logs/killtests-2026-11/exp006/C-score.json` | 10,113 | `sha256:5a244c587589e2daaf79ef191b5a8844aa85db448f43cca1dd5cb4a306c07f1d` | part C scores, by graph and source, paired CIs |
| `B-sensitivity-per-key.json` | `logs/killtests-2026-11/exp006/B-sensitivity-per-key.json` | 415,137 | `sha256:39a73a964856d4bbd2c6a766e074a08c601efc8dce6af76612524fed809f427e` | per-question strict / set / set_proj, part B |
| `C-sensitivity-per-key.json` | `logs/killtests-2026-11/exp006/C-sensitivity-per-key.json` | 478,880 | `sha256:337b40b25a1ada6bfe5b712d67236581c5f9c7ae23bb2863af5533e37c8275d5` | per-question strict / set / set_proj, part C |
| `diff.json` | `logs/killtests-2026-11/typed-verify-v3/diff.json` | 6,363,280 | `sha256:52a4087656e543d82216658b3fe73fb872840e12701f8fe2d171fca1f7c80ea4` | pre-run differential check, 6,000 random v3 requests |
| `gold.json` (verify) | `logs/killtests-2026-11/typed-verify-v3/gold.json` | 1,148,924 | `sha256:ce0a76442555257f48fd8979118bf2f9c932a19a8e5333413869c34b5143c2b6` | pre-run gold check on CypherBench terrorist_attack training questions |

Run log: `logs/killtests-2026-11/exp006-run.log` (one pass, zero generation errors). The smoke run is in `logs/killtests-2026-11/exp006-smoke/`.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
