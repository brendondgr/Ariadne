"""O3 — rank: order a node set and keep the top ``k``, with ties (S8).

The key is a property (``prop``), or the number of distinct nodes a walk
(``by_walk``) reaches from each node. Every node tied with the k-th is kept.
Nodes without the property are left out of a property ranking and counted
(``unranked``). A walk count of 0 is a real value. Order: key, then stored id
ascending.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Hop


@dataclass(frozen=True)
class Rank:
    of: object
    order: str
    k: int
    prop: str | None = None
    by_walk: tuple[Hop, ...] | None = None
