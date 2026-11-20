"""O2 — aggregate: one value computed over a node set.

``count`` counts distinct nodes; ``count_values`` counts distinct present values
of ``prop``. ``sum``, ``avg``, ``min``, ``max`` and ``median`` read ``prop``
over distinct nodes (S1), skipping missing values. Over nothing, ``count`` and
``sum`` are 0 and the rest are ``null``. The row cap never bounds the inputs
(S7). Median of an even count is the mean of the two middle values (S11).
"""

from __future__ import annotations

from dataclasses import dataclass

FNS = ("count", "count_values", "sum", "avg", "min", "max", "median")
#: Functions that need a numeric property; ``min``/``max`` also take dates.
NUMERIC_ONLY = ("sum", "avg", "median")


@dataclass(frozen=True)
class Aggregate:
    of: object
    fn: str
    prop: str | None = None
