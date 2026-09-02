# Expansion bank

| | |
|---|---|
| questions | 572 |
| dev / holdout | 284 / 288 |
| distinct specs | 492 |
| census shapes covered | 34 / 34 |
| author | claude-opus-5 (subagent) |
| keep rate | 98.6% |
| sha256 | `ad99afb18934bd7db233c292d235a4350c332114c357ea624123031ff0ab434e` |

By tier: {'D0': 61, 'D1': 63, 'D2': 77, 'D3': 89, 'D4': 117, 'D5': 105, 'D6': 60}

**The split is `sha256(spec_id)` parity, drawn before anything was run.** It
cannot have been influenced by which half scores better.

**This bank is deliberately skewed** toward under-represented shapes. Pooled
accuracy over it is not a natural-distribution estimate. Report per-shape, and
reweight using `meta.reweighting.census_instances` for a comparable figure.
