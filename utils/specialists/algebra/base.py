"""The building blocks of the internal form, and today's operations.

Semantics: ``docs/era-2-expansion/operator-algebra.md``. Rule ids (S1-S12) in
comments point there. Every class here is plain, frozen data. Nothing compiles
or runs; ``utils/specialists/cypher/compile.py`` and ``gremlin/compile.py`` do.

Everything that yields nodes is a *node set*:
- the anchors;
- a scan of a label;
- an earlier step's result;
- a walk;
- or one of the set operators in other modules (filter, union, absence, reach).

Result operators (describe, expand, count, aggregate, rank, …) take node sets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

DIRECTIONS = ("out", "in")

#: Condition operators. The value types each takes are checked in ``validate.py``.
COMPARE = ("=", "<>", "<", ">", "<=", ">=")
TEXT = ("starts_with", "ends_with", "contains_text")
LIST = ("contains", "not_contains")
TIME = ("before", "after", "between", "year")
PRESENCE = ("present", "missing")
COND_OPS = COMPARE + TEXT + LIST + ("size",) + TIME + PRESENCE


@dataclass(frozen=True)
class Cond:
    """One condition on a node's or a relationship's property (S4-S6).

    ``value`` is the comparison value. For ``between`` it is a 2-tuple ``(from, to)``,
    inclusive. For ``size`` and ``year``, ``cmp`` is the comparison (one of
    ``COMPARE``) and ``value`` an integer. ``present`` and ``missing`` take no value.
    """

    prop: str
    op: str
    value: Any = None
    cmp: str | None = None


@dataclass(frozen=True)
class Hop:
    """One step of a walk: a card relationship, its direction, and the label reached.

    An empty ``target`` keeps every card label the relationship reaches (S2).
    ``edge_conds`` filter the relationship itself (O7a; time conditions are O7b).
    """

    relation: str
    direction: str
    target: str = ""
    edge_conds: tuple[Cond, ...] = ()


# --- node sets ---------------------------------------------------------------

@dataclass(frozen=True)
class Anchors:
    """Resolved stored ids (S12: an id that matches nothing is ``anchor_not_found``)."""

    ids: tuple[str, ...]
    label: str = ""


@dataclass(frozen=True)
class Scan:
    """Every node of one card label (S2)."""

    label: str


@dataclass(frozen=True)
class FromStep:
    """An earlier step's node result, by step id; ``labels`` are what it may hold."""

    step: str
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class Walk:
    """The nodes at the end of ``hops`` from ``start``.

    ``depth`` > 1 repeats a single hop 1..depth times (today's ``depth``; acyclic, S10).
    ``last_conds`` filter the last hop's nodes (today's ``eqfilter`` is one ``=`` here).
    """

    start: "NodeSet"
    hops: tuple[Hop, ...]
    depth: int = 1
    last_conds: tuple[Cond, ...] = ()


@dataclass(frozen=True)
class Intersect:
    """Nodes in every part (S1)."""

    parts: tuple["NodeSet", ...]


# --- today's results -----------------------------------------------------------

@dataclass(frozen=True)
class Describe:
    """Each anchor node with its properties."""

    anchors: Anchors


@dataclass(frozen=True)
class Expand:
    """A walk's end nodes and every node it passes through (today's ``expand``)."""

    walk: Walk


@dataclass(frozen=True)
class Count:
    """How many distinct nodes are in a set (S1)."""

    of: "NodeSet"


@dataclass(frozen=True)
class Common:
    """Nodes adjacent to every anchor (today's ``common``)."""

    anchors: Anchors


@dataclass(frozen=True)
class Nodes:
    """A node set as the answer: ids, names and the listed ``props``."""

    of: "NodeSet"
    props: tuple[str, ...] = ()


@dataclass(frozen=True)
class Values:
    """``prop`` of each distinct node in a set; ``distinct`` drops repeated values."""

    of: "NodeSet"
    prop: str
    distinct: bool = False


# Filled in by ``ir.py`` once every operator module is imported.
NodeSet = Union[Anchors, Scan, FromStep, Walk, Intersect, Any]
