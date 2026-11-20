# POINTERS — EXP-2026-11-020

Large artifacts live outside `docs/research/`, which must stay cloneable in
seconds. This file is the only link between this experiment and its raw run
output. **Every entry needs a hash.**

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| rubric | docs/evaluation/shape-count-2026-11/RUBRIC.md | 6929 | sha256:99ce04ce13c54052d8e806a7ca5b778e98ad6e6548b767cb116b58353bb72b1e | the codes and coverage rule, written before labelling |
| drawn items | docs/evaluation/shape-count-2026-11/items.json | 72564 | sha256:8759a5c4278b9c3fa3a6fd84092c8ea3c41ad4346e5ca8baf06cc37da58a2a9a | 673 item ids, families, the second labeller's 135 (no external text) |
| labeller A | docs/evaluation/shape-count-2026-11/labels-a.jsonl | 74487 | sha256:e058d61564bb5141e902b3b3c2ec26771d39d98502fb8817a51a5140cc1fb14b | Opus 5.5, all 673 items (three batches, concatenated in order) |
| labeller B | docs/evaluation/shape-count-2026-11/labels-b.jsonl | 12600 | sha256:39014fbfa2f5b20fb9db00e3a5b2e5a0b50421598f74c037f683cbf47c319691 | Sonnet 5.5, the 135 drawn items, blind to A |
| adjudication | docs/evaluation/shape-count-2026-11/adjudicated.jsonl | 761 | sha256:c1cac4654ec914611832a4f5bf541271c7f79ea85374be016354a9e7f691cf5e | the 5 stage disagreements, settled with reasons |
| per question | docs/evaluation/shape-count-2026-11/per_question.jsonl | 217085 | sha256:f10cd1af5c4dd4b24e90f065b707309be465e415501bbaf99ae5298c087b6bcf | 2,076 rows: every question's codes and who labelled it |
| counts | docs/evaluation/shape-count-2026-11/counts.json | 19429 | sha256:760d7c50947077a2db02d19444bccbae620faa825704540efd7083557cc204d2 | every curve, code share and the agreement figures |

The external benchmarks themselves are not committed (D-020): AttackQA rev 1cecfc24 and CTIBench
rev 9237e163, fetched by `utils/evaluation/external/fetch.py` into `.cache/external-benchmarks/`.

Regenerate hashes with:

```bash
uv run python -m utils.research_record.hashing <path>
```
