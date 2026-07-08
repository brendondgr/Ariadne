"""Preflight checks: pass/warn/fail semantics and remediation text. Hermetic."""

from __future__ import annotations

import socket
from pathlib import Path

from utils.launcher.preflight import (
    FAIL,
    PASS,
    WARN,
    CheckResult,
    check_node_modules,
    check_port,
    check_source_cards,
    hard_failures,
    run_preflight,
)


def test_check_port_free_and_taken():
    # Bind a throwaway port, then check it: must FAIL with remediation.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        taken = sock.getsockname()[1]
        result = check_port(taken, "web")
        assert result.status == FAIL
        assert str(taken) in result.remediation or "--port" in result.remediation
    # Released now: must PASS.
    assert check_port(taken, "web").status == PASS


def test_node_modules_missing_warn_vs_fail(tmp_path: Path):
    assert check_node_modules(tmp_path, will_install=True).status == WARN
    result = check_node_modules(tmp_path, will_install=False)
    assert result.status == FAIL
    assert "npm install" in result.remediation
    (tmp_path / "node_modules").mkdir()
    assert check_node_modules(tmp_path, will_install=False).status == PASS


def test_source_cards_missing_warns_with_build_command(tmp_path: Path):
    result = check_source_cards(tmp_path)
    assert result.status == WARN
    assert "--build" in result.remediation
    cards = tmp_path / "source_cards"
    cards.mkdir()
    (cards / "attack.json").write_text("{}")
    result = check_source_cards(tmp_path)
    assert result.status == PASS and "attack.json" in result.detail


def test_run_preflight_with_injected_checks_never_raises():
    def crashes() -> CheckResult:
        raise RuntimeError("boom")

    def warns() -> CheckResult:
        return CheckResult("warns", WARN, "degraded", "fix it like this")

    def multi() -> list[CheckResult]:
        return [CheckResult("a", PASS), CheckResult("b", PASS)]

    results = run_preflight(
        root=Path("."), web_port=1, api_port=2, will_install=True,
        checks=[crashes, warns, multi],
    )
    assert [r.status for r in results] == [FAIL, WARN, PASS, PASS]
    assert "crashed" in results[0].detail
    fails = hard_failures(results)
    assert len(fails) == 1 and fails[0].name == "crashes"


def test_real_preflight_shape(tmp_path: Path):
    """The real check list runs end-to-end (against this repo) without raising."""
    results = run_preflight(
        root=Path.cwd(), web_port=1, api_port=2, will_install=True)
    names = [r.name for r in results]
    assert "npm" in names and "python deps" in names
    assert any(n == "langgraph pipeline" for n in names)
    compiled = next(r for r in results if r.name == "langgraph pipeline")
    assert compiled.status == PASS and "compiled" in compiled.detail
