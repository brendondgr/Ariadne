"""Live-source health: turn graph-backend reachability into structured status.

``utils.graph_loader.main.run_graph_health`` raises ``ConnectionError`` as soon
as any backend is unreachable, which is the wrong shape for a polling endpoint —
the UI needs a per-backend verdict, not an all-or-nothing exception. This module
performs the same fast TCP reachability probe per backend (no driver, no
credentials, short timeout) and folds in Docker container state so a backend that
is booting can be reported as ``starting`` rather than ``down``.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass

from utils.graph_loader.config import LoaderConfig

# Endpoint fallbacks mirror utils.graph_loader.main.DEFAULT_ENDPOINTS.
_DEFAULT_ENDPOINTS: dict[str, tuple[str, int]] = {
    "neo4j": ("127.0.0.1", 5456),
    "gremlin": ("127.0.0.1", 6455),
}

# Probe timeout kept short so the polling endpoint stays responsive when a
# backend is down (a dead port blocks for the full timeout otherwise).
_PROBE_TIMEOUT_S = 2.0


@dataclass(frozen=True)
class SourceHealth:
    backend: str
    status: str  # "live" | "down" | "starting"
    uri: str
    reason: str | None = None


def _endpoint_from_uri(uri: str, fallback: tuple[str, int]) -> tuple[str, int]:
    """Extract (host, port) from a bolt:// or ws(s):// URI, else the fallback."""
    if uri.startswith("bolt://"):
        host_port = uri.removeprefix("bolt://").split("/", 1)[0]
        host, _, port = host_port.partition(":")
        return host or fallback[0], int(port or "7687")
    if uri.startswith(("ws://", "wss://")):
        host_port = uri.split("://", 1)[1].split("/", 1)[0]
        host, _, port = host_port.partition(":")
        return host or fallback[0], int(port or "8182")
    return fallback


def _tcp_reachable(host: str, port: int, timeout: float = _PROBE_TIMEOUT_S) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def docker_state() -> tuple[bool, dict[str, str], str | None]:
    """Best-effort Docker compose status.

    Returns ``(available, services, reason)``. ``available`` is ``False`` when
    Docker is not installed or the daemon is unreachable; callers must not assume
    container state in that case.
    """
    try:
        from utils.infrastructure import docker_status

        return True, docker_status(), None
    except FileNotFoundError:
        return False, {}, "docker executable not found"
    except Exception as exc:  # docker daemon down, compose error, etc.
        return False, {}, f"{type(exc).__name__}: {exc}"


def _is_starting(docker_available: bool, services: dict[str, str], backend: str) -> bool:
    """True when the container exists/runs but the endpoint is not accepting yet."""
    if not docker_available:
        return False
    state = services.get(backend, "").lower()
    return any(token in state for token in ("running", "starting", "created", "restarting"))


def live_sources(config: LoaderConfig | None = None) -> list[SourceHealth]:
    """Probe each graph backend and return a per-backend health verdict.

    Never raises: an unreachable backend is reported as ``down`` (or ``starting``
    when its Docker container is up but the port is not accepting yet).
    """
    config = config or LoaderConfig.from_data_dir()
    docker_available, services, _ = docker_state()

    probes = (
        ("neo4j", config.neo4j_uri),
        ("gremlin", config.gremlin_uri),
    )

    results: list[SourceHealth] = []
    for backend, uri in probes:
        host, port = _endpoint_from_uri(uri, _DEFAULT_ENDPOINTS[backend])
        if _tcp_reachable(host, port):
            results.append(SourceHealth(backend=backend, status="live", uri=uri))
        elif _is_starting(docker_available, services, backend):
            results.append(
                SourceHealth(
                    backend=backend,
                    status="starting",
                    uri=uri,
                    reason=f"container up; endpoint {host}:{port} not accepting yet",
                )
            )
        else:
            results.append(
                SourceHealth(
                    backend=backend,
                    status="down",
                    uri=uri,
                    reason=f"no TCP connection to {host}:{port}",
                )
            )
    return results
