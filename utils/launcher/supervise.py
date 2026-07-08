#!/usr/bin/env python3
"""Readiness-gated process supervision.

The old launcher declared the stack "started" the moment both processes were
spawned. This one earns the word: spawn the API → poll its ``/api/health``
until it answers → spawn the web app → poll its port until it serves → only
then report ready. On any child exiting, the child's last stderr lines are
shown instead of a bare "process exited".
"""

from __future__ import annotations

import collections
import http.client
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable

DEFAULT_READY_TIMEOUT_S = 90.0


@dataclass
class Child:
    """One supervised process and its retained output tail."""

    name: str
    proc: subprocess.Popen
    tail: collections.deque[str] = field(default_factory=lambda: collections.deque(maxlen=30))

    def remember(self, line: str) -> None:
        self.tail.append(line)


def api_health_ready(api_port: int, timeout_s: float = 2.0) -> bool:
    """One readiness probe: does GET /api/health answer at all?"""
    try:
        conn = http.client.HTTPConnection("127.0.0.1", api_port, timeout=timeout_s)
        conn.request("GET", "/api/health")
        response = conn.getresponse()
        response.read()
        return response.status < 500
    except OSError:
        return False
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def port_serving(port: int, timeout_s: float = 2.0) -> bool:
    """One readiness probe: does the port accept a TCP connection?"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_s)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_ready(
    child: Child,
    probe: Callable[[], bool],
    *,
    what: str,
    timeout_s: float = DEFAULT_READY_TIMEOUT_S,
    poll_interval_s: float = 0.5,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[bool, str]:
    """Poll ``probe`` until true, the child dies, or the timeout expires.

    Returns ``(ready, reason)``; ``reason`` names what went wrong when not
    ready. Injectable clock/sleep keep this hermetically testable.
    """
    deadline = clock() + timeout_s
    while clock() < deadline:
        code = child.proc.poll()
        if code is not None:
            tail = "\n".join(child.tail) or "(no output captured)"
            return False, (
                f"the {child.name} process exited with code {code} before {what} was ready.\n"
                f"Last output:\n{tail}"
            )
        if probe():
            return True, ""
        sleep(poll_interval_s)
    return False, f"{what} did not become ready within {timeout_s:.0f}s"


def terminate_all(children: list[Child], *, wait_s: float = 8.0) -> None:
    """Politely stop every still-running child, escalating to kill if needed."""
    for child in children:
        if child.proc.poll() is None:
            child.proc.terminate()
    for child in children:
        try:
            child.proc.wait(timeout=wait_s)
        except subprocess.TimeoutExpired:
            child.proc.kill()


def monitor(
    children: list[Child],
    *,
    poll_interval_s: float = 0.4,
    sleep: Callable[[float], None] = time.sleep,
    on_exit: Callable[[Child, int], None] | None = None,
) -> int:
    """Run until any child exits; report it and return its code."""
    while True:
        for child in children:
            code = child.proc.poll()
            if code is not None:
                if on_exit is not None:
                    on_exit(child, code)
                return code or 0
        sleep(poll_interval_s)
