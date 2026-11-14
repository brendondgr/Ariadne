# POINTERS — EXP-2026-11-001

Run outputs live under `logs/killtests-2026-11/` (gitignored); the small summaries are copied into this folder. Run of 2026-11-13 19:01–19:45 from tag `killtests-run` (eb676358).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| `candidates.json` | `logs/killtests-2026-11/t2/candidates.json` | 943,303 | `sha256:0ff8e5bd28c71dcdaa696a3e207f0dcdc7b4947ca16b5f4ebf48662adf4c6146` | anchor candidates per question |
| `decide.json` | `logs/killtests-2026-11/t2/decide.json` | 732,572 | `sha256:45931be0dd208f658ede60b048c3350775a764da298fad00ea25f851c0a8ab3c` | decider anchor and facet probabilities |
| `execute.json` | `logs/killtests-2026-11/t2/execute.json` | 3,082,667 | `sha256:eeffb7f1f26e5506e25fa513dd30d000f27b1786535cf10f13bfaaf15ad62545` | interpretations and executed record sets, gold |
| `score.json` | `logs/killtests-2026-11/t2/score.json` | 334,035 | `sha256:4466924147ac4c7ac70add5c8c11e757d085ad7a780ec564e3139a2cec790275` | per-item scores and summary (copied to data/) |
| `preconditions.json` | `logs/killtests-2026-11/preconditions.json` | 697 | `sha256:44cb3f553ca1ee84d626508254ecb9370e5f3bce774ea2404bb42aeebf474a34` | served models, graph counts, commit at launch |
| `report.json` | `logs/killtests-2026-11/report.json` | 1,157 | `sha256:9409e3edb9e27506c00dbd65b6b916894b5892015aa0c06007308d13d9720a78` | kill-rule verdicts |

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
