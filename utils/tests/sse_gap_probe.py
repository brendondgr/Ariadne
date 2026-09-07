#!/usr/bin/env python3
"""Measure the longest silence on the workbench's SSE streams under load.

This is the instrument that found the bug, kept because the failure it measures
is invisible to the test suite: on 2026-09-07 every one of twelve concurrent
llm-drafter questions **succeeded** server-side, and five of twelve would still
have died in the browser, because ``web/lib/api.ts`` cancels any stream idle
past ``SSE_STALL_MS`` (90 s). "All green, half the runs fail" is exactly the
shape a unit test cannot see.

So the number this reports is not latency — it is the longest the socket went
**quiet**, counting keep-alive comments as traffic, which is the only quantity
the client's watchdog actually measures.

Run it against a live workbench (it needs real graph backends and a real model;
nothing here is hermetic, which is why it lives under ``utils/tests`` as a tool
rather than as a pytest case)::

    uv run python utils/tests/sse_gap_probe.py --n 12
    uv run python utils/tests/sse_gap_probe.py --n 4 --api http://127.0.0.1:16601/api/query
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

DEFAULT_API = "http://127.0.0.1:16501/api/query"

#: Must match ``SSE_STALL_MS`` in ``web/lib/streamConfig.ts``. A gap over this is
#: a run the browser would have cancelled, however healthy the server thought it.
CLIENT_STALL_BUDGET_S = 90.0

QUESTIONS = [
    "What is Phishing?",
    "Which techniques does APT29 use?",
    "How does CAPEC-66 relate to ATT&CK techniques?",
    "What mitigations exist for T1566?",
    "List the sub-techniques of Process Injection.",
    "What is the CAPEC entry for SQL Injection?",
    "Which ATT&CK tactics does Credential Access include?",
    "Correlate CWE identifiers between ATT&CK and CAPEC.",
    "What software does the Lazarus Group use?",
    "Describe the technique T1055.",
    "Which attack patterns target authentication?",
    "What data sources detect lateral movement?",
]


def probe_one(index: int, question: str, api: str, cap_s: float) -> dict:
    """Stream one question, timing the arrival of every frame (keep-alives too)."""
    started = time.monotonic()
    result = {
        "index": index, "question": question,
        "max_silence_s": 0.0, "silent_after": "(connect)",
        "total_s": 0.0, "events": 0, "keepalives": 0, "outcome": "",
    }
    last_at, last_what = started, "(connect)"
    try:
        with requests.post(
            api,
            json={"question": question, "mode": "query", "drafter": "llm"},
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=(5, cap_s),
        ) as response:
            response.raise_for_status()
            buffer = ""
            for chunk in response.iter_content(chunk_size=1):
                buffer += chunk.decode("utf-8", "replace")
                while "\n\n" in buffer:
                    frame, buffer = buffer.split("\n\n", 1)
                    now = time.monotonic()
                    if now - last_at > result["max_silence_s"]:
                        result["max_silence_s"] = round(now - last_at, 2)
                        result["silent_after"] = last_what
                    if frame.startswith(":"):
                        result["keepalives"] += 1
                        last_at, last_what = now, "keepalive"
                        continue
                    name = next(
                        (ln[6:].strip() for ln in frame.split("\n") if ln.startswith("event:")),
                        "",
                    )
                    if not name:
                        continue
                    result["events"] += 1
                    if name == "status":
                        body = next(
                            (ln[5:] for ln in frame.split("\n") if ln.startswith("data:")), "{}"
                        )
                        try:
                            name = f"status({json.loads(body).get('phase', '')})"
                        except json.JSONDecodeError:
                            pass
                    last_at, last_what = now, name
                if time.monotonic() - started > cap_s:
                    result["outcome"] = "HARD_CAP"
                    break
            result["outcome"] = result["outcome"] or "OK"
    except Exception as exc:  # noqa: BLE001 - a probe reports failures, never raises
        result["outcome"] = f"{type(exc).__name__}: {exc}"
    result["total_s"] = round(time.monotonic() - started, 2)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=12, help="concurrent questions")
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--cap", type=float, default=800.0, help="per-request cap (s)")
    args = parser.parse_args(argv)

    questions = [QUESTIONS[i % len(QUESTIONS)] for i in range(args.n)]
    with ThreadPoolExecutor(max_workers=args.n) as pool:
        results = list(
            pool.map(lambda a: probe_one(a[0], a[1], args.api, args.cap), enumerate(questions))
        )

    print(f"\n{'run':>3} {'max silence':>12} {'after':<22} {'total':>8} {'ka':>4}  outcome")
    for r in sorted(results, key=lambda r: -r["max_silence_s"]):
        flag = " <<<" if r["max_silence_s"] > CLIENT_STALL_BUDGET_S else ""
        print(
            f"{r['index']:>3} {r['max_silence_s']:>11.1f}s {r['silent_after']:<22} "
            f"{r['total_s']:>7.1f}s {r['keepalives']:>4}  {r['outcome']}{flag}"
        )

    over = [r for r in results if r["max_silence_s"] > CLIENT_STALL_BUDGET_S]
    worst = max(r["max_silence_s"] for r in results)
    print(
        f"\n{len(over)}/{len(results)} runs exceeded the client's {CLIENT_STALL_BUDGET_S:.0f}s "
        f"stall budget; worst silence {worst:.1f}s"
    )
    # A run the browser would have killed is a failure even when the server
    # reported success -- that gap between the two is the whole point.
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
