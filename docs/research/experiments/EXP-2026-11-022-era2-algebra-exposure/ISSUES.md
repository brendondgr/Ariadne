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

## 2026-11-23 — The stop rule fired again on the fixed core sitting (Gemma, variants)
**Impact:** the chain halted after the core sitting (fix-round-4 tree 840f20da); core+ext and off-B
were not run. The sitting is kept as `phase-h/core-superseded-2/`. Its stop check, and the
confidence bar against off-A alone (provisional), are in `metrics-stop-check.json`.
- **Against off-A:**
  - Gemma's exact variant answers fell 354 → 335 (−19; bar −10).
  - Qwen held: T-lazy 328 → 324, T-full 346 → 343.
  - Confidently wrong: 54 → 54, 52 → 47, 30 → 30.
  - Dev kept 265 / 268 / 253; dev confidently wrong 0 / 0 / 1.
  - Probe core exact 87 / 90 / 81 of 99.
- **Provisional bar:** both Qwen arms are confident on every Amendment 3 check. Gemma fails only variants exact: −0.027 [−0.052, −0.002].
**Cause:** `vs-offA-variants-by-cause.json`. Fix 4 did what it was for. Gemma's operator-step losses fell
from 17 to 7, and its text-scan losses from 11 to 1. Two kinds of teaching refusal remain,
and both land on the repair turn, after which no turn follows, so the refusal is final and the answer abstains:
- a one-entity scan ("looks up one named entity"): 5 Gemma losses, e.g. a TaxonomyEntry scan on
  `entry_id = 'T1021'`, which as stored is `1021`;
- an empty text scan: 3 Gemma losses and 1 Qwen T-full loss.

The rest of Gemma's net loss (41 lost, 22 won) is clean plans of today's step kinds (20 lost, 15
won) and other refusals (6 lost, 4 won). Gemma's off runs on this bank are 350 (EXP-2026-11-018) and 354
(off-A), and its core runs are 338 and 335, so the drop is not an off-A outlier. 11 items are exact in both
off runs and lost in both core runs, against 3 the other way round. Most are T4/T5 questions that describe
an entity, where Gemma reaches for a scan.
**Resolution:** fix round 5 (PROTOCOL Amendment 4), the first of the two Amendment 2 allows.
**Paper implication:** a teaching refusal costs an answer when it lands on the last turn; any
refuse-and-teach guard needs a last-turn policy.

## 2026-11-23 — The fix-5 proving set fails Amendment 4's bar on two counts
**Impact:** the Stage 3 chain was not started on the fix-5 tree (18702758). Scores: `fix5-small/score.json`.
- **Teaching refusal final: 1** (Gemma core, C-CWE-02 T4). The repair reply ran away and came back
  empty (`parse_error: empty model response`). The planner then keeps the first plan, and so
  the first turn's empty-text-scan refusal became final. Fix 5 checked only a repair turn that
  returned a plan.
- **Controls lost to an operator step, on arms that lost none in the fix-4 set: 2.**
  - **T-lazy core, F-CTM-04 T0.** The model unions Technique and SubTechnique, then expands
    mitigations `from_step` the union with `anchor_label` Technique. The `algebra_producer`
    coercion narrowed the start to Technique, so every sub-technique was dropped (Jaccard 0.4).
  - **T-lazy core+ext, dev control D5-mitigates-x_mitre_platforms-M1042.** The model filtered
    `x_mitre_domains contains 'SaaS'` where it meant `x_mitre_platforms`. That is a choice of
    property, not an operator defect. Off-A lost the same item with no operator, and so did the
    first core sitting. 0 of the 105 filter conditions in the variant runs (core sitting 2 and
    fix-5) use a value absent from their own property, so no guard was written for it.
- **Probe tune exact:** within 5 of fix-4 on every arm (largest gap 3). This clause passes.
- **Recovered core-sitting losses:** core 7/32, 6/20, 23/40; core+ext 12/32, 11/20, 16/40
  (T-lazy, T-full, Gemma).

**Cause, by a sweep of every operator loss vs off-A in the set:** besides the two refusal cases, the
main operator loss is one shape: a step whose start is narrower than today's step would be.
- **A cross-graph `from_step`** compiles to `FromStep(q, [named label])`, which matches
  `(v:Technique)`. Today's cross-graph step matches its seed ids with no label
  (`MATCH (n) WHERE coalesce(n.attack_id, n.id) IN $ids`), and the join key declares that
  Technique *and* SubTechnique carry the key. Examples: F-FAN-02/03 T0–T1 (T-full, both
  configurations) and F-CTM-06.
- **A step from an operator step that holds several labels** is narrowed to its one
  `anchor_label`. Across every sitting, 11 such narrowings exist; 10 lost their item.

**Resolution:** fix round 6 (PROTOCOL Amendment 5), the last that Amendment 2 allows.
**Paper implication:** an operator IR that types its seeds must not be stricter than the
untyped path it replaces. A label filter the old path never applied silently drops rows.

## 2026-11-23 — The fix-6 proving set fails Amendment 5's control clause; no fix round remains
**Impact:** the Stage 3 chain is not run on the fix-6 tree (c998650a). Per Amendments 2 and 5, both
switches stay off and Step 9 closes. Scores: `fix6-small/score.json`.
- **Teaching refusals final:** 0 on every arm. That clause passes. Fix 1 (re-checking the first
  plan after an empty repair reply) did what it was for.
- **Probe tune exact:** within 2 of fix-5 on every arm. That clause passes.
- **Controls that off-A answered right, lost to an operator step on an arm that lost none in
  the fix-4 set: 3.**
  - **T-full core+ext, F-CTT-01 T3:** churn. The model anchored CAPEC-63 where the question
    names Phishing (CAPEC-98). The union in the plan plays no part.
  - **T-lazy core, F-FAN-01 T2, and T-full core+ext, F-CTM-04 T0:** the same plan shape,
    chosen this time and not in fix 4 or fix 5. The model describes Technique and SubTechnique
    from the CAPEC step, unions the two describes, then expands mitigations from the union.
    - Fix 6 made that shape's mitigations complete. F-CTM-04 now returns every gold mitigation;
      fix 5's run of the same shape on T-lazy returned 2 of 8.
    - The answer still overshoots. The union reads *through* the describes (`through_describe`),
      but `redundant_describes` drops a describe only beside a today-kind expand twin. So both
      describes stay in the plan, and their facet blocks add parent techniques and tactics
      nobody asked for (F-FAN-01: T1027, T1546, T1564, TA0003–5; F-CTM-04: TA0009).
    - This is the defect fix round 3 meant to remove ("the describe, now unused, is dropped as
      before"). It covered only plans with an expand twin.
- **Recovered core-sitting losses (reported, not gated):** core 6/32, 10/20, 18/40; core+ext
  10/32, 7/20, 17/40.
- **Operator losses against off-A on the set:** core 9, 3, 5; core+ext 7, 6, 5 (T-lazy, T-full,
  Gemma). In the second core sitting they were 9, 7, 6.

**Resolution:**
- No fix round remains (Amendment 2 allowed two after round 4; both are spent).
- `ARIADNE_ALGEBRA_CORE` and `ARIADNE_ALGEBRA_EXTENDED` stay off by default; their code stays.
- The describe read-through defect is OPEN_QUESTIONS Q66.

**Paper implication:** each fix removed the defect it targeted, and the model then found a new plan
shape that reached the next one. A proving set of re-runs cannot tell the two apart. Only a
plan-shape inventory with a model-free replay can.
