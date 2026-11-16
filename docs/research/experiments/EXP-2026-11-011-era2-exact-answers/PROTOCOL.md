# PROTOCOL — EXP-2026-11-011 Era 2 Step 5: exact answers, result handles, nothing cut silently

Written 2026-11-16, before the recorded runs below. **Disclosed:** the code and its unit and live
tests already exist. A dry run of the hub timings was done while building, and after it the
Neo4j fetch was changed twice: no server-side sort, then one collected list instead of a million
records. The recorded hub run is new and uses the committed code.

## Question

After Step 5, does every path return **complete** result sets with **exact** totals, and say so
explicitly whenever a ceiling stops it? Concretely:
- Do paged and unpaged fetches agree, and do totals equal the database's own count?
- Do set operations on handles equal the database's own operations?
- Do hubs of 10⁵ and 10⁶ edges come back exact and fast?
- Do the existing banks' answers stay the same?

## What changed

1. **Connectors** return `Rows`, which know whether more rows existed beyond the cap.
2. **The scaffold** probes a result that filled its ceiling exactly with one extra row. A cut
   result is `partial`, with a `ceiling` trace; `execute` always records `row_ceiling` and
   `truncated`.
3. **The composer** never writes "All N" for a cut list. It states the real total, or "at
   least N" at a row ceiling, and adds a note.
4. **The agent layer:**
   - `utils/agent/exact.py`: full sets with exact totals in Neo4j and Gremlin, in stream or
     keyset mode, with an explicit ceiling;
   - `utils/agent/handles.py`: `set:<n>` handles stored in the run log's database, with set
     operations and keyset paging;
   - `utils/agent/view.py`: the lossless view (exact total, exact facet counts with the
     remainder counted, a labelled sample, and an empty-result diagnosis with the nearest
     options).
5. **The fast-path envelope** carries the full result sets, stored as handles, and is
   `partial` when a set was cut.

## Gates (from the plan)

- **G1, zero silent truncations.** The syntax-tree scan finds no row cap outside the governed
  one. The scaffold flags a cut and does not flag an exact fit. The composer never says "All
  N" for a cut list. This is checked by `test_never_silent_truncation.py`,
  `test_never_silent.py` and `test_ceiling_live.py`.
- **G2, paged equals unpaged** (stream against keyset, with page size 7), and every total equals
  the database's `count(DISTINCT …)`. Measured on the kill-test fixture graphs (CypherBench in
  Neo4j and Gremlin), over 4 set shapes, in both backends. The backends must also return
  identical sets.
- **G3, set operations equal the database.** `intersect` on two handles equals a database-side
  intersection query, in both backends.
- **G4, the composer's count equals the database's.** On the 284 dev questions (authored plan,
  `generic_composed`), checked over every enumeration claim:
  - "X has N <things>: …" must have N equal to the ids it lists plus the number it says are
    withheld;
  - "N result(s) for this question" must have N equal to its result's distinct ids;
  - no result may hit its ceiling.

  Together with G1 (no other cap exists), that makes N the number of rows the database
  returned. *Amended before any run: none of the 284 dev answers uses the "N result(s)" form,
  so the check covers the form they do use, 516 claims.*

## Expectations

- **E1, hubs.** The 10⁵- and 10⁶-edge hubs come back exact (every member, total equal to edge
  count) in both backends. The p95 over 20 fetches stays within the cards' 5 s query timeout.
  Keyset equals stream on the 10⁵ hub.
- **E2, recorded-answer regression.** The deterministic arm on both banks and `generic_composed`
  on dev, compared with the same arms run just before Step 5 (at 38e803e5, the walk-fix tree):
  identical answers and ids. The only differences allowed are the new trace fields
  (`row_ceiling`, `truncated`). Any other change is listed and explained.
- **E3, ceiling census.** At the authored plans' lifted limit of 20,000 rows, 0 of 284 dev
  questions hit the ceiling; the plan expected this, since current answers are under 1,000
  rows. The census also counts how many would hit the planner's 1,000-row limit: an
  observation, with no expectation set.

## Procedure

```bash
uv run python scripts/era2_hub_bench.py bench --out docs/research/experiments/EXP-2026-11-011-era2-exact-answers/data
uv run python scripts/era2_exact_check.py --out docs/research/experiments/EXP-2026-11-011-era2-exact-answers/data
```

`era2_exact_check.py` runs the live and offline suites named above, the regression runs and
diffs, the ceiling census and the G4 count check, and writes `data/exact.json`.

## What would falsify this

- **Any G1–G4 failure** blocks the Step 5 commit until it is fixed.
- **A changed recorded answer** (E2) that the change does not explain is a defect.
- **A hub over the timeout** is reported as is: it bounds what the agent can fetch in one call.
