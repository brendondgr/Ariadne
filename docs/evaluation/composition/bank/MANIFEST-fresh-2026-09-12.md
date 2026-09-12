# Expansion bank

| | |
|---|---|
| questions | 282 |
| dev / holdout | 0 / 0 |
| split rule | none — one whole bank, used once |
| distinct specs | 282 |
| census shapes covered | 34 / 34 |
| author | claude-opus-5 (subagent) |
| keep rate | 97.9% |
| sha256 | `69e901d670664d6173b0907cb2e582887fcfbc91c66bece23c9ba68122296a0d` |

By tier: {'D0': 25, 'D1': 28, 'D2': 33, 'D3': 40, 'D4': 65, 'D5': 56, 'D6': 35}

**The split is `sha256(spec_id)` parity, drawn before anything was run.** It
cannot have been influenced by which half scores better.

**This bank is deliberately skewed** toward under-represented shapes. Pooled
accuracy over it is not a natural-distribution estimate. Report per-shape, and
reweight using `meta.reweighting.census_instances` for a comparable figure.
