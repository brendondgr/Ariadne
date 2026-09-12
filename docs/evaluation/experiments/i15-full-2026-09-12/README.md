# i15-full-2026-09-12 — both banks, both model-free arms, after I-15 and I-16

Answer files are gitignored (only judgment sidecars are tracked) and neither arm
here was graded, so nothing in this directory spends the holdout. Both arms run
with every LLM seam off and regenerate byte-for-byte:

```bash
uv run python -m utils.evaluation.experiment_untruncated --arm generic_composed \
  --bank docs/evaluation/composition/bank/bank-dev.json \
  --root docs/evaluation/experiments/i15-full-2026-09-12/dev --workers 16
```

The committed evidence is `EXP-2026-09-018/data/flag_classes.json` and
`data/i16_contradictions.json`. The comparison baselines are
`i16-full-2026-09-12` (after I-16, before I-15) and `i16-baseline-c5cb2906`
(before both).

`i15-slice-2026-09-12` and `i15-slice2-2026-09-12` are the 12-case judged
acceptance test for I-15 — quoting only, and quoting plus the provenance fix.
Their judgment sidecars **are** tracked, because they are the evidence that
quoting alone changed nothing.
