# Issues

- Scaffold captured a dirty tree because the new experiment directory was being created. Execution metadata will be captured from the committed prototype.
- No independent holdout or end-to-end answer run is part of this diagnostic.
- Seed 0 is a reproducibility marker; the algorithms use no randomness.
- Baseline full research validation fails on pre-existing pointer hash drift in EXP-2026-07-011 (two current builder files) and EXP-2026-09-012 (the mutable evaluation directory). These historical records are not modified. New experiment validation is run separately; the generated index is refreshed.
- Measurement completed from committed code with a clean worktree at run start. Later analysis/docs do not alter the recorded retrieval implementation.
- Raw predictions stay local and are hash-pinned; the new predictions.jsonl ignore pattern follows the existing raw-answer policy. Metrics, report generator, and generated tables are committed.
- T1/T2 gold includes retired and invented anchors; the diagnostic retains them in its denominator and does not mislabel this as positive-query accuracy. Current cards also lack complete public-ID formatting metadata.

## 2026-11-15 — Source-card pointers re-hashed; the cards are generated files
**Impact:** None on the stored diagnostic outputs, which were not recomputed. `data/source_cards/attack.json` and `capec.json` are rewritten whenever the pipeline loads the cards, most recently on 2026-11-15 during EXP-2026-11-009's reruns. A re-run of this diagnostic would read today's cards, not the hashed ones.
**Cause:** The artifact changed after the pointer was recorded; `make validate-research` flagged the hash.
**Resolution:** Both rows re-hashed, each with the previous hash in its note.
