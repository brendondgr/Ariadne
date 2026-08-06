#!/usr/bin/env python3
"""Regenerate every figure from its committed generator. See `make figures`.

Discovers generators rather than listing them, so a new experiment's figures are
picked up without editing this script:

  docs/research/experiments/*/figures/make_figures.py   per-experiment figures
  docs/research/figures/sources/make_*.py               promoted figures

With --check, regenerates into a scratch copy and fails if anything differs from
what is committed. That is the form CI uses: if a generator no longer reproduces
its figure, the figure is stale and must not reach the paper.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.research_record.paths import (  # noqa: E402
    EXPERIMENTS_ROOT,
    FIGURES_ROOT,
    REPO_ROOT,
)


TABLES_ROOT = FIGURES_ROOT.parent / "tables"


def generators() -> list[Path]:
    """Every committed generator, discovered rather than listed.

    A new experiment's figures are picked up without editing this script.
    """
    found = sorted(EXPERIMENTS_ROOT.glob("EXP-*/figures/make_figures.py"))
    found += sorted((FIGURES_ROOT / "sources").glob("make_*.py"))
    found += sorted((TABLES_ROOT / "sources").glob("make_*.py"))
    return found


def _run(script: Path) -> bool:
    result = subprocess.run(
        [sys.executable, str(script)], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  FAILED {script.relative_to(REPO_ROOT)}", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return False
    return True


#: Artifact types a generator is responsible for producing.
_ARTIFACT_SUFFIXES = {".svg", ".pdf", ".png", ".tex"}


def _output_dir(script: Path) -> Path:
    """Where a generator writes.

    A generator under ``sources/`` writes to its parent (``figures/``,
    ``tables/``); a per-experiment ``make_figures.py`` writes beside itself.
    """
    return script.parent.parent if script.parent.name == "sources" else script.parent


def _artifacts(script: Path) -> list[Path]:
    out_dir = _output_dir(script)
    if not out_dir.is_dir():
        return []
    return sorted(
        p for p in out_dir.iterdir() if p.is_file() and p.suffix in _ARTIFACT_SUFFIXES
    )


def _generated_markdown(script: Path) -> list[Path]:
    """Generated .md tables carry a DO-NOT-EDIT banner; treat those as artifacts too."""
    out_dir = _output_dir(script)
    if not out_dir.is_dir():
        return []
    return sorted(
        p for p in out_dir.glob("*.md")
        if p.is_file() and "GENERATED" in p.read_text()[:200]
    )


def _figure_files(script: Path) -> list[Path]:
    return [*_artifacts(script), *_generated_markdown(script)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if a regenerated figure differs from the committed one",
    )
    args = parser.parse_args()

    scripts = generators()
    if not scripts:
        print("no figure generators found")
        return 0

    snapshots: dict[Path, Path] = {}
    scratch: tempfile.TemporaryDirectory[str] | None = None
    if args.check:
        scratch = tempfile.TemporaryDirectory()
        for script in scripts:
            for fig in _figure_files(script):
                copy = Path(scratch.name) / fig.relative_to(REPO_ROOT).as_posix().replace("/", "__")
                shutil.copy2(fig, copy)
                snapshots[fig] = copy

    ok = True
    for script in scripts:
        print(f"regenerating {script.relative_to(REPO_ROOT)}")
        ok &= _run(script)

    if not ok:
        return 1

    if args.check:
        stale = [
            fig
            for fig, copy in snapshots.items()
            if not fig.is_file() or not filecmp.cmp(fig, copy, shallow=False)
        ]
        new = [fig for script in scripts for fig in _figure_files(script) if fig not in snapshots]
        if stale or new:
            for fig in [*stale, *new]:
                print(f"  STALE {fig.relative_to(REPO_ROOT)}", file=sys.stderr)
            print(
                "\nFigures differ from their generators. Run `make figures` and commit.",
                file=sys.stderr,
            )
            return 1
        print(f"all figures current ({len(snapshots)} file(s))")
        if scratch:
            scratch.cleanup()
    else:
        print(f"regenerated figures from {len(scripts)} generator(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
