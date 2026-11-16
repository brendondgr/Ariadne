#!/usr/bin/env python3
"""Rows that know whether they were cut (Era 2, Step 5).

A connector returns at most ``max_result_rows`` rows. Before Step 5 a result cut
at that ceiling looked exactly like a complete one, which is how "the Cypher
connector stops at 1,000 rows with no flag" happened. :class:`Rows` is a plain
``list`` (every existing caller keeps working) carrying ``truncated``: True when
the backend had more rows than were returned, False when every row is here, and
None when the connector cannot tell (the query's own LIMIT equalled the cap; the
scaffold then probes with one extra row, see ``base.py``).
"""

from __future__ import annotations

from typing import Any


class Rows(list):
    """A list of result rows plus whether more existed beyond the cap."""

    def __init__(self, rows: list[dict[str, Any]] | None = None, *, truncated: bool | None = None,
                 ceiling: int | None = None) -> None:
        super().__init__(rows or [])
        self.truncated = truncated
        self.ceiling = ceiling


__all__ = ["Rows"]
