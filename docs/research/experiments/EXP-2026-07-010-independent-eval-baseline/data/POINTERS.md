# POINTERS — EXP-2026-07-010

This run is superseded and its artifacts are archived, not regenerable: the
pipeline it graded no longer exists in that configuration.

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Report (Markdown) | `docs/evaluation/archive/independent-eval.md` | 3795 | sha256:f3cb73bdbf98c7d9bb5d208416b39c3e99bf52ec29a01b9ff91a1f35ad552667 | The graded report |
| Report (JSON) | `docs/evaluation/archive/independent-eval.json` | 453 | sha256:e3ea09422130279962209e24f33565f3bc604d804a7f05c8d6fd61301f6649ca | Aggregate scores only (453 bytes) — description corrected 2026-09-09 (RESULTS A-1); the per-question verdicts are the row below |
| Failure analysis | `docs/evaluation/archive/independent-eval-analysis.md` | 10784 | sha256:3616227a55c2d59bd952d3445298bb52a11213f85a670273c6f7ee2f9e08fb6a | The analysis that produced the four fixes merged in df700ee |
| Per-question verdicts + graded answers | `docs/evaluation/answers` | 1543550 | sha256:c0828b086db25b88856e0893d156bf634676eb5d1ca80a5aed9d2a403c0eb763 | The 120 saved answers this panel graded and the 120 `*.judgment.json` files (one Sonnet 5 verdict each: `case_id, verdict, correctness, …`) from which every number here recomputes. Added 2026-09-09 (RESULTS A-1); tree hash via `utils.research_record.hashing` |
