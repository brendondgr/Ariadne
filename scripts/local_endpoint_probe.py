#!/usr/bin/env python3
"""Measure what a local llama.cpp endpoint actually is, and what it can take.

Three things, in order, each of which can stop the run:

1. **Identity.** Resolve the alias and assert the served model is the one the
   experiment claims. An alias is not a model — `skynet` has served three
   different architectures over this project's life and nothing noticed until
   `OPEN_QUESTIONS.md` Q12 — so a figure attributed to weights nobody verified is
   a figure attributed to nothing. The gate reads the `model` field off the
   *response envelope*, never `GET /v1/models`, which reports relay
   configuration rather than what answered.

2. **Context ceiling.** Double `max_tokens` on a trivial prompt until the server
   refuses, then binary-search the boundary, and record the refusal body
   *verbatim*. The judge's 400s on `:9090` were misdiagnosed twice because
   nobody read one. The prompt is trivial on purpose: the model hits EOS after a
   few tokens regardless of the cap, so a probe asking for a million tokens
   costs the same as one asking for a thousand. What is being measured is the
   server's *validation*, not its generation.

3. **Concurrency.** Walk a ladder of simultaneous requests with a fixed prompt,
   recording aggregate tokens/second, p50 and p95 latency, and every error. The
   knee — the rung where throughput stops rising while p95 keeps climbing — is
   the worker count every later step uses. llama.cpp serves a fixed number of
   slots and queues past them, so over-subscribing buys latency and nothing
   else; on a shared desktop it also buys an unusable afternoon.

The ladder never climbs past a rung that failed, and it runs rung 1 alone first:
if a single request's p50 is already above `--slow-p50`, the model is too slow to
be worth a full bank and this says so at a cost of ten calls rather than a night.

Usage:

    uv run python scripts/local_endpoint_probe.py                     # gate on minicpm
    uv run python scripts/local_endpoint_probe.py --expect gemma      # gate on something else
    uv run python scripts/local_endpoint_probe.py --allow-identity-mismatch
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

DEFAULT_BASE_URL = "http://localhost:4000/v1"
DEFAULT_ALIAS = "local"
DEFAULT_RUNGS = (1, 2, 4, 8, 12)
DEFAULT_CALLS = 10

#: The ladder's prompt. Fixed across every rung so the rungs are comparable, and
#: shaped to emit a predictable couple of hundred tokens so throughput is
#: measured over real generation rather than over one word.
LADDER_PROMPT = "Count from 1 to 120, separated by single spaces. Output nothing else."

#: The bisect's prompt. Deliberately trivial — see the module docstring.
CEILING_PROMPT = "Reply with exactly: OK"

#: Never ask for more than this many tokens while bisecting. A server that
#: accepts it is reported as "no ceiling below the cap" rather than probed
#: further, because the answer past this point does not change any decision.
DEFAULT_TOKEN_CAP = 1 << 20  # 1,048,576


# --------------------------------------------------------------------------- #
# Call records
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Call:
    """One completion attempt, successful or not."""

    ok: bool
    latency_s: float
    completion_tokens: int = 0
    prompt_tokens: int = 0
    status: int | None = None
    error: str | None = None
    #: The server's own response body on a failure, kept verbatim.
    body: str | None = None
    served_model: str | None = None


@dataclass
class Rung:
    """One concurrency level's worth of calls."""

    concurrency: int
    calls: int
    wall_s: float
    ok: int
    errors: int
    completion_tokens: int
    #: Aggregate throughput: every token the rung produced over its wall clock.
    #: This is the number that stops rising at the knee.
    tokens_per_s: float
    #: Throughput of a single stream, averaged over the rung's calls.
    per_call_tokens_per_s: float
    p50_s: float
    p95_s: float
    min_s: float
    max_s: float
    loadavg_1m: float
    stop_reason: str | None = None
    error_samples: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Pure helpers (the part the tests drive)
# --------------------------------------------------------------------------- #


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile. Empty input is 0.0, not an exception.

    Nearest-rank rather than interpolated because ten samples per rung cannot
    support interpolation, and a p95 that is a real observation is easier to
    reconcile with the error log than one that is an average of two.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(q / 100.0 * len(ordered)) - 1))
    return ordered[index]


def summarize_rung(concurrency: int, calls: list[Call], wall_s: float, loadavg: float) -> Rung:
    """Fold a rung's calls into the row that goes in the report."""
    ok_calls = [c for c in calls if c.ok]
    latencies = [c.latency_s for c in ok_calls]
    tokens = sum(c.completion_tokens for c in ok_calls)
    per_call = [
        c.completion_tokens / c.latency_s
        for c in ok_calls
        if c.latency_s > 0 and c.completion_tokens
    ]
    failures = [c for c in calls if not c.ok]
    return Rung(
        concurrency=concurrency,
        calls=len(calls),
        wall_s=round(wall_s, 3),
        ok=len(ok_calls),
        errors=len(failures),
        completion_tokens=tokens,
        tokens_per_s=round(tokens / wall_s, 2) if wall_s > 0 else 0.0,
        per_call_tokens_per_s=round(sum(per_call) / len(per_call), 2) if per_call else 0.0,
        p50_s=round(percentile(latencies, 50), 3),
        p95_s=round(percentile(latencies, 95), 3),
        min_s=round(min(latencies), 3) if latencies else 0.0,
        max_s=round(max(latencies), 3) if latencies else 0.0,
        loadavg_1m=round(loadavg, 2),
        error_samples=[(c.body or c.error or "")[:400] for c in failures[:3]],
    )


def rung_stop_reason(rung: Rung, *, rung1_p50: float, cores: int) -> str | None:
    """Why the ladder must not climb past this rung, or None to continue.

    Three hard stops, in the order they matter. An error means the server is
    already refusing work, so a higher rung measures the refusal rather than the
    model. A p95 above four times the single-stream p50 means requests are
    queueing rather than sharing, which is the knee having been passed rather
    than approached. A load average above the core count means the box is
    saturated and every later number would describe contention.
    """
    if rung.errors:
        return f"{rung.errors}/{rung.calls} calls errored"
    if rung1_p50 > 0 and rung.p95_s > 4 * rung1_p50:
        return f"p95 {rung.p95_s}s exceeds 4x rung-1 p50 ({round(4 * rung1_p50, 3)}s)"
    if cores > 0 and rung.loadavg_1m > cores:
        return f"load average {rung.loadavg_1m} exceeds {cores} cores"
    return None


def find_knee(rungs: list[Rung]) -> int:
    """The concurrency to use downstream: the last rung that improved throughput.

    "Improved" is aggregate tokens/second rising by more than 5% over the best
    seen so far. A rung that merely matches the previous one is not a gain — it
    is the plateau — and the lower concurrency is preferred there because it
    leaves the box responsive for the same output.
    """
    usable = [r for r in rungs if r.ok == r.calls and r.ok > 0]
    if not usable:
        return 1
    best = usable[0]
    for rung in usable[1:]:
        if rung.tokens_per_s > best.tokens_per_s * 1.05:
            best = rung
    return best.concurrency


def bisect_ceiling(
    accepts: Callable[[int], tuple[bool, str | None]],
    *,
    start: int = 256,
    cap: int = DEFAULT_TOKEN_CAP,
) -> dict[str, Any]:
    """Find the largest accepted ``max_tokens`` by doubling then binary search.

    ``accepts(n)`` returns ``(accepted, refusal_body)``. The refusal body of the
    *first* rejection is what gets recorded: it is the server's own account of
    its limit, and it usually names the number this function is trying to infer.
    """
    if not accepts(start)[0]:
        _, body = accepts(start)
        return {
            "largest_accepted": None,
            "smallest_refused": start,
            "refusal_body": body,
            "note": f"the starting probe of {start} tokens was already refused",
        }

    low = start
    high: int | None = None
    refusal: str | None = None
    probe = start
    while probe < cap:
        probe = min(probe * 2, cap)
        accepted, body = accepts(probe)
        if accepted:
            low = probe
            if probe >= cap:
                break
        else:
            high = probe
            refusal = body
            break

    if high is None:
        return {
            "largest_accepted": low,
            "smallest_refused": None,
            "refusal_body": None,
            "note": f"no ceiling below the probe cap of {cap} tokens",
        }

    while high - low > 1:
        mid = (low + high) // 2
        accepted, body = accepts(mid)
        if accepted:
            low = mid
        else:
            high = mid
            refusal = body or refusal

    return {
        "largest_accepted": low,
        "smallest_refused": high,
        "refusal_body": refusal,
        "note": None,
    }


def identity_verdict(served: str | None, expect: str) -> dict[str, Any]:
    """Whether the weights that answered are the ones the experiment names."""
    passed = bool(served) and expect.lower() in (served or "").lower()
    return {
        "expected_substring": expect,
        "served_model": served,
        "passed": passed,
    }


# --------------------------------------------------------------------------- #
# Transport
# --------------------------------------------------------------------------- #


def post_chat(
    base_url: str,
    alias: str,
    prompt: str,
    *,
    max_tokens: int,
    timeout: float,
) -> Call:
    """One completion. Never raises; a failure is a `Call` carrying the body."""
    payload = {
        "model": alias,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        # The body is the point. Read it before the handle closes.
        try:
            text = exc.read().decode("utf-8", "replace")
        except Exception:  # pragma: no cover - defensive
            text = ""
        return Call(
            ok=False,
            latency_s=time.monotonic() - started,
            status=exc.code,
            error=f"HTTP {exc.code}",
            body=text,
        )
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return Call(
            ok=False,
            latency_s=time.monotonic() - started,
            error=f"{type(exc).__name__}: {exc}",
        )
    usage = body.get("usage") or {}
    return Call(
        ok=True,
        latency_s=time.monotonic() - started,
        completion_tokens=int(usage.get("completion_tokens") or 0),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        status=200,
        served_model=body.get("model"),
    )


def run_rung(call: Callable[[], Call], concurrency: int, calls: int) -> tuple[list[Call], float]:
    """Fire ``calls`` requests ``concurrency`` at a time; return them and the wall clock."""
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(lambda _: call(), range(calls)))
    return results, time.monotonic() - started


def _loadavg() -> float:
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError):  # pragma: no cover - not on Linux
        return 0.0


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--alias", default=DEFAULT_ALIAS)
    parser.add_argument(
        "--expect",
        default="minicpm",
        help="substring the served model id must contain (default: minicpm)",
    )
    parser.add_argument(
        "--allow-identity-mismatch",
        action="store_true",
        help="continue past a failed identity gate, recording the failure in the output. "
        "The numbers are then attributed to whatever actually answered.",
    )
    parser.add_argument("--rungs", default=",".join(str(r) for r in DEFAULT_RUNGS))
    parser.add_argument("--calls", type=int, default=DEFAULT_CALLS)
    parser.add_argument("--gen-tokens", type=int, default=512, help="max_tokens for ladder calls")
    parser.add_argument("--token-cap", type=int, default=DEFAULT_TOKEN_CAP)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument(
        "--slow-p50",
        type=float,
        default=20.0,
        help="abort if a single concurrent call's p50 exceeds this many seconds",
    )
    parser.add_argument("--skip-ceiling", action="store_true")
    parser.add_argument(
        "--out",
        default="docs/research/experiments/EXP-2026-09-019-small-model-generic/data/endpoint.json",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    report: dict[str, Any] = {
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "base_url": base_url,
        "alias": args.alias,
        "host": {"cores": os.cpu_count() or 0, "loadavg_1m_at_start": round(_loadavg(), 2)},
    }

    # -- 1. identity -------------------------------------------------------- #
    probe = post_chat(base_url, args.alias, "hi", max_tokens=2048, timeout=args.timeout)
    if not probe.ok:
        report["identity"] = {
            "expected_substring": args.expect,
            "served_model": None,
            "passed": False,
            "error": probe.error,
            "body": probe.body,
        }
        _write(args.out, report)
        print(f"FAIL: could not reach {args.alias} at {base_url}: {probe.error}", file=sys.stderr)
        return 2

    verdict = identity_verdict(probe.served_model, args.expect)
    report["identity"] = verdict
    print(f"alias {args.alias!r} at {base_url} is served by {probe.served_model!r}")
    if not verdict["passed"]:
        message = (
            f"identity gate FAILED: expected a model id containing {args.expect!r}, "
            f"got {probe.served_model!r}"
        )
        if not args.allow_identity_mismatch:
            _write(args.out, report)
            print(message, file=sys.stderr)
            print(
                "Load the intended weights, or rerun with --allow-identity-mismatch "
                "to measure the box as it stands.",
                file=sys.stderr,
            )
            return 3
        report["identity"]["overridden"] = True
        print(f"WARNING: {message} — continuing under --allow-identity-mismatch.")
        print("         Every number below describes "
              f"{probe.served_model!r}, not {args.expect!r}.")

    # -- 2. context ceiling ------------------------------------------------- #
    if args.skip_ceiling:
        report["context_ceiling"] = {"skipped": True}
    else:
        print("\nbisecting the max_tokens ceiling ...")
        seen: dict[int, tuple[bool, str | None]] = {}

        def accepts(n: int) -> tuple[bool, str | None]:
            if n not in seen:
                call = post_chat(
                    base_url, args.alias, CEILING_PROMPT, max_tokens=n, timeout=args.timeout
                )
                seen[n] = (call.ok, call.body or call.error)
                print(f"  max_tokens={n:<9} {'accepted' if call.ok else 'REFUSED'}")
            return seen[n]

        ceiling = bisect_ceiling(accepts, cap=args.token_cap)
        report["context_ceiling"] = ceiling
        if ceiling["largest_accepted"]:
            print(f"  largest accepted: {ceiling['largest_accepted']}")
        if ceiling["refusal_body"]:
            print(f"  server said, verbatim: {ceiling['refusal_body'][:300]}")

    # -- 3. concurrency ladder ---------------------------------------------- #
    rungs = [int(r) for r in args.rungs.split(",") if r.strip()]
    cores = os.cpu_count() or 0
    ladder: list[Rung] = []
    rung1_p50 = 0.0

    def ladder_call() -> Call:
        return post_chat(
            base_url, args.alias, LADDER_PROMPT, max_tokens=args.gen_tokens, timeout=args.timeout
        )

    print(f"\nconcurrency ladder ({args.calls} calls per rung):")
    header = f"  {'conc':>4}  {'ok':>5}  {'tok/s':>8}  {'tok/s/req':>9}  {'p50 s':>7}  {'p95 s':>7}  {'load':>5}"
    print(header)
    for index, concurrency in enumerate(rungs):
        calls, wall = run_rung(ladder_call, concurrency, args.calls)
        rung = summarize_rung(concurrency, calls, wall, _loadavg())
        if index == 0:
            rung1_p50 = rung.p50_s
        rung.stop_reason = rung_stop_reason(rung, rung1_p50=rung1_p50, cores=cores)
        ladder.append(rung)
        print(
            f"  {rung.concurrency:>4}  {rung.ok:>2}/{rung.calls:<2}  {rung.tokens_per_s:>8.1f}"
            f"  {rung.per_call_tokens_per_s:>9.1f}  {rung.p50_s:>7.2f}  {rung.p95_s:>7.2f}"
            f"  {rung.loadavg_1m:>5.1f}"
        )
        if rung.error_samples:
            print(f"        first error: {rung.error_samples[0][:200]}")

        # The single-stream gate, before any higher rung is allowed to run.
        if index == 0 and rung.p50_s > args.slow_p50:
            rung.stop_reason = (
                f"single-stream p50 {rung.p50_s}s exceeds --slow-p50 {args.slow_p50}s"
            )
            print(f"\nSTOP: {rung.stop_reason}")
            print("      This model is too slow for a full bank; recorded and stopping.")
            break
        if rung.stop_reason:
            print(f"\nSTOP after concurrency {concurrency}: {rung.stop_reason}")
            break

    report["ladder"] = [asdict(r) for r in ladder]
    knee = find_knee(ladder)
    report["chosen_concurrency"] = knee
    report["ladder_stopped_at"] = next(
        (r.concurrency for r in ladder if r.stop_reason), None
    )

    _write(args.out, report)
    print(f"\nchosen concurrency: {knee}")
    print(f"written: {args.out}")
    if not report["identity"]["passed"]:
        print(
            "\nNOTE: the identity gate did not pass. These numbers describe "
            f"{report['identity']['served_model']!r}."
        )
    return 0


def _write(path: str, report: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
