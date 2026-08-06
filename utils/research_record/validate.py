"""Validation — section 7.3 of ``AGENT_INSTRUCTIONS.md``.

Convention without enforcement decays, and every check below exists because the
corresponding failure is one this repository has already made at least once: a
figure nobody can regenerate, a metric quoted from a run that no longer exists,
an index that went stale three weeks ago.

Eight conditions, each reported with the file that caused it:

1. a missing ``manifest.yaml``, ``PROTOCOL.md``, or ``RESULTS.md``
2. a manifest that fails schema validation
3. ``status: complete`` with empty ``metrics.values``
4. a figure listed in the manifest with no file, or a figure file not listed
5. a figure folder with no generating script
6. a ``data/POINTERS.md`` row without a hash
7. a ``supports_claims`` ID absent from ``CLAIMS.md``
8. a stale ``INDEX.md``
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from utils.research_record.manifest import Manifest, ManifestError, load_manifest
from utils.research_record.paths import (
    CLAIMS_PATH,
    INDEX_PATH,
    REQUIRED_FIGURE_SUFFIXES,
    REQUIRED_FILES,
    REPO_ROOT,
    experiment_dirs,
)

_CLAIM_ID_RE = re.compile(r"\bC-\d{3}\b")
_HASH_TOKEN_RE = re.compile(r"\b(sha256|md5):[0-9a-f]{32,64}\b")


@dataclass(frozen=True)
class Finding:
    """One validation failure, tied to the file that caused it."""

    check: str
    where: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.check}] {self.where}: {self.detail}"


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def known_claim_ids() -> set[str]:
    """Every claim ID declared in ``CLAIMS.md``."""
    if not CLAIMS_PATH.is_file():
        return set()
    return set(_CLAIM_ID_RE.findall(CLAIMS_PATH.read_text()))


def check_required_files(exp: Path) -> list[Finding]:
    """Condition 1."""
    return [
        Finding("required-files", _rel(exp), f"missing {name}")
        for name in REQUIRED_FILES
        if not (exp / name).is_file()
    ]


def check_metrics(exp: Path, manifest: Manifest) -> list[Finding]:
    """Condition 3 — a completed experiment that recorded no numbers."""
    if manifest.status == "complete" and not manifest.metrics.values:
        return [
            Finding(
                "empty-metrics",
                _rel(exp / "manifest.yaml"),
                "status is 'complete' but metrics.values is empty — "
                "a completed experiment recorded no numbers",
            )
        ]
    return []


def check_figures(exp: Path, manifest: Manifest) -> list[Finding]:
    """Conditions 4 and 5 — figure/manifest agreement, and a generator."""
    findings: list[Finding] = []
    figures_dir = exp / "figures"
    declared = set(manifest.figures)

    for name in sorted(declared):
        for suffix in REQUIRED_FIGURE_SUFFIXES:
            if not (figures_dir / f"{name}{suffix}").is_file():
                findings.append(
                    Finding(
                        "figure-missing",
                        _rel(figures_dir),
                        f"manifest lists figure {name!r} but {name}{suffix} does not exist",
                    )
                )

    if figures_dir.is_dir():
        on_disk = {
            p.stem
            for p in figures_dir.iterdir()
            if p.is_file() and p.suffix in {*REQUIRED_FIGURE_SUFFIXES, ".png"}
        }
        for orphan in sorted(on_disk - declared):
            findings.append(
                Finding(
                    "figure-unlisted",
                    _rel(figures_dir / orphan),
                    "figure file exists but is not in the manifest's figures: list",
                )
            )
        if declared and not any(figures_dir.glob("*.py")):
            findings.append(
                Finding(
                    "figure-no-generator",
                    _rel(figures_dir),
                    "figures exist with no generating script in the same folder — "
                    "a figure that cannot be regenerated does not go in the paper",
                )
            )
    return findings


def check_pointers(exp: Path) -> list[Finding]:
    """Condition 6 — every artifact pointer carries a hash."""
    pointers = exp / "data" / "POINTERS.md"
    if not pointers.is_file():
        return []
    findings: list[Finding] = []
    for lineno, line in enumerate(pointers.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|--"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        # Header rows and the empty template row carry no artifact.
        if not cells or not cells[0] or cells[0].lower() in {"artifact", "---"}:
            continue
        if not _HASH_TOKEN_RE.search(stripped):
            findings.append(
                Finding(
                    "pointer-no-hash",
                    f"{_rel(pointers)}:{lineno}",
                    f"artifact {cells[0]!r} has no sha256:/md5: hash — "
                    "a path without a hash does not pin content",
                )
            )
    return findings


def check_claims(exp: Path, manifest: Manifest, claim_ids: set[str]) -> list[Finding]:
    """Condition 7 — no orphan claim references."""
    return [
        Finding(
            "unknown-claim",
            _rel(exp / "manifest.yaml"),
            f"supports_claims lists {cid} which is not in docs/research/CLAIMS.md",
        )
        for cid in manifest.supports_claims
        if cid not in claim_ids
    ]


def check_index() -> list[Finding]:
    """Condition 8 — the index matches what the manifests say."""
    from utils.research_record.index import render_index

    expected = render_index()
    if not INDEX_PATH.is_file():
        return [Finding("stale-index", _rel(INDEX_PATH), "INDEX.md does not exist — run `make index`")]
    if INDEX_PATH.read_text() != expected:
        return [
            Finding(
                "stale-index",
                _rel(INDEX_PATH),
                "INDEX.md does not match the manifests — run `make index`",
            )
        ]
    return []


def validate_experiment(exp: Path, claim_ids: set[str] | None = None) -> list[Finding]:
    """Every per-experiment check. Returns an empty list when the folder is valid."""
    if claim_ids is None:
        claim_ids = known_claim_ids()

    findings = check_required_files(exp)
    manifest_path = exp / "manifest.yaml"
    if not manifest_path.is_file():
        return findings  # nothing further is checkable without a manifest

    try:
        manifest = load_manifest(manifest_path)
    except ManifestError as exc:
        findings.append(Finding("schema", _rel(manifest_path), str(exc).split(": ", 1)[-1]))
        return findings

    expected_dir = f"{manifest.id}-{manifest.slug}"
    if exp.name != expected_dir:
        findings.append(
            Finding(
                "id-mismatch",
                _rel(manifest_path),
                f"directory is {exp.name!r} but id + slug imply {expected_dir!r} — "
                "the ID is the only handle used in code, figures, and the paper, "
                "so it must match the folder that carries it",
            )
        )

    findings += check_metrics(exp, manifest)
    findings += check_figures(exp, manifest)
    findings += check_pointers(exp)
    findings += check_claims(exp, manifest, claim_ids)
    return findings


def validate_all(paths: list[Path] | None = None, *, check_index_freshness: bool = True) -> list[Finding]:
    """Validate the given experiment folders, or every one if not specified."""
    targets = paths if paths is not None else experiment_dirs()
    claim_ids = known_claim_ids()
    findings: list[Finding] = []
    for exp in targets:
        findings += validate_experiment(exp, claim_ids)
    if check_index_freshness:
        findings += check_index()
    return findings
