#!/usr/bin/env python3
"""Result handles (Era 2, Step 5): every result kept server-side as ``set:<n>``.

The agent never moves rows through the model. A tool's full result is stored
here for the run -- every id, the exact total, whether it is complete, the
query that produced it -- and the model gets back a handle and a bounded view
(:mod:`utils.agent.view`). Later tools take handles as inputs, so building on a
result never drops a row.

Handles live in the run log's SQLite file (table ``handles``), so a run that
resumes after a crash or a clarification still has every set it made.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS handles (
    run_id   TEXT NOT NULL,
    n        INTEGER NOT NULL,
    kind     TEXT NOT NULL,
    ids      TEXT NOT NULL,
    total    INTEGER NOT NULL,
    complete INTEGER NOT NULL,
    query    TEXT NOT NULL,
    origin   TEXT NOT NULL,
    created  REAL NOT NULL,
    PRIMARY KEY (run_id, n)
) WITHOUT ROWID;
"""

SET_OPS = ("intersect", "union", "minus")


@dataclass(frozen=True)
class SetRecord:
    handle: str
    kind: str
    ids: tuple[str, ...]
    total: int
    complete: bool
    query: str
    origin: dict[str, Any] = field(default_factory=dict)


def _n(handle: str) -> int:
    if not isinstance(handle, str) or not handle.startswith("set:") or not handle[4:].isdigit():
        raise KeyError(f"not a handle: {handle!r} (handles look like set:3)")
    return int(handle[4:])


class HandleStore:
    """The sets of one run. Thread-safe; shares the run log's database file."""

    def __init__(self, path: str | Path, run_id: str) -> None:
        self.path = Path(path)
        self.run_id = run_id
        self._c = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None, timeout=30)
        self._lock = threading.RLock()
        with self._lock:
            self._c.execute("PRAGMA journal_mode=WAL")
            self._c.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._c.close()

    def put(self, kind: str, ids: list[str] | tuple[str, ...], *, total: int | None = None,
            complete: bool = True, query: str = "", origin: dict[str, Any] | None = None) -> SetRecord:
        """Store a set; returns its record with a new handle. ``total`` defaults to len(ids)."""
        uniq = sorted(set(map(str, ids)))
        tot = len(uniq) if total is None else int(total)
        if complete and tot != len(uniq):
            raise ValueError(f"a complete set's total ({tot}) must equal its ids ({len(uniq)})")
        if not complete and tot < len(uniq):
            raise ValueError("an incomplete set's total cannot be below the ids it holds")
        with self._lock:
            self._c.execute("BEGIN IMMEDIATE")
            try:
                n = self._c.execute("SELECT COALESCE(MAX(n), 0) + 1 FROM handles WHERE run_id = ?",
                                    (self.run_id,)).fetchone()[0]
                self._c.execute(
                    "INSERT INTO handles (run_id, n, kind, ids, total, complete, query, origin, created) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (self.run_id, n, kind, json.dumps(uniq), tot, int(complete), query,
                     json.dumps(origin or {}, sort_keys=True), time.time()))
                self._c.execute("COMMIT")
            except BaseException:
                self._c.execute("ROLLBACK")
                raise
        return SetRecord(f"set:{n}", kind, tuple(uniq), tot, complete, query, origin or {})

    def get(self, handle: str) -> SetRecord:
        n = _n(handle)
        with self._lock:
            row = self._c.execute("SELECT kind, ids, total, complete, query, origin FROM handles "
                                  "WHERE run_id = ? AND n = ?", (self.run_id, n)).fetchone()
        if row is None:
            raise KeyError(f"no {handle} in this run")
        return SetRecord(handle, row[0], tuple(json.loads(row[1])), int(row[2]), bool(row[3]), row[4],
                         json.loads(row[5]))

    def handles(self) -> list[str]:
        with self._lock:
            rows = self._c.execute("SELECT n FROM handles WHERE run_id = ? ORDER BY n", (self.run_id,)).fetchall()
        return [f"set:{r[0]}" for r in rows]

    def set_op(self, op: str, a: str, b: str) -> SetRecord:
        """intersect / union / minus of two stored sets, as a new handle.

        Exact when both inputs are complete. If either is not, the result is
        marked incomplete (its total is then what was computed, a lower bound
        for intersect and union, and not meaningful for minus), never guessed.
        """
        if op not in SET_OPS:
            raise ValueError(f"op must be one of {SET_OPS}")
        x, y = self.get(a), self.get(b)
        sx, sy = set(x.ids), set(y.ids)
        out = sx & sy if op == "intersect" else sx | sy if op == "union" else sx - sy
        kind = x.kind if x.kind == y.kind or op == "minus" else f"{x.kind}|{y.kind}"
        return self.put(kind, sorted(out), complete=x.complete and y.complete,
                        query=f"{op}({a}, {b})", origin={"op": op, "inputs": [a, b]})

    def page(self, handle: str, after: str | None = None, size: int = 100) -> list[str]:
        """Keyset paging over a stored set: ids greater than ``after``, in order."""
        ids = self.get(handle).ids
        start = 0
        if after is not None:
            import bisect
            start = bisect.bisect_right(ids, after)
        return list(ids[start:start + size])


__all__ = ["SET_OPS", "HandleStore", "SetRecord"]
