# ISSUES — EXP-2026-09-008

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

## 2026-09-09 — `code.dirty: true`: the overnight driver was uncommitted when the first judgments were written
**Impact:** none on any number; provenance only.
**Cause:** `code.commit` is `ce1d95c` (2026-09-05 22:57, the plan edit). The
driver `scripts/overnight_2026_09_06.py` and this experiment directory were
first committed at `45f3226` (23:52:38), one and a half minutes after the first
calibration sidecar was written (23:51:07), and `393d8ac` (23:58) changed the
llama.cpp track's worker count and deadline while that track was already
running. The code that produced the numbers is therefore `45f3226`/`393d8ac`
with the tree not guaranteed clean between them.
**Resolution:** `code.commit` left at the recorded value, `dirty: true` kept.
**Paper implication:** none.

## 2026-09-09 — the orchestrator's `with_evidence` counter reported 30/30 when the truth was 0/30 (thinking-cap probe)
**Impact:** `data/state-qwen.json` phase D still records `with_evidence: 30`;
the manifest's `thinkcap512_records_retrieved` (0) and
`thinkcap512_gate_rejected` (28) are the corrected values, read from the 30
answers.
**Cause:** the counter read `records or results`, and `results` counts
sub-question slots including failures.
**Resolution:** found and fixed before any conclusion was drawn (RESULTS
lines 123–127); the state file is annotated rather than rewritten (RESULTS A-3).
**Paper implication:** the thinkcap verdict is unaffected; any figure quoted
from `state-qwen.json` directly is wrong.

## 2026-09-09 — `gemma-4-26B-it` mid band is n=18: the llama.cpp endpoint stopped answering
**Impact:** the mid-band mean 0.6239 and the inversion margin 0.0196 are over
18 cases, not 20. The ceiling band (the usability verdict) completed 20/20.
**Cause:** `:4000/local` stopped answering even a 16-token request for over
400 s; two cases are on disk as `*.judgment.gemma26.error.txt`.
**Resolution:** not re-run; reported with the caveat (RESULTS Limits).
`data/ceiling-resolution.json`, written mid-run, says the band was "not
measured" — that field is stale and is annotated in place (RESULTS A-3).
**Paper implication:** state n=18 wherever the inversion is quoted.

## 2026-09-09 — `data/state-gemma31.json` phases B/B2/B3 are EXP-2026-09-007's, not this experiment's
**Impact:** none on this experiment's numbers.
**Cause:** the same overnight driver ran the calibration (phase A) and then
spent the calibrated gemma4-31B-mtp on the holdout's `llm_query` answers
(phase B, suffix `.gem`) and position-2 passes on all three arms (B2/B3,
`.gemp2`) — 288 × 3 judgments under
`docs/evaluation/experiments/holdout-spend-2026-09-05`. The driver wrote one
state file per track, so those phases landed here.
**Resolution:** left in place as the run log they are; not pointed from
`data/POINTERS.md` (EXP-2026-09-007 points at that directory).
**Paper implication:** none.

## 2026-09-09 — seeds not recorded for the thinking-cap probe
**Impact:** the 30 capped answers cannot be regenerated bit-for-bit.
**Cause:** grading is temperature 0 with no seed field; the probe's generation
went through `utils.evaluation.experiment_untruncated` with whatever
`LLM_SEED` the environment held, and the driver did not record it.
**Resolution:** `seeds: []`. The paired direction (0 vs 3 retrieved, 28 vs 4
gate-rejected) is the result, not the absolute rates.
**Paper implication:** none beyond what RESULTS Limits already says.

## 2026-09-09 — the manifest was a scaffold until the record repair
See RESULTS.md A-1 for every field filled on 2026-09-09 (old → new) and how
each was established. `data/thinkcap-probe.json` was corrected in place
(holdout 0.4031 → 0.4039, RESULTS A-2).
