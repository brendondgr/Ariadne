#!/usr/bin/env python3
"""Conversational threads for Ariadne.

This package adds the memory-inclusive, multi-threaded chat layer on top of the
existing single-shot pipeline:

* ``store`` — stdlib-SQLite persistence for conversation threads and their turns.
* ``config`` — env-driven configuration (DB path, LLM knobs, retry caps).

Later steps add the conversational orchestration graph (Orchestration -> Router
-> {Answer | Graph Extraction -> Validation -> Answer}) that wraps the existing
``utils.orchestration`` super-graph as a "Graph Extraction" subgraph.
"""

from __future__ import annotations

from utils.conversation.store import (
    ConversationRecord,
    ConversationStore,
    TurnRecord,
)

__all__ = ["ConversationRecord", "ConversationStore", "TurnRecord"]
