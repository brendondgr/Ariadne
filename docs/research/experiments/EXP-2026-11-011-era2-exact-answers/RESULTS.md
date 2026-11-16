# RESULTS — EXP-2026-11-011 Era 2 Step 5: exact answers, result handles, nothing cut silently

## 1. Headline

**Every gate passes.** Nothing is cut silently any more, and every set comes back complete with
its exact total.

| Gate | Result |
|---|---|
| G1, no silent cut | holds |
| G2, paged sets equal unpaged; totals equal the database's own count | holds, in both backends, and the backends return identical sets |
| G3, set operations on handles | equal the database's own intersections |
| G4, the composer's counts | consistent on all 516 enumeration claims |

- **Hubs.** Hubs of 10⁵ and 10⁶ edges come back exact in Neo4j and in Gremlin. The slowest p95
  is 3.47 s, inside the 5 s card timeout.
- **Regression.** Every recorded answer is unchanged.
- **One question changes status.** At the planner's 1,000-row limit,
  `D4-mitigates-uses-M1047` hits the ceiling. Before Step 5 that was a silent cut; it is now an
  explicit `partial`.

## 2. Results table

From `data/exact.json` and `data/hubs.json`. Hub figures are p95 over 20 fetches on the scratch
stores.

| Hub | Backend | Exact | Median | p95 | Keyset = stream |
|---|---|---|---:|---:|---|
| 10⁵ | Neo4j | yes (100,000) | 0.41 s | 0.46 s | yes (3.8 s in pages of 10,000) |
| 10⁶ | Neo4j | yes (1,000,000) | 1.46 s | 1.54 s | — |
| 10⁵ | Gremlin | yes (100,000) | 0.75 s | 0.80 s | yes (6.5 s in pages of 10,000) |
| 10⁶ | Gremlin | yes (1,000,000) | 3.30 s | 3.47 s | — |

| Check | Result |
|---|---|
| G1 suites: source scan, scaffold probe, composer, live ceiling | 12, 3 and 2 tests, all pass |
| G2 and G3: `test_exact_live.py` (4 set shapes × 2 backends, cross-backend, intersect and union) | 20 of 20 pass |
| Handles and the fast-path envelope | 13 and 20 tests, all pass |
| G4 enumeration counts (dev, authored plan) | 516 claims, 0 mismatches |
| E2 regression, deterministic arm, bank-2026-08-19 | 30 of 30 identical |
| E2 regression, deterministic arm, bank-2026-08-20 | 30 of 30 identical |
| E2 regression, `generic_composed`, dev | 284 of 284 identical |
| E3 ceiling census at 20,000 rows | 0 of 284 |
| E3 ceiling census at 1,000 rows (observation) | 1 of 284: `D4-mitigates-uses-M1047::indirect` |

## 3. Figures

None.

## 4. Interpretation

**Expectations against outcomes:** all met.
- G1 to G4: met.
- E1: every hub is exact and within the timeout.
- E2: no answer changed.
- E3: 0 ceiling hits at 20,000 rows.

**What Step 5 gives the rest of era 2:**
- **For the agent loop (Step 11):** the loop can build on results through handles without ever
  moving rows through the model. Every set it holds is complete or says it is not.
- **For the composer:** it can no longer claim "All N" for a list it cut.
- **For the fast path:** its envelope now carries the full sets, which Step 11's
  fast-then-loop arm needs to compare like with like.
- **For RQ2:** questions with answers above the ceiling are now `partial`, not silently short.

**The one ceiling hit shows the change.** At the planner's 1,000-row limit, a question about the
techniques that a mitigation's users use returned more rows than the limit. Before, its answer
looked complete. Now it says it is partial, and why.

## 5. Threats to validity

- **The hubs are synthetic** (one hub, uniform leaves), on scratch containers with default
  memory. Real hubs with property-rich neighbours fetch more bytes. The exact executor returns
  ids only, and views fetch properties only for the sample and the facets.
- **Keyset paging re-walks the hub on every page.** At 10⁶ it would take minutes, so it was
  checked against streaming only at 10⁵. Streaming is the default.
- **G4 checks the composer's arithmetic plus the absence of any other cap,** not a fresh
  database count for each of the 516 claims.

## 6. What surprised us

- **The composer told an untruth whenever it hit its own listing bound:** it wrote "All 200
  result(s)" for a longer list. No current answer had reached that bound, so no figure was
  affected, but it would have happened on the first large set.
- **Neo4j's speed depended on the shape of the reply,** not on the traversal. Returning one
  collected list instead of a million records cut the 10⁶ fetch from 8.3 s to 1.5 s.

## 7. Follow-ups

- **Step 8's tools** take handles as inputs and return views, built on `exact.py`, `handles.py`
  and `view.py`.
- **Step 11** should report `partial` answers separately from `answered`.

## 8. Reproduction

```bash
uv run python scripts/era2_hub_bench.py load      # recreates the scratch hubs
uv run python scripts/era2_hub_bench.py bench --out docs/research/experiments/EXP-2026-11-011-era2-exact-answers/data
uv run python scripts/era2_exact_check.py --out docs/research/experiments/EXP-2026-11-011-era2-exact-answers/data
```
