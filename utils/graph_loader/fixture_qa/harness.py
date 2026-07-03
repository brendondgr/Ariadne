#!/usr/bin/env python3
"""Fixture-QA harness.

Reconciles, for one dataset, three independent views of the graph:

    raw source  ==  canonical build manifest  ==  live graph database

plus a live referential-integrity check and an explicit revoked/deprecated
handling check. Emits ``data/graphs/<dataset>/runtime/fixture-qa-report.json``
and raises ``FixtureQAError`` on any failure so it can gate a pipeline.

This is the "fixture-QA harness" from the report: cheap to run, highest-value,
and the thing that catches silent ingestion drops before they poison answers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.io import read_jsonl

from ..config import LOAD_BACKENDS, LoaderConfig
from ..loader import _expected_counts
from ..registry import resolve_dataset
from ..stores.factory import create_graph_store
from .composite_keys import composite_key_checks, constraint_check
from .raw_counts import RawCounts, raw_counts_for

logger = logging.getLogger(__name__)


class FixtureQAError(Exception):
    """Raised when a fixture-QA reconciliation fails."""


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class FixtureQAReport:
    dataset: str
    passed: bool
    generated_at: str
    checks: list[CheckResult]
    raw: dict[str, Any]
    manifest_counts: dict[str, Any]
    live: dict[str, Any]
    report_path: str | None = None
    errors: list[str] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["checks"] = [c.as_dict() for c in self.checks]
        return data


def _load_runtime_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _reconcile_map(
    name: str,
    left_label: str,
    left: dict[str, int],
    right_label: str,
    right: dict[str, int],
    keys: list[str],
) -> CheckResult:
    """Compare two count maps over ``keys`` and build a CheckResult."""
    mismatches = []
    for key in keys:
        a = left.get(key, 0)
        b = right.get(key, 0)
        if a != b:
            mismatches.append(f"{key}: {left_label}={a} {right_label}={b}")
    if mismatches:
        return CheckResult(name, False, "; ".join(mismatches))
    return CheckResult(
        name, True, f"{len(keys)} keys reconcile ({left_label} == {right_label})"
    )


def _revoked_deprecated_check(
    dataset: str,
    raw: RawCounts,
    manifest: dict[str, Any],
    nodes_path: Path,
) -> list[CheckResult]:
    """Assert revoked/deprecated objects are handled exactly as declared."""
    checks: list[CheckResult] = []

    if dataset == "attack":
        meta = manifest.get("metadata", {})
        m_rev = int(meta.get("filtered_revoked", -1))
        m_dep = int(meta.get("filtered_deprecated", -1))
        r_rev = raw.excluded.get("revoked", 0)
        r_dep = raw.excluded.get("deprecated", 0)
        ok = m_rev == r_rev and m_dep == r_dep
        checks.append(
            CheckResult(
                "excluded_counts_raw_vs_manifest",
                ok,
                f"raw(revoked={r_rev}, deprecated={r_dep}) "
                f"manifest(revoked={m_rev}, deprecated={m_dep})",
            )
        )
        # No revoked/deprecated object may survive into the canonical artifact
        # (and therefore the live DB, which the count reconciliation confirms).
        leaked = 0
        for node in read_jsonl(nodes_path):
            props = node.get("properties", {})
            if props.get("revoked") is True or props.get("x_mitre_deprecated") is True:
                leaked += 1
        checks.append(
            CheckResult(
                "no_revoked_deprecated_leakage",
                leaked == 0,
                f"{leaked} revoked/deprecated nodes present in canonical artifact "
                "(expected 0)",
            )
        )
    elif dataset == "capec":
        # CAPEC loads the full catalog; retired patterns must carry a filterable
        # Status property so specialists can exclude them.
        with_status = 0
        without_status = 0
        for node in read_jsonl(nodes_path):
            if node.get("label") != "AttackPattern":
                continue
            props = node.get("properties", {})
            if props.get("Status") or node.get("Status"):
                with_status += 1
            else:
                without_status += 1
        checks.append(
            CheckResult(
                "capec_attack_patterns_have_status",
                without_status == 0 and with_status > 0,
                f"{with_status} AttackPattern nodes carry a Status property, "
                f"{without_status} missing it (specialists filter on Status)",
            )
        )
    return checks


def run_fixture_qa(
    dataset: str,
    *,
    loader_config: LoaderConfig | None = None,
    build_config: BuildConfig | None = None,
    store_factory: Callable[..., Any] | None = None,
    write_report: bool = True,
    expected_dir: Path | None = None,
) -> FixtureQAReport:
    """Run the full fixture-QA reconciliation for one dataset."""
    loader_config = loader_config or LoaderConfig.from_data_dir()
    build_config = build_config or BuildConfig.from_data_dir(loader_config.data_dir)
    store_factory = store_factory or create_graph_store

    target = resolve_dataset(dataset, "verify", loader_config)
    manifest = target.manifest
    expected = _expected_counts(manifest)
    manifest_nodes_by_label = dict(manifest.get("counts", {}).get("nodes_by_label", {}))
    manifest_edges_by_type = dict(
        manifest.get("counts", {}).get("relationships_by_type", {})
    )

    raw = raw_counts_for(dataset, build_config)

    checks: list[CheckResult] = []

    # 1. raw -> manifest node reconciliation over primary (raw-derivable) labels.
    primary = sorted(raw.primary_labels)
    checks.append(
        _reconcile_map(
            "raw_vs_manifest_nodes",
            "raw",
            raw.nodes_by_label,
            "manifest",
            manifest_nodes_by_label,
            primary,
        )
    )

    # 2. revoked / deprecated handling.
    checks.extend(
        _revoked_deprecated_check(dataset, raw, manifest, target.nodes_path)
    )

    # 3. composite (attack_id, stix_type) join-key checks against the
    #    checked-in collision fixture (attack only).
    identity: dict[str, Any] = {}
    if dataset == "attack":
        key_checks, identity = composite_key_checks(
            build_config, target.nodes_path, expected_dir
        )
        checks.extend(key_checks)

    # 4 + 5. manifest -> live reconciliation and referential integrity per loaded backend.
    live: dict[str, Any] = {}
    for backend in sorted(LOAD_BACKENDS):
        backend_target = target.backends.get(backend)
        if backend_target is None:
            continue
        runtime_manifest = _load_runtime_manifest(backend_target.runtime_manifest_path)
        if runtime_manifest is None:
            continue  # backend never loaded; nothing live to reconcile

        store = store_factory(backend, target, loader_config)
        backend_live: dict[str, Any] = {}
        try:
            store.connect()
            verification = store.verify_loaded_graph(expected)
            backend_live["nodes"] = verification.actual.nodes
            backend_live["edges"] = verification.actual.edges
            checks.append(
                CheckResult(
                    f"manifest_vs_live_counts[{backend}]",
                    verification.passed,
                    "counts reconcile"
                    if verification.passed
                    else "; ".join(verification.errors[:5]),
                )
            )
            integrity = store.referential_integrity()
            backend_live["referential_integrity"] = {
                "dangling_edges": integrity.dangling_edges,
                "nodes_missing_id": integrity.nodes_missing_id,
            }
            checks.append(
                CheckResult(
                    f"referential_integrity[{backend}]",
                    integrity.passed,
                    "0 dangling edges, 0 id-less nodes"
                    if integrity.passed
                    else "; ".join(integrity.details),
                )
            )
            live_constraints = store.list_constraint_names()
            backend_live["constraints"] = live_constraints
            check = constraint_check(dataset, backend, live_constraints)
            if check is not None:
                checks.append(check)
        except Exception as exc:  # pragma: no cover - live failure path
            checks.append(
                CheckResult(f"live_query[{backend}]", False, f"live query failed: {exc}")
            )
        finally:
            store.close()
        live[backend] = backend_live

    passed = all(c.passed for c in checks)
    errors = [f"{c.name}: {c.detail}" for c in checks if not c.passed]

    report = FixtureQAReport(
        dataset=dataset,
        passed=passed,
        generated_at=datetime.now(timezone.utc).isoformat(),
        checks=checks,
        raw={
            "source_path": raw.source_path,
            "object_count": raw.object_count,
            "nodes_by_label": raw.nodes_by_label,
            "primary_labels": sorted(raw.primary_labels),
            "excluded": raw.excluded,
            "notes": raw.notes,
        },
        manifest_counts={
            "nodes": expected.nodes,
            "edges": expected.edges,
            "nodes_by_label": manifest_nodes_by_label,
            "relationships_by_type": manifest_edges_by_type,
        },
        live=live,
        errors=errors,
        identity=identity,
    )

    if write_report:
        report_path = (
            loader_config.data_dir
            / "graphs"
            / dataset
            / "runtime"
            / "fixture-qa-report.json"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.as_dict(), f, indent=2, sort_keys=True)
            f.write("\n")
        report.report_path = str(report_path)

    return report


def run_fixture_qa_command(
    dataset: str, config: LoaderConfig | None = None
) -> FixtureQAReport:
    """CLI-facing fixture-QA run: log a summary and raise on failure."""
    report = run_fixture_qa(dataset, loader_config=config)
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        logger.info("fixture-qa[%s] %s %s — %s", dataset, status, check.name, check.detail)
    if report.passed:
        logger.info(
            "Fixture-QA passed for %s (%d checks). Report: %s",
            dataset,
            len(report.checks),
            report.report_path,
        )
    else:
        logger.error("Fixture-QA FAILED for %s: %s", dataset, report.errors)
        raise FixtureQAError("; ".join(report.errors[:5]))
    return report
