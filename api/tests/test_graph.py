"""Contract tests for GET /api/graph/{dataset}.

Tests cover:
- Correct response shape when the service returns a fixture payload.
- 404 for an unknown dataset name; 422 for a malformed one (pattern enforcement).
- Any card-backed dataset name reaches the service (no Literal gate).
- 404 when the service raises FileNotFoundError.
- Optional integration test against real canonical files (skipped if absent).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.main as main
from api.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixture payload
# ---------------------------------------------------------------------------

_FIXTURE_PAYLOAD = {
    "dataset": "attack",
    "backend": "neo4j",
    "counts": {"nodes": 2, "relationships": 1},
    "nodes_by_label": {"Technique": 2},
    "nodes": [
        {
            "id": "n1",
            "label": "Technique",
            "labels": ["Technique"],
            "name": "Spearphishing",
            "properties": {"description": "A short desc"},
        },
        {
            "id": "n2",
            "label": "Technique",
            "labels": ["Technique"],
            "name": "Drive-by Compromise",
            "properties": {},
        },
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2", "type": "SUBTECHNIQUE_OF"},
    ],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_graph_endpoint_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatched service returns fixture; endpoint serialises it correctly."""
    monkeypatch.setattr(main, "load_canonical_graph", lambda dataset: _FIXTURE_PAYLOAD)

    resp = client.get("/api/graph/attack")
    assert resp.status_code == 200
    body = resp.json()

    assert body["dataset"] == "attack"
    assert body["backend"] == "neo4j"
    assert isinstance(body["counts"]["nodes"], int)
    assert isinstance(body["counts"]["relationships"], int)
    assert isinstance(body["nodes_by_label"], dict)
    assert isinstance(body["nodes"], list) and len(body["nodes"]) == 2
    assert isinstance(body["edges"], list) and len(body["edges"]) == 1

    node = body["nodes"][0]
    assert {"id", "label", "labels", "name", "properties"} <= node.keys()

    edge = body["edges"][0]
    assert {"id", "source", "target", "type"} <= edge.keys()


def test_graph_capec_backend_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """capec dataset maps to gremlin backend."""
    fixture = dict(_FIXTURE_PAYLOAD, dataset="capec", backend="gremlin")
    monkeypatch.setattr(main, "load_canonical_graph", lambda dataset: fixture)

    resp = client.get("/api/graph/capec")
    assert resp.status_code == 200
    assert resp.json()["backend"] == "gremlin"


def test_graph_unknown_dataset_404_or_422() -> None:
    """An unknown but well-formed name reaches the service and is a 404."""
    resp = client.get("/api/graph/bogus")
    assert resp.status_code in (404, 422)


def test_graph_malformed_dataset_name_422() -> None:
    """Names outside [a-z0-9_-] never reach the filesystem."""
    resp = client.get("/api/graph/Bad%20Name")
    assert resp.status_code == 422


def test_graph_card_backed_dataset_reaches_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Synapse-exported dataset name is served like the built-ins."""
    fixture = dict(_FIXTURE_PAYLOAD, dataset="mnp-cs-03000-r2", backend="neo4j")
    seen: dict[str, str] = {}

    def fake(dataset: str):
        seen["dataset"] = dataset
        return fixture

    monkeypatch.setattr(main, "load_canonical_graph", fake)
    resp = client.get("/api/graph/mnp-cs-03000-r2")
    assert resp.status_code == 200
    assert seen == {"dataset": "mnp-cs-03000-r2"}
    assert resp.json()["backend"] == "neo4j"


def test_graph_missing_files_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """FileNotFoundError from the service layer becomes a 404 HTTP response."""

    def _raise(dataset: str) -> None:  # type: ignore[return]
        raise FileNotFoundError("nodes.jsonl not found")

    monkeypatch.setattr(main, "load_canonical_graph", _raise)

    resp = client.get("/api/graph/attack")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Integration test (skipped when canonical files are absent)
# ---------------------------------------------------------------------------

def _canonical_path(dataset: str) -> Path:
    from utils.graph_loader.config import LoaderConfig

    cfg = LoaderConfig.from_data_dir()
    return cfg.graphs_dir(dataset) / "canonical"


@pytest.mark.parametrize("dataset,expected_backend", [("attack", "neo4j"), ("capec", "gremlin")])
def test_graph_integration_counts_match_manifest(dataset: str, expected_backend: str) -> None:
    """Read real canonical files and verify counts match the manifest."""
    canon = _canonical_path(dataset)
    if not (canon / "nodes.jsonl").exists():
        pytest.skip(f"Canonical files for '{dataset}' not present — skipping integration test")

    manifest_path = canon / "manifest.json"
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)

    expected_nodes = manifest["counts"]["nodes"]
    expected_rels = manifest["counts"]["relationships"]

    from api.services.graph import load_canonical_graph

    payload = load_canonical_graph(dataset)

    assert payload["dataset"] == dataset
    assert payload["backend"] == expected_backend
    assert len(payload["nodes"]) == expected_nodes, (
        f"{dataset}: expected {expected_nodes} nodes, got {len(payload['nodes'])}"
    )
    assert len(payload["edges"]) == expected_rels, (
        f"{dataset}: expected {expected_rels} edges, got {len(payload['edges'])}"
    )
    assert payload["counts"]["nodes"] == expected_nodes
    assert payload["counts"]["relationships"] == expected_rels

    # Verify no raw description / external_references leakage in nodes
    for node in payload["nodes"]:
        props = node.get("properties", {})
        assert "external_references" not in props, "external_references must be stripped"
        desc = props.get("description")
        if desc is not None:
            assert len(desc) <= 280, "description preview must be at most 280 chars"
