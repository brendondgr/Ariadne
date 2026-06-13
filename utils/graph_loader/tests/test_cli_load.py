#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from utils.graph_loader.main import GraphLoaderNotReadyError, run_graph_command


def test_cli_help_shows_dataset_and_graph() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--dataset" in result.stdout
    assert "--graph" in result.stdout
    assert "health" in result.stdout
    assert "verify" in result.stdout


def test_cli_missing_dataset_for_load() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--graph", "neo4j"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "--dataset is required" in result.stderr or "--dataset is required" in result.stdout


def test_cli_capec_not_built() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--dataset", "capec", "--graph", "neo4j"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "CAPEC canonical artifacts are not built yet" in combined


@pytest.mark.skipif(
    not Path("data/graphs/attack/canonical/manifest.json").exists(),
    reason="ATT&CK artifacts not built",
)
def test_cli_attack_neo4j_resolves_before_load_stub() -> None:
    with pytest.raises(GraphLoaderNotReadyError):
        run_graph_command(dataset="attack", graph="neo4j")


@pytest.mark.skipif(
    not Path("data/graphs/attack/canonical/manifest.json").exists(),
    reason="ATT&CK artifacts not built",
)
def test_cli_attack_verify_resolves_before_verify_stub() -> None:
    with pytest.raises(GraphLoaderNotReadyError):
        run_graph_command(dataset="attack", graph="verify")


def test_cli_graph_health_checks_backends() -> None:
    """Health succeeds when Docker graph services are reachable (may be running locally)."""
    result = subprocess.run(
        [sys.executable, "main.py", "--graph", "health"],
        capture_output=True,
        text=True,
    )
    combined = result.stdout + result.stderr
    assert "Graph backend neo4j is" in combined
    assert "Graph backend gremlin is" in combined


def test_graph_health_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.graph_loader import main as graph_main

    monkeypatch.setattr(graph_main, "_tcp_reachable", lambda *_a, **_k: False)
    with pytest.raises(ConnectionError, match="unreachable"):
        run_graph_command(dataset=None, graph="health")


def test_run_graph_command_requires_graph() -> None:
    with pytest.raises(ValueError, match="--graph is required"):
        run_graph_command(dataset="attack", graph=None)


def test_run_graph_command_requires_dataset_for_load() -> None:
    with pytest.raises(ValueError, match="--dataset is required"):
        run_graph_command(dataset=None, graph="neo4j")
