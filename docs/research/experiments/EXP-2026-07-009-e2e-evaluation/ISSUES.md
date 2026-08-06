# ISSUES — EXP-2026-07-009

## 2026-08-06 — Back-filled; commit not recoverable

**Impact:** `code.commit` unknown, `code.dirty` unverified.
**Resolution:** The deterministic portion re-runs cheaply; do that before
publication rather than trusting the back-fill.

## 2026-07-26 — The judge is the model under test

**Impact:** The `--judge` scores (faithfulness 0.9733, groundedness 0.9342,
evidence sufficiency 0.95) come from `skynet` grading answers `skynet` wrote.

**Cause:** The opt-in judge uses the configured synthesis model by default.

**Resolution:** Not a defect to fix here — it is why the independent cross-model
panel (`EXP-2026-07-010`) was run. Recorded so the two are never conflated.

**Paper implication:** These three numbers must never appear as evidence of
answer quality. Cite the independent panel instead.

## 2026-07-26 — Two tiers report x_source_exact = 0.0

**Impact:** The *adversarial* and *easy* tiers show 0.0 for cross-source exact
match, which reads as failure in the rendered table.

**Cause:** Neither tier contains cross-source questions, so the metric has an
empty population and the renderer prints 0.0 rather than n/a.

**Resolution:** Not fixed in the renderer. Documented here and in RESULTS.md §2.

**Paper implication:** Do not reproduce the by-tier table without the
explanation; it invites a reviewer to read two zeroes as two failures.
