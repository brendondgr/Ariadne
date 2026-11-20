"""O4 — verify: is node ``a`` joined to node ``b``?

With ``relation`` (and optionally ``direction``), only that relationship counts;
without, any card relationship between their labels, in either direction. The
answer is ``exists``, the witness relationships (name, direction, properties),
and the compiled query with its parameters as proof. An id that matches no node
is ``anchor_not_found``, not ``false`` (S12).
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Anchors


@dataclass(frozen=True)
class Verify:
    a: Anchors
    b: Anchors
    relation: str | None = None
    direction: str | None = None
