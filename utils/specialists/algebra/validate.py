"""Check an operator tree against a card, before anything compiles.

``check(node, card)`` returns the card labels a node set may hold, or ``None``
for a result operator. It raises :class:`InvalidOp` with a message that says what
is allowed instead, because the planner reads these messages (Step 8's
teaching errors).

The card is ``utils.agent.catalog.CardModel``: labels with typed properties, and
relationships with the (source, target) label pairs they join.
"""

from __future__ import annotations

import re
from typing import Any

from .aggregate import FNS as AGG_FNS, NUMERIC_ONLY, Aggregate
from .base import (COMPARE, COND_OPS, DIRECTIONS, LIST, PRESENCE, TEXT, TIME, Anchors, Common, Cond, Count,
                   Describe, Expand, FromStep, Hop, Intersect, Nodes, Scan, Values, Walk)
from .edges import Having, Union_
from .filters import Where
from .groupby import FNS as GROUP_FNS, GroupBy
from .path import DEFAULT_DEPTH, PATH_DIRECTIONS, Reach, Shortest
from .rank import Rank
from .typescan import TypeScan
from .verify import Verify

#: Paths have their own cap (operator-algebra.md, amendment 1).
PATH_MAX_DEPTH = 10
NUMERIC_TYPES = ("integer", "number", "number_text")
DATE_TYPES = ("date", "datetime")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


class InvalidOp(ValueError):
    """An operator tree the card does not allow. ``where`` names the part."""

    def __init__(self, where: str, message: str) -> None:
        super().__init__(f"{where}: {message}")
        self.where = where


def _need(cond: bool, where: str, message: str) -> None:
    if not cond:
        raise InvalidOp(where, message)


def _labels(card: Any) -> frozenset[str]:
    return frozenset(card.labels)


def _prop_types(card: Any, labels: frozenset[str], prop: str) -> set[str]:
    return {card.labels[lab].properties[prop].vtype for lab in labels
            if lab in card.labels and prop in card.labels[lab].properties}


def _check_value(where: str, op: str, vtype: str, c: Cond) -> None:
    if op in PRESENCE:
        _need(c.value is None, where, f"{op} takes no value")
        return
    if op in ("size", "year"):
        _need(c.cmp in COMPARE, where, f"{op} needs cmp, one of {list(COMPARE)}")
        _need(isinstance(c.value, int) and not isinstance(c.value, bool), where, f"{op} needs an integer value")
        return
    if op == "between":
        ok = isinstance(c.value, (tuple, list)) and len(c.value) == 2 and all(
            isinstance(v, str) and ISO_DATE.match(v) for v in c.value)
        _need(ok, where, "between needs two ISO dates, (from, to), inclusive")
        return
    if op in ("before", "after"):
        _need(isinstance(c.value, str) and bool(ISO_DATE.match(c.value)), where, f"{op} needs an ISO date YYYY-MM-DD")
        return
    if vtype in NUMERIC_TYPES:
        _need(isinstance(c.value, (int, float)) and not isinstance(c.value, bool), where,
              f"{c.prop} is a number; give a numeric value")
    elif vtype == "boolean":
        _need(isinstance(c.value, bool), where, f"{c.prop} is true/false; give a boolean")
    elif vtype in DATE_TYPES:
        _need(isinstance(c.value, str) and bool(ISO_DATE.match(c.value)), where, f"{c.prop} is a date; give YYYY-MM-DD")
    else:
        _need(isinstance(c.value, str), where, f"{c.prop} is text; give a string")


def allowed_ops(vtype: str) -> tuple[str, ...]:
    """The condition ops a card value type takes (S5, S6)."""
    if vtype in NUMERIC_TYPES or vtype in DATE_TYPES:  # number_text: as the number it spells (amendment 2)
        base = COMPARE + (TIME if vtype in DATE_TYPES else ())
    elif vtype == "boolean":
        base = ("=", "<>")
    elif vtype == "list":
        base = LIST + ("size",)
    else:  # text orders by code point (amendment 2); ISO dates stored as text take the time ops (S6)
        base = COMPARE + TEXT + TIME
    return base + PRESENCE


def check_conds(conds: tuple[Cond, ...], types_of: Any, where: str) -> None:
    """``types_of(prop)`` gives the property's card value types where it exists."""
    for i, c in enumerate(conds):
        w = f"{where}[{i}]"
        _need(isinstance(c, Cond), w, "a condition must be a Cond")
        _need(c.op in COND_OPS, w, f"op must be one of {list(COND_OPS)}")
        types = types_of(c.prop)
        _need(bool(types), w, f"unknown property {c.prop!r}")
        _need(len(types) == 1, w, f"{c.prop} has different types on these labels: {sorted(types)}")
        vtype = next(iter(types))
        _need(c.op in allowed_ops(vtype), w, f"{c.prop} ({vtype}) takes {list(allowed_ops(vtype))}, not {c.op!r}")
        _check_value(w, c.op, vtype, c)


def _reached(card: Any, start: frozenset[str], relation: str, direction: str) -> frozenset[str]:
    pats = card.relations[relation].patterns
    if direction == "out":
        return frozenset(o for s, o in pats if s in start)
    if direction == "in":
        return frozenset(s for s, o in pats if o in start)
    return frozenset(o for s, o in pats if s in start) | frozenset(s for s, o in pats if o in start)


def check_hop(card: Any, start: frozenset[str], hop: Hop, where: str) -> frozenset[str]:
    _need(isinstance(hop, Hop), where, "a hop must be a Hop")
    _need(hop.relation in card.relations, where,
          f"unknown relationship {hop.relation!r}; options {sorted(card.relations)}")
    _need(hop.direction in DIRECTIONS, where, f"direction must be one of {list(DIRECTIONS)}")
    reach = _reached(card, start, hop.relation, hop.direction)
    _need(bool(reach), where, f"{hop.relation} ({hop.direction}) joins none of {sorted(start)}")
    if hop.target:
        _need(hop.target in reach, where,
              f"{hop.relation} ({hop.direction}) from {sorted(start)} reaches {sorted(reach)}, not {hop.target}")
        reach = frozenset([hop.target])
    if hop.edge_conds:
        eprops = card.relations[hop.relation].properties
        check_conds(hop.edge_conds, lambda p: {eprops[p].vtype} if p in eprops else set(), f"{where}.edge_conds")
    return reach


def check_walk(card: Any, start: frozenset[str], hops: tuple[Hop, ...], depth: int, where: str) -> frozenset[str]:
    _need(len(hops) >= 1, where, "a walk needs at least one hop")
    _need(isinstance(depth, int) and 1 <= depth <= card.max_depth, where, f"depth must be 1..{card.max_depth}")
    labels = start
    for i, h in enumerate(hops):
        labels = check_hop(card, labels, h, f"{where}.hops[{i}]")
    if depth > 1:
        _need(len(hops) == 1, where, "depth > 1 repeats a single hop")
        _need(bool(labels & start), where, f"{hops[0].relation} does not repeat: it leaves {sorted(start)}")
        # A repeated walk may stop at any step, so it holds both ends' labels.
        labels = labels | (start & _reached(card, start, hops[0].relation, hops[0].direction))
    return labels


def _anchor_labels(card: Any, a: Anchors, where: str) -> frozenset[str]:
    _need(isinstance(a, Anchors), where, "needs Anchors")
    _need(len(a.ids) >= 1 and all(isinstance(x, str) and x for x in a.ids), where, "needs at least one id")
    if a.label:
        _need(a.label in card.labels, where, f"unknown label {a.label!r}; options {sorted(card.labels)}")
        return frozenset([a.label])
    return _labels(card)


def _one(card: Any, a: Anchors, where: str) -> frozenset[str]:
    labels = _anchor_labels(card, a, where)
    _need(len(a.ids) == 1, where, "takes exactly one id")
    return labels


def check(node: Any, card: Any, where: str = "op") -> frozenset[str] | None:
    """Validate ``node``; the labels a node set may hold, or ``None`` for a result."""
    w = f"{where}:{type(node).__name__}"
    props = lambda labels: (lambda p: _prop_types(card, labels, p))  # noqa: E731
    # --- node sets
    if isinstance(node, Anchors):
        return _anchor_labels(card, node, w)
    if isinstance(node, Scan):
        _need(node.label in card.labels, w, f"unknown label {node.label!r}; options {sorted(card.labels)}")
        return frozenset([node.label])
    if isinstance(node, FromStep):
        _need(bool(node.step), w, "names no step")
        _need(set(node.labels) <= set(card.labels), w, f"unknown labels {sorted(set(node.labels) - set(card.labels))}")
        return frozenset(node.labels) or _labels(card)
    if isinstance(node, Walk):
        labels = check_walk(card, check(node.start, card, w + ".start"), node.hops, node.depth, w)
        check_conds(node.last_conds, props(labels), w + ".last_conds")
        return labels
    if isinstance(node, (Intersect, Union_)):
        _need(len(node.parts) >= 2, w, "needs at least two parts")
        sets = [check(p, card, f"{w}.parts[{i}]") for i, p in enumerate(node.parts)]
        if isinstance(node, Union_):
            return frozenset().union(*sets)
        out = frozenset.intersection(*sets)
        _need(bool(out), w, "the parts share no label, so the intersection is always empty")
        return out
    if isinstance(node, Where):
        labels = check(node.of, card, w + ".of")
        _need(len(node.conds) >= 1, w, "needs at least one condition")
        check_conds(node.conds, props(labels), w + ".conds")
        return labels
    if isinstance(node, Having):
        labels = check(node.of, card, w + ".of")
        reach = check_hop(card, labels, node.hop, w + ".hop")
        check_conds(node.target_conds, props(reach), w + ".target_conds")
        if node.target is not None:
            _need(bool(reach & check(node.target, card, w + ".target")), w, "the target holds no label the hop reaches")
        return labels
    if isinstance(node, TypeScan):
        _need(node.label in card.labels, w, f"unknown label {node.label!r}; options {sorted(card.labels)}")
        check_conds(node.conds, props(frozenset([node.label])), w + ".conds")
        return frozenset([node.label])
    if isinstance(node, Reach):
        start = check(node.start, card, w + ".start")
        _need(isinstance(node.depth, int) and 1 <= node.depth <= PATH_MAX_DEPTH, w, f"depth must be 1..{PATH_MAX_DEPTH}")
        rels = node.rels or tuple((r, "both") for r in card.relations)
        for i, (r, d) in enumerate(rels):
            _need(r in card.relations, f"{w}.rels[{i}]", f"unknown relationship {r!r}")
            _need(d in PATH_DIRECTIONS, f"{w}.rels[{i}]", f"direction must be one of {list(PATH_DIRECTIONS)}")
        seen, frontier = set(), set(start)
        for _ in range(node.depth):
            nxt = set()
            for r, d in rels:
                nxt |= _reached(card, frozenset(frontier), r, d)
            frontier = nxt - seen
            seen |= nxt
            if not frontier:
                break
        _need(bool(seen), w, "these relationships reach nothing from the start")
        return frozenset(seen)
    # --- results
    if isinstance(node, Describe):
        _anchor_labels(card, node.anchors, w + ".anchors")
        return None
    if isinstance(node, Common):
        _anchor_labels(card, node.anchors, w + ".anchors")
        _need(len(node.anchors.ids) >= 2, w, "common needs at least two anchors")
        return None
    if isinstance(node, Expand):
        check(node.walk, card, w + ".walk")
        return None
    if isinstance(node, (Count, Nodes)):
        labels = check(node.of, card, w + ".of")
        for p in getattr(node, "props", ()):
            _need(bool(_prop_types(card, labels, p)), w, f"unknown property {p!r}")
        return None
    if isinstance(node, Values):
        labels = check(node.of, card, w + ".of")
        _need(bool(_prop_types(card, labels, node.prop)), w, f"unknown property {node.prop!r}")
        return None
    if isinstance(node, Aggregate):
        labels = check(node.of, card, w + ".of")
        _need(node.fn in AGG_FNS, w, f"fn must be one of {list(AGG_FNS)}")
        if node.fn == "count":
            _need(node.prop is None, w, "count counts nodes; it takes no prop")
            return None
        _check_agg_prop(card, labels, node.fn, node.prop, w)
        return None
    if isinstance(node, Rank):
        labels = check(node.of, card, w + ".of")
        _need(node.order in ("asc", "desc"), w, "order must be asc or desc")
        _need(isinstance(node.k, int) and node.k >= 1, w, "k must be a positive integer")
        _need((node.prop is None) != (node.by_walk is None), w, "rank by exactly one of prop or by_walk")
        if node.prop is not None:
            t = _prop_types(card, labels, node.prop)
            _need(len(t) == 1 and next(iter(t)) in NUMERIC_TYPES + DATE_TYPES + ("string",), w,
                  f"{node.prop!r} must be one orderable property (number, date or text)")
        else:
            check_walk(card, labels, node.by_walk, 1, w + ".by_walk")
        return None
    if isinstance(node, Verify):
        la, lb = _one(card, node.a, w + ".a"), _one(card, node.b, w + ".b")
        if node.relation is not None:
            _need(node.relation in card.relations, w, f"unknown relationship {node.relation!r}")
            d = node.direction or "both"
            _need(d in PATH_DIRECTIONS, w, f"direction must be one of {list(PATH_DIRECTIONS)}")
            _need(bool(_reached(card, la, node.relation, d) & lb), w,
                  f"{node.relation} ({d}) never joins {sorted(la)} to {sorted(lb)}")
        else:
            _need(node.direction is None, w, "direction needs a relation")
        return None
    if isinstance(node, GroupBy):
        members = check(node.members, card, w + ".members")
        ends = check_walk(card, members, node.hops, 1, w)
        check_conds(node.end_conds, lambda p: _prop_types(card, ends, p), w + ".end_conds")
        _need(node.fn in GROUP_FNS, w, f"fn must be one of {list(GROUP_FNS)}")
        if node.fn == "count":
            _need(node.prop is None, w, "count counts nodes; it takes no prop")
        else:
            _check_agg_prop(card, ends, node.fn, node.prop, w)
        if node.having is not None:
            op, val = node.having
            _need(op in COMPARE and isinstance(val, (int, float)) and not isinstance(val, bool), w,
                  f"having must be (op in {list(COMPARE)}, number)")
            # A number compares only with a numeric group value: min/max of a text or
            # date property is text, which no numeric `having` can select (EXP-2026-11-021).
            numeric = node.fn != "count" and (node.fn in NUMERIC_ONLY or bool(
                _prop_types(card, ends, node.prop) & set(NUMERIC_TYPES)))
            _need(node.fn == "count" or numeric, w,
                  f"having compares a number; {node.fn}({node.prop}) is not numeric")
        _need(node.order in (None, "asc", "desc"), w, "order must be asc or desc")
        _need(node.k is None or (node.order is not None and isinstance(node.k, int) and node.k >= 1), w,
              "k needs an order and must be a positive integer")
        return None
    if isinstance(node, Shortest):
        _one(card, node.a, w + ".a")
        _one(card, node.b, w + ".b")
        _need(node.a.ids != node.b.ids, w, "the two ends must differ")
        _need(isinstance(node.depth, int) and 1 <= node.depth <= PATH_MAX_DEPTH, w, f"depth must be 1..{PATH_MAX_DEPTH}")
        for i, (r, d) in enumerate(node.rels):
            _need(r in card.relations, f"{w}.rels[{i}]", f"unknown relationship {r!r}")
            _need(d in PATH_DIRECTIONS, f"{w}.rels[{i}]", f"direction must be one of {list(PATH_DIRECTIONS)}")
        return None
    raise InvalidOp(w, "not an operator of the algebra")


def _check_agg_prop(card: Any, labels: frozenset[str], fn: str, prop: str | None, w: str) -> None:
    _need(prop is not None, w, f"{fn} needs a prop")
    t = _prop_types(card, labels, prop)
    _need(len(t) == 1, w, f"unknown or mixed-type property {prop!r}")
    vtype = next(iter(t))
    if fn in NUMERIC_ONLY:
        _need(vtype in NUMERIC_TYPES, w, f"{fn} needs a numeric property; {prop} is {vtype}")
    elif fn in ("min", "max"):
        _need(vtype in NUMERIC_TYPES + DATE_TYPES + ("string",), w, f"{fn} needs a number or a date; {prop} is {vtype}")


__all__ = ["DEFAULT_DEPTH", "InvalidOp", "PATH_MAX_DEPTH", "allowed_ops", "check", "check_conds", "check_hop",
           "check_walk"]
