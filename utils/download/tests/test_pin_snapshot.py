#!/usr/bin/env python3
"""Tests for snapshot checksum recording and backfill in the downloader."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from utils.download.downloader import DatasetDownloader, checksum_record


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _seed_raw(tmp_path: Path) -> DatasetDownloader:
    downloader = DatasetDownloader(data_dir=tmp_path)
    downloader.ensure_dirs()
    (downloader.attack_dir / "enterprise-attack.json").write_bytes(b'{"type":"bundle"}')
    (downloader.capec_dir / "capec_latest.xml").write_bytes(b"<Catalog/>")
    return downloader


def test_checksum_record_matches_hashlib(tmp_path: Path) -> None:
    f = tmp_path / "x.json"
    f.write_bytes(b"hello world")
    record = checksum_record(f)
    assert record["sha256"] == _sha256(b"hello world")
    assert record["size_bytes"] == 11


def test_pin_snapshot_writes_metadata_and_versions(tmp_path: Path) -> None:
    downloader = _seed_raw(tmp_path)
    checksums = downloader.pin_snapshot()

    assert checksums["attack"]["sha256"] == _sha256(b'{"type":"bundle"}')
    assert checksums["capec"]["sha256"] == _sha256(b"<Catalog/>")

    attack_meta = json.loads((downloader.attack_dir / "metadata.json").read_text())
    assert attack_meta["sha256"] == checksums["attack"]["sha256"]
    assert attack_meta["size_bytes"] == len(b'{"type":"bundle"}')

    versions = json.loads((tmp_path / "versions.json").read_text())
    assert versions["checksums"]["attack"]["sha256"] == checksums["attack"]["sha256"]
    assert versions["checksums"]["capec"]["sha256"] == checksums["capec"]["sha256"]


def test_pin_snapshot_preserves_download_date_and_url(tmp_path: Path) -> None:
    downloader = _seed_raw(tmp_path)
    # Pre-existing metadata with an original timestamp + versions with a date.
    (downloader.attack_dir / "metadata.json").write_text(
        json.dumps({"source_url": "http://example/orig", "downloaded_at": "2020-01-01T00:00:00+00:00"})
    )
    (tmp_path / "versions.json").write_text(
        json.dumps({"attack_version": "19.0", "capec_version": "3.9", "download_date": "2020-01-01"})
    )
    downloader.pin_snapshot()

    attack_meta = json.loads((downloader.attack_dir / "metadata.json").read_text())
    assert attack_meta["downloaded_at"] == "2020-01-01T00:00:00+00:00"
    assert attack_meta["source_url"] == "http://example/orig"
    versions = json.loads((tmp_path / "versions.json").read_text())
    assert versions["download_date"] == "2020-01-01"


def test_pin_snapshot_missing_file_raises(tmp_path: Path) -> None:
    downloader = DatasetDownloader(data_dir=tmp_path)
    downloader.ensure_dirs()
    with pytest.raises(FileNotFoundError):
        downloader.pin_snapshot()
