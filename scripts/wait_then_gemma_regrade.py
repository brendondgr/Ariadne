#!/usr/bin/env python3
"""Wait for gemma4-31B-mtp, then start the gemma half of EXP-2026-09-006.

Readiness is **two consecutive real completions with non-empty content**, not a
health flag and not an alias. `default-model-2` reports `failed` while it boots
and reports the *previous* upstream model until the swap lands, so a single
green probe is not evidence. Both graders in this project are reasoning models:
an empty `content` beside a full `reasoning` means the budget was too small, and
is downstream indistinguishable from a model with nothing to say -- which has
defeated this project four times.

Launches the gemma track detached, so its lifetime is not tied to this waiter.

    uv run python scripts/wait_then_gemma_regrade.py --until 15:45
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.cross_family_regrade import GEMMA_MODEL, GEMMA_URL, probe  # noqa: E402

LOG = REPO / "logs/cross-family-2026-09-05"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", default="15:45")
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--phase", nargs="*",
                    default=["c021", "c022", "c012", "rest"])
    args = ap.parse_args()

    hh, mm = (int(x) for x in args.until.split(":"))
    deadline = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)
    LOG.mkdir(parents=True, exist_ok=True)

    good = 0
    while datetime.now() < deadline:
        try:
            info = probe(GEMMA_URL, GEMMA_MODEL)
        except Exception as exc:                                  # noqa: BLE001
            info = {"error": f"{type(exc).__name__}: {exc}"}
        served = info.get("served_model") or ""
        ok = bool(info.get("content_chars")) and "gemma" in served.lower()
        good = good + 1 if ok else 0
        print(f"{datetime.now():%H:%M:%S} good={good} {json.dumps(info)[:220]}",
              flush=True)
        if good >= 2:
            break
        time.sleep(args.interval)
    else:
        print("deadline reached without a ready gemma; not launching", flush=True)
        return 1

    cmd = ["uv", "run", "python", "scripts/cross_family_regrade.py",
           "--track", "gemma", "--phase", *args.phase,
           "--deadline", args.until, "--skip-probe"]
    out = (LOG / "gemma-regrade.log").open("w")
    proc = subprocess.Popen(cmd, cwd=REPO, stdout=out, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True)
    print(f"launched gemma track pid={proc.pid} -> {LOG / 'gemma-regrade.log'}",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
