#!/usr/bin/env python3
"""Recovery primitives for the Ariadne data pipeline.

Provides the building blocks behind the pipeline's error-handling policy:

* **Backup-and-replace** for on-disk artifacts that already exist — copy the
  existing state aside, then let the caller rebuild into a clean directory,
  rather than failing on stale leftovers (``backup_directory`` /
  ``prepare_clean_dir`` / ``restore_directory``).
* **Failure classification** — decide whether a raised exception is a
  ``stale_state`` (an artifact/graph already existing on disk),
  ``transient`` (worth retrying), or ``needs_human`` (stop with an actionable
  message) condition (``classify_failure``).
* **Bounded retry** with exponential backoff for transient failures
  (``retry_with_backoff``).

The module is intentionally dependency-free (stdlib only) so both the builder
(``utils/kg_builder``) and the pipeline runner (``utils/yolo.py``) can consume it.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, TypeVar

FailureClass = Literal["stale_state", "transient", "needs_human"]

T = TypeVar("T")


@dataclass(frozen=True)
class BackupRecord:
    """Where an existing directory was moved before a clean rebuild."""

    original: Path
    backup: Path


def _timestamp() -> str:
    """UTC timestamp safe for use in a directory name."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_empty_dir(path: Path) -> bool:
    return path.is_dir() and not any(path.iterdir())


def backup_directory(
    path: Path,
    *,
    backups_root: Path | None = None,
    label: str | None = None,
) -> BackupRecord | None:
    """Move ``path`` aside to a timestamped backup, returning the record.

    Returns ``None`` when there is nothing to back up (the path does not exist
    or is an empty directory). The backup is created under ``backups_root``
    (default: ``<path.parent>/_backups``) as ``<label or path.name>-<UTC stamp>``
    so it never collides with, or is mistaken for, the live artifacts.
    """
    path = Path(path)
    if not path.exists() or _is_empty_dir(path):
        return None

    root = backups_root if backups_root is not None else path.parent / "_backups"
    root.mkdir(parents=True, exist_ok=True)

    name = label or path.name
    dest = root / f"{name}-{_timestamp()}"
    # Guard against an extremely unlikely same-second collision.
    suffix = 1
    while dest.exists():
        dest = root / f"{name}-{_timestamp()}-{suffix}"
        suffix += 1

    shutil.move(str(path), str(dest))
    return BackupRecord(original=path, backup=dest)


def prepare_clean_dir(
    path: Path,
    *,
    backups_root: Path | None = None,
    label: str | None = None,
) -> BackupRecord | None:
    """Ensure ``path`` exists and is empty, backing up any existing contents.

    This is the "make a new copy, then replace" primitive: a non-empty
    directory is moved to a backup first, then a fresh empty directory is
    created at ``path``. Returns the backup record (or ``None`` if there was
    nothing to preserve).
    """
    path = Path(path)
    record = backup_directory(path, backups_root=backups_root, label=label)
    path.mkdir(parents=True, exist_ok=True)
    return record


def restore_directory(record: BackupRecord) -> Path:
    """Restore a backup created by :func:`backup_directory`.

    Replaces the (possibly newly written) original with the backed-up copy.
    Returns the restored original path.
    """
    original = record.original
    if original.exists():
        shutil.rmtree(original) if original.is_dir() else original.unlink()
    shutil.move(str(record.backup), str(original))
    return original


# ── Failure classification ────────────────────────────────────────────────────

# Substrings that identify an "already exists / stale on-disk state" failure
# that backup-and-replace can recover from.
_STALE_MARKERS = (
    "not in schema",
    "already exists",
    "duplicate",
    "missing canonical artifact",
)

# Exception types that are transient and worth retrying.
_TRANSIENT_TYPES: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
)

# Substrings that mark an otherwise-generic error as transient.
_TRANSIENT_MARKERS = (
    "timed out",
    "timeout",
    "connection refused",
    "connection reset",
    "temporarily unavailable",
    "unreachable",
)


def classify_failure(exc: BaseException) -> FailureClass:
    """Classify an exception for the pipeline's recovery policy.

    * ``stale_state`` — an artifact/graph already existing on disk caused a
      consistency failure (recoverable by backup + clean rebuild).
    * ``transient`` — a network/IO hiccup worth retrying.
    * ``needs_human`` — anything else; stop and surface for human input.

    Transient classification takes precedence over stale markers so a genuine
    connection error is never mistaken for stale state.
    """
    message = str(exc).lower()

    if isinstance(exc, _TRANSIENT_TYPES) or any(m in message for m in _TRANSIENT_MARKERS):
        return "transient"

    # ArtifactValidationError lives in kg_builder; match by name to avoid a
    # cross-package import while still recognising the build-time failure.
    type_names = {t.__name__ for t in type(exc).__mro__}
    if "ArtifactValidationError" in type_names or any(m in message for m in _STALE_MARKERS):
        return "stale_state"

    return "needs_human"


# ── Bounded retry ─────────────────────────────────────────────────────────────


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    retries: int = 2,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    should_retry: Callable[[BaseException], bool] | None = None,
    sleep: Callable[[float], None] | None = None,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> T:
    """Call ``fn``, retrying on retryable failures with exponential backoff.

    ``retries`` is the number of *additional* attempts after the first, so the
    function is invoked at most ``retries + 1`` times. ``should_retry`` decides
    whether a given exception is retryable (default: ``classify_failure`` returns
    ``"transient"``). The last exception is re-raised once attempts are
    exhausted or a non-retryable error is seen. ``on_retry`` is invoked before
    each backoff sleep with ``(attempt, exc, delay)`` for logging/observability.
    """
    if should_retry is None:
        should_retry = lambda exc: classify_failure(exc) == "transient"  # noqa: E731
    if sleep is None:
        sleep = time.sleep

    attempt = 0
    delay = base_delay
    while True:
        try:
            return fn()
        except BaseException as exc:  # noqa: BLE001 — re-raised below; policy decides
            attempt += 1
            if attempt > retries or not should_retry(exc):
                raise
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            sleep(delay)
            delay *= backoff
