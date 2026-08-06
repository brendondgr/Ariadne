"""Experiment scaffolding — section 7.1 of ``AGENT_INSTRUCTIONS.md``.

Allocates the next ID, copies ``templates/experiment/``, and pre-fills the
fields a human would otherwise get wrong or skip: today's date, the git commit,
the branch, and whether the tree was dirty. Capturing provenance at scaffold
time is the whole point — anything that depends on remembering to record the
commit afterwards will not happen.
"""

from __future__ import annotations

import datetime as _dt
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from utils.research_record.paths import EXPERIMENTS_ROOT, REPO_ROOT, TEMPLATE_ROOT

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class ScaffoldError(Exception):
    """Raised when an experiment cannot be scaffolded."""


@dataclass(frozen=True)
class GitState:
    commit: str
    branch: str
    dirty: bool


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def git_state() -> GitState:
    """Current commit, branch, and dirty-tree status.

    Falls back to ``unknown`` rather than guessing — an invented commit is worse
    than an admitted gap, and the validator accepts ``unknown``.
    """
    commit = _git("rev-parse", "HEAD") or "unknown"
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    status = _git("status", "--porcelain")
    return GitState(commit=commit, branch=branch, dirty=bool(status))


def next_id(when: _dt.date | None = None) -> str:
    """Allocate the next ``EXP-YYYY-MM-NNN`` for the given month.

    Numbering restarts each month, and gaps are never reused: the sequence is
    max+1 over the month, not count+1, so deleting a directory (which should not
    happen) cannot silently recycle an ID that already appears in a paper draft.
    """
    when = when or _dt.date.today()
    prefix = f"EXP-{when.year:04d}-{when.month:02d}-"
    used = [
        int(p.name[len(prefix) : len(prefix) + 3])
        for p in EXPERIMENTS_ROOT.glob(f"{prefix}*")
        if p.is_dir() and p.name[len(prefix) : len(prefix) + 3].isdigit()
    ]
    return f"{prefix}{(max(used) + 1) if used else 1:03d}"


def _prefill(text: str, *, exp_id: str, slug: str, today: _dt.date, git: GitState) -> str:
    replacements = {
        "id: EXP-YYYY-MM-NNN": f"id: {exp_id}",
        "slug: <kebab-slug>": f"slug: {slug}",
        "date_started: YYYY-MM-DD": f"date_started: {today.isoformat()}",
        "  commit: unknown          #": f"  commit: {git.commit}          #",
        "  branch: unknown": f"  branch: {git.branch}",
        "  dirty: false             #": f"  dirty: {str(git.dirty).lower()}             #",
        "<EXP-ID>": exp_id,
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def scaffold(slug: str, *, when: _dt.date | None = None) -> Path:
    """Create a new experiment folder from the template. Returns its path."""
    if not _SLUG_RE.match(slug):
        raise ScaffoldError(
            f"slug {slug!r} must be lowercase kebab-case (letters, digits, single hyphens)"
        )
    if not TEMPLATE_ROOT.is_dir():
        raise ScaffoldError(f"template missing at {TEMPLATE_ROOT}")

    today = when or _dt.date.today()
    exp_id = next_id(today)
    target = EXPERIMENTS_ROOT / f"{exp_id}-{slug}"
    if target.exists():
        raise ScaffoldError(f"{target} already exists")

    shutil.copytree(TEMPLATE_ROOT, target)
    git = git_state()
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.suffix in {".md", ".yaml"}:
            path.write_text(
                _prefill(path.read_text(), exp_id=exp_id, slug=slug, today=today, git=git)
            )

    (target / "logs").mkdir(exist_ok=True)
    (target / "logs" / ".gitkeep").touch()
    (target / "tables").mkdir(exist_ok=True)
    (target / "tables" / ".gitkeep").touch()
    return target
