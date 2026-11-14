#!/usr/bin/env python3
"""Start or stop the supervised kill-test chain.

    uv run python scripts/killtests_ctl.py start     # or: make killtests-start
    uv run python scripts/killtests_ctl.py stop      # or: make killtests-stop

``start`` launches ``killtests_supervise.sh`` detached (its own session, so it
outlives the shell that started it) unless a live supervisor already holds the
pid file. ``stop`` signals the supervisor and every chain process; finished
stages and cached items are kept, so a later ``start`` resumes.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def out_dir() -> Path:
    smoke = os.environ.get("KILLTESTS_SMOKE", "0").strip().lower() in {"1", "true", "yes"}
    return REPO / os.environ.get("KILLTESTS_OUT", "logs/killtests-2026-11" + ("/smoke" if smoke else ""))


def supervisor_pid(out: Path) -> int | None:
    try:
        pid = int((out / "supervisor.pid").read_text().strip())
        if "killtests_supervise.sh" in Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace"):
            return pid
    except (FileNotFoundError, ValueError, PermissionError):
        pass
    return None


def chain_pids() -> list[int]:
    out = subprocess.run(["ps", "-eo", "pid,args", "--no-headers"], capture_output=True, text=True).stdout
    pids = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "python" in Path(parts[1]).name and parts[2].endswith("scripts/killtests_run.py"):
            pids.append(int(parts[0]))
    return pids


def start() -> int:
    out = out_dir()
    out.mkdir(parents=True, exist_ok=True)
    pid = supervisor_pid(out)
    if pid:
        print(f"supervisor already running (pid {pid})")
        return 0
    env = {**os.environ, "KILLTESTS_OUT": str(out.relative_to(REPO))}
    subprocess.Popen(["bash", str(REPO / "scripts/killtests_supervise.sh")], cwd=REPO, env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(20):
        time.sleep(0.5)
        pid = supervisor_pid(out)
        if pid:
            print(f"supervisor started (pid {pid}); output in {out.relative_to(REPO)}")
            return 0
    print("supervisor did not start; see supervisor.log")
    return 1


def stop() -> int:
    out = out_dir()
    pid = supervisor_pid(out)
    if pid:
        os.kill(pid, signal.SIGTERM)
    for p in chain_pids():
        try:
            os.kill(p, signal.SIGTERM)
        except ProcessLookupError:
            pass
    pf = out / "supervisor.pid"
    if pf.exists():
        pf.unlink()
    print("stopped")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "start":
        raise SystemExit(start())
    if cmd == "stop":
        raise SystemExit(stop())
    print(__doc__)
    raise SystemExit(2)
