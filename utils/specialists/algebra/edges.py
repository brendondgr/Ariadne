"""O7 — edge filters, time, union and absence.

- **Edge filters (O7a)** are ``Hop.edge_conds``: conditions on a relationship's own
  properties, with the same rules as node filters.
- **Time (O7b)** is the ``before``, ``after``, ``between`` and ``year`` condition ops,
  on node or relationship properties. Dates are ISO text and compare on their
  ``YYYY-MM-DD`` prefix (S6); a value that is not ISO-shaped never matches.
- **Union (O7c)** is the nodes of any part, by stored id (S1).
- **Having (O7d, and pattern constraints)** keeps the nodes of a set that have
  (``exists=True``) or lack (``exists=False``) a relationship ``hop`` to a node
  that meets ``target_conds`` (and, when given, is in ``target``). Absence is
  ``exists=False``. A member joined only to nodes that fail the conditions
  counts as lacking it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Cond, Hop


@dataclass(frozen=True)
class Union_:
    parts: tuple[object, ...]


@dataclass(frozen=True)
class Having:
    of: object
    hop: Hop
    exists: bool = True
    target_conds: tuple[Cond, ...] = ()
    target: object | None = None


def Absence(of: object, hop: Hop, target_conds: tuple[Cond, ...] = ()) -> Having:  # noqa: N802 - a constructor
    """The members of ``of`` with no ``hop`` to a node meeting ``target_conds``."""
    return Having(of, hop, False, target_conds)
