#!/usr/bin/env python3
"""Stdlib-SQLite persistence for conversation threads and their turns.

The store is the single source of truth for "savable" threads: every consumer
(the conversational graph, the API, and — through it — the web sidebar) reads and
writes threads through :class:`ConversationStore`. No third-party dependency is
used; the stdlib :mod:`sqlite3` module gives us transactional writes, stable
ordering, and cheap queries as thread counts grow.

Design rules:

* A short-lived connection is opened per operation (``check_same_thread`` is a
  non-issue) so the store is safe to call from FastAPI's sync threadpool.
* Foreign keys + ``ON DELETE CASCADE`` are enabled per connection so deleting a
  conversation removes its turns atomically.
* WAL journaling improves read/write concurrency for the interactive UI.
* Timestamps are ISO-8601 UTC strings; ids are uuid4 hex.
* Assistant turns carry a free-form JSON ``payload`` (the assembled server-side
  answer/evidence/plan) so a thread rehydrates fully without re-running anything.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    seq             INTEGER NOT NULL,
    role            TEXT NOT NULL,
    question        TEXT,
    payload_json    TEXT,
    mode            TEXT,
    drafter         TEXT,
    route           TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_turns_conversation_seq
    ON turns (conversation_id, seq);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class ConversationRecord:
    """A conversation thread header (no turns)."""

    id: str
    title: str
    created_at: str
    updated_at: str
    turn_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "turn_count": self.turn_count,
        }


@dataclass(frozen=True)
class TurnRecord:
    """One turn (a ``user`` message or an ``assistant`` reply) within a thread."""

    id: str
    conversation_id: str
    seq: int
    role: str
    created_at: str
    question: str | None = None
    payload: dict[str, Any] | None = None
    mode: str | None = None
    drafter: str | None = None
    route: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "seq": self.seq,
            "role": self.role,
            "created_at": self.created_at,
            "question": self.question,
            "payload": self.payload,
            "mode": self.mode,
            "drafter": self.drafter,
            "route": self.route,
        }


class ConversationNotFound(KeyError):
    """Raised when an operation targets a conversation id that does not exist."""


class ConversationStore:
    """Thread + turn persistence backed by a single SQLite file."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        if self._path.parent and str(self._path.parent) not in ("", "."):
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # -- connection -------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # -- conversations ----------------------------------------------------

    def create_conversation(
        self, title: str, *, conversation_id: str | None = None
    ) -> ConversationRecord:
        """Create an empty thread and return its header."""
        cid = conversation_id or _new_id()
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (cid, title, now, now),
            )
        return ConversationRecord(
            id=cid, title=title, created_at=now, updated_at=now, turn_count=0
        )

    def list_conversations(self) -> list[ConversationRecord]:
        """All threads, most-recently-updated first, with turn counts."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT c.id, c.title, c.created_at, c.updated_at, "
                "       COUNT(t.id) AS turn_count "
                "FROM conversations c "
                "LEFT JOIN turns t ON t.conversation_id = c.id "
                "GROUP BY c.id "
                "ORDER BY c.updated_at DESC, c.created_at DESC"
            ).fetchall()
        return [self._to_conversation(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> ConversationRecord | None:
        """Return a thread header, or ``None`` if it does not exist."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT c.id, c.title, c.created_at, c.updated_at, "
                "       (SELECT COUNT(*) FROM turns t WHERE t.conversation_id = c.id) "
                "         AS turn_count "
                "FROM conversations c WHERE c.id = ?",
                (conversation_id,),
            ).fetchone()
        return self._to_conversation(row) if row else None

    def rename_conversation(
        self, conversation_id: str, title: str
    ) -> ConversationRecord:
        """Rename a thread; raises :class:`ConversationNotFound` if missing."""
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, conversation_id),
            )
            if cur.rowcount == 0:
                raise ConversationNotFound(conversation_id)
        record = self.get_conversation(conversation_id)
        assert record is not None  # just updated
        return record

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a thread and (via cascade) its turns. Returns whether it existed."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
            return cur.rowcount > 0

    # -- turns ------------------------------------------------------------

    def append_turn(
        self,
        conversation_id: str,
        role: str,
        *,
        question: str | None = None,
        payload: dict[str, Any] | None = None,
        mode: str | None = None,
        drafter: str | None = None,
        route: str | None = None,
    ) -> TurnRecord:
        """Append a turn, bump the thread's ``updated_at``, and return the record.

        Raises :class:`ConversationNotFound` if the thread does not exist.
        """
        now = _now()
        tid = _new_id()
        payload_json = json.dumps(payload) if payload is not None else None
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if exists is None:
                raise ConversationNotFound(conversation_id)
            seq_row = conn.execute(
                "SELECT COALESCE(MAX(seq), -1) + 1 AS next_seq "
                "FROM turns WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            seq = int(seq_row["next_seq"])
            conn.execute(
                "INSERT INTO turns (id, conversation_id, seq, role, question, "
                "payload_json, mode, drafter, route, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tid,
                    conversation_id,
                    seq,
                    role,
                    question,
                    payload_json,
                    mode,
                    drafter,
                    route,
                    now,
                ),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
        return TurnRecord(
            id=tid,
            conversation_id=conversation_id,
            seq=seq,
            role=role,
            created_at=now,
            question=question,
            payload=payload,
            mode=mode,
            drafter=drafter,
            route=route,
        )

    def list_turns(self, conversation_id: str) -> list[TurnRecord]:
        """All turns of a thread in insertion order (``seq`` ascending)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, conversation_id, seq, role, question, payload_json, "
                "mode, drafter, route, created_at "
                "FROM turns WHERE conversation_id = ? ORDER BY seq ASC",
                (conversation_id,),
            ).fetchall()
        return [self._to_turn(row) for row in rows]

    # -- mapping ----------------------------------------------------------

    @staticmethod
    def _to_conversation(row: sqlite3.Row) -> ConversationRecord:
        return ConversationRecord(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            turn_count=int(row["turn_count"]) if "turn_count" in row.keys() else 0,
        )

    @staticmethod
    def _to_turn(row: sqlite3.Row) -> TurnRecord:
        raw = row["payload_json"]
        payload = json.loads(raw) if raw else None
        return TurnRecord(
            id=row["id"],
            conversation_id=row["conversation_id"],
            seq=int(row["seq"]),
            role=row["role"],
            created_at=row["created_at"],
            question=row["question"],
            payload=payload,
            mode=row["mode"],
            drafter=row["drafter"],
            route=row["route"],
        )
