"""Live-source health: turn graph-backend reachability into structured status.

``utils.graph_loader.main.run_graph_health`` raises ``ConnectionError`` as soon
as any backend is unreachable, which is the wrong shape for a polling endpoint —
the UI needs a per-backend verdict, not an all-or-nothing exception.

A bare TCP probe is not enough: a container can accept connections while its graph
is empty or its credentials are wrong, which would falsely read as *live*. So this
module combines two signals — a fast TCP reachability probe (to tell ``down`` from
``starting`` via Docker state) and the planner's **content** probe (node counts +
expected labels, the same verdict the real query pipeline trusts). A backend is
only ``live`` when its port is reachable *and* its graph is actually loaded;
otherwise it is ``down`` with the reason (empty graph, auth failure, …). The
content probe carries a short TTL cache, reused here so the 5s UI poll does not
hammer the backends. Any failure to run the content probe degrades gracefully to
the TCP verdict — this module never raises.
"""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from utils.graph_loader.config import LoaderConfig
from utils.synthesis.config import SynthesisConfig

logger = logging.getLogger("ariadne.api.health")

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
    nodes: int | None = None


@dataclass(frozen=True)
class LlmHealth:
    """Reachability verdict for the synthesis LLM endpoint (the drafter LLM).

    ``status`` is ``live`` when the configured OpenAI-compatible endpoint's
    host:port accepts a TCP connection, ``down`` otherwise — the same fast,
    never-raising probe the graph backends use. ``enabled`` reflects whether the
    LLM is turned on in config; ``live``/``down`` is about reachability so the
    header pill tells the analyst the truth regardless of the toggle.
    """

    status: str  # "live" | "down"
    base_url: str
    model: str
    enabled: bool
    reason: str | None = None


def _http_host_port(url: str) -> tuple[str, int] | None:
    """Extract (host, port) from an http(s) base URL, defaulting the port."""
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.hostname, port


def llm_health(config: SynthesisConfig | None = None) -> LlmHealth:
    """Probe the synthesis LLM endpoint's reachability. Never raises.

    A live endpoint means an analyst who selects the LLM drafter will actually
    reach a model; a down endpoint means the pipeline would fall back to the
    deterministic composer. Reachability is a fast TCP probe of the base URL's
    host:port (mirrors the graph health check).
    """
    config = config or SynthesisConfig.from_env()
    hostport = _http_host_port(config.llm_base_url)
    if hostport is None:
        return LlmHealth(
            status="down",
            base_url=config.llm_base_url,
            model=config.llm_model,
            enabled=config.llm_enabled,
            reason=f"unparseable LLM base_url: {config.llm_base_url!r}",
        )
    host, port = hostport
    if _tcp_reachable(host, port):
        return LlmHealth(
            status="live",
            base_url=config.llm_base_url,
            model=config.llm_model,
            enabled=config.llm_enabled,
        )
    return LlmHealth(
        status="down",
        base_url=config.llm_base_url,
        model=config.llm_model,
        enabled=config.llm_enabled,
        reason=f"no TCP connection to {host}:{port}",
    )


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


@dataclass(frozen=True)
class _ContentVerdict:
    """Per-backend graph-loaded verdict distilled from the planner content probe."""

    loaded: bool
    nodes: int
    reason: str | None


# One planner agent is reused across polls so its short-TTL probe cache absorbs the
# 5s UI refresh instead of reconnecting to both graphs every time. Built lazily and
# rebuilt only if construction fails (bad config, missing cards, …).
_content_agent = None  # type: ignore[var-annotated]


def _content_verdicts() -> dict[str, _ContentVerdict] | None:
    """Return {backend: verdict} from the planner content probe, or None on failure.

    The probe checks node counts and expected labels — the same "is the graph
    actually loaded" test the query pipeline uses — so a reachable-but-empty or
    unauthorized backend is reported as not loaded. Never raises; on any error it
    returns ``None`` and the caller degrades to the bare TCP verdict.
    """
    global _content_agent
    try:
        if _content_agent is None:
            from utils.planner.agent import PlanningAgent

            _content_agent = PlanningAgent()
        view = _content_agent.live_sources()
    except Exception as exc:  # noqa: BLE001 - health must never raise; degrade to TCP
        logger.info("content probe unavailable; falling back to TCP verdict: %s", exc)
        _content_agent = None  # force a rebuild next call in case config changed
        return None

    verdicts: dict[str, _ContentVerdict] = {}
    for src in view.sources.values():
        prior = verdicts.get(src.backend)
        # A backend is loaded if any of its datasets is; keep the richest node count.
        loaded = bool(src.live) or (prior.loaded if prior else False)
        nodes = max(int(src.node_count), prior.nodes if prior else 0)
        reason = None if loaded else (src.reason or (prior.reason if prior else None))
        verdicts[src.backend] = _ContentVerdict(loaded=loaded, nodes=nodes, reason=reason)
    return verdicts


def live_sources(config: LoaderConfig | None = None) -> list[SourceHealth]:
    """Probe each graph backend and return a per-backend health verdict.

    A backend is ``live`` only when its port is reachable *and* its graph is
    actually loaded (the planner content probe confirms node counts / labels).
    Reachable but empty/unauthorized reads as ``down`` with the reason; a booting
    container reads as ``starting``. Never raises.
    """
    config = config or LoaderConfig.from_data_dir()
    docker_available, services, _ = docker_state()
    verdicts = _content_verdicts()

    probes = (
        ("neo4j", config.neo4j_uri),
        ("gremlin", config.gremlin_uri),
    )

    results: list[SourceHealth] = []
    for backend, uri in probes:
        host, port = _endpoint_from_uri(uri, _DEFAULT_ENDPOINTS[backend])
        if not _tcp_reachable(host, port):
            if _is_starting(docker_available, services, backend):
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
            continue

        # Port is reachable — the graph must also be loaded to count as live.
        verdict = verdicts.get(backend) if verdicts is not None else None
        if verdict is None:
            # Content probe unavailable: trust reachability alone (legacy behaviour).
            results.append(SourceHealth(backend=backend, status="live", uri=uri))
        elif verdict.loaded:
            results.append(
                SourceHealth(backend=backend, status="live", uri=uri, nodes=verdict.nodes)
            )
        else:
            results.append(
                SourceHealth(
                    backend=backend,
                    status="down",
                    uri=uri,
                    reason=verdict.reason or "backend reachable but graph not loaded",
                    nodes=verdict.nodes,
                )
            )
    return results
