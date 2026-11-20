"""The two switches that expose the operator algebra to the typed planner (Step 9, Phase G).

Both are read at call time and both default **off**. Off means unchanged: the
typed planner's prompt, tool specs, step checking and every compiled query are
byte-identical to the tree before Phase G (``test_algebra_exposure.py`` checks
the prompt by hash and ``scripts/algebra_typed_snapshot.py`` the queries).

- ``ARIADNE_ALGEBRA_CORE=1``: operators 1-7 (filter, aggregate, rank, verify,
  typescan, groupby, union and absence) become step kinds; today's kinds are
  also validated by the algebra; a typed-step filter on a property the store
  does not hold natively matches nothing (amendment 4) instead of being dropped.
- ``ARIADNE_ALGEBRA_EXTENDED=1``, only with CORE: reach, shortest path, and the
  time condition ops (before, after, between, year).
"""

from __future__ import annotations

import os

_ON = {"1", "true", "yes", "on"}


def core_on() -> bool:
    return os.environ.get("ARIADNE_ALGEBRA_CORE", "0").strip().lower() in _ON


def extended_on() -> bool:
    """Reach, shortest and the time ops: only meaningful with CORE."""
    return core_on() and os.environ.get("ARIADNE_ALGEBRA_EXTENDED", "0").strip().lower() in _ON


__all__ = ["core_on", "extended_on"]
