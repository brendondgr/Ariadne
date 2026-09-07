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


# --------------------------------------------------------------------------- #
# unset_env_values — the inverse of set_env_values
# --------------------------------------------------------------------------- #


def test_unset_env_values_comments_the_assignment_and_clears_the_process(
    tmp_path, monkeypatch
):
    """Clearing keeps the old value legible instead of deleting the line.

    Deleting would lose both the value and the documentation comment above it;
    rewriting it with some other value would pin a moving target. Commenting is
    the only option that leaves the file self-explanatory.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Judge endpoint, second GPU.\nEVAL_LLM_MODEL=judge-model\nKEEP=me\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EVAL_LLM_MODEL", "judge-model")

    config.unset_env_values(["EVAL_LLM_MODEL"], env_file=env_file)

    body = env_file.read_text(encoding="utf-8")
    assert "# Judge endpoint, second GPU." in body, "documentation survives"
    assert "# unset by Ariadne: EVAL_LLM_MODEL=judge-model" in body
    assert "KEEP=me" in body, "unrelated keys are untouched"
    assert "EVAL_LLM_MODEL" not in os.environ


def test_unset_env_values_preserves_indentation(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("    INDENTED=1\n", encoding="utf-8")
    config.unset_env_values(["INDENTED"], env_file=env_file)
    assert env_file.read_text(encoding="utf-8").startswith("    # unset by Ariadne: ")


def test_unset_env_values_tolerates_a_missing_file(tmp_path, monkeypatch):
    """An operator who has never written a .env must not hit an exception."""
    monkeypatch.setenv("SOME_KEY", "value")
    config.unset_env_values(["SOME_KEY"], env_file=tmp_path / "absent.env")
    assert "SOME_KEY" not in os.environ


def test_set_then_unset_then_set_again(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("A=1\n", encoding="utf-8")
    config.set_env_values({"A": "2"}, env_file=env_file)
    assert os.environ["A"] == "2"
    config.unset_env_values(["A"], env_file=env_file)
    assert "A" not in os.environ
    config.set_env_values({"A": "3"}, env_file=env_file)
    assert os.environ["A"] == "3"
    assert "A=3" in env_file.read_text(encoding="utf-8")
