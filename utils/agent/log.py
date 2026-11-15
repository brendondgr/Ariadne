#!/usr/bin/env python3
"""The run log (Era 2, Step 3): every agent run is an append-only list of events.

After GAIFA's store (``services/agent/agent/store.py``), cut down to what a
retrieval agent needs. Two tables:

    runs(id, question, graph, mode, state, caller, parent_id, fork_seq,
         created, updated, tree_commit, request)
    events(run_id, seq, ts, type, payload, served_model, tree_commit)

**The log is the run.** The messages sent to the model are rebuilt from it
before every call (:mod:`utils.agent.rebuild`), so a run can pause for a
clarification, resume after a crash, be replayed, or be forked at any step,
and the record of what happened is the same object that drives what happens
next. Nothing is ever updated or deleted in ``events``.

**Provenance on every event.** Each row carries the served model (registry name
and verified token id, e.g. ``gemma4-31b/106``) when a model was involved, and
the code commit the run used. Research runners read model identity from here,
never from configuration (:func:`RunLog.provenance`).

**Concurrency.** WAL mode; each append takes the write lock with
``BEGIN IMMEDIATE``, reads ``MAX(seq)`` and inserts in one transaction, so
concurrent writers (threads or processes, each with their own ``RunLog``) get
distinct, gap-free sequence numbers.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.agent.contracts import AgentRequest

#: The closed set of event types (plan v2 Step 3). A new type must be added here.
EVENT_TYPES = (
    "request",       # the AgentRequest, first event of every run
    "fast_path",     # the deterministic path's verdict: confident or not, and why
    "model_call",    # one model turn: text, calls, finish_reason, usage, seconds
    "repair",        # one RepairEvent from utils.llm.repair, with the call it touched
    "tool_call",     # a call about to execute (after validation and coercion)
    "tool_result",   # its result: the bounded view, the handle, totals
    "validator",     # the answer validator's verdict on a finish
    "clarification", # asked (the questions) or answered (the caller's answers)
    "answer",        # the composed answer before the envelope
    "envelope",      # the AnswerEnvelope returned to the caller; last event of a finished run
    "error",         # something broke; the run may still resume
    "state",         # a state change of the run
)

#: Run states. ``running`` restarts from its log; ``needs_clarification`` waits
#: for resume(run_id, answers); ``done`` and ``failed`` are final.
STATES = ("running", "needs_clarification", "done", "failed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    question    TEXT NOT NULL,
    graph       TEXT NOT NULL,
    mode        TEXT NOT NULL,
    state       TEXT NOT NULL,
    caller      TEXT NOT NULL DEFAULT '{}',
    parent_id   TEXT,
    fork_seq    INTEGER,
    created     REAL NOT NULL,
    updated     REAL NOT NULL,
    tree_commit TEXT NOT NULL,
    request     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_state ON runs (state, updated);
CREATE TABLE IF NOT EXISTS events (
    run_id       TEXT NOT NULL,
    seq          INTEGER NOT NULL,
    ts           REAL NOT NULL,
    type         TEXT NOT NULL,
    payload      TEXT NOT NULL,
    served_model TEXT,
    tree_commit  TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS events_type ON events (type, ts);
"""


def tree_commit(repo: Path | None = None) -> str:
    """The code commit a run uses, with ``-dirty`` when the tree has changes."""
    repo = repo or Path(__file__).resolve().parents[2]
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                             text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo,
                               capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return (sha or "unknown") + ("-dirty" if dirty else "")


def new_run_id() -> str:
    return "r_" + secrets.token_hex(6)


@dataclass(frozen=True)
class Event:
    run_id: str
    seq: int
    ts: float
    type: str
    payload: dict[str, Any]
    served_model: str | None
    tree_commit: str

    def as_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "seq": self.seq, "ts": self.ts, "type": self.type,
                "payload": self.payload, "served_model": self.served_model,
                "tree_commit": self.tree_commit}


class RunLog:
    """One SQLite file of runs and their events. Safe across threads and processes."""

    def __init__(self, path: str | Path, *, commit: str | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.commit = commit or tree_commit()
        self._c = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None, timeout=30)
        self._c.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._c.execute("PRAGMA journal_mode=WAL")
            self._c.execute("PRAGMA synchronous=NORMAL")
            self._c.execute("PRAGMA busy_timeout=30000")
            self._c.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._c.close()

    def __enter__(self) -> "RunLog":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- runs ------------------------------------------------------------- #

    def create_run(self, request: AgentRequest, *, run_id: str | None = None,
                   parent_id: str | None = None, fork_seq: int | None = None) -> str:
        """Open a run and log its ``request`` event. Returns the run id."""
        rid = run_id or new_run_id()
        now = time.time()
        req = request.model_dump(mode="json")
        with self._lock:
            self._c.execute(
                "INSERT INTO runs (id, question, graph, mode, state, caller, parent_id, fork_seq, "
                "created, updated, tree_commit, request) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (rid, request.question, json.dumps(request.graph), request.mode, "running",
                 json.dumps(req["caller"]), parent_id, fork_seq, now, now, self.commit, json.dumps(req)))
        if parent_id is None:
            self.append(rid, "request", req)
        return rid

    def run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._c.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"no run {run_id!r} in {self.path}")
        r = dict(row)
        for k in ("graph", "caller", "request"):
            r[k] = json.loads(r[k])
        return r

    def request(self, run_id: str) -> AgentRequest:
        return AgentRequest.model_validate(self.run(run_id)["request"])

    def runs(self, state: str | None = None) -> list[dict[str, Any]]:
        sql, args = "SELECT id, state, question, updated FROM runs", ()
        if state:
            sql, args = sql + " WHERE state = ?", (state,)
        with self._lock:
            return [dict(r) for r in self._c.execute(sql + " ORDER BY updated", args).fetchall()]

    def set_state(self, run_id: str, state: str, *, why: str = "") -> int:
        """Change a run's state; the change is itself an event."""
        if state not in STATES:
            raise ValueError(f"unknown state {state!r}")
        seq = self.append(run_id, "state", {"state": state, **({"why": why} if why else {})})
        with self._lock:
            self._c.execute("UPDATE runs SET state = ?, updated = ? WHERE id = ?", (state, time.time(), run_id))
        return seq

    # -- events ----------------------------------------------------------- #

    def append(self, run_id: str, type: str, payload: dict[str, Any], *,
               served_model: str | None = None) -> int:
        """Append one event atomically; returns its sequence number."""
        if type not in EVENT_TYPES:
            raise ValueError(f"unknown event type {type!r}; add it to EVENT_TYPES")
        body = json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)
        with self._lock:
            self._c.execute("BEGIN IMMEDIATE")
            try:
                seq = self._c.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE run_id = ?",
                                      (run_id,)).fetchone()[0]
                self._c.execute(
                    "INSERT INTO events (run_id, seq, ts, type, payload, served_model, tree_commit) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (run_id, seq, time.time(), type, body, served_model, self.commit))
                self._c.execute("UPDATE runs SET updated = ? WHERE id = ?", (time.time(), run_id))
                self._c.execute("COMMIT")
            except BaseException:
                self._c.execute("ROLLBACK")
                raise
        return seq

    def events(self, run_id: str, *, upto: int | None = None) -> list[Event]:
        sql = "SELECT * FROM events WHERE run_id = ?"
        args: tuple[Any, ...] = (run_id,)
        if upto is not None:
            sql, args = sql + " AND seq <= ?", (run_id, upto)
        with self._lock:
            rows = self._c.execute(sql + " ORDER BY seq", args).fetchall()
        return [Event(r["run_id"], r["seq"], r["ts"], r["type"], json.loads(r["payload"]),
                      r["served_model"], r["tree_commit"]) for r in rows]

    # -- fork and provenance ---------------------------------------------- #

    def fork(self, run_id: str, at_seq: int) -> str:
        """A new run whose log is this one's up to ``at_seq``, minus a trailing unresolved step.

        The fork starts ``running``; driving it re-asks the model from that point.
        Its events are copies (same payloads, new run id), so the parent is untouched.
        """
        from utils.agent.rebuild import trim_unresolved

        kept = trim_unresolved(self.events(run_id, upto=at_seq))
        if not kept or kept[0].type != "request":
            raise ValueError("a fork must keep at least the request event")
        rid = self.create_run(self.request(run_id), parent_id=run_id, fork_seq=at_seq)
        for e in kept:
            if e.type == "state":
                continue
            self.append(rid, e.type, e.payload, served_model=e.served_model)
        self.append(rid, "state", {"state": "running", "why": f"forked from {run_id} at seq {at_seq}"})
        return rid

    def provenance(self, run_id: str) -> dict[str, Any]:
        """Which models served a run, read from the log; flags calls missing identity or usage."""
        calls = [e for e in self.events(run_id) if e.type == "model_call"]
        missing_model = [e.seq for e in calls if not e.served_model]
        missing_usage = [e.seq for e in calls
                         if not (e.payload.get("usage") or {}).get("completion_tokens")
                         and not (e.payload.get("usage") or {}).get("prompt_tokens")]
        return {
            "run_id": run_id,
            "models": sorted({e.served_model for e in calls if e.served_model}),
            "model_calls": len(calls),
            "commits": sorted({e.tree_commit for e in self.events(run_id)}),
            "missing_served_model": missing_model,
            "missing_usage": missing_usage,
            "ok": not missing_model and not missing_usage,
        }


__all__ = ["EVENT_TYPES", "STATES", "Event", "RunLog", "new_run_id", "tree_commit"]
