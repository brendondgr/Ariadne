# ISSUES — EXP-2026-09-029

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

<!-- Entry template — newest first:

## YYYY-MM-DD — <one-line summary>
**Impact:** what this changes about the reported numbers (e.g. "seed 3 excluded; n=4 not 5 for this cell").
**Cause:** the mechanism, if known.
**Resolution:** what was done. "Not resolved" is a valid answer.
**Paper implication:** what must be stated in the paper because of this.

-->

## 2026-09-16 — the bridge shows the judge claims, not evidence records
**Impact:** faithfulness, groundedness and the hallucination lists are biased against every answer;
completeness (gold identifiers stated) and abstention are the readings to use.
**Cause:** `scripts/variant_harness.py` rows keep entity ids, claims, queries and abstentions, not
the evidence records; `scripts/judge_variants.py` therefore hands the judge an answer with no
records, and the rubric marks stated identifiers as unsupported.
**Resolution:** stated here and in RESULTS.md; not repaired inside this experiment.
**Paper implication:** quote only completeness and abstention from this pass.

## 2026-09-16 — the run started before the folder existed
**Impact:** `dirty: true`; the protocol was written during the run with no judgment read.
**Cause:** the judge was launched from Step 10's checklist before the experiment was scaffolded.
**Resolution:** disclosed; the run's inputs are hash-pinned. **Paper implication:** none.
