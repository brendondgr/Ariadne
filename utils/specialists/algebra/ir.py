"""The internal form in one place: every operator class, and JSON round trip.

``to_dict`` and ``from_dict`` give each operator tree a plain JSON form, so a
plan can log it, a test can store it, and a later step can load it unchanged.
Every node carries ``"@": <class name>`` (not ``op``, which ``Cond`` uses). Tuples become lists in JSON and come
back as tuples.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .aggregate import Aggregate
from .base import (Anchors, Common, Cond, Count, Describe, Expand, FromStep, Hop, Intersect, Nodes, Scan, Values,
                   Walk)
from .edges import Absence, Having, Union_
from .filters import Where
from .groupby import GroupBy
from .path import Reach, Shortest
from .rank import Rank
from .typescan import TypeScan
from .validate import InvalidOp, check
from .verify import Verify

#: Every class of the algebra, by name.
OPS: dict[str, type] = {c.__name__: c for c in (
    Cond, Hop, Anchors, Scan, FromStep, Walk, Intersect, Describe, Expand, Count, Common, Nodes, Values,
    Where, Aggregate, Rank, Verify, TypeScan, GroupBy, Union_, Having, Reach, Shortest)}
#: Which operator (1-8, or 0 for today's) each class belongs to.
OPERATOR_OF: dict[str, int] = {
    "Anchors": 0, "Scan": 0, "FromStep": 0, "Walk": 0, "Intersect": 0, "Describe": 0, "Expand": 0, "Count": 0,
    "Common": 0, "Nodes": 0, "Values": 0, "Where": 1, "Aggregate": 2, "Rank": 3, "Verify": 4, "TypeScan": 5,
    "GroupBy": 6, "Union_": 7, "Having": 7, "Reach": 8, "Shortest": 8}


def to_dict(node: Any) -> Any:
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        out: dict[str, Any] = {"@": type(node).__name__}
        for f in dataclasses.fields(node):
            out[f.name] = to_dict(getattr(node, f.name))
        return out
    if isinstance(node, (tuple, list)):
        return [to_dict(x) for x in node]
    return node


def from_dict(data: Any) -> Any:
    if isinstance(data, dict) and "@" in data:
        cls = OPS.get(data["@"])
        if cls is None:
            raise InvalidOp("from_dict", f"unknown class {data['@']!r}")
        names = {f.name for f in dataclasses.fields(cls)}
        extra = set(data) - names - {"@"}
        if extra:
            raise InvalidOp("from_dict", f"{data['@']} has no field(s) {sorted(extra)}")
        return cls(**{k: from_dict(v) for k, v in data.items() if k != "@"})
    if isinstance(data, list):
        return tuple(from_dict(x) for x in data)
    return data


def operators_used(node: Any) -> set[int]:
    """The operator numbers a tree uses (0 = today's); edge conditions count as 7."""
    out: set[int] = set()

    def walk(x: Any) -> None:
        if dataclasses.is_dataclass(x) and not isinstance(x, type):
            name = type(x).__name__
            if name in OPERATOR_OF:
                out.add(OPERATOR_OF[name])
            if name == "Hop" and x.edge_conds:
                out.add(7)
            if name == "Cond" and x.op in ("before", "after", "between", "year"):
                out.add(7)
            for f in dataclasses.fields(x):
                walk(getattr(x, f.name))
        elif isinstance(x, (tuple, list)):
            for y in x:
                walk(y)

    walk(node)
    return out


__all__ = ["Absence", "Aggregate", "Anchors", "Common", "Cond", "Count", "Describe", "Expand", "FromStep",
           "GroupBy", "Having", "Hop", "Intersect", "InvalidOp", "Nodes", "OPERATOR_OF", "OPS", "Rank", "Reach",
           "Scan", "Shortest", "TypeScan", "Union_", "Values", "Verify", "Walk", "Where", "check", "from_dict",
           "operators_used", "to_dict"]
