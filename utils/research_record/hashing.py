"""Content hashes for config files and large run artifacts.

A pointer without a hash is a path that may or may not still hold what it held
when the number was computed. The validator rejects those, so this module is
what makes ``data/POINTERS.md`` trustworthy.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

_CHUNK = 1 << 20  # 1 MiB — the largest artifact in this repository is ~2.6 MB


def sha256_file(path: Path) -> str:
    """Return ``sha256:<hex>`` for a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def sha256_tree(root: Path, pattern: str = "**/*") -> str:
    """Return a stable ``sha256:<hex>`` over every file under ``root``.

    Directory hashes let one pointer stand for a run's whole output directory
    rather than 120 separate rows. Paths are sorted and folded into the digest
    alongside the content so that a rename is a change, not a no-op.
    """
    digest = hashlib.sha256()
    for path in sorted(p for p in root.glob(pattern) if p.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(sha256_file(path).encode())
    return f"sha256:{digest.hexdigest()}"


def _main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m utils.research_record.hashing <path> [...]", file=sys.stderr)
        return 2
    for raw in argv:
        path = Path(raw)
        if not path.exists():
            print(f"missing: {raw}", file=sys.stderr)
            return 1
        if path.is_dir():
            size = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
            print(f"{sha256_tree(path)}  {raw}  ({size} bytes, tree)")
        else:
            print(f"{sha256_file(path)}  {raw}  ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(_main(sys.argv[1:]))
