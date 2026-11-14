# POINTERS — EXP-2026-11-003

Run outputs live under `logs/killtests-2026-11/` (gitignored); the small summaries are copied into this folder. Run of 2026-11-13 19:01–19:45 from tag `killtests-run` (eb676358).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `parity.json` | `logs/killtests-2026-11/t1/parity.json` | 1,626 | `sha256:caf712d304a18021642f9a6a830d49a4698687fac326f08e947be107ec6d1a53` | mirror parity check (copied to data/) |
| `gold.json` | `logs/killtests-2026-11/t1/gold.json` | 1,799,638 | `sha256:fbcf7ba1a0791202b49b8ad4bc3206ccee8cd544fe472df0432f4aea33941ca4` | sampled questions with executed gold |
| `generate.json` | `logs/killtests-2026-11/t1/generate.json` | 638,459 | `sha256:bd015ed29a28473c7eaf843ee77e96a5261732c0e4952517b60cdf0a695d4e87` | every generation, served model recorded |
| `execute.json` | `logs/killtests-2026-11/t1/execute.json` | 111,044 | `sha256:6b4d55580a2cb025aeb584b0050b66eec73a3602859bd7fce03e52beb31da73e` | execution status and correctness per generation |
| `score.json` | `logs/killtests-2026-11/t1/score.json` | 3,313 | `sha256:06e73460d3f3f113f0d12f7b55506cab20224b5ae00611ea0abe4f090afe0d9f` | scores by arm, model, category (copied to data/) |
| `preconditions.json` | `logs/killtests-2026-11/preconditions.json` | 697 | `sha256:44cb3f553ca1ee84d626508254ecb9370e5f3bce774ea2404bb42aeebf474a34` | served models, graph counts, commit at launch |
| `report.json` | `logs/killtests-2026-11/report.json` | 1,157 | `sha256:9409e3edb9e27506c00dbd65b6b916894b5892015aa0c06007308d13d9720a78` | kill-rule verdicts |
| `score-gemma4-31b.json` | `logs/killtests-2026-11/t1-models/gemma4-31b__via_default-model/t1/score.json` | 3,258 | `sha256:6751c5cafb412ca13462acef92ae84fe838965b6674b3f276f511eb637af69e0` | Gemma 4 31B scores, added 2026-11-14 (copied to data/) |
| `score-qwen38-27b.json` | `logs/killtests-2026-11/t1-models/qwen38-27b__via_default-model-2/t1/score.json` | 3,309 | `sha256:3d13b1281c4f6980d66932f7d58c36b295787d6ae17af79368c0ddf0b164a9c9` | Qwen 3.8 27B scores, added 2026-11-14 (copied to data/) |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
