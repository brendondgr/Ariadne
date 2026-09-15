# Issues

- Scaffold captured a dirty tree because the new experiment directory was being created. Execution metadata will be captured from the committed prototype.
- No independent holdout or end-to-end answer run is part of this diagnostic.
- Seed 0 is a reproducibility marker; the algorithms use no randomness.
- Baseline full research validation fails on pre-existing pointer hash drift in EXP-2026-07-011 (two current builder files) and EXP-2026-09-012 (the mutable evaluation directory). These historical records are not modified. New experiment validation is run separately; the generated index is refreshed.
