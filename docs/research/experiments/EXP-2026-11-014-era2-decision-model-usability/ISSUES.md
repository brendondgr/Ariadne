# ISSUES — EXP-2026-11-014

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

## 2026-11-17 — Round 2: the tree was dirty again, and the drift check was re-run
**Impact:** none on any figure.
- **What was uncommitted.** The round-2 code (`build2`, `run_orders`, `extra_orders` and the
  round-2 scorer) was uncommitted while round 2 ran. Amendment 2 itself was committed first
  (154c9113).
- **The re-check.** pplx's `/health` reported a server temperature of 1.55 before round 2.
  The client sends 1.0 on every request, so this is the server default. The drift check was
  re-run as amendment 2 requires: pplx agreed on 1.0 and d3 on 0.98 (`data/drift2.json`).
  Round 1's `drift.json` is unchanged.
- **Added after the first round-2 score:** agreement with Qwen on gated items, in the
  shortlist cells. It is computed from the saved records.

**Cause:** the code was written and run in one sitting.
**Resolution:** committed together with the results.
**Paper implication:** none.

## 2026-11-17 — Round 2: equal flip rates for the two shortlist choosers
**Impact:** none. Both choosers flip 28 of 464 items, but the two sets share only 7. It was
checked as a suspected scoring bug and is a coincidence.
**Resolution:** reported in RESULTS §2.9.
**Paper implication:** none.

## 2026-11-17 — The tree was dirty during the runs, in the experiment's own uncommitted code
**Impact:** none on any figure.
- **What was uncommitted.** `scripts/era2_usability.py`, `scripts/era2_usability_score.py`,
  the `yesno_batch`/`yesno_decide` additions to `utils/decision/usability.py`, their tests, and
  amendment 1 of the protocol. Everything ran from the commit that records these results.
- **What changed after the runs.** Three derived figures were added to the scorer after the
  first score: the share of the wording gain from shared items, agreement with Qwen on gated
  items, and the yes/no diagnostics. All three are computed from the saved records; no call
  was re-made.

**Cause:** the code was written and run in one sitting, before the commit.
**Resolution:** `dirty: true` in the manifest. The commit that adds the results also adds the
code.
**Paper implication:** none.

## 2026-11-17 — pplx's yes/no answers follow the answer order, not the option
**Impact:** the yes/no and verifier cells for pplx measure position bias, not judgment
(RESULTS §2.4). This is a finding, not a defect. It was checked as a suspected bug before
scoring.
- **The check.** The request carries a per-question `question` field, which the client's
  protocol documents, and the yes key is mapped by position in both orders.
- **What it showed.** P(yes) moves by 0.09 with the answer order. Within one item it varies by
  a median of only 0.104, against d3's 0.4047.

**Cause:** pplx-decider is trained for choosing among described options, not for one-option
yes/no.
**Resolution:** reported as measured.
**Paper implication:** do not use pplx-decider as a yes/no judge or verifier.

## 2026-11-17 — The frozen rule-filter match treats a hyphen as a word boundary
**Impact:** some items were narrowed less than intended. "Sub-techniques" in a question also
counts as naming "technique", so Technique targets are kept alongside SubTechnique ones. This
favours the filter, and it still did not help (RESULTS §2.3).
**Cause:** `\b` matches at a hyphen. The rule was frozen in the protocol and had already run
when a unit test exposed this.
**Resolution:** not changed, since the rule is pre-registered.
`utils/decision/tests/test_usability.py` pins the behaviour so that a later fix is a visible
amendment.
**Paper implication:** none beyond noting it with the rule filter's result.

## 2026-11-17 — The D4 role population is 464, not the 458 the protocol's counts note first said
**Impact:** none on any figure. Erratum 1 had already corrected the narrowed count (312, not
365). The population note's "of the 458" should read "of the 464": 458 multi-option items,
plus 6 "none" items with exactly two options.
**Cause:** a hand count before the builder ran.
**Resolution:** amendment 1's counts note states 464, and every figure is on 464.
**Paper implication:** none.

## 2026-11-17 — pplx-decider was unreachable at first
**Impact:** none. Connections through the SSH tunnel to :7500 were reset for a few minutes
before the drift check. The server came back on its own, the drift check then agreed on 1.0,
and no record was written while it was down.
**Cause:** the tunnel, not the server.
**Resolution:** waited.
**Paper implication:** none.

## 2026-11-17 — No graph was read, so there was no Gremlin store check
**Impact:** none. Every item, option and target kind comes from Step 7's saved
`items.jsonl`. The usual step of checking vertex counts after a machine restart does not
apply here.
**Resolution:** not needed.
**Paper implication:** none.
