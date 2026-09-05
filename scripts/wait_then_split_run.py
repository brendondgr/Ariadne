#!/usr/bin/env python3
"""Wait until both GPUs genuinely answer, then probe and launch the split run.

"Listening" is not "ready": the 2026-09-05 probe fired 0.6 s after launch and
got ten responses with no ``choices`` key at all, because vLLM was still loading
weights. Readiness here means a real completion with non-empty ``content`` from
each alias, twice in a row -- a single success can land while the second GPU is
still warming.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from utils.config import load_env  # noqa: E402

load_env()
from scripts.split_llm_query_run import BASE_URL, MODELS  # noqa: E402

LOG = REPO / "logs/2026-09-05/wait.log"
MAX_WAIT_MIN = 60


def say(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")


def healthy(model: str) -> tuple[bool, str]:
    import requests

    try:
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            json={"model": model, "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                  "max_tokens": 512, "temperature": 0.0},
            timeout=180,
        )
        body = r.json()
        if "choices" not in body:
            return False, f"no choices: {json.dumps(body)[:120]}"
        msg = body["choices"][0]["message"]
        content = msg.get("content") or ""
        if not content.strip():
            return False, f"empty content (reasoning={len(msg.get('reasoning') or '')} chars)"
        return True, f"served={body.get('model')} content={content.strip()[:20]!r}"
    except Exception as exc:                                       # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    say(f"waiting for {MODELS} on {BASE_URL} (up to {MAX_WAIT_MIN} min)")
    deadline = time.time() + MAX_WAIT_MIN * 60
    streak = 0
    while time.time() < deadline:
        results = {m: healthy(m) for m in MODELS}
        for m, (ok, detail) in results.items():
            say(f"  {m}: {'READY' if ok else 'not ready'} — {detail}")
        if all(ok for ok, _ in results.values()):
            streak += 1
            # Two consecutive clean rounds: one success can land while the other
            # GPU is still loading.
            if streak >= 2:
                say("both GPUs ready twice in a row — probing")
                break
        else:
            streak = 0
        time.sleep(60)
    else:
        say("gave up waiting; NOT launching")
        return 1

    say("running the clock-vs-budget probe")
    r = subprocess.run(["uv", "run", "python", "scripts/split_llm_query_run.py"],
                       cwd=REPO, capture_output=True, text=True)
    say(r.stdout[-1500:] if r.stdout else "(no stdout)")
    if r.returncode != 0:
        say(f"launcher exited {r.returncode}; stderr: {r.stderr[-500:]}")
        return r.returncode
    say("split run launched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
