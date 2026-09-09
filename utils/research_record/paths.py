"""Where the research record lives, resolved once."""

from __future__ import annotations

from pathlib import Path

#: Repository root — this file is ``<root>/utils/research_record/paths.py``.
REPO_ROOT = Path(__file__).resolve().parents[2]

RESEARCH_ROOT = REPO_ROOT / "docs" / "research"
EXPERIMENTS_ROOT = RESEARCH_ROOT / "experiments"
TEMPLATE_ROOT = RESEARCH_ROOT / "templates" / "experiment"
FIGURES_ROOT = RESEARCH_ROOT / "figures"

INDEX_PATH = RESEARCH_ROOT / "INDEX.md"
CLAIMS_PATH = RESEARCH_ROOT / "CLAIMS.md"
CURRENT_PATH = RESEARCH_ROOT / "CURRENT.md"

#: Files every experiment directory must carry (section 3).
REQUIRED_FILES = ("manifest.yaml", "PROTOCOL.md", "RESULTS.md")

#: Figure formats a promoted or experiment figure must be emitted in.
REQUIRED_FIGURE_SUFFIXES = (".svg", ".pdf")


def experiment_dirs() -> list[Path]:
    """Every experiment directory, sorted by ID."""
    if not EXPERIMENTS_ROOT.is_dir():
        return []
    return sorted(
        p for p in EXPERIMENTS_ROOT.iterdir() if p.is_dir() and p.name.startswith("EXP-")
    )
