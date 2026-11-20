"""O8 — reach and shortest path (S10).

Paths are acyclic: no node repeats. ``rels`` is a tuple of
``(relation, direction)`` pairs. Direction is ``out``, ``in`` or ``both``. An
empty tuple means every card relationship, either direction.

- **Reach** is a node set: every node reachable from ``start`` in 1 to ``depth``
  steps. It never includes the anchors, since an acyclic path cannot return to
  its start.
- **Shortest** returns every acyclic path of the minimum length from ``a`` to
  ``b``, each as alternating stored ids and relationship names. If there is
  none within ``depth``, it says so.
- **Hitting the depth cap** with frontier left marks the result ``partial`` (S7).
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Anchors

DEFAULT_DEPTH = 6
PATH_DIRECTIONS = ("out", "in", "both")


@dataclass(frozen=True)
class Reach:
    start: object
    rels: tuple[tuple[str, str], ...] = ()
    depth: int = DEFAULT_DEPTH


@dataclass(frozen=True)
class Shortest:
    a: Anchors
    b: Anchors
    rels: tuple[tuple[str, str], ...] = ()
    depth: int = DEFAULT_DEPTH
