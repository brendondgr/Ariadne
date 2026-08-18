# PROTOCOL — EXP-2026-08-006 The template bridges as outer joins

**Pre-registered by `EXP-2026-08-005` RESULTS §4**, which named the five
identifiers this run is expected to recover before it ran: `CAPEC-116`,
`CAPEC-456`, `CAPEC-679`, `CAPEC-603`, `CAPEC-40`.

## 1. The change

`capec_maps_to` and `cwe_chain` projected `.out(edge)` — an inner join, which
drops an anchor with nothing on the far side. They now fold the mappings into a
possibly-empty list, exactly as the generic bridge has since `EXP-2026-08-004`.
The CWE chain stays asymmetric: inner on the first hop, so only patterns that
genuinely exploit the weakness appear; outer on the second.

## 2. Why this needed a new baseline

Unlike `EXP-2026-08-005`, this is **not** additive: it rewrites query strings
the frozen fixture covers. `freeze/arm-baseline-2` pins the tree immediately
before it. Captured with `git archive` from that tag, the cascade emits queries
byte-identical to `freeze/holdout-v1` for all ten frozen shapes — which is an
independent confirmation that everything between the two tags was additive.

Generation 2 of the fixture keeps the eight untouched cases verbatim and
hand-authors the two rewritten ones from the outer-join semantics, so the
isolation assertion is not regenerated from the code it checks.

## 3. Runs

Fixtures reloaded, then `--arm deterministic` on both banks at
`ORCH_MAX_HOPS=5`, paired against the `EXP-2026-08-005` roots.

## 4. What must not move

The development catalogue, and the abstention behaviour on every negative case.
