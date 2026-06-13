from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

DOCKER_DIR = Path(__file__).resolve().parents[2] / "docker"
COMPOSE_FILE = DOCKER_DIR / "docker-compose.yml"
ENV_FILE = DOCKER_DIR / ".env"

SERVICE_LABELS = {
    "neo4j": "Neo4j",
    "gremlin": "Gremlin",
}

SERVICE_ENDPOINTS = {
    "neo4j": "http://127.0.0.1:5455",
    "gremlin": "http://127.0.0.1:6455",
}

DEFAULT_START_TIMEOUT_SECONDS = 180


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
    command = [
        "docker",
        "compose",
        "-f",
        str(COMPOSE_FILE),
        "--project-directory",
        str(DOCKER_DIR),
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
        if state.lower() == "running":
            if health:
                states[service] = health.capitalize()
            else:
                states[service] = "Running"
        else:
            states[service] = state.capitalize()

    return states


def _endpoint_ready(url: str, timeout_seconds: float = 3.0) -> bool:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return 200 <= response.status < 500
    except urllib.error.HTTPError as exc:
        return 200 <= exc.code < 500
    except (urllib.error.URLError, TimeoutError):
        return False


def _wait_for_services(timeout_seconds: int = DEFAULT_START_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout_seconds
    logger.info("Waiting for graph infrastructure to become ready...")

    while time.monotonic() < deadline:
        states = _service_states()
        running = {
            service: state
            for service, state in states.items()
            if state.lower() in {"running", "healthy"}
        }

        if len(running) == len(SERVICE_LABELS):
            endpoints_ready = all(
                _endpoint_ready(SERVICE_ENDPOINTS[service]) for service in SERVICE_LABELS
            )
            if endpoints_ready:
                for service, label in SERVICE_LABELS.items():
                    logger.info("%s is ready (%s)", label, SERVICE_ENDPOINTS[service])
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

    logger.info("Starting Neo4j and Gremlin containers")
    _run_compose("up", "-d", env=env)

    _wait_for_services(timeout_seconds=timeout_seconds)

    logger.info("Graph infrastructure is running:")
    logger.info("  Neo4j Browser -> http://localhost:5455")
    logger.info("  Neo4j Bolt    -> bolt://localhost:5456")
    logger.info("  Gremlin       -> http://localhost:6455")


def docker_stop() -> None:
    """Stop and remove compose-managed containers."""
    logger.info("Stopping graph infrastructure containers")
    _run_compose("down")


def docker_status() -> dict[str, str]:
    """Return human-readable status for managed services."""
    states = _service_states()
    for service, label in SERVICE_LABELS.items():
        logger.info("%-8s %s", label, states[service])
    return states
