"""O6 — groupby: one value per member of a set, keeping members with nothing (S9).

For each member, walk ``hops``, keep the end nodes meeting ``end_conds``
(amendment 2), and aggregate (``fn`` over the distinct end nodes, or over their
``prop``). Every member is kept: count 0 and sum 0 when the
walk is empty, the other functions ``null``. ``having`` (a comparison and a
number) runs after that, so ``count = 0`` can be selected. ``order`` with ``k``
ranks the groups with ties (S8); a null value sorts last in either order.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Cond, Hop

FNS = ("count", "sum", "avg", "min", "max", "median")


@dataclass(frozen=True)
class GroupBy:
    members: object
    hops: tuple[Hop, ...]
    fn: str = "count"
    prop: str | None = None
    having: tuple[str, float] | None = None
    order: str | None = None
    k: int | None = None
    end_conds: tuple[Cond, ...] = ()
