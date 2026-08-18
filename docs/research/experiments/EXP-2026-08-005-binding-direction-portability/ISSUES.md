# ISSUES — EXP-2026-08-005

## 2026-08-18 — Nothing in this experiment is judged

**Impact:** all figures are retrieval. `0.8952` may not be printed beside Arm A's
`0.689` correctness from `EXP-2026-08-002`, and this arm's precision is
unmeasured.

**Resolution:** not resolvable with this instrument. Recorded as follow-up 1.

## 2026-08-18 — The blind figure here is co-authored with its own test

**Impact:** holdout v1 diagnosed the defect this experiment repairs, so a v1
number measured after the repair is exactly the co-authoring the holdout exists
to expose — the same failure that made the 120-question bank read 0.99.

**Resolution:** the number stands as a **diagnostic** and is labelled as one in
`RESULTS.md` §5. The headline blind figure must come from a holdout v2 drawn
after the fix. Not fixed here; recorded as follow-up 3.

## 2026-08-18 — The templates keep the inner join, deliberately

**Impact:** five identifiers still miss on the blind set. `capec_maps_to` and
`cwe_chain` drop an anchor with no mapping, which `EXP-2026-08-004` fixed on the
generic branch only.

**Cause:** porting it rewrites query strings the frozen fixture covers, so it
breaks `test_generic_only_isolation.py` and makes the 2026-07-26 arm figures
non-comparable.

**Resolution:** not fixed. This is an operator decision about whether the arm
figures are re-run, unchanged from `EXP-2026-08-004`'s `ISSUES.md`. What this
experiment adds is the price: five identifiers in four named cases.

## 2026-08-18 — The audit's CAPEC seed vocabulary is one family wide

**Impact:** the audit draws seed exemplars from the committed question banks,
and every CAPEC-source task in them anchors on a CAPEC identifier. CWE and
ATT&CK anchors reach the Gremlin builder only via `--seed capec=...`, so the
CAPEC side of the inventory is less complete than the ATT&CK side.

**Resolution:** documented in `seed_vocabulary`'s docstring and exposed as a CLI
flag rather than hidden. A dataset whose catalogue is narrow gets a narrow
audit, and that is a fact about the catalogue worth seeing.

## 2026-08-18 — `seed_in_scope` under-reports where identifiers are translated

**Impact:** the triage flag reads the seed through the learned schemes. CAPEC's
analyst identifier (`CAPEC-1`) is not its stored one (`capec:attack-pattern:1`),
so CAPEC findings triage as misroutes even when the seed's label is in scope.

**Note:** the mismatch verdict itself is unaffected — it is judged on the values
the builder actually bound, which are post-translation.

## 2026-08-18 — Two false positives were found by the test suite, not by review

**Impact:** the first version of the check rejected `subtechnique_parent`
(`WHERE t.attack_id IN $ids OR st.attack_id IN $ids`, satisfiable via the second
disjunct) and would have rejected `technique_tactics` (`WHERE (t:Technique OR
t:SubTechnique)`, one alias carrying two labels). Both would have dropped real
answers.

**Resolution:** fixed — bindings group by parameter, and an alias may carry
several labels. Recorded because it corrects the Step 2 inventory published in
commit `ec01fe7`: 22 repairable findings over 6 templates was wrong; 16 over 5
is right. It is also the argument for the guard's timid bias.

## 2026-08-18 — Seeds and variance

**Impact:** `n_runs: 1`, seeds unrecorded, one snapshot, n=30 on the blind set.
Consistent with every prior arm run in this repository and no better.
