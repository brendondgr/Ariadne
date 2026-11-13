"""A live progress file the health call reads: ``<out_dir>/heartbeat.json``.

Rewritten atomically by the running stage. ``beat`` is throttled so a stage
mapping thousands of fast items does not rewrite the file thousands of times.
The health call treats a heartbeat older than ten minutes as a stalled run.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

_lock = threading.Lock()
_last = 0.0
_path: Path | None = None
_extra: dict = {}


def configure(out_dir: Path, **extra: object) -> None:
    global _path, _extra
    _path = out_dir / "heartbeat.json"
    _extra = dict(extra)
    out_dir.mkdir(parents=True, exist_ok=True)


def beat(stage: str, done: int, total: int, errors: int, *, throttle_s: float = 0.0, **extra: object) -> None:
    global _last
    if _path is None:
        return
    now = time.time()
    with _lock:
        if throttle_s and now - _last < throttle_s and done < total:
            return
        _last = now
        rec = {
            "stage": stage,
            "done": done,
            "total": total,
            "errors": errors,
            "pid": os.getpid(),
            "updated_at": now,
            "updated_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
            **_extra,
            **extra,
        }
        tmp = _path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rec, indent=1))
        os.replace(tmp, _path)


def read(out_dir: Path) -> dict | None:
    p = out_dir / "heartbeat.json"
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
