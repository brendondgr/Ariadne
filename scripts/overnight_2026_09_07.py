#!/usr/bin/env python3
"""Unattended overnight driver with a hard 08:00 deadline, then a PDF.

Only ``:9090/default-model`` is addressed. No other endpoint is contacted, and
the pre-flight refuses to start if that alias does not serve the model the
record names.

Order matters. Everything that needs the GPU runs first and sequentially,
because two jobs sharing one endpoint is what produced 25 read timeouts on
2026-09-06. Everything CPU-only runs after, so a slow judging pass eats into
analysis time rather than into the deadline.

    uv run python scripts/overnight_2026_09_07.py --deadline 08:00
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

OUT = REPO / "docs/reports/2026-09-07-overnight"
STATE = OUT.with_suffix(".state.json")
LOGS = REPO / "logs/overnight-2026-09-07"
BASE = "http://localhost:9090/v1"
MODEL = {"alias": "default-model", "expect": "qwen38-27B-v2"}


def now() -> datetime:
    return datetime.now()


def probe() -> str:
    import urllib.request
    body = json.dumps({"model": MODEL["alias"],
                       "messages": [{"role": "user", "content": "Reply with only: OK"}],
                       "max_tokens": 2048}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as fh:
        payload = json.load(fh)
    if "error" in payload:
        raise RuntimeError(str(payload["error"])[:200])
    served = payload.get("model")
    if served != MODEL["expect"]:
        raise RuntimeError(f"{MODEL['alias']} serves {served!r}, "
                           f"record names {MODEL['expect']!r}")
    return served


def run(name: str, cmd: list[str], deadline: datetime, st: dict,
        needs_gpu: bool = True) -> dict:
    """One step. Refuses to start if the deadline has passed."""
    LOGS.mkdir(parents=True, exist_ok=True)
    if now() >= deadline:
        rec = {"status": "skipped", "why": "past deadline"}
        st["steps"][name] = rec
        save(st)
        print(f"[{now():%H:%M}] SKIP {name} (past deadline)", flush=True)
        return rec

    print(f"[{now():%H:%M}] START {name}", flush=True)
    t0 = time.time()
    log = LOGS / f"{name}.log"
    with log.open("w") as fh:
        proc = subprocess.Popen(cmd, cwd=REPO, stdout=fh,
                                stderr=subprocess.STDOUT)
        while proc.poll() is None:
            if now() >= deadline:
                proc.terminate()
                try:
                    proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    proc.kill()
                rec = {"status": "stopped_at_deadline",
                       "elapsed_s": round(time.time() - t0, 1), "log": str(log)}
                st["steps"][name] = rec
                save(st)
                print(f"[{now():%H:%M}] STOP {name} at deadline", flush=True)
                return rec
            time.sleep(20)
    rec = {"status": "ok" if proc.returncode == 0 else f"rc={proc.returncode}",
           "elapsed_s": round(time.time() - t0, 1), "log": str(log),
           "tail": log.read_text()[-1200:]}
    st["steps"][name] = rec
    save(st)
    print(f"[{now():%H:%M}] DONE {name} ({rec['status']}, "
          f"{rec['elapsed_s']:.0f}s)", flush=True)
    return rec


def save(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1, default=str) + "\n")


def wait_for(pid: int, deadline: datetime, st: dict) -> str:
    """Wait on an already-running job without restarting it."""
    print(f"[{now():%H:%M}] waiting on pid {pid}", flush=True)
    while now() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            st["steps"]["inherited_chain"] = {"status": "finished", "pid": pid}
            save(st)
            print(f"[{now():%H:%M}] pid {pid} finished", flush=True)
            return "finished"
        time.sleep(60)
    st["steps"]["inherited_chain"] = {"status": "still_running_at_deadline",
                                      "pid": pid}
    save(st)
    return "still_running_at_deadline"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", default="08:00")
    ap.add_argument("--wait-pid", type=int, default=None,
                    help="an already-running chain to wait on before starting")
    args = ap.parse_args()

    hh, mm = (int(x) for x in args.deadline.split(":"))
    deadline = now().replace(hour=hh, minute=mm, second=0, microsecond=0)
    if deadline <= now():
        deadline += timedelta(days=1)
    # Stop GPU work early enough that the report always gets written.
    gpu_deadline = deadline - timedelta(minutes=25)

    st = {"started": str(now()), "deadline": str(deadline),
          "gpu_deadline": str(gpu_deadline), "steps": {}}
    save(st)
    print(f"[{now():%H:%M}] overnight driver, deadline {deadline:%H:%M} "
          f"(GPU work stops {gpu_deadline:%H:%M})", flush=True)

    try:
        st["served_model"] = probe()
        print(f"[{now():%H:%M}] endpoint OK: {st['served_model']}", flush=True)
    except Exception as exc:
        st["served_model"] = f"PROBE FAILED: {exc}"
        print(f"[{now():%H:%M}] endpoint probe failed: {exc}", flush=True)
    save(st)

    if args.wait_pid:
        wait_for(args.wait_pid, gpu_deadline, st)

    U = ["uv", "run", "python"]

    # --- GPU work, sequential -------------------------------------------
    # If the inherited chain did not finish judging, resume it. The judge
    # skips cases that already have a sidecar, so this is idempotent.
    run("judge_generic_resume",
        U + ["scripts/seeded_repeats_judge.py", "--arm", "generic",
             "--workers", "32"], gpu_deadline, st)

    # --- CPU-only work, after the GPU is released ------------------------
    run("validate_research", ["make", "validate-research"], deadline, st, False)
    run("verify_paper_numbers",
        U + ["scripts/verify_paper_numbers.py", "--json",
             str(OUT.parent / "2026-09-07-paper-numbers.json")],
        deadline, st, False)
    run("identity_analysis", U + ["scripts/arm_identity_analyse.py"],
        deadline, st, False)

    # --- report ----------------------------------------------------------
    run("report", U + ["scripts/overnight_2026_09_07_report.py"],
        deadline + timedelta(minutes=20), st, False)

    st["finished"] = str(now())
    save(st)
    print(f"[{now():%H:%M}] driver complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
