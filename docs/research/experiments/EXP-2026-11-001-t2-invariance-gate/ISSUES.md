# ISSUES — EXP-2026-11-001

## Two defects in the shipped `GremlinQueryBuilder.expand` (found 2026-11-13)

`utils/specialists/gremlin/builder.py`, `expand()`:

1. **Wrong relationship name.** It inlines the registry's relationship name (`ChildOf`) into
   `.out("ChildOf")`. The CAPEC store's edges carry the loader's label (`CHILD_OF`,
   `utils/graph_loader/stores/gremlin.gremlin_edge_label`). Every CAPEC relation facet whose
   registry name differs from its stored label returns nothing: ChildOf, CanPrecede, CanFollow,
   PeerOf and CanAlsoBe. Probe: `CAPEC-66 ChildOf out` returned 0 records; translated, it returns
   `CAPEC-248`.
2. **Attack-pattern-only anchor id.** It anchors with `_capec_gremlin_id`, whose own docstring
   says it is wrong for about one CAPEC id in ten (views and categories). The rest of the
   builder uses `_capec_candidate_ids`.

Not fixed in the shipped code during this experiment, because the tree is frozen at
`killtests-start` for the comparison. The kill-test executor (`utils/killtests/graph.py`) works
around both. Fixing them is a follow-up for the shipped primitive.

## Slot gold

Three issues, handled by the pre-run amendments in PROTOCOL.md:
- the `HAS_TECHNIQUE` label on group, software and campaign technique questions (49 items);
- two-label targets (47 items);
- absent anchors (18 items).
