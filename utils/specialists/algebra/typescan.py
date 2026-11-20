"""O5 — typescan: every node of a label that meets the conditions.

``scan`` with filters, and with an exact total even when the rows shown are
capped (S7).
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Cond


@dataclass(frozen=True)
class TypeScan:
    label: str
    conds: tuple[Cond, ...] = ()
