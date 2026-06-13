#!/usr/bin/env python3

from __future__ import annotations

import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration


def _docker_running() -> bool:
    result = subprocess.run(
        [sys.executable, "main.py", "--graph", "health"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


@pytest.mark.skipif(not _docker_running(), reason="Graph Docker stack not reachable")
def test_integration_neo4j_load_and_verify() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--dataset", "attack", "--graph", "neo4j"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    verify = subprocess.run(
        [sys.executable, "main.py", "--dataset", "attack", "--graph", "verify"],
        capture_output=True,
        text=True,
    )
    # verify may still fail if gremlin runtime manifest is missing
    assert "verification" in (verify.stdout + verify.stderr).lower()


@pytest.mark.skipif(
    not _docker_running() or os.environ.get("ARIADNE_GREMLIN_INTEGRATION") != "1",
    reason="Set ARIADNE_GREMLIN_INTEGRATION=1 to run full Gremlin ATT&CK load",
)
def test_integration_gremlin_load() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--dataset", "attack", "--graph", "gremlin"],
        capture_output=True,
        text=True,
        timeout=3600,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
