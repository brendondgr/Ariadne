"""Validation — section 7.3 of ``AGENT_INSTRUCTIONS.md``.

Convention without enforcement decays, and every check below exists because the
corresponding failure is one this repository has already made at least once: a
figure nobody can regenerate, a metric quoted from a run that no longer exists,
an index that went stale three weeks ago, a pointer table left as the blank
template, a withdrawn number quoted as current.

Fourteen conditions, each reported with the file that caused it:

1. a missing ``manifest.yaml``, ``PROTOCOL.md``, or ``RESULTS.md``
2. a manifest that fails schema validation
3. ``status: complete`` with empty ``metrics.values``
4. a figure listed in the manifest with no file, or a figure file not listed
5. a figure folder with no generating script
6. a ``data/POINTERS.md`` row without a hash
7. a ``supports_claims`` ID absent from ``CLAIMS.md``
8. a stale ``INDEX.md`` or ``CURRENT.md``
9. a terminal experiment with ``date_completed: null``
10. a terminal experiment still carrying a scaffold placeholder (``<...>``)
11. a terminal experiment whose pointer table is empty (no artifact rows and no
    explicit "no external artifacts" statement)
12. a terminal experiment without ``data/metrics.json``, or whose manifest
    ``metrics.values`` contain a number that appears nowhere in it
13. a one-directional ``supersedes`` / ``superseded_by`` link, a link to an
    experiment that does not exist, or ``status: superseded`` with no successor
14. a pointer whose path exists and whose hash no longer matches
    (a path that does not exist on this machine is skipped, not failed —
    raw run output is gitignored and a fresh clone must still validate)

Conditions 9–14 were added on 2026-09-09 after a full audit found that the
first eight passed on 47 experiments of which thirteen had blank contract
files, impossible commits, or withdrawn headline values.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from utils.research_record.hashing import sha256_file, sha256_tree
from utils.research_record.manifest import Manifest, ManifestError, load_manifest
from utils.research_record.paths import (
    CLAIMS_PATH,
    CURRENT_PATH,
    INDEX_PATH,
    REQUIRED_FIGURE_SUFFIXES,
    REQUIRED_FILES,
    REPO_ROOT,
    experiment_dirs,
)

_CLAIM_ID_RE = re.compile(r"\bC-\d{3}\b")
_HASH_TOKEN_RE = re.compile(r"\b(sha256|md5):[0-9a-f]{32,64}\b")
_PLACEHOLDER_RE = re.compile(r"<[a-z][^<>]{2,60}>|EXP-YYYY|YYYY-MM-DD")
_NO_ARTIFACTS_RE = re.compile(r"no (external|large|raw) artifacts", re.IGNORECASE)


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


@dataclass(frozen=True)
class PointerRow:
    lineno: int
    artifact: str
    path: str
    hash: str | None


def read_pointer_rows(pointers: Path) -> list[PointerRow]:
    """Every artifact row of a ``POINTERS.md`` table, header and blank rows dropped."""
    rows: list[PointerRow] = []
    if not pointers.is_file():
        return rows
    for lineno, line in enumerate(pointers.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|--"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells or not cells[0] or cells[0].lower() in {"artifact", "---"}:
            continue
        match = _HASH_TOKEN_RE.search(stripped)
        path = cells[1].strip("`") if len(cells) > 1 else ""
        rows.append(PointerRow(lineno, cells[0], path, match.group(0) if match else None))
    return rows


def check_pointers(exp: Path) -> list[Finding]:
    """Condition 6 — every artifact pointer carries a hash."""
    pointers = exp / "data" / "POINTERS.md"
    return [
        Finding(
            "pointer-no-hash",
            f"{_rel(pointers)}:{row.lineno}",
            f"artifact {row.artifact!r} has no sha256:/md5: hash — "
            "a path without a hash does not pin content",
        )
        for row in read_pointer_rows(pointers)
        if row.hash is None
    ]


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
    """Condition 8 — the generated files match what the manifests say."""
    from utils.research_record.index import render_current, render_index

    findings: list[Finding] = []
    for path, render in ((INDEX_PATH, render_index), (CURRENT_PATH, render_current)):
        if not path.is_file():
            findings.append(
                Finding("stale-index", _rel(path), f"{path.name} does not exist — run `make index`")
            )
        elif path.read_text() != render():
            findings.append(
                Finding(
                    "stale-index",
                    _rel(path),
                    f"{path.name} does not match the manifests — run `make index`",
                )
            )
    return findings


def check_dates(exp: Path, manifest: Manifest) -> list[Finding]:
    """Condition 9 — a finished experiment knows when it finished."""
    findings: list[Finding] = []
    where = _rel(exp / "manifest.yaml")
    if manifest.is_terminal and manifest.date_completed is None:
        findings.append(
            Finding("no-date-completed", where, f"status is {manifest.status!r} but date_completed is null")
        )
    if manifest.date_completed is not None and manifest.date_completed < manifest.date_started:
        findings.append(
            Finding(
                "date-order",
                where,
                f"date_completed {manifest.date_completed} precedes date_started {manifest.date_started}",
            )
        )
    return findings


def _string_fields(obj: object, prefix: str = "") -> list[tuple[str, str]]:
    """Every string leaf in a nested mapping/list, with its dotted path."""
    out: list[tuple[str, str]] = []
    if isinstance(obj, str):
        out.append((prefix, obj))
    elif isinstance(obj, dict):
        for key, value in obj.items():
            out += _string_fields(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            out += _string_fields(value, f"{prefix}[{i}]")
    return out


def check_placeholders(exp: Path, manifest: Manifest) -> list[Finding]:
    """Condition 10 — no scaffold placeholder survives into a finished record."""
    if not manifest.is_terminal:
        return []
    findings: list[Finding] = []
    for field, value in _string_fields(manifest.model_dump(mode="json")):
        if _PLACEHOLDER_RE.search(value):
            findings.append(
                Finding(
                    "placeholder",
                    _rel(exp / "manifest.yaml"),
                    f"{field} still holds the scaffold placeholder {value!r} — "
                    "write the value, or 'unknown' and an ISSUES.md line",
                )
            )
    return findings


def check_pointer_table_filled(exp: Path, manifest: Manifest) -> list[Finding]:
    """Condition 11 — a finished experiment names its raw artifacts, or says it has none."""
    if not manifest.is_terminal:
        return []
    pointers = exp / "data" / "POINTERS.md"
    if not pointers.is_file():
        return [Finding("pointer-table-missing", _rel(exp / "data"), "no data/POINTERS.md")]
    if read_pointer_rows(pointers):
        return []
    if _NO_ARTIFACTS_RE.search(pointers.read_text()):
        return []
    return [
        Finding(
            "pointer-table-empty",
            _rel(pointers),
            "the artifact table is empty — list every raw directory this experiment "
            "reads, with a hash, or state 'no external artifacts' and why",
        )
    ]


def _numbers_in(obj: object) -> set[float]:
    found: set[float] = set()
    if isinstance(obj, bool):
        return found
    if isinstance(obj, (int, float)):
        if isinstance(obj, float) and math.isnan(obj):
            return found
        found.add(round(float(obj), 6))
    elif isinstance(obj, dict):
        for value in obj.values():
            found |= _numbers_in(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            found |= _numbers_in(value)
    return found


def check_metrics_file(exp: Path, manifest: Manifest) -> list[Finding]:
    """Condition 12 — the canonical metrics file exists and backs the manifest."""
    if not manifest.is_terminal:
        return []
    metrics_path = exp / "data" / "metrics.json"
    where = _rel(metrics_path)
    if not metrics_path.is_file():
        return [
            Finding(
                "metrics-file-missing",
                _rel(exp / "data"),
                "no data/metrics.json — the manifest's numbers must be readable by machine "
                "from the file the figures and CURRENT.md are built from",
            )
        ]
    try:
        payload = json.loads(metrics_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [Finding("metrics-file-unreadable", where, f"cannot parse: {exc}")]
    present = _numbers_in(payload)
    findings: list[Finding] = []
    for name, cell in manifest.metrics.values.items():
        mean = round(float(cell.mean), 6)
        close = any(abs(mean - p) < 5e-5 for p in present)
        if not close:
            findings.append(
                Finding(
                    "metric-not-in-file",
                    where,
                    f"manifest metric {name} = {cell.mean} appears nowhere in metrics.json — "
                    "the manifest was typed, not read",
                )
            )
    return findings


def check_links(manifests: dict[str, Manifest]) -> list[Finding]:
    """Condition 13 — supersession links are symmetric and resolvable."""
    findings: list[Finding] = []
    for exp_id, manifest in manifests.items():
        where = f"docs/research/experiments/{exp_id}-{manifest.slug}/manifest.yaml"
        for field, target in (("supersedes", manifest.supersedes), ("superseded_by", manifest.superseded_by)):
            if target is None:
                continue
            other = manifests.get(target)
            if other is None:
                findings.append(Finding("link-unresolved", where, f"{field}: {target} is not an experiment on record"))
                continue
            back = other.superseded_by if field == "supersedes" else other.supersedes
            if back != exp_id:
                other_field = "superseded_by" if field == "supersedes" else "supersedes"
                findings.append(
                    Finding(
                        "link-one-way",
                        where,
                        f"{field}: {target}, but {target}.{other_field} is {back!r} — "
                        "a supersession link is recorded in both manifests or it is not recorded",
                    )
                )
        if manifest.status == "superseded" and manifest.superseded_by is None:
            findings.append(
                Finding("superseded-no-successor", where, "status is 'superseded' but superseded_by is null")
            )
        for rel in manifest.related:
            if rel not in manifests:
                findings.append(Finding("link-unresolved", where, f"related: {rel} is not an experiment on record"))
    return findings


def check_pointer_hashes(exp: Path) -> list[Finding]:
    """Condition 14 — a pointer whose target is present still hashes the same."""
    pointers = exp / "data" / "POINTERS.md"
    findings: list[Finding] = []
    for row in read_pointer_rows(pointers):
        if row.hash is None or not row.hash.startswith("sha256:"):
            continue
        target = (REPO_ROOT / row.path) if row.path else None
        if target is None or not target.exists():
            continue  # gitignored raw output is not on every machine; see module docstring
        actual = sha256_tree(target) if target.is_dir() else sha256_file(target)
        if actual != row.hash:
            findings.append(
                Finding(
                    "pointer-hash-mismatch",
                    f"{_rel(pointers)}:{row.lineno}",
                    f"{row.path} hashes to {actual[:19]}… but the row records {row.hash[:19]}… — "
                    "the artifact changed after the number was recorded; re-hash it and say what changed in ISSUES.md",
                )
            )
    return findings


def validate_experiment(
    exp: Path,
    claim_ids: set[str] | None = None,
    *,
    verify_hashes: bool = True,
) -> list[Finding]:
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
    findings += check_dates(exp, manifest)
    findings += check_placeholders(exp, manifest)
    findings += check_pointer_table_filled(exp, manifest)
    findings += check_metrics_file(exp, manifest)
    if verify_hashes:
        findings += check_pointer_hashes(exp)
    return findings


def load_all_manifests(paths: list[Path] | None = None) -> dict[str, Manifest]:
    """Every readable manifest on record, keyed by experiment ID."""
    out: dict[str, Manifest] = {}
    for exp in paths if paths is not None else experiment_dirs():
        try:
            manifest = load_manifest(exp / "manifest.yaml")
        except (ManifestError, OSError):
            continue
        out[manifest.id] = manifest
    return out


def validate_all(
    paths: list[Path] | None = None,
    *,
    check_index_freshness: bool = True,
    verify_hashes: bool = True,
) -> list[Finding]:
    """Validate the given experiment folders, or every one if not specified."""
    targets = paths if paths is not None else experiment_dirs()
    claim_ids = known_claim_ids()
    findings: list[Finding] = []
    for exp in targets:
        findings += validate_experiment(exp, claim_ids, verify_hashes=verify_hashes)
    # Links are checked over the whole record even when a subset was requested:
    # a one-way link is a defect in two files, and only one may be in `paths`.
    findings += check_links(load_all_manifests())
    if check_index_freshness:
        findings += check_index()
    return findings
