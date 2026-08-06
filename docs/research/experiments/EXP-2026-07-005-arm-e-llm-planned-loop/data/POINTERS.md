# POINTERS — EXP-2026-07-005

The raw run output for this arm — one answer file and one judgment file per
question — stays under `docs/evaluation/experiments/`. It is not copied here:
`docs/research/` must stay cloneable in seconds, and this arm's artifacts alone
are 7.7 MB.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Arm artifacts | `docs/evaluation/experiments/untruncated-loop2/llm_loop/` | 7734237 | sha256:446abccc71f9419ed2035820d66fd8e6aeb531404b471aa5b063d3563b4570da | 120 answer files (answer + full retrieved evidence + executed queries) and 120 independent judgment files |
| Recomputed figures | `docs/plans/robustness/_overnight/numbers.json` | 21403 | sha256:12a748f017c35b913ac19fc8387230f1b2be58954fd8e515efd8287e6badb311 | Every metric in `metrics.json`, recomputed from the judgment files above |

The directory hash folds each file's relative path and content digest in sorted
order, so a rename counts as a change. Recompute with:

```bash
uv run python -m utils.research_record.hashing docs/evaluation/experiments/untruncated-loop2/llm_loop
```
