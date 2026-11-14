"""A live progress file the health call reads: ``<out_dir>/heartbeat.json``.

T1 runs in parallel with T2 -> T3, so the file holds one entry per stage that
has reported, each with its own progress and timestamp:

    {"stages": {"t2/decide": {"done": 120, "total": 524, "errors": 0,
                              "started_at": ..., "updated_at": ...}, ...},
     "pid": ..., "updated_at": <newest stage update>}

``beat`` is throttled so a stage mapping thousands of fast items does not
rewrite the file thousands of times. The health call treats a heartbeat whose
newest update is older than ten minutes as a stalled run.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

_lock = threading.Lock()
_last: dict[str, float] = {}
_path: Path | None = None
_state: dict = {"stages": {}}
_extra: dict = {}


def configure(out_dir: Path, **extra: object) -> None:
    global _path, _extra, _state
    _path = out_dir / "heartbeat.json"
    _extra = dict(extra)
    out_dir.mkdir(parents=True, exist_ok=True)
    prev = read(out_dir) or {}
    _state = {"stages": dict(prev.get("stages") or {})}


def beat(stage: str, done: int, total: int, errors: int, *, throttle_s: float = 0.0, **extra: object) -> None:
    if _path is None:
        return
    now = time.time()
    with _lock:
        if throttle_s and now - _last.get(stage, 0.0) < throttle_s and done < total:
            return
        _last[stage] = now
        prev = _state["stages"].get(stage) or {}
        started = prev.get("started_at") if prev.get("done", 0) <= done and prev.get("started_at") else now
        _state["stages"][stage] = {"done": done, "total": total, "errors": errors,
                                   "started_at": started, "updated_at": now, **extra}
        rec = {**_state, "pid": os.getpid(), "updated_at": now,
               "updated_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)), **_extra}
        tmp = _path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rec, indent=1))
        os.replace(tmp, _path)


def read(out_dir: Path) -> dict | None:
    p = out_dir / "heartbeat.json"
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
