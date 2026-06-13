#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_cli_help_shows_build_choices() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--build {attack,capec,all}" in result.stdout


@pytest.mark.skipif(
    not Path("data/raw/attack/v19.0/enterprise-attack.json").exists(),
    reason="Real ATT&CK dataset not downloaded",
)
def test_cli_build_all() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--build", "all"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Skipping CAPEC build" in result.stdout
    assert Path("data/graphs/attack/canonical/manifest.json").exists()
