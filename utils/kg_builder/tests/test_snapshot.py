#!/usr/bin/env python3
"""Tests for pinned-snapshot verification used to gate builds."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.snapshot import (
    SnapshotChecksumError,
    read_pinned_checksum,
    verify_pinned_snapshot,
)

_RAW = b'{"type":"bundle","objects":[]}'
_SHA = hashlib.sha256(_RAW).hexdigest()


def _seed(tmp_path: Path, *, pin: str | None) -> BuildConfig:
    raw_dir = tmp_path / "raw" / "attack" / "v19.0"
    raw_dir.mkdir(parents=True)
    (raw_dir / "enterprise-attack.json").write_bytes(_RAW)
    versions: dict = {"attack_version": "19.0", "capec_version": "3.9"}
    if pin is not None:
        versions["checksums"] = {"attack": {"sha256": pin, "size_bytes": len(_RAW)}}
    (tmp_path / "versions.json").write_text(json.dumps(versions))
    return BuildConfig.from_data_dir(tmp_path)


def test_read_pinned_checksum(tmp_path: Path) -> None:
    config = _seed(tmp_path, pin=_SHA)
    assert read_pinned_checksum(config.data_dir, "attack") == _SHA
    assert read_pinned_checksum(config.data_dir, "capec") is None


def test_verify_matches(tmp_path: Path) -> None:
    config = _seed(tmp_path, pin=_SHA)
    status = verify_pinned_snapshot(config, "attack")
    assert status.pinned
    assert status.matches


def test_verify_mismatch_raises(tmp_path: Path) -> None:
    config = _seed(tmp_path, pin="deadbeef")
    with pytest.raises(SnapshotChecksumError):
        verify_pinned_snapshot(config, "attack")


def test_verify_mismatch_non_strict_returns_status(tmp_path: Path) -> None:
    config = _seed(tmp_path, pin="deadbeef")
    status = verify_pinned_snapshot(config, "attack", strict=False)
    assert status.pinned
    assert not status.matches


def test_verify_unpinned_warns_not_raises(tmp_path: Path) -> None:
    config = _seed(tmp_path, pin=None)
    status = verify_pinned_snapshot(config, "attack")
    assert not status.pinned
    assert status.actual_sha256 == _SHA


def test_verify_missing_raw_raises(tmp_path: Path) -> None:
    (tmp_path / "versions.json").write_text(
        json.dumps({"attack_version": "19.0", "capec_version": "3.9"})
    )
    config = BuildConfig.from_data_dir(tmp_path)
    with pytest.raises(FileNotFoundError):
        verify_pinned_snapshot(config, "attack")
