# RESULTS — EXP-2026-09-021 Paraphrase robustness at T0–T3

**Status: running.** `PROTOCOL.md` was pre-registered on 2026-09-15 with three
hypotheses and their falsifiers before any arm ran. This file is filled in as the
steps complete, and nothing is written here that `data/` does not carry.

Plan: [`docs/plans/2026-09-15-paraphrase-robustness-t0-t3.md`](../../../plans/2026-09-15-paraphrase-robustness-t0-t3.md).

**Scope, stated once.** `T0`–`T3` are the tiers in scope. `T4`/`T5` are reported
but are not targets; they exist here so that a lever which helps the tiers in
scope by breaking the others is visible rather than hidden. Every figure is per
tier — the bank over-samples the paraphrase tiers on purpose, so a pooled T0–T3
number would be an artifact of the sampling and none is produced.

## Step 1 — the instrument reproduces (complete, 2026-09-15)

No model, no judge. `data/metrics_reference.json`.

Variants are scored against their own gold question's captured behaviour, so a
reference that is not reproducible makes every downstream figure meaningless.
The 120 golden questions were captured twice on the shipped tree:

| | |
|---|---|
| captures | 2 |
| byte-identical | **yes** — `sha256:891a26147cc65672…` both times |
| questions | 120, **0 errors** |
| extracted nothing | 9 |

**`T0` = 1.0000**, and it is a *determinism control, not an accuracy figure*. It
says the tree reproduces itself; it says nothing about whether the answers are
right. Anything below 1.0000 here would have invalidated the experiment.

The 9 empty captures are expected: 8 are the bank's named negative and exclusion
controls — `T9999`, `G9999`, `C9999`, retired `T1002`/`T1004`, `CAPEC-99999`,
deprecated `CAPEC-557`/`CAPEC-91` — where returning nothing *is* the correct
behaviour.

**One defect blocked the start and is recorded as `I-1`**: the loader's staleness
check refused to run against a graph whose data had not changed
(`EXP-2026-09-018` `I-21`, still unfixed, second occurrence). Proved unchanged
two ways — the canonical manifest differs from the loaded one in exactly one key,
`build_timestamp`, and live counts match `expected_counts` per label on both
stores — then re-stamped by `scripts/revalidate_load_manifest.py`, which refuses
to re-stamp when either check fails.
