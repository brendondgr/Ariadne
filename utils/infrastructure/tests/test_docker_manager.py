#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.infrastructure import docker_manager


def test_compose_paths_point_at_docker_directory() -> None:
    assert docker_manager.DOCKER_DIR.name == "docker"
    assert docker_manager.COMPOSE_FILE.name == "docker-compose.yml"
    assert docker_manager.ENV_FILE.name == ".env"


def test_service_states_maps_running_containers() -> None:
    payload = [
        {
            "Service": "neo4j",
            "State": "running",
            "Health": "healthy",
            "Name": "ariadne-neo4j",
        },
        {
            "Service": "gremlin",
            "State": "running",
            "Health": "unhealthy",
            "Name": "ariadne-gremlin",
        },
    ]
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="\n".join(json.dumps(entry) for entry in payload),
        stderr="",
    )

    with patch.object(docker_manager, "_run_compose", return_value=completed):
        states = docker_manager._service_states()

    assert states == {
        "neo4j": "Healthy (ariadne-neo4j)",
        "gremlin": "Unhealthy (ariadne-gremlin)",
    }


def test_service_ready_uses_tcp_for_gremlin() -> None:
    with (
        patch.object(docker_manager, "_http_endpoint_ready", return_value=True) as http_ready,
        patch.object(docker_manager, "_tcp_endpoint_ready", return_value=True) as tcp_ready,
    ):
        assert docker_manager._service_ready("neo4j", "running") is True
        assert docker_manager._service_ready("gremlin", "running") is True

    http_ready.assert_called_once()
    tcp_ready.assert_called_once()


def test_docker_start_pulls_up_and_waits() -> None:
    with (
        patch.object(docker_manager, "_run_compose") as run_compose,
        patch.object(docker_manager, "_wait_for_services") as wait_for_services,
    ):
        docker_manager.docker_start(neo4j_version="5.26", gremlin_version="3.8.0")

    assert run_compose.call_count == 2
    pull_call = run_compose.call_args_list[0]
    up_call = run_compose.call_args_list[1]

    assert pull_call.args == ("pull",)
    assert up_call.args == ("up", "-d")
    assert pull_call.kwargs["env"]["NEO4J_VERSION"] == "5.26"
    assert pull_call.kwargs["env"]["GREMLIN_VERSION"] == "3.8.0"
    wait_for_services.assert_called_once()


def test_docker_stop_runs_compose_down() -> None:
    with patch.object(docker_manager, "_run_compose") as run_compose:
        docker_manager.docker_stop()

    run_compose.assert_called_once_with("down")


def test_cli_help_shows_docker_choices() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--docker {start,stop,status}" in result.stdout
    assert "--neo4j-version NEO4J_VERSION" in result.stdout
    assert "--gremlin-version GREMLIN_VERSION" in result.stdout


@pytest.mark.skipif(
    subprocess.run(["docker", "info"], capture_output=True).returncode != 0,
    reason="Docker is not available",
)
def test_docker_compose_file_is_valid() -> None:
    compose_file = Path("docker/docker-compose.yml")
    assert compose_file.exists()

    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "--project-directory",
            "docker",
            "config",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
