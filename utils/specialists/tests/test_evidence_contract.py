#!/usr/bin/env python3
"""The evidence reader's coupling to template output, pinned as a test.

D-025 decides that the reader's dispatch on template-emitted column shapes is
**part of what C-012 compares**, not an artifact to be corrected away —
guaranteeing that a query's output is consumable is a property templates
provide, and the free-form baseline wears its absence. A decision recorded only
in prose is unenforced, so this module turns it into a property.

The contract is narrow and exact: **every ``<entity>_id`` column the Cypher
builder emits must be a column the normalizer dispatches on, and vice versa.**
Both directions matter and they fail differently:

* A template emitting a new ``*_id`` with no reader branch falls through to
  ``_normalize_flat``, which reads neither column and emits ``unknown`` ids.
  That is exactly the failure mode that cost the free-form arm 7 of its 30
  questions in EXP-2026-08-008 (Q18), reached from the other direction.
* A reader branch for a column no template emits is dead dispatch — the same
  class of inflation as the two unreachable templates deleted in the record-
  hardening plan's step 2.

Deliberately scoped to ``*_id`` columns. Payload columns (``*_name``,
``properties_json``, ``facets``) are not dispatch keys and adding one is not a
contract change; ``facets`` is the one non-id dispatch key and is asserted
separately.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pytest

from utils.specialists.cypher.normalizer import CypherNormalizer

BUILDER = Path(__file__).resolve().parents[1] / "cypher" / "builder.py"

#: Columns aliased inside a subquery or WITH clause that never reach a result
#: row. Listed explicitly rather than inferred: an alias that stops being an
#: intermediate should fail this test loudly and be re-classified by a human.
_INTERMEDIATE_ALIASES = frozenset(
    {
        "anchors", "cand", "cnt", "exact", "h", "hop", "hops", "members",
        "n", "nodes", "outgoing", "page", "raw", "rel", "rel_type", "source",
        "sources", "total",
    }
)

#: The bare ``id`` column emitted by ``label_scan``, whose branch is the flat
#: fallback by design rather than by omission.
_FLAT_FALLBACK_COLUMNS = frozenset({"id"})

#: Columns that DO reach a result row but are not dispatch keys: they qualify a
#: neighbour the row already identifies rather than identifying a record of
#: their own. ``via_id`` names the hop a chained neighbour was reached through,
#: and is read by `_normalize_generic_neighbors` — the branch `neighbour_id`
#: already selected — never dispatched on. Listed rather than inferred, for the
#: same reason as the intermediates: one that starts identifying a record should
#: fail this test loudly.
_QUALIFIER_COLUMNS = frozenset({"via_id"})


def _emitted_id_columns() -> set[str]:
    """Every ``<entity>_id`` alias the Cypher builder projects into a result row."""
    source = BUILDER.read_text()
    aliases = set(re.findall(r"\bAS\s+([a-z_][a-z0-9_]*)", source))
    aliases -= _INTERMEDIATE_ALIASES
    aliases -= _QUALIFIER_COLUMNS
    aliases -= _FLAT_FALLBACK_COLUMNS
    return {a for a in aliases if a.endswith("_id")}


def _dispatched_id_columns() -> set[str]:
    """Every ``<entity>_id`` column ``CypherNormalizer.normalize`` branches on.

    Read from the AST of ``normalize`` rather than from a hand-kept list, so the
    test cannot drift from the code it is pinning.
    """
    src = inspect.getsource(CypherNormalizer.normalize)
    tree = ast.parse(src.lstrip() if src.startswith(" ") else src)
    found: set[str] = set()
    for node in ast.walk(tree):
        # matches `"technique_id" in rows[0]`
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            if isinstance(node.ops[0], ast.In) and isinstance(node.left, ast.Constant):
                value = node.left.value
                if isinstance(value, str) and value.endswith("_id"):
                    found.add(value)
    return found


def test_every_emitted_id_column_has_a_reader_branch() -> None:
    """A template may not emit an id column the reader cannot dispatch on."""
    orphaned = _emitted_id_columns() - _dispatched_id_columns()
    assert not orphaned, (
        f"template(s) emit {sorted(orphaned)} but the normalizer does not "
        "dispatch on them, so those rows fall through to _normalize_flat and "
        "emit `unknown` ids. Add a branch to CypherNormalizer.normalize, or "
        "classify the alias as an intermediate in this module."
    )


def test_every_reader_branch_has_a_template_that_emits_it() -> None:
    """The reader may not carry dispatch for a column nothing produces."""
    dead = _dispatched_id_columns() - _emitted_id_columns()
    assert not dead, (
        f"the normalizer dispatches on {sorted(dead)} but no Cypher template "
        "emits those columns — dead dispatch. Remove the branch, or the "
        "template that fed it should be restored."
    )


def test_facets_is_the_only_non_id_dispatch_key() -> None:
    """``describe`` is dispatched by ``facets``; nothing else may be.

    Guards the assumption that scoping this contract to ``*_id`` columns is
    sufficient. If a new non-id dispatch key appears, this contract no longer
    covers the whole surface and must be widened.
    """
    src = inspect.getsource(CypherNormalizer.normalize)
    tree = ast.parse(src.lstrip() if src.startswith(" ") else src)
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            if isinstance(node.ops[0], ast.In) and isinstance(node.left, ast.Constant):
                value = node.left.value
                if isinstance(value, str) and not value.endswith("_id"):
                    keys.add(value)
    assert keys == {"facets"}, (
        f"non-id dispatch keys are {sorted(keys)}, expected just ['facets']. "
        "The *_id-scoped contract above no longer covers the dispatch surface."
    )


#: Every column shape the reader dispatches on, and the handler written for it.
#: Ordering inside ``normalize`` is load-bearing — ``software_id`` +
#: ``technique_id`` must beat the actor-software branch, and both must beat the
#: bare ``technique_id`` branch — so these cases pin the order, not just the map.
ROUTING_CASES: list[tuple[tuple[str, ...], str]] = [
    (("anchor_id", "neighbour_id"), "_normalize_generic_neighbors"),
    (("technique_id", "detection_id"), "_normalize_technique_detection"),
    (("tactic_id", "mitigation_id"), "_normalize_tactic_technique_mitigations"),
    (("technique_id", "mitigation_id"), "_normalize_technique_mitigations"),
    (("campaign_id", "group_id"), "_normalize_campaign_attribution"),
    (("software_id", "technique_id"), "_normalize_software_techniques"),
    (("software_id", "group_id"), "_normalize_actor_software"),
    (("software_id", "campaign_id"), "_normalize_actor_software"),
    (("parent_id", "subtechnique_id"), "_normalize_subtechnique_parent"),
    (("datacomponent_id", "analytic_id"), "_normalize_datacomponent_analytics"),
    (("technique_id", "in_tactic_id"), "_normalize_technique_tactics"),
    (("technique_id",), "_normalize_technique_rows"),
    (("facets",), "_normalize_describe"),
    (("id",), "_normalize_flat"),
]


class _StubCard:
    """The minimum a card must expose for dispatch; no graph, no fixtures."""

    provenance = {"id_scheme": "attack-id"}
    dataset = "attack"
    runtime_backend = "neo4j"


def _top_level_handlers() -> set[str]:
    """Handlers ``normalize`` itself dispatches to.

    Read from ``normalize``'s own AST, not from ``dir()``: second-level helpers
    like ``_normalize_seeded_technique_rows`` are called *by* a handler rather
    than by the dispatcher, and are not part of the column-shape contract.
    """
    src = inspect.getsource(CypherNormalizer.normalize)
    tree = ast.parse(src.lstrip() if src.startswith(" ") else src)
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.startswith("_normalize_")
    }


def test_routing_cases_cover_every_dispatch_branch() -> None:
    """The case list must not fall behind the code it pins."""
    missing = _top_level_handlers() - {h for _, h in ROUTING_CASES}
    assert not missing, (
        f"{sorted(missing)} are dispatch branches with no routing case. Add one, "
        "or the branch is unreachable and should be deleted."
    )


def test_no_routing_case_names_a_handler_that_is_not_dispatched() -> None:
    """A case for a branch ``normalize`` no longer reaches is a stale case."""
    stale = {h for _, h in ROUTING_CASES} - _top_level_handlers()
    assert not stale, (
        f"{sorted(stale)} appear in ROUTING_CASES but `normalize` never calls "
        "them — the branch was removed and the case outlived it."
    )


@pytest.mark.parametrize(
    "columns,expected_handler", ROUTING_CASES, ids=lambda v: "+".join(v) if isinstance(v, tuple) else v
)
def test_column_shape_routes_to_its_handler(
    monkeypatch: pytest.MonkeyPatch, columns: tuple[str, ...], expected_handler: str
) -> None:
    """Each declared column shape reaches the handler written for it."""
    called: list[str] = []
    for handler in {h for _, h in ROUTING_CASES}:
        monkeypatch.setattr(
            CypherNormalizer,
            handler,
            lambda *a, _h=handler, **k: (called.append(_h), [])[1],
            raising=True,
        )

    rows = [{c: "X" for c in columns}]
    CypherNormalizer().normalize(rows, resolved=None, query="", card=_StubCard())

    assert called == [expected_handler], (
        f"columns {list(columns)} routed to {called or ['<nothing>']}, "
        f"expected {expected_handler}"
    )
