# EXP-2026-08-013 — Protocol

## Phase 1 — the routing floor (this run)

Hold everything constant except the number of live sources.

1. `scripts/tri_compose.py` builds `data-tri/` from the three existing sources:
   each card, each overlay, and each `graphs/<dataset>/canonical/` tree. The
   canonical tree is not optional — the schema registry is built from it, and a
   composition without it leaves every schema-driven primitive falling through
   to a hardcoded MITRE fallback while still *looking* like it routed correctly.
   `--check` refuses such a composition.
2. Per-source endpoints via `ARIADNE_ENDPOINT_<DATASET>`. Required: two of the
   three sources are Neo4j-backed, and a URI resolved by backend gives them the
   same address.
3. Run bank 3 (117 questions, both arms) under `--tri`. The bank, the gold and
   the scorer are the ones EXP-2026-08-011 used, unmodified.
4. Compare per question and per kind against the single-source run of the same
   bank at the same commit.

**No knowledge is supplied.** There is no mapping, no join, no authored
correspondence between the identity graph and either catalogue. That is
deliberate: it makes the reading a floor rather than a demonstration, and
whatever phase 2 adds has to beat it.

**Pre-registered reading.** Any per-kind figure that moves is the cost of extra
sources. Any that does not is evidence the retrieval path is genuinely
card-driven, since the same code answered the same questions identically with
three schemas loaded instead of one.

## Phase 1a — fix the router, re-run both conditions (done)

The defect phase 1 found is fixed and both conditions were re-run at the same
commit, so the comparison is not confounded by the fix. Pre-registered reading,
unchanged: any per-kind figure that moves is the cost of extra sources.

## Phase 2 — cross-source correlation (not started)

Was blocked on phase 1's finding; that block is now lifted. Correlating a customer finding with
ATT&CK is not worth building while the router pulls in ATT&CK for 68% of
questions that have nothing to do with it: a correct correlation would be
indistinguishable from the noise already arriving.

When it is unblocked, the bridge cannot be a value join. The identity graph
contains no ATT&CK identifier anywhere, so there is nothing to join *on*. The
correspondence is between an **edge type** and a technique — a `DC_SYNC` edge is
T1003.006, `WRITE_GP_LINK` is T1484.001 — which is knowledge supplied by us, not
a fact discovered in the data, and must be declared and reviewed exactly as
`CANONICAL_JOIN_KEYS` requires. Any result measured against a mapping we authored
must say so plainly.
