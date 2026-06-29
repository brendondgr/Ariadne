"""Unit tests for utils/yolo.py — table renderer, abort policy, credential detection."""

from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

import pytest

from utils.yolo import _GUARD_FAILED, StepResult, YoloRunner, print_summary_table


# ── table renderer ────────────────────────────────────────────────────────────


def _capture_table(results):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        print_summary_table(results)
    finally:
        sys.stdout = old
    return buf.getvalue()


def test_table_renders_all_statuses():
    results = [
        StepResult("Download", status="ok", detail="ATT&CK v19.0", duration_s=1.2),
        StepResult("Build", status="skipped", detail="already present"),
        StepResult("Credentials", status="skipped", detail="using defaults"),
        StepResult("Docker", status="ok", detail="running", duration_s=30.0),
        StepResult("Load ATT&CK", status="ok", detail="1914 nodes", duration_s=12.3),
        StepResult("Load CAPEC", status="failed", detail="connection refused"),
        StepResult("Verify", status="pending", detail=""),
    ]
    out = _capture_table(results)
    assert "✓" in out
    assert "—" in out
    assert "✗" in out
    assert "ATT&CK v19.0" in out
    assert "connection refused" in out
    assert "1 step(s) failed" in out


def test_table_success_message():
    results = [
        StepResult("Step A", status="ok", detail="done", duration_s=1.0),
        StepResult("Step B", status="skipped", detail="already done"),
    ]
    out = _capture_table(results)
    assert "All steps completed successfully" in out


def test_table_long_detail_truncated():
    long_detail = "x" * 200
    results = [StepResult("Step", status="ok", detail=long_detail)]
    out = _capture_table(results)
    assert "…" in out  # truncation marker


# ── StepResult symbol / label ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "status,symbol,label",
    [
        ("ok", "✓", "OK"),
        ("skipped", "—", "Skipped"),
        ("failed", "✗", "FAILED"),
        ("pending", "·", "Pending"),
    ],
)
def test_step_result_symbol_and_label(status, symbol, label):
    r = StepResult("name", status=status)
    assert r.symbol == symbol
    assert r.status_label == label


# ── credential detection ──────────────────────────────────────────────────────


def test_credentials_step_skipped_on_default_password():
    runner = YoloRunner.__new__(YoloRunner)
    with patch("utils.yolo.env_str", return_value="password"):
        r = runner._step_credentials()
    assert r.status == "skipped"
    assert "defaults" in r.detail.lower()


def test_credentials_step_skipped_when_already_configured():
    runner = YoloRunner.__new__(YoloRunner)
    with patch("utils.yolo.env_str", return_value="my-super-secret-pw"):
        r = runner._step_credentials()
    assert r.status == "skipped"
    assert "configured" in r.detail.lower()


# ── abort policy ─────────────────────────────────────────────────────────────


def _make_runner():
    """Build a YoloRunner with a mocked LoaderConfig so no I/O happens."""
    runner = YoloRunner.__new__(YoloRunner)
    cfg = MagicMock()
    cfg.data_dir = MagicMock()
    runner._config = cfg
    runner._data_dir = MagicMock()
    return runner


def test_abort_after_download_failure():
    runner = _make_runner()

    failed_dl = StepResult("1. Download Datasets", status="failed", detail="network error")
    runner._step_download = lambda: failed_dl
    runner._step_build = MagicMock(side_effect=AssertionError("should not be called"))
    runner._step_credentials = MagicMock(side_effect=AssertionError("should not be called"))
    runner._step_docker_start = MagicMock(side_effect=AssertionError("should not be called"))
    runner._step_load_attack = MagicMock(side_effect=AssertionError("should not be called"))
    runner._step_load_capec = MagicMock(side_effect=AssertionError("should not be called"))
    runner._step_verify = MagicMock(side_effect=AssertionError("should not be called"))

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        results = runner.run()

    assert results[0].status == "failed"
    assert all(r.status == "skipped" for r in results[1:])
    assert "Earlier step failed" in results[1].detail


def test_load_failures_do_not_abort_verify():
    runner = _make_runner()

    runner._step_download = lambda: StepResult("1. Download Datasets", status="ok")
    runner._step_build = lambda: StepResult("2. Build Artifacts", status="ok")
    runner._step_credentials = lambda: StepResult("3. Configure Credentials", status="skipped")
    runner._step_docker_start = lambda: StepResult("4. Start Docker Infrastructure", status="ok")
    runner._step_load_attack = lambda: StepResult(
        "5. Load ATT&CK → Neo4j", status="failed", detail="auth error"
    )
    runner._step_load_capec = lambda: StepResult(
        "6. Load CAPEC → Gremlin", status="failed", detail="timeout"
    )
    verify_result = StepResult("7. Verify Graphs", status="ok", detail="ATT&CK ✓  CAPEC ✓")
    runner._step_verify = lambda: verify_result

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        results = runner.run()

    assert results[4].status == "failed"
    assert results[5].status == "failed"
    assert results[6].status == "ok"


# ── exit-code logic ───────────────────────────────────────────────────────────


def test_exit_code_0_when_no_failures():
    results = [
        StepResult("A", status="ok"),
        StepResult("B", status="skipped"),
    ]
    assert not any(r.status == "failed" for r in results)


def test_exit_code_1_when_any_failure():
    results = [
        StepResult("A", status="ok"),
        StepResult("B", status="failed", detail="oops"),
    ]
    assert any(r.status == "failed" for r in results)


# ── needs_input status ─────────────────────────────────────────────────────────


def test_needs_input_symbol_and_label():
    r = StepResult("name", status="needs_input")
    assert r.symbol == "?"
    assert r.status_label == "NEEDS INPUT"


def test_table_reports_needs_input():
    results = [StepResult("Build", status="needs_input", detail="needs human input: bad schema")]
    out = _capture_table(results)
    assert "?" in out
    assert "need human input" in out


# ── _guarded retry / classification ────────────────────────────────────────────


def test_guarded_retries_transient_then_succeeds():
    runner = _make_runner()
    r = StepResult("step")
    calls = {"n": 0}

    def action():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("connection refused")
        return "value"

    buf = io.StringIO()
    with patch("utils.recovery.time.sleep"), patch("sys.stdout", buf):
        result = runner._guarded(r, action, retries=3)

    assert result == "value"
    assert calls["n"] == 3
    assert r.status == "pending"  # caller sets ok; guard leaves status untouched on success


def test_guarded_transient_exhausted_marks_failed():
    runner = _make_runner()
    r = StepResult("step")

    def action():
        raise TimeoutError("still slow")

    with patch("utils.recovery.time.sleep"):
        result = runner._guarded(r, action, retries=1)

    assert result is _GUARD_FAILED
    assert r.status == "failed"
    assert "slow" in r.detail


def test_guarded_needs_human_marks_needs_input():
    runner = _make_runner()
    r = StepResult("step")

    def action():
        raise ValueError("totally unexpected condition")

    result = runner._guarded(r, action)

    assert result is _GUARD_FAILED
    assert r.status == "needs_input"
    assert "needs human input" in r.detail


# ── build step: validate / repair / escalate ───────────────────────────────────


def test_build_step_skips_when_existing_artifacts_valid():
    runner = _make_runner()
    runner._invalid_canonical_datasets = lambda: []
    with patch("utils.yolo.KGBuildRunner") as mock_runner:
        r = runner._step_build()
    assert r.status == "skipped"
    assert "validated" in r.detail.lower()
    mock_runner.assert_not_called()


def test_build_step_rebuilds_clean_on_stale_artifacts():
    runner = _make_runner()
    runner._invalid_canonical_datasets = lambda: ["attack"]
    buf = io.StringIO()
    with patch("utils.yolo.KGBuildRunner") as mock_runner, patch("sys.stdout", buf):
        r = runner._step_build()
    assert r.status == "ok"
    assert "rebuilt clean" in r.detail
    mock_runner.return_value.build_all.assert_called_once()


def test_build_step_escalates_clean_rebuild_failure():
    runner = _make_runner()
    runner._invalid_canonical_datasets = lambda: ["attack"]
    buf = io.StringIO()
    with patch("utils.yolo.KGBuildRunner") as mock_runner, patch("sys.stdout", buf):
        mock_runner.return_value.build_all.side_effect = ValueError(
            "Canonical relationship type not in schema: authored"
        )
        r = runner._step_build()
    assert r.status == "needs_input"
    assert "needs human input" in r.detail


def test_needs_input_in_abort_step_halts_pipeline():
    runner = _make_runner()
    runner._step_download = lambda: StepResult("1. Download Datasets", status="ok")
    runner._step_build = lambda: StepResult(
        "2. Build Artifacts", status="needs_input", detail="needs human input: x"
    )
    runner._step_credentials = MagicMock(side_effect=AssertionError("should not run"))
    runner._step_docker_start = MagicMock(side_effect=AssertionError("should not run"))
    runner._step_load_attack = MagicMock(side_effect=AssertionError("should not run"))
    runner._step_load_capec = MagicMock(side_effect=AssertionError("should not run"))
    runner._step_verify = MagicMock(side_effect=AssertionError("should not run"))

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        results = runner.run()

    assert results[1].status == "needs_input"
    assert all(r.status == "skipped" for r in results[2:])
