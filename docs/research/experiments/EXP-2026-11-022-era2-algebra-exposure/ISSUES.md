# ISSUES — EXP-2026-11-022

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

## 2026-11-22 — Phase H stop rule fired after the core sitting (Gemma, variants)
**Impact:** Stage 3 halted after two of four sittings (off-A, core); core+ext and off-B were not run.
Against off-A, Gemma T-lazy-G's exact variant answers fell from 354 to 338 (−16; the bar is −10).
Its confidently wrong count barely moved (30 → 31). Both Qwen arms passed: exact 328 → 331 and
346 → 341, confidently wrong 54 → 46 and 52 → 39. Dev kept 262/269/253 → 262/267/251, with 0
confidently wrong throughout. The probe measure half shows the help side clearly: core exact
84, 86 and 80 of 99 (off: 0).
**Cause:** item-level churn (`phase-h/core-vs-offA-variants.json`). Gemma lost 39 and won 23;
17 of the losses used an operator step and 14 of those abstained. 11 were a type scan with
`contains_text` on `name` or `description`, carrying the model's own paraphrase of an
entity it could not name (tiers T4 and T5: no id, no exact name). A literal substring scan for
a paraphrase matches nothing. Off, the same questions went through `resolve_entity`'s fuzzy
match. The non-operator churn (22 lost, 19 won) is balanced, i.e. noise. Qwen loses the same way
less often (2–3 text scans; 11–12 operator losses against 3–6 operator wins).
**Resolution:** stopped as the protocol requires and reported to the operator. Phase G's three
fix rounds are spent, so a further fix is the operator's decision.
**Paper implication:** a literal text-condition operator displaces fuzzy entity resolution on
paraphrased questions unless the planner is told the difference; report as an exposure cost.
