#!/usr/bin/env python3
"""Create/update the Neo4j login stored in the central ``.env``.

This wires the ``--neo4j-login`` CLI command. It collects a Bolt URI, username,
and password (interactively or from supplied values) and writes the matching
``NEO4J_*`` variables back to the project ``.env`` so both the Docker container
auth (``NEO4J_AUTH``) and the runtime loader (``NEO4J_USER`` / ``NEO4J_PASSWORD``)
stay in sync.
"""

from __future__ import annotations

import getpass
import logging
from pathlib import Path

from utils.config import env_str, set_env_values
from utils.graph_loader.config import (
    DEFAULT_NEO4J_PASSWORD,
    DEFAULT_NEO4J_URI,
    DEFAULT_NEO4J_USER,
)

logger = logging.getLogger(__name__)


def _prompt(label: str, default: str, *, secret: bool = False) -> str:
    """Prompt for a value, returning ``default`` when the input is empty."""
    if secret:
        entered = getpass.getpass(f"{label} [hidden, press Enter to keep current]: ")
        return entered if entered else default

    suffix = f" [{default}]" if default else ""
    entered = input(f"{label}{suffix}: ").strip()
    return entered if entered else default


def create_neo4j_login(
    *,
    uri: str | None = None,
    user: str | None = None,
    password: str | None = None,
    env_file: str | Path | None = None,
) -> Path:
    """Collect Neo4j credentials and persist them to the central ``.env``.

    Any of ``uri`` / ``user`` / ``password`` left as ``None`` is prompted for
    interactively, pre-filled with the current value (or built-in default).

    Returns:
        The path to the ``.env`` file that was written.
    """
    current_uri = env_str("NEO4J_URI", DEFAULT_NEO4J_URI)
    current_user = env_str("NEO4J_USER", DEFAULT_NEO4J_USER)
    current_password = env_str("NEO4J_PASSWORD", DEFAULT_NEO4J_PASSWORD)

    resolved_uri = uri if uri is not None else _prompt("Neo4j Bolt URI", current_uri)
    resolved_user = user if user is not None else _prompt("Neo4j username", current_user)
    resolved_password = (
        password
        if password is not None
        else _prompt("Neo4j password", current_password, secret=True)
    )

    if not resolved_user:
        raise ValueError("Neo4j username must not be empty.")
    if not resolved_password:
        raise ValueError("Neo4j password must not be empty.")
    if len(resolved_password) < 8:
        raise ValueError(
            "Neo4j password must be at least 8 characters. Neo4j 5.x enforces a "
            "minimum password length and the container crash-loops with "
            "\"The minimum password length is 8 characters\" otherwise."
        )
    if "/" in resolved_user:
        raise ValueError(
            "Neo4j username must not contain '/': it breaks the NEO4J_AUTH "
            "\"<user>/<password>\" form."
        )
    if resolved_user != "neo4j":
        raise ValueError(
            f"Neo4j admin username must be 'neo4j', not {resolved_user!r}. "
            "Neo4j 5.x only lets NEO4J_AUTH set the password for the built-in "
            "'neo4j' admin user; a different name makes the container crash-loop "
            "with \"Invalid admin username, it must be neo4j.\""
        )

    written = set_env_values(
        {
            "NEO4J_URI": resolved_uri,
            "NEO4J_USER": resolved_user,
            "NEO4J_PASSWORD": resolved_password,
            "NEO4J_AUTH": f"{resolved_user}/{resolved_password}",
        },
        env_file=env_file,
    )

    logger.info("Neo4j login saved to %s", written)
    logger.info("  URI  -> %s", resolved_uri)
    logger.info("  User -> %s", resolved_user)
    logger.info("  Password updated (value hidden).")
    logger.info(
        "Restart the stack (`--docker stop` then `--docker start`) for container "
        "auth changes to take effect."
    )
    return written
