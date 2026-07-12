#!/usr/bin/env python3
"""Ariadne one-shot setup — run ``python3 setup.py`` on a fresh clone.

NOT a setuptools packaging script: this project builds with hatchling (see
``pyproject.toml``); this file is an interactive bootstrap wizard. It walks a
fresh clone all the way to a running analyst workbench:

    python3 setup.py            # interactive — inspect and confirm each step
    python3 setup.py --yes      # non-interactive, all defaults
    python3 setup.py --no-launch  # set everything up, print the launch command

Stage 1 (this file) is pure stdlib so it works before any environment
exists: it finds ``uv`` (offering the official installer if missing), runs
``uv sync``, then re-execs stage 2 (``utils/setup_wizard``) inside the
project environment. Stage 2 handles prerequisites, ``.env``, the full data
pipeline, web dependencies, and launching ``app.py``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UV_INSTALL_CMD = "curl -LsSf https://astral.sh/uv/install.sh | sh"


def _has_flag(argv: list[str], *names: str) -> bool:
    return any(name in argv for name in names)


def _find_uv() -> str | None:
    uv = shutil.which("uv")
    if uv:
        return uv
    # The official installer's default target, for a just-installed uv that
    # is not on PATH yet in this shell.
    candidate = Path.home() / ".local" / "bin" / "uv"
    return str(candidate) if candidate.is_file() else None


def _ensure_uv(assume_yes: bool) -> str | None:
    uv = _find_uv()
    if uv:
        return uv

    print("  ✗ `uv` (the Python environment manager this project uses) is not installed.")
    print(f"    Install it with:  {UV_INSTALL_CMD}")
    print("    (or see https://docs.astral.sh/uv/getting-started/installation/)")
    if assume_yes:
        return None

    answer = input("  Run that installer now? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        return None
    code = subprocess.run(["sh", "-c", UV_INSTALL_CMD]).returncode
    if code != 0:
        print(f"  ✗ The uv installer exited with code {code}.")
        return None
    return _find_uv()


def _run_sync(uv: str, assume_yes: bool) -> bool:
    while True:
        print("  → uv sync — creating the project environment and installing dependencies …",
              flush=True)
        code = subprocess.run([uv, "sync"], cwd=ROOT).returncode
        if code == 0:
            print("  ✓ Python environment ready (.venv)")
            return True
        print(f"  ✗ `uv sync` failed (exit {code}).")
        if assume_yes:
            return False
        answer = input("  Retry? [Y/n] ").strip().lower()
        if answer in ("n", "no"):
            return False


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    assume_yes = _has_flag(argv, "--yes", "-y")
    skip_sync = _has_flag(argv, "--skip-sync")

    print("\n  Ariadne setup — stage 1 (environment bootstrap)\n")

    uv = _ensure_uv(assume_yes)
    if not uv:
        print("  Install uv, then re-run `python3 setup.py`.")
        return 1

    if skip_sync:
        os.environ["ARIADNE_SETUP_SYNC"] = "skipped"
    else:
        if not _run_sync(uv, assume_yes):
            return 1
        os.environ["ARIADNE_SETUP_SYNC"] = "ok"

    # Hand off to stage 2 inside the project env. The guard variable keeps any
    # accidental nested invocation of setup.py from bootstrapping twice.
    os.environ["ARIADNE_SETUP_REEXEC"] = "1"
    stage2 = [uv, "run", "python", "-m", "utils.setup_wizard", *argv]
    os.execvp(stage2[0], stage2)
    return 1  # unreachable


if __name__ == "__main__":
    sys.exit(main())
