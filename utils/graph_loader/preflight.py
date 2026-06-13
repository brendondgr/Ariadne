#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from utils.kg_builder.validate import ArtifactValidationError, validate_canonical_artifacts

from .config import LoaderConfig
from .registry import DatasetLoadTarget
from .validation.semantic import SemanticValidationError, validate_semantic_artifacts


class PreflightError(Exception):
    """Raised when preflight checks fail before loading."""


@dataclass(frozen=True)
class PreflightResult:
    """Successful preflight outcome."""

    dataset: str
    backend: str
    semantic_valid: bool
    manifest_hash_ok: bool
    backend_reachable: dict[str, bool]
    node_count: int
    edge_count: int


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest_hashes(manifest_path: Path) -> None:
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    recorded = manifest.get("hashes", {})
    if not recorded:
        raise PreflightError(f"Manifest missing hashes: {manifest_path}")

    artifact_paths: dict[str, str] = dict(manifest.get("canonical", {}))
    for backend, exports in manifest.get("exports", {}).items():
        for export_name, export_path in exports.items():
            artifact_paths[f"{backend}_{export_name}"] = export_path

    for name, expected_hash in recorded.items():
        path_str = artifact_paths.get(name)
        if not path_str:
            raise PreflightError(f"Manifest hash entry {name!r} has no resolvable path.")
        path = Path(path_str)
        if not path.exists():
            raise PreflightError(f"Manifest hash target missing: {path}")
        actual = _file_sha256(path)
        if actual != expected_hash:
            raise PreflightError(
                f"Manifest hash mismatch for {name}: expected {expected_hash}, got {actual}"
            )


def _default_tcp_check(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _endpoint_host_port(endpoint: str, fallback: tuple[str, int]) -> tuple[str, int]:
    if endpoint.startswith("bolt://"):
        host_port = endpoint.removeprefix("bolt://").split("/", 1)[0]
    elif endpoint.startswith("ws://") or endpoint.startswith("wss://"):
        host_port = endpoint.split("://", 1)[1].split("/", 1)[0]
    else:
        return fallback
    host, _, port = host_port.partition(":")
    return host, int(port or str(fallback[1]))


def check_backend_reachability(
    target: DatasetLoadTarget,
    backends: list[str],
    tcp_check: Callable[[str, int, float], bool] = _default_tcp_check,
) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for backend in backends:
        endpoint = target.endpoints[backend]
        host, port = _endpoint_host_port(
            endpoint,
            ("127.0.0.1", 5456 if backend == "neo4j" else 6455),
        )
        results[backend] = tcp_check(host, port, 3.0)
    return results


def run_preflight(
    target: DatasetLoadTarget,
    *,
    backends: list[str] | None = None,
    check_reachability: bool = True,
    tcp_check: Callable[[str, int, float], bool] = _default_tcp_check,
) -> PreflightResult:
    """Validate artifacts, manifest hashes, semantics, and optional backend reachability."""
    backends = backends or list(target.backends.keys())

    try:
        artifact_summary = validate_canonical_artifacts(target.canonical_dir)
    except ArtifactValidationError as exc:
        raise PreflightError(str(exc)) from exc

    try:
        verify_manifest_hashes(target.manifest_path)
    except PreflightError:
        raise
    except Exception as exc:
        raise PreflightError(f"Manifest hash verification failed: {exc}") from exc

    semantic = validate_semantic_artifacts(
        target.nodes_path,
        target.relationships_path,
        target.schema_path,
    )
    if not semantic.valid:
        raise SemanticValidationError("; ".join(semantic.errors[:5]))

    reachable: dict[str, bool] = {}
    if check_reachability:
        reachable = check_backend_reachability(target, backends, tcp_check=tcp_check)
        if not all(reachable.values()):
            down = ", ".join(name for name, ok in reachable.items() if not ok)
            raise PreflightError(f"Graph backend unreachable: {down}")

    return PreflightResult(
        dataset=target.dataset,
        backend=target.backend,
        semantic_valid=True,
        manifest_hash_ok=True,
        backend_reachable=reachable,
        node_count=artifact_summary["nodes"],
        edge_count=artifact_summary["relationships"],
    )
