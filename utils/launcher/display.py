#!/usr/bin/env python3
"""How the launcher displays information: prefixed streams + the status board.

Stdlib-only by design (nothing extra in the boot path). ANSI color is used
only when stdout is a TTY and ``NO_COLOR`` is unset, so ``python app.py``
reads identically in terminals, CI logs, and pipes.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Callable

from .preflight import FAIL, PASS, WARN, CheckResult

# Source tags are padded to one width so the columns line up.
_TAG_WIDTH = 12

_ANSI = {
    "reset": "\x1b[0m",
    "dim": "\x1b[2m",
    "bold": "\x1b[1m",
    "teal": "\x1b[36m",
    "violet": "\x1b[35m",
    "yellow": "\x1b[33m",
    "red": "\x1b[31m",
    "green": "\x1b[32m",
}

# Real error lines, not CamelCase identifiers: `AppDevOverlayErrorBoundary`
# and friends stream constantly from the Next dev overlay and must NOT count.
# `\berror\b` needs a word boundary (so `ErrorBoundary` inside one identifier
# doesn't match); `\w+error:` catches `TypeError:`-style prefixes; `⨯` is
# Next's own failure glyph.
_ERROR_RE = re.compile(
    r"(?i)(?:\berror\b|\w+error:|\bexception\b|\btraceback\b|\bfailed\b|\bfatal\b|\bunhandled\b|⨯)"
)


def looks_like_error(line: str) -> bool:
    """True for genuine error/failure lines worth always showing (and painting red)."""
    return bool(_ERROR_RE.search(line))


def use_color(stream: IO[str] | None = None) -> bool:
    """Color only on a TTY with NO_COLOR unset."""
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def _paint(text: str, color: str, *, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{_ANSI[color]}{text}{_ANSI['reset']}"


def format_line(source: str, line: str, *, color: bool) -> str:
    """One child-output line: ``[api] …`` with error lines highlighted."""
    tag_color = {"api": "teal", "web": "violet", "preflight": "dim", "smoke": "green"}.get(
        source, "dim"
    )
    tag = _paint(f"[{source}]".ljust(_TAG_WIDTH), tag_color, enabled=color)
    body = line.rstrip("\n")
    if looks_like_error(body):
        body = _paint(body, "red", enabled=color)
    return f"{tag}{body}"


def stream_output(
    source: str,
    stream: IO[str],
    *,
    color: bool,
    emit: Callable[[str], None] = print,
    filter_fn: Callable[[str], bool] | None = None,
) -> threading.Thread:
    """Pump a child's text stream line-by-line onto ``emit`` from a daemon thread.

    ``filter_fn`` (when given) decides which lines are shown — the launcher
    quiets noisy dev-server output unless --verbose is passed. Error-marked
    lines are always shown.
    """

    def pump() -> None:
        for line in iter(stream.readline, ""):
            body = line.rstrip("\n")
            if not body:
                continue
            if filter_fn is not None and not filter_fn(body) and not looks_like_error(body):
                continue
            emit(format_line(source, body, color=color))
        stream.close()

    thread = threading.Thread(target=pump, name=f"pump-{source}", daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# The status board.
# ---------------------------------------------------------------------------

_STATUS_GLYPH = {PASS: "✓", WARN: "⚠", FAIL: "✗"}
_STATUS_COLOR = {PASS: "green", WARN: "yellow", FAIL: "red"}


@dataclass(frozen=True)
class BoardInfo:
    """Everything the ready banner shows besides the checks themselves."""

    web_url: str
    api_url: str
    mode: str  # "development" | "production"
    orchestrator: str  # e.g. "LangGraph (10 nodes)"
    data_versions: dict[str, str]


def data_versions(root: Path) -> dict[str, str]:
    """Dataset snapshot versions from data/versions.json (best-effort)."""
    path = root / "data" / "versions.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    versions: dict[str, str] = {}
    for dataset, meta in raw.items() if isinstance(raw, dict) else []:
        if isinstance(meta, dict):
            version = meta.get("version") or meta.get("downloaded") or ""
            if version:
                versions[str(dataset)] = str(version)
    return versions


def render_board(info: BoardInfo, checks: list[CheckResult], *, color: bool) -> str:
    """The boxed startup summary: URLs, orchestrator, and every check's verdict."""
    rows: list[tuple[str, str]] = [
        ("web", info.web_url),
        ("api", info.api_url),
        ("mode", info.mode),
        ("orchestrator", info.orchestrator),
    ]
    if info.data_versions:
        rows.append(("data", ", ".join(f"{k} {v}" for k, v in sorted(info.data_versions.items()))))

    check_rows: list[tuple[str, str, str]] = []
    for c in checks:
        glyph = _paint(_STATUS_GLYPH[c.status], _STATUS_COLOR[c.status], enabled=color)
        text = c.detail or c.status
        if c.status != PASS and c.remediation:
            text += f"  → {c.remediation}"
        check_rows.append((glyph, c.name, text))

    label_w = max(
        [len(label) for label, _ in rows] + [len(name) for _, name, _ in check_rows] + [1]
    )
    lines = ["┌─ Ariadne workbench " + "─" * 24]
    for label, value in rows:
        lines.append(f"│ {label.ljust(label_w)}  {_paint(value, 'bold', enabled=color)}")
    lines.append("├" + "─" * 44)
    for glyph, name, text in check_rows:
        lines.append(f"│ {glyph} {name.ljust(label_w)}  {text}")
    lines.append("└" + "─" * 44)
    return "\n".join(lines)
