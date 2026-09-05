#!/usr/bin/env python3
"""Carry the split re-run through to a finished, plain-language report.

Waits on the two run PIDs, merges the halves, refuses to judge a run that did
not do what it was for, grades it on the same instrument as the other two arms,
and writes a report a reader can follow without knowing the codebase.

Serialises against whatever else is using the :4000 relay, because the one time
two things shared it the timings became a measurement of contention.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from utils.config import load_env  # noqa: E402

load_env()

SPLIT = REPO / "docs/evaluation/experiments/llm-query-split-2026-09-05"
MERGED = SPLIT / "llm_query" / "answers"
LOG = REPO / "logs/2026-09-05/finish.log"
BANK_DIR = REPO / "docs/evaluation/composition/bank"


def say(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def wait_pids() -> None:
    pids = json.loads((REPO / "logs/2026-09-05/pids.json").read_text())
    say(f"waiting on run pids {pids}")
    while any(alive(p) for p in pids.values()):
        time.sleep(120)
    say("both halves finished")


def merge() -> dict:
    MERGED.mkdir(parents=True, exist_ok=True)
    copied = 0
    for tag in ("a", "b"):
        src = SPLIT / tag / "llm_query" / "answers"
        for p in sorted(src.glob("*.json")) if src.is_dir() else []:
            if ".judgment" in p.name:
                continue
            shutil.copy2(p, MERGED / p.name)
            copied += 1
    built = empty_len = empty_other = 0
    for p in MERGED.glob("*.json"):
        if ".judgment" in p.name:
            continue
        a = json.loads(p.read_text())
        r = (a.get("logic_flow") or {}).get("results") or [{}]
        if str(r[0].get("query") or ""):
            built += 1
        else:
            (globals().__setitem__("_", None))
            err = str(r[0].get("error") or "")
            if "empty query" in err:
                empty_len += 1
            else:
                empty_other += 1
    out = {"answers": copied, "queries_built": built,
           "empty_query": empty_len, "other_failure": empty_other}
    say(f"merged: {json.dumps(out)}")
    return out


def wait_for_relay() -> None:
    """The :4000 grader is single-tenant by convention here, not by enforcement."""
    while subprocess.run(["pgrep", "-f", "judge_llmq"], capture_output=True).returncode == 0:
        say("waiting for the previous judging to release the relay")
        time.sleep(180)


def judge() -> dict:
    from scripts import overnight_two_track as ot

    out = {}
    for suffix, position in (("", 1), (".pass2", 2)):
        s = ot._judge(SPLIT, "llm_query", url=ot.QWEN_URL, model=ot.QWEN_MODEL,
                      workers=ot.QWEN_WORKERS, suffix=suffix, position=position)
        say(f"judged llm_query{suffix or '.pass1'}: {json.dumps(s)[:160]}")
        out[suffix or ".pass1"] = s
    return out


def main() -> int:
    wait_pids()
    stats = merge()
    (BANK_DIR / "split-merge-2026-09-05.json").write_text(json.dumps(stats, indent=1) + "\n")

    if stats["answers"] < 284:
        say(f"only {stats['answers']}/284 answers — NOT judging a partial arm")
    elif stats["queries_built"] <= 140:
        say(f"only {stats['queries_built']} built a query, no better than the last run "
            f"(140) — NOT judging")
    else:
        wait_for_relay()
        say("judging on :4000, two counterbalanced passes")
        judge()

    say("writing the report")
    subprocess.run(["uv", "run", "python", "scripts/plain_report.py"], cwd=REPO, check=False)
    say("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
