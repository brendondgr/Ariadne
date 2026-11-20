"""O1 — filter: keep the nodes of a set that satisfy every condition (S4, S5, S6).

A missing property never matches, not even ``<>`` or ``not_contains`` (S4).
``present`` and ``missing`` test whether the property exists at all. Several
conditions are joined by AND; OR is ``union`` (``edges.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Cond


@dataclass(frozen=True)
class Where:
    of: object
    conds: tuple[Cond, ...]
