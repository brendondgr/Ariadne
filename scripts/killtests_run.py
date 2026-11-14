#!/usr/bin/env python3
"""The kill-test chain: T2 -> T3 in one thread, T1 alongside, then the report.

    uv run python scripts/killtests_run.py               # everything
    uv run python scripts/killtests_run.py --only t2     # one test (t3 implies t2's first two stages)
    KILLTESTS_SMOKE=1 uv run python scripts/killtests_run.py

Every stage resumes: finished stages are skipped, a half-finished stage redoes
only its unfinished items. ``chain.json`` records each test's state and the
last failure, which the supervisor reads to decide whether to restart and the
health call reads to report. Exit code 0 only when every requested test
finished and the report was written.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.config import load_env  # noqa: E402

load_env()

from utils.killtests import analysis, config, heartbeat, provenance  # noqa: E402
from utils.killtests.stages import Stage, atomic_write_json  # noqa: E402
from utils.killtests.t1 import run as t1  # noqa: E402
from utils.killtests.t2 import run as t2  # noqa: E402
from utils.killtests.t3 import run as t3  # noqa: E402

_lock = threading.Lock()


def _chain_path(cfg) -> Path:
    return cfg.out_dir / "chain.json"


def _update(cfg, test: str, **fields) -> None:
    with _lock:
        p = _chain_path(cfg)
        try:
            state = json.loads(p.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            state = {"tests": {}}
        state["tests"].setdefault(test, {}).update(fields, updated_at=time.time())
        state["updated_at"] = time.time()
        atomic_write_json(p, state)


def _guard(cfg, test: str, fn) -> bool:
    _update(cfg, test, status="running", started_at=time.time())
    try:
        fn()
        _update(cfg, test, status="done")
        return True
    except BaseException as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        _update(cfg, test, status="failed", error=f"{type(exc).__name__}: {exc}"[:500], traceback=tb[-3000:])
        print(tb, file=sys.stderr, flush=True)
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["t1", "t2", "t3"], action="append")
    args = ap.parse_args(argv)
    which = args.only or ["t1", "t2", "t3"]
    cfg = config.get()
    out = cfg.out_dir
    out.mkdir(parents=True, exist_ok=True)
    heartbeat.configure(out, run="smoke" if cfg.smoke else "full")
    pre = out / "preconditions.json"
    if not pre.exists():
        atomic_write_json(pre, provenance.preconditions(cfg, include_t1="t1" in which))
    atomic_write_json(out / "run_header.json", provenance.header(cfg, which=which, started_at=time.time()))

    results = {}

    def t2_t3():
        if "t2" in which or "t3" in which:
            ok = _guard(cfg, "t2", lambda: t2.run(cfg, out) if "t2" in which
                        else t2.stage_decide(cfg, out, t2.stage_candidates(cfg, out)))
            results["t2"] = ok
            if ok and "t3" in which:
                cand = t2.stage_candidates(cfg, out)
                dec = t2.stage_decide(cfg, out, cand)
                results["t3"] = _guard(cfg, "t3", lambda: t3.run(cfg, out, cand, dec))
            elif "t3" in which:
                results["t3"] = False

    threads = [threading.Thread(target=t2_t3, name="t2-t3")]
    if "t1" in which:
        threads.append(threading.Thread(target=lambda: results.__setitem__("t1", _guard(cfg, "t1", lambda: t1.run(cfg, out))),
                                        name="t1"))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if all(results.get(t) for t in which):
        rep = Stage(out, "report")
        verdicts = analysis.write(cfg, which)
        rep.finish({t: {k: v for k, v in r.items() if k != "metrics"} for t, r in verdicts.items()})
        _update(cfg, "report", status="done")
        print(json.dumps({t: r["verdict"] for t, r in verdicts.items()}))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
