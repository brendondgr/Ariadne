#!/usr/bin/env python3
"""Configuration for the conversational threads layer.

Every knob is env-driven with documented defaults, mirroring the
planner/specialist/synthesis/orchestration config idiom. Step 1 only needs the
SQLite database path; the fuller ``ConversationConfig`` (router/answer/validation
LLM knobs, retry caps) is added in Step 2.
"""

from __future__ import annotations

import os
from pathlib import Path

from utils.config import data_dir, env_str

# Default database file, relative to the resolved data directory.
DEFAULT_DB_NAME = "conversations.sqlite3"


def conversation_db_path() -> Path:
    """Resolve the conversation SQLite path.

    ``ARIADNE_CONVERSATION_DB`` wins when set (absolute or relative). Otherwise
    the DB lives at ``<ARIADNE_DATA_DIR>/conversations.sqlite3`` (``data/`` by
    default, which is gitignored).
    """
    override = os.environ.get("ARIADNE_CONVERSATION_DB", "").strip()
    if override:
        return Path(override)
    return Path(env_str("ARIADNE_DATA_DIR", data_dir())) / DEFAULT_DB_NAME
