from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import time
from pathlib import Path

from utils.config import ENV_FILE as ROOT_ENV_FILE
from utils.config import env_int

logger = logging.getLogger(__name__)

DOCKER_DIR = Path(__file__).resolve().parents[2] / "docker"
COMPOSE_FILE = DOCKER_DIR / "docker-compose.yml"
ENV_FILE = DOCKER_DIR / ".env"  # committed fallback base layer for compose

# Host ports the local stack is published on (central .env, section 4).
NEO4J_HTTP_PORT = env_int("NEO4J_HTTP_PORT", 5455)
NEO4J_BOLT_PORT = env_int("NEO4J_BOLT_PORT", 5456)
GREMLIN_PORT = env_int("GREMLIN_PORT", 6455)

SERVICE_LABELS = {
    "neo4j": "Neo4j",
    "gremlin": "Gremlin",
}

SERVICE_CONTAINERS = {
    "neo4j": "ariadne-neo4j",
    "gremlin": "ariadne-gremlin",
}

SERVICE_ENDPOINTS = {
    "neo4j": ("127.0.0.1", NEO4J_BOLT_PORT),
    "gremlin": ("127.0.0.1", GREMLIN_PORT),
}

DEFAULT_START_TIMEOUT_SECONDS = env_int("ARIADNE_DOCKER_START_TIMEOUT", 180)


def _compose_env(
    *,
    neo4j_version: str | None = None,
    gremlin_version: str | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    if neo4j_version:
        env["NEO4J_VERSION"] = neo4j_version
    if gremlin_version:
        env["GREMLIN_VERSION"] = gremlin_version
    return env


def _run_compose(
    *args: str,
    check: bool = True,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    # Layer env files: docker/.env (committed base) then the root .env
    # (central source of truth) so root values override the base.
    env_file_args: list[str] = []
    for env_file in (ENV_FILE, ROOT_ENV_FILE):
        if env_file.exists():
            env_file_args.extend(["--env-file", str(env_file)])

    command = [
        "docker",
        "compose",
        "-f",
        str(COMPOSE_FILE),
        "--project-directory",
        str(DOCKER_DIR),
        *env_file_args,
        *args,
    ]
    logger.debug("Running command: %s", " ".join(command))
    return subprocess.run(
        command,
        check=check,
        capture_output=capture_output,
        text=True,
        env=env,
    )


def _service_states() -> dict[str, str]:
    result = _run_compose("ps", "--format", "json", capture_output=True)
    states: dict[str, str] = {name: "Not running" for name in SERVICE_LABELS}

    if not result.stdout.strip():
        return states

    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        service = entry.get("Service", "")
        if service not in states:
            continue

        state = entry.get("State", "unknown")
        health = entry.get("Health", "")
        container_name = entry.get("Name", SERVICE_CONTAINERS.get(service, service))

        if state.lower() != "running":
            states[service] = f"{state.capitalize()} ({container_name})"
            continue

        if health:
            states[service] = f"{health.capitalize()} ({container_name})"
        else:
            states[service] = f"Running ({container_name})"

    return states


def _tcp_endpoint_ready(host: str, port: int, timeout_seconds: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _service_ready(service: str, compose_state: str) -> bool:
    if compose_state.lower() != "running":
        return False

    host, port = SERVICE_ENDPOINTS[service]
    return _tcp_endpoint_ready(host, port)


def _compose_running_states() -> dict[str, str]:
    result = _run_compose("ps", "--format", "json", capture_output=True)
    states: dict[str, str] = {name: "not running" for name in SERVICE_LABELS}

    if not result.stdout.strip():
        return states

    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        service = entry.get("Service", "")
        if service in states:
            states[service] = entry.get("State", "unknown").lower()

    return states


def _wait_for_services(timeout_seconds: int = DEFAULT_START_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout_seconds
    logger.info(
        "Waiting for compose services %s (containers: %s) to become ready...",
        ", ".join(SERVICE_LABELS[service] for service in SERVICE_LABELS),
        ", ".join(SERVICE_CONTAINERS[service] for service in SERVICE_LABELS),
    )

    while time.monotonic() < deadline:
        compose_states = _compose_running_states()
        if all(
            _service_ready(service, compose_states[service])
            for service in SERVICE_LABELS
        ):
            for service, label in SERVICE_LABELS.items():
                host, port = SERVICE_ENDPOINTS[service]
                logger.info(
                    "%s is ready via tcp://%s:%s (%s)",
                    label,
                    host,
                    port,
                    SERVICE_CONTAINERS[service],
                )
            return

        time.sleep(2)

    states = _service_states()
    details = ", ".join(
        f"{SERVICE_LABELS[service]}={states[service]}" for service in SERVICE_LABELS
    )
    raise TimeoutError(
        f"Timed out after {timeout_seconds}s waiting for Docker services ({details})."
    )


def docker_start(
    *,
    neo4j_version: str | None = None,
    gremlin_version: str | None = None,
    timeout_seconds: int = DEFAULT_START_TIMEOUT_SECONDS,
) -> None:
    """Pull pinned images, start containers, and wait until endpoints respond."""
    env = _compose_env(neo4j_version=neo4j_version, gremlin_version=gremlin_version)

    if not ENV_FILE.exists():
        raise FileNotFoundError(f"Missing Docker env file: {ENV_FILE}")

    logger.info("Pulling Docker images from %s", COMPOSE_FILE)
    _run_compose("pull", env=env)

    logger.info(
        "Starting containers %s",
        " and ".join(SERVICE_CONTAINERS.values()),
    )
    _run_compose("up", "-d", env=env)

    _wait_for_services(timeout_seconds=timeout_seconds)

    logger.info("Graph infrastructure is running:")
    logger.info("  Neo4j Browser -> http://localhost:%s", NEO4J_HTTP_PORT)
    logger.info("  Neo4j Bolt    -> bolt://localhost:%s", NEO4J_BOLT_PORT)
    logger.info("  Gremlin       -> http://localhost:%s", GREMLIN_PORT)


def docker_stop() -> None:
    """Stop and remove compose-managed containers."""
    logger.info("Stopping graph infrastructure containers")
    _run_compose("down")


def docker_stop_service(service: str) -> None:
    """Stop one or all compose-managed graph services without removing them.

    Args:
        service: ``"neo4j"``, ``"gremlin"``, or ``"all"``.
    """
    if service == "all":
        logger.info("Stopping all graph services")
        for svc, label in SERVICE_LABELS.items():
            logger.info("  Stopping %s (%s)", label, SERVICE_CONTAINERS[svc])
        _run_compose("stop", *SERVICE_LABELS.keys())
    elif service in SERVICE_LABELS:
        label = SERVICE_LABELS[service]
        container = SERVICE_CONTAINERS[service]
        logger.info("Stopping %s (%s)", label, container)
        _run_compose("stop", service)
    else:
        raise ValueError(
            f"Unknown graph service {service!r}. "
            f"Choose from: {', '.join(sorted(SERVICE_LABELS))} or 'all'."
        )


def docker_status() -> dict[str, str]:
    """Return human-readable status for managed services."""
    states = _service_states()
    for service, label in SERVICE_LABELS.items():
        logger.info("%-8s %s", label, states[service])
    return states
