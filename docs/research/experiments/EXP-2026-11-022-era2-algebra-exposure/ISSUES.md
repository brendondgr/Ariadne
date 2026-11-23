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

## 2026-11-22 — Fix round 4 (a deviation), on the operator's decision
**Impact:** the measured core configuration is the fixed one. The first core sitting stays on
record (`phase-h/core-superseded-1/`, moved from `phase-h/core/`) as the stop-rule evidence. off-A is reused across the fix.
**Cause:** the stop rule (entry above).
**Resolution:** PROTOCOL Amendment 1: literal-text teaching, and an empty whole-label text scan
refused once, counted live at planning time.
**Paper implication:** report that core passed only after a fourth teaching fix, which Stage 1 did
not allow, and report the first core sitting's numbers beside the fixed ones.
**Proving set (2026-11-23):** `fix4-small/score.json` (scorer `data/fix4_score.py`, runner
`data/fix4_prove.sh`). It cleared Amendment 1's bar:
- Gemma core's operator-attributed variant losses: 4 on these items, against 14 on the same items in the first core sitting (bar: well below 17).
- No control was lost to an operator step on an arm that lost none in round 4.
- Probe tune exact stayed within 5 of round 4 on every arm (largest gap 3).
Disclosed: Gemma core lost one control to an operator step (F-FAN-01 T2, a union of three anchor walks whose output fed a Technique expand). That arm also lost one in round 4 (A-LKP-04 T4), so the bar does not apply to it.
The first proving attempt failed preflight on a stale store (the full pytest after the fix rewrote `data/`); its logs are in `fix4-small/stale-store-attempt/`. The stores were reloaded and the proving set re-run whole.
