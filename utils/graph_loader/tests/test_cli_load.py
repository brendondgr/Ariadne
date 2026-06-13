#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from utils.graph_loader.main import run_graph_command


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


def test_cli_attack_neo4j_load_with_memory_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    if not Path("data/graphs/attack/canonical/manifest.json").exists():
        pytest.skip("ATT&CK artifacts not built")

    from utils.graph_loader.stores.memory import MemoryGraphStore

    monkeypatch.setattr(
        "utils.graph_loader.loader.run_preflight",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "utils.graph_loader.loader.create_graph_store",
        lambda *_a, **_k: MemoryGraphStore(backend="neo4j"),
    )
    run_graph_command(dataset="attack", graph="neo4j")


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
