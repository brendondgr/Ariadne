#!/usr/bin/env python3
"""Central configuration loader for Ariadne.

This module is the single entry point for reading project configuration from
the root ``.env`` file. It loads ``.env`` into ``os.environ`` exactly once and
exposes small typed helpers (``env_str``/``env_int``/``env_bool``) that the rest
of the codebase uses to read values with sensible fallback defaults.

Design rules (intentional):

* ``load_env()`` must be called explicitly from process entry points (e.g.
  ``main.py``) — never as an import-time side effect. This keeps the test
  suite deterministic: pytest imports modules directly and therefore never
  auto-loads ``.env``, so tests always see the hardcoded fallback defaults.
* Real environment variables always win over ``.env`` (``override=False``),
  so CI and shell exports keep their usual precedence.
"""

from __future__ import annotations

import os
from pathlib import Path

# Project root = two levels up from this file (utils/config.py -> utils -> root).
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Canonical central configuration file at the repository root.
ENV_FILE = PROJECT_ROOT / ".env"

# Guard so repeated load_env() calls are cheap no-ops within one process.
_loaded = False


def load_env(env_file: str | Path | None = None, *, override: bool = False) -> Path | None:
    """Load the central ``.env`` file into ``os.environ``.

    Args:
        env_file: Optional explicit path. Defaults to ``<project root>/.env``.
        override: If ``True``, values in the file replace existing environment
            variables. Defaults to ``False`` so real env vars take precedence.

    Returns:
        The path that was loaded, or ``None`` if no file existed.
    """
    global _loaded

    path = Path(env_file) if env_file is not None else ENV_FILE

    # Only short-circuit the default load; explicit paths always reload.
    if env_file is None and _loaded:
        return path if path.exists() else None

    if not path.exists():
        if env_file is None:
            _loaded = True
        return None

    from dotenv import load_dotenv

    load_dotenv(dotenv_path=path, override=override)

    if env_file is None:
        _loaded = True

    return path


def env_str(name: str, default: str) -> str:
    """Return a string env var, falling back to ``default`` when unset/empty."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def env_int(name: str, default: int) -> int:
    """Return an int env var, falling back to ``default`` when unset/invalid."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_bool(name: str, default: bool) -> bool:
    """Return a bool env var, parsing common truthy/falsy spellings."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def data_dir() -> str:
    """Resolve the project data directory (``ARIADNE_DATA_DIR``, default ``data``)."""
    return env_str("ARIADNE_DATA_DIR", "data")


def _format_env_value(value: str) -> str:
    """Render a value for a ``.env`` line, quoting only when necessary."""
    if value == "" or any(ch.isspace() or ch in "\"'#$\\" for ch in value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def set_env_values(
    updates: dict[str, str], env_file: str | Path | None = None
) -> Path:
    """Update ``KEY=VALUE`` pairs in the central ``.env``, preserving layout.

    Existing assignments are rewritten in place (comments, ordering, and blank
    lines are untouched); keys not already present are appended at the end. The
    current process environment is updated too so later reads in the same run
    see the new values.

    Args:
        updates: Mapping of env var name to its new value.
        env_file: Optional explicit path. Defaults to ``<project root>/.env``.

    Returns:
        The path that was written.
    """
    path = Path(env_file) if env_file is not None else ENV_FILE

    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)

    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            indent = line[: len(line) - len(stripped)]
            lines[index] = f"{indent}{key}={_format_env_value(remaining.pop(key))}"

    for key, value in remaining.items():
        lines.append(f"{key}={_format_env_value(value)}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for key, value in updates.items():
        os.environ[key] = value

    return path
