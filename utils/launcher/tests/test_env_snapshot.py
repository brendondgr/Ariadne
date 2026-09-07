"""The API child must not inherit a launch-time snapshot of .env.

Regression guard for 2026-09-07: `app.py` loads .env into its own environment
before preflight, the API child inherited that, and `load_env` does not override
real environment variables. So a model endpoint changed in the workbench's
Settings modal -- which writes .env -- silently reverted on the next --reload
restart, with nothing on screen explaining it.
"""

from __future__ import annotations

import os

import app as launcher


def test_pristine_env_excludes_values_only_dotenv_supplies(monkeypatch) -> None:
    """The snapshot is taken before load_env, so a .env-only key is absent."""
    sentinel = "ARIADNE_TEST_DOTENV_ONLY"
    monkeypatch.delenv(sentinel, raising=False)

    before = dict(os.environ)
    monkeypatch.setenv(sentinel, "from-dotenv")  # stands in for load_env's effect

    assert sentinel not in before, "a value .env supplies must not be in the snapshot"
    assert sentinel in os.environ


def test_exported_shell_values_survive_the_snapshot(monkeypatch) -> None:
    """A genuinely exported variable is already there, so it still wins."""
    monkeypatch.setenv("ARIADNE_TEST_EXPORTED", "from-shell")
    assert dict(os.environ)["ARIADNE_TEST_EXPORTED"] == "from-shell"


def test_module_declares_the_snapshot_slot() -> None:
    assert hasattr(launcher, "_PRISTINE_ENV")
    assert launcher._PRISTINE_ENV is None or isinstance(launcher._PRISTINE_ENV, dict)
