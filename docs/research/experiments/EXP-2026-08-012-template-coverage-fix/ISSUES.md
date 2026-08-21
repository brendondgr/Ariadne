# Issues — EXP-2026-08-012

## I1 — Fix 1 is not a bug fix. It is a product decision, and it is not taken here

I described the pinned `(t:Technique)` target as "a single word" and a defect.
That was wrong, and the evidence is in this repository.

`evalset/questions.py::_top_level` filters the execution-accuracy gold to
parent techniques for exactly three templates — `group_techniques`,
`tactic_techniques`, `campaign_techniques`:

```python
def _top_level(ids: list[str]) -> list[str]:
    objs = a["objects"]
    return [i for i in ids if objs.get(i, {}).get("label") == "Technique"]
```

`gold_bank.py` collects every `attack-pattern` target from raw STIX, which
includes sub-techniques; `_top_level` then deliberately drops them. So the
narrow answer is an intentional roll-up, not an accident, and the pinned target
implements it faithfully.

**The two external benchmarks disagree with each other about this.** CTIBench's
`cti-ate` prompt says outright *"excluding any subtechnique IDs"*. AttackQA
lists them — its gold for G0020 is `T1120, T1480.001, T1542.002, T1564.005`,
three of four being sub-techniques. There is no neutral answer available.

**What widening would buy and cost.** Measured, both ways:

| | before | Fix 2 only | both fixes |
|---|---:|---:|---:|
| external recall | 0.6836 | 0.7633 | **0.9825** |
| `techniques_for_group` | 0.295 | 0.295 | 0.979 |
| `techniques_for_campaign` | 0.326 | 0.326 | 0.975 |
| internal answers changed | — | **0 of 60** | 0 of 60 |
| internal query strings changed | — | **0** | 2 |
| specialist suite | 1 pre-existing | 1 pre-existing | **7 failures** |

The seven are not noise. They include `test_generic_only_isolation`, the
frozen-tree guard that pins query strings back to `freeze/holdout-v1` and
`freeze/arm-baseline-2` so the recorded arm figures stay comparable, and
`test_score_execution`, which drops from ≥0.90 to **0.8478** with seven cases
bucketed `over_broad` — the narrow gold pushing back, correctly, on its own
terms.

Adopting Fix 1 therefore requires three deliberate acts: a generation-3 frozen
fixture with these two templates marked superseded (the repository already has
a documented procedure for this, used when the outer join moved two strings),
regenerating the execution-accuracy gold, and accepting that published EX
figures move.

**The patch is kept, not discarded:** `data/proposed-fix1-widen-target.patch`
applies cleanly to `utils/specialists/cypher/builder.py`. It is a decision
waiting on an owner, not an unfinished task.

## I2 — the unit test passed while the feature did not work

The first version of Fix 2 asserted on `draft.query` and passed. The external
run then scored the four families at 0.000 exactly as before.

The template was correct and firing. The **normalizer** had no branch for its
`group_id` / `software_id` columns, so the rows fell through to
`_normalize_flat` and every identifier came back as `unknown`. Four records
retrieved, zero readable.

A query-string test cannot see that. The measurement could, immediately. The
lesson is narrow and worth keeping: a new template is not one change but two,
and the round trip is the only thing that proves it.

## I3 — two tests failed because the gap closed, and one of them documented the gap

`test_binding_check::test_the_gate_fails_a_misrouted_draft_end_to_end` asserted
that the binding gate *refuses* "Which groups relate to S0154?". Its own comment
explained why: *"the router picks the Group template because Group was named,
and no direction flip repairs it because the template does not walk that edge.
The gate is what stops it executing."*

That was an accurate description of the defect. The gate was doing the only
thing available to it. With `group_software` walking the edge there is no
misroute left to catch, so the assertion is now inverted and the reason is
recorded in the test.

`test_binding_audit::test_no_reverse_direction_ask_is_left_unserved` lost
`("group_techniques", "S0154")` from its residue of known-unserved asks, for
the same reason.

Neither is a regression. Both are the audit shrinking.

## I4 — one pre-existing failure, from the worktree rather than the code

`test_docs_contracts::test_every_cited_repo_path_exists` fails in this worktree
because `POINTERS.md` files cite paths under `docs/evaluation/experiments/`,
which is gitignored and exists only in the main checkout. Verified failing on
the unmodified tree before any change here.
