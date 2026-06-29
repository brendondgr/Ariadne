"""Unit tests for utils/recovery.py — backup/clean/restore, classification, retry."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.recovery import (
    BackupRecord,
    backup_directory,
    classify_failure,
    prepare_clean_dir,
    restore_directory,
    retry_with_backoff,
)


class _StaleError(Exception):
    """Stand-in for kg_builder.ArtifactValidationError (matched by class name)."""


class ArtifactValidationError(Exception):
    """Same name as the real builder error; classification matches by name."""


# ── backup_directory / prepare_clean_dir / restore_directory ───────────────────


def test_backup_directory_moves_existing_contents(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "schema.json").write_text("old", encoding="utf-8")

    record = backup_directory(canonical)

    assert record is not None
    assert not canonical.exists()  # moved aside
    assert (record.backup / "schema.json").read_text(encoding="utf-8") == "old"
    assert record.backup.parent == canonical.parent / "_backups"


def test_backup_directory_returns_none_for_missing_or_empty(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    assert backup_directory(missing) is None

    empty = tmp_path / "empty"
    empty.mkdir()
    assert backup_directory(empty) is None
    assert empty.exists()


def test_prepare_clean_dir_backs_up_then_yields_empty_dir(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "relationships.jsonl").write_text("stale", encoding="utf-8")

    record = prepare_clean_dir(canonical)

    assert record is not None
    assert canonical.is_dir()
    assert not any(canonical.iterdir())  # fresh + empty
    assert (record.backup / "relationships.jsonl").read_text(encoding="utf-8") == "stale"


def test_prepare_clean_dir_no_backup_when_absent(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    record = prepare_clean_dir(canonical)
    assert record is None
    assert canonical.is_dir()


def test_restore_directory_replaces_original_with_backup(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "schema.json").write_text("good", encoding="utf-8")

    record = prepare_clean_dir(canonical)
    assert record is not None
    # A failed rebuild leaves a bad partial in place.
    (canonical / "schema.json").write_text("bad-partial", encoding="utf-8")

    restored = restore_directory(record)

    assert restored == canonical
    assert (canonical / "schema.json").read_text(encoding="utf-8") == "good"
    assert not record.backup.exists()


def test_backups_are_unique_across_calls(tmp_path: Path) -> None:
    paths = []
    for i in range(3):
        canonical = tmp_path / "canonical"
        canonical.mkdir()
        (canonical / "f").write_text(str(i), encoding="utf-8")
        record = backup_directory(canonical)
        assert record is not None
        paths.append(record.backup)
    assert len(set(paths)) == 3


# ── classify_failure ───────────────────────────────────────────────────────────


def test_classify_stale_state_by_message() -> None:
    assert classify_failure(ValueError("relationship type not in schema: authored")) == "stale_state"
    assert classify_failure(RuntimeError("Missing canonical artifact: x")) == "stale_state"


def test_classify_stale_state_by_artifact_validation_error_name() -> None:
    assert classify_failure(ArtifactValidationError("anything at all")) == "stale_state"


def test_classify_transient() -> None:
    assert classify_failure(ConnectionError("boom")) == "transient"
    assert classify_failure(TimeoutError("slow")) == "transient"
    assert classify_failure(OSError("Connection refused")) == "transient"


def test_transient_wins_over_stale_markers() -> None:
    # A connection error message must not be misread as stale state.
    assert classify_failure(ConnectionError("not in schema but really a timeout")) == "transient"


def test_classify_needs_human_default() -> None:
    assert classify_failure(ValueError("totally unexpected condition")) == "needs_human"
    assert classify_failure(KeyError("missing key")) == "needs_human"


# ── retry_with_backoff ─────────────────────────────────────────────────────────


def test_retry_succeeds_after_transient_failures() -> None:
    calls = {"n": 0}
    slept: list[float] = []

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("temporarily unavailable")
        return "ok"

    result = retry_with_backoff(
        flaky, retries=3, base_delay=0.5, backoff=2.0, sleep=slept.append
    )

    assert result == "ok"
    assert calls["n"] == 3
    assert slept == [0.5, 1.0]  # exponential backoff, no sleep on success


def test_retry_reraises_after_exhaustion() -> None:
    calls = {"n": 0}

    def always_fail() -> None:
        calls["n"] += 1
        raise TimeoutError("nope")

    with pytest.raises(TimeoutError):
        retry_with_backoff(always_fail, retries=2, sleep=lambda _d: None)
    assert calls["n"] == 3  # first attempt + 2 retries


def test_retry_does_not_retry_non_transient() -> None:
    calls = {"n": 0}

    def permanent() -> None:
        calls["n"] += 1
        raise ValueError("unexpected")

    with pytest.raises(ValueError):
        retry_with_backoff(permanent, retries=5, sleep=lambda _d: None)
    assert calls["n"] == 1  # classified needs_human -> no retry


def test_retry_on_retry_callback_observed() -> None:
    events: list[tuple[int, str, float]] = []

    def flaky() -> str:
        if len(events) < 1:
            raise ConnectionError("reset")
        return "done"

    retry_with_backoff(
        flaky,
        retries=2,
        base_delay=1.0,
        sleep=lambda _d: None,
        on_retry=lambda attempt, exc, delay: events.append((attempt, type(exc).__name__, delay)),
    )
    assert events == [(1, "ConnectionError", 1.0)]
