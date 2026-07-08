"""Display layer: prefixing, error highlighting, filtering, the status board."""

from __future__ import annotations

import io
from pathlib import Path

from utils.launcher.display import (
    BoardInfo,
    data_versions,
    format_line,
    render_board,
    stream_output,
    use_color,
)
from utils.launcher.preflight import FAIL, PASS, WARN, CheckResult


def test_format_line_prefixes_and_pads():
    line = format_line("api", "hello", color=False)
    assert line.startswith("[api]")
    assert "hello" in line
    # Same column for different tags.
    other = format_line("web", "hello", color=False)
    assert line.index("hello") == other.index("hello")


def test_format_line_color_only_when_asked():
    assert "\x1b[" not in format_line("api", "hello", color=False)
    assert "\x1b[" in format_line("api", "hello", color=True)


def test_error_lines_highlighted_in_color_mode():
    plain = format_line("api", "Traceback (most recent call last):", color=True)
    assert "\x1b[31m" in plain  # red


def test_real_error_tokens_detected():
    from utils.launcher.display import looks_like_error

    for line in (
        "ERROR: kaboom",
        "TypeError: x is not a function",
        "Unhandled Runtime Error",
        "⨯ Another next dev server is already running.",
        "npm install failed (exit 1)",
        "Traceback (most recent call last):",
    ):
        assert looks_like_error(line), line


def test_camelcase_component_names_are_not_errors():
    """Next's dev-overlay React tree spams identifiers containing 'Error' —
    they must neither be shown by the always-show-errors rule nor painted red."""
    from utils.launcher.display import looks_like_error

    for line in (
        "  <AppDevOverlayErrorBoundary globalError={[...]}>",
        "    <HTTPAccessFallbackBoundary notFound={<NotAllowedRootHTTPFallbackError>}>",
        "      <RedirectErrorBoundary router={{...}}>",
        "  <ReplaySsrOnlyErrors>",
        "<HotReload globalError={[...]} webSocket={WebSocket}>",
    ):
        assert not looks_like_error(line), line


def test_use_color_respects_no_color_and_tty(monkeypatch):
    class NotTty(io.StringIO):
        def isatty(self):
            return False

    class Tty(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.delenv("NO_COLOR", raising=False)
    assert use_color(NotTty()) is False
    assert use_color(Tty()) is True
    monkeypatch.setenv("NO_COLOR", "1")
    assert use_color(Tty()) is False


def test_stream_output_pumps_filters_and_always_shows_errors():
    src = io.StringIO("ready on port 3000\nboring line\nERROR: kaboom\n")
    out: list[str] = []
    thread = stream_output(
        "web", src, color=False, emit=out.append,
        filter_fn=lambda line: "ready" in line,
    )
    thread.join(timeout=5)
    joined = "\n".join(out)
    assert "ready on port 3000" in joined
    assert "boring line" not in joined
    assert "kaboom" in joined, "error lines must never be filtered out"


def test_render_board_shows_urls_checks_and_remediation():
    info = BoardInfo(
        web_url="http://localhost:16500", api_url="http://127.0.0.1:16501",
        mode="development", orchestrator="LangGraph (10 nodes)",
        data_versions={"attack": "17.0"},
    )
    checks = [
        CheckResult("npm", PASS, "/usr/bin/npm"),
        CheckResult("capec (gremlin)", WARN, "not live", "uv run main.py --docker start"),
        CheckResult("api port 16501", FAIL, "already in use", "stop the process"),
    ]
    board = render_board(info, checks, color=False)
    assert "http://localhost:16500" in board
    assert "LangGraph (10 nodes)" in board
    assert "attack 17.0" in board
    assert "✓" in board and "⚠" in board and "✗" in board
    assert "→ uv run main.py --docker start" in board
    assert "\x1b[" not in board  # color off ⇒ plain text


def test_data_versions_reads_real_repo_file():
    versions = data_versions(Path.cwd())
    assert isinstance(versions, dict)  # tolerates absent/odd file shapes


def test_data_versions_missing_file(tmp_path: Path):
    assert data_versions(tmp_path) == {}
