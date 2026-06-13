#!/usr/bin/env python3

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path) -> Any:
    """Load JSON from a plain or gzip-compressed file."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (UnicodeDecodeError, json.JSONDecodeError):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)


def write_json(path: Path, data: Any, *, sort_keys: bool = True) -> None:
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=sort_keys)
        f.write("\n")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True))
            f.write("\n")


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_canonical_records(
    nodes_path: Path,
    relationships_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load canonical node and edge records from JSONL files."""
    return list(read_jsonl(nodes_path)), list(read_jsonl(relationships_path))


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
