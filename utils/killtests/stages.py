"""Resumable stages: a crash costs in-flight items, never the run.

A *stage* is a named step whose output is one JSON file written atomically
(temp file, then ``os.replace``) plus a ``<stage>.done`` marker. A restarted
chain skips any stage whose marker exists.

Inside a stage, :class:`ItemCache` keeps one JSON line per finished item, keyed,
so a stage killed half-way resumes from the items it already finished.
Appends are flushed per line; a torn last line (a kill mid-write) is skipped
on read, so the cache is never corrupted by an interruption.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from . import heartbeat


def atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(obj, fh, indent=1, sort_keys=False, default=str)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def read_json(path: Path) -> Any:
    with open(path) as fh:
        return json.load(fh)


class ItemCache:
    """Append-only, keyed, crash-tolerant per-item results."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._items: dict[str, Any] = {}
        if path.exists():
            with open(path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # torn final line from a kill mid-write
                    self._items[rec["key"]] = rec["value"]

    def __contains__(self, key: str) -> bool:
        return key in self._items

    def get(self, key: str) -> Any:
        return self._items.get(key)

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            with open(self.path, "a") as fh:
                fh.write(json.dumps({"key": key, "value": value}, default=str) + "\n")
                fh.flush()
            self._items[key] = value

    def values(self) -> dict[str, Any]:
        return dict(self._items)

    def __len__(self) -> int:
        return len(self._items)


class Stage:
    """One named, resumable step writing ``<out_dir>/<name>.json``."""

    def __init__(self, out_dir: Path, name: str) -> None:
        self.out_dir = out_dir
        self.name = name
        self.label = f"{out_dir.name}/{name}"
        self.output = out_dir / f"{name}.json"
        self.marker = out_dir / f"{name}.done"
        self.cache = ItemCache(out_dir / "cache" / f"{name}.jsonl")
        self.errors = 0

    @property
    def done(self) -> bool:
        return self.marker.exists() and self.output.exists()

    def finish(self, result: Any) -> None:
        atomic_write_json(self.output, result)
        self.marker.write_text("done\n")

    def load(self) -> Any:
        return read_json(self.output)

    def map(
        self,
        items: Iterable[tuple[str, Any]],
        fn: Callable[[Any], Any],
        *,
        workers: int = 1,
        total: int | None = None,
    ) -> dict[str, Any]:
        """Run ``fn`` over ``(key, item)`` pairs not yet cached; return every result.

        A raising item is recorded as ``{"error": "..."}`` and counted, never
        dropped silently and never retried in the same pass. A restart retries
        error items, because only successes are written to the cache.
        """
        pending = [(k, it) for k, it in items if k not in self.cache]
        n_total = total if total is not None else len(pending) + len(self.cache)
        results: dict[str, Any] = {}
        done = len(self.cache)
        heartbeat.beat(self.label, done, n_total, self.errors)

        def _one(key: str, item: Any) -> tuple[str, Any, bool]:
            try:
                return key, fn(item), True
            except Exception as exc:  # noqa: BLE001
                return key, {"error": f"{exc.__class__.__name__}: {exc}"[:500]}, False

        if workers <= 1:
            for key, item in pending:
                k, v, ok = _one(key, item)
                done = self._record(k, v, ok, done, n_total, results)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = [pool.submit(_one, k, it) for k, it in pending]
                for fut in as_completed(futs):
                    k, v, ok = fut.result()
                    done = self._record(k, v, ok, done, n_total, results)
        merged = self.cache.values()
        merged.update({k: v for k, v in results.items() if k not in merged})
        heartbeat.beat(self.label, n_total, n_total, self.errors)
        return merged

    def _record(self, key: str, value: Any, ok: bool, done: int, total: int, results: dict) -> int:
        if ok:
            self.cache.put(key, value)
        else:
            self.errors += 1
            results[key] = value
        done += 1
        heartbeat.beat(self.label, done, total, self.errors, throttle_s=5.0)
        return done
