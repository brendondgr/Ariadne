#!/usr/bin/env python3
"""Pinned-snapshot verification for builds.

The gold Q&A answers (REF:<id> values) are computed against a specific data
state, so builds must run only from the exact ATT&CK v19.0 / CAPEC v3.9 files
that were pinned by sha256. This module recomputes a raw file's checksum and
compares it to the pin recorded in ``data/versions.json`` (or the per-source
``metadata.json``), failing fast if MITRE silently shipped a new revision.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .config import BuildConfig
from .io import file_sha256

logger = logging.getLogger(__name__)


class SnapshotChecksumError(Exception):
    """Raised when a raw source file does not match its pinned checksum."""


@dataclass(frozen=True)
class SnapshotStatus:
    dataset: str
    raw_file: str
    actual_sha256: str
    pinned_sha256: str | None

    @property
    def pinned(self) -> bool:
        return self.pinned_sha256 is not None

    @property
    def matches(self) -> bool:
        return self.pinned and self.actual_sha256 == self.pinned_sha256


def read_pinned_checksum(data_dir: Path, dataset: str) -> str | None:
    """Return the pinned sha256 for a dataset from versions.json, if recorded."""
    versions_file = Path(data_dir) / "versions.json"
    if not versions_file.exists():
        return None
    with open(versions_file, encoding="utf-8") as f:
        versions = json.load(f)
    return versions.get("checksums", {}).get(dataset, {}).get("sha256")


def verify_pinned_snapshot(
    config: BuildConfig, dataset: str, *, strict: bool = True
) -> SnapshotStatus:
    """Verify a dataset's raw file matches its pinned checksum.

    When ``strict`` and a pin exists, a mismatch raises ``SnapshotChecksumError``.
    An absent pin is a warning, not an error, so pre-pin snapshots still build.
    """
    raw_file = config.paths().for_dataset(dataset).raw_file
    if not raw_file.exists():
        raise FileNotFoundError(
            f"Raw {dataset} source not found at {raw_file}. "
            "Run `uv run main.py --download` first."
        )

    actual = file_sha256(raw_file)
    pinned = read_pinned_checksum(config.data_dir, dataset)
    status = SnapshotStatus(
        dataset=dataset,
        raw_file=str(raw_file),
        actual_sha256=actual,
        pinned_sha256=pinned,
    )

    if pinned is None:
        logger.warning(
            "No pinned checksum for %s in versions.json; building from unpinned "
            "%s (sha256=%s). Run the snapshot pin to record it.",
            dataset,
            raw_file.name,
            actual,
        )
        return status

    if not status.matches:
        message = (
            f"Pinned-snapshot mismatch for {dataset}: {raw_file} sha256={actual} "
            f"does not match pinned {pinned}. The raw source drifted from the "
            "pinned snapshot; rebuild the pin deliberately if this is intended."
        )
        if strict:
            raise SnapshotChecksumError(message)
        logger.error(message)
        return status

    logger.info("Pinned-snapshot verified for %s (sha256=%s).", dataset, actual)
    return status
