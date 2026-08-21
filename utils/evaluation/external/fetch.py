#!/usr/bin/env python3
"""Fetch the two external benchmarks, at pinned revisions, into a local cache.

Neither file is committed. CTIBench is CC-BY-NC-SA-4.0 and share-alike would
follow a redistributed copy into this repository; AttackQA is Apache-2.0 but is
7 MB of someone else's data that adds nothing to the history. What *is*
committed is every score computed from them, which is our own work (D-020).

Revisions are pinned so a re-run measures the same benchmark. An unpinned fetch
would silently re-point the experiment at whatever the dataset became.
"""

from __future__ import annotations

import csv
import hashlib
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

#: Resolved 2026-08-21. Changing either of these changes what the experiment
#: measured, so a change belongs in a dated amendment, not a silent edit.
CTI_BENCH_REVISION = "9237e1636ee3e168fbe5ebdcc1c571de0525e568"
ATTACKQA_REVISION = "1cecfc248dc85a1efa69e7a8edc18e107fa58459"

CACHE = Path(os.environ.get("EXTERNAL_CACHE_DIR", ".cache/external-benchmarks"))


@dataclass(frozen=True)
class Source:
    """One downloadable file, and the licence that governs what we may do with it."""

    name: str
    url: str
    filename: str
    licence: str
    redistributable: bool


CTI_ATE = Source(
    name="cti-ate",
    url=f"https://huggingface.co/datasets/AI4Sec/cti-bench/resolve/{CTI_BENCH_REVISION}/cti-ate.tsv",
    filename="cti-ate.tsv",
    licence="CC-BY-NC-SA-4.0",
    redistributable=False,
)

ATTACKQA = Source(
    name="attackqa",
    url=f"https://huggingface.co/datasets/sambanovasystems/attackqa/resolve/{ATTACKQA_REVISION}/attackqa.parquet",
    filename="attackqa.parquet",
    licence="Apache-2.0",
    redistributable=True,
)

SOURCES = {s.name: s for s in (CTI_ATE, ATTACKQA)}


def fetch(source: Source, cache: Path | None = None) -> Path:
    """Download once into the cache; return the local path.

    A cached file is trusted on presence rather than re-hashed against a pinned
    digest, because neither publisher documents one. The revision in the URL is
    the reproducibility guarantee; the digest we compute is recorded so a
    re-download that differs is visible rather than assumed identical.
    """
    root = cache or CACHE
    root.mkdir(parents=True, exist_ok=True)
    path = root / source.filename
    if not path.is_file():
        with urllib.request.urlopen(source.url, timeout=300) as response:
            path.write_bytes(response.read())
    return path


def digest(path: Path) -> str:
    """sha256 of a fetched file, for the manifest."""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def read_cti_ate(path: Path) -> list[dict[str, str]]:
    """The 60 rows, verbatim. Columns: URL, Platform, Description, Prompt, GT."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_attackqa(path: Path) -> Iterator[dict[str, Any]]:
    """Stream AttackQA's rows as dicts.

    Imported lazily: pyarrow is needed for this one file and nothing else in the
    project, so a missing wheel should fail here rather than at import time in
    every test session that touches this package.
    """
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    columns = table.schema.names
    data = table.to_pydict()
    for index in range(table.num_rows):
        yield {column: data[column][index] for column in columns}
