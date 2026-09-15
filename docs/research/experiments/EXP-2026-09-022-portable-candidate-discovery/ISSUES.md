# Issues

- Scaffold captured a dirty tree because the new experiment directory was being created. Execution metadata will be captured from the committed prototype.
- No independent holdout or end-to-end answer run is part of this diagnostic.
- Seed 0 is a reproducibility marker; the algorithms use no randomness.
- Baseline full research validation fails on pre-existing pointer hash drift in EXP-2026-07-011 (two current builder files) and EXP-2026-09-012 (the mutable evaluation directory). These historical records are not modified. New experiment validation is run separately; the generated index is refreshed.
- Measurement completed from committed code with a clean worktree at run start. Later analysis/docs do not alter the recorded retrieval implementation.
- Raw predictions stay local and are hash-pinned; the new predictions.jsonl ignore pattern follows the existing raw-answer policy. Metrics, report generator, and generated tables are committed.
- T1/T2 gold includes retired and invented anchors; the diagnostic retains them in its denominator and does not mislabel this as positive-query accuracy. Current cards also lack complete public-ID formatting metadata.
