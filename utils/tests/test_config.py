#!/usr/bin/env python3
"""Tests for the central .env configuration loader (utils/config.py)."""

from __future__ import annotations

import os

import pytest

from utils import config


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep each test's env mutations local and reset the load guard."""
    monkeypatch.setattr(config, "_loaded", False)


def test_load_env_reads_values_from_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ARIADNE_TEST_KEY=from_file\n", encoding="utf-8")
    monkeypatch.delenv("ARIADNE_TEST_KEY", raising=False)

    loaded = config.load_env(env_file)

    assert loaded == env_file
    assert os.environ["ARIADNE_TEST_KEY"] == "from_file"


def test_load_env_does_not_override_real_env_by_default(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ARIADNE_TEST_KEY=from_file\n", encoding="utf-8")
    monkeypatch.setenv("ARIADNE_TEST_KEY", "from_shell")

    config.load_env(env_file)

    assert os.environ["ARIADNE_TEST_KEY"] == "from_shell"


def test_load_env_override_true_replaces_real_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ARIADNE_TEST_KEY=from_file\n", encoding="utf-8")
    monkeypatch.setenv("ARIADNE_TEST_KEY", "from_shell")

    config.load_env(env_file, override=True)

    assert os.environ["ARIADNE_TEST_KEY"] == "from_file"


def test_load_env_missing_file_returns_none(tmp_path):
    missing = tmp_path / "does-not-exist.env"
    assert config.load_env(missing) is None


def test_env_str_falls_back_when_unset(monkeypatch):
    monkeypatch.delenv("ARIADNE_TEST_KEY", raising=False)
    assert config.env_str("ARIADNE_TEST_KEY", "fallback") == "fallback"


def test_env_str_falls_back_when_empty(monkeypatch):
    monkeypatch.setenv("ARIADNE_TEST_KEY", "")
    assert config.env_str("ARIADNE_TEST_KEY", "fallback") == "fallback"


def test_env_int_parses_and_falls_back(monkeypatch):
    monkeypatch.setenv("ARIADNE_TEST_KEY", "42")
    assert config.env_int("ARIADNE_TEST_KEY", 7) == 42

    monkeypatch.setenv("ARIADNE_TEST_KEY", "not-a-number")
    assert config.env_int("ARIADNE_TEST_KEY", 7) == 7


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", True), ("true", True), ("YES", True), ("on", True),
     ("0", False), ("false", False), ("no", False), ("off", False)],
)
def test_env_bool_parses_common_spellings(monkeypatch, raw, expected):
    monkeypatch.setenv("ARIADNE_TEST_KEY", raw)
    assert config.env_bool("ARIADNE_TEST_KEY", not expected) is expected


def test_data_dir_default(monkeypatch):
    monkeypatch.delenv("ARIADNE_DATA_DIR", raising=False)
    assert config.data_dir() == "data"

    monkeypatch.setenv("ARIADNE_DATA_DIR", "/tmp/ariadne-data")
    assert config.data_dir() == "/tmp/ariadne-data"
