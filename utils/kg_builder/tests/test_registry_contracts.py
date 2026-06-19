#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from pathlib import Path

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.main import KGBuildRunner
from utils.kg_builder.registry import (
    build_attack_source_card,
    build_capec_source_card,
    write_attack_source_card,
    write_capec_source_card,
)

# Env-var names follow ALL_CAPS_UNDERSCORES; literal passwords/tokens don't.
_ENV_VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")

_KNOWN_CREDENTIAL_VALUES = {"password", "secret", "token", "apikey", "api_key"}


def _looks_like_literal_credential(value: str) -> bool:
    """Return True if *value* looks like a literal secret rather than an env-var name."""
    if not isinstance(value, str):
        return False
    lower = value.lower()
    if any(kw in lower for kw in _KNOWN_CREDENTIAL_VALUES):
        return not _ENV_VAR_RE.match(value)
    return False


def _assert_no_literal_secrets(obj: object, path: str = "") -> None:
    """Recursively assert that no dict value looks like a literal credential."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_lower = k.lower()
            if any(kw in key_lower for kw in _KNOWN_CREDENTIAL_VALUES):
                assert _ENV_VAR_RE.match(str(v)), (
                    f"Literal credential found at {path}.{k}={v!r}; store env-var names only"
                )
            _assert_no_literal_secrets(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_literal_secrets(item, f"{path}[{i}]")


_ATTACK_OVERLAY = {
    "connection": {
        "backend": "neo4j",
        "uri": "bolt://localhost:7687",
        "database": "neo4j",
        "auth_env": {"user": "NEO4J_USER", "password": "NEO4J_PASSWORD"},
        "read_only": True,
        "timeout_ms": 5000,
    },
    "safety": {
        "read_only": True,
        "max_result_rows": 1000,
        "max_traversal_depth": 3,
        "query_timeout_ms": 5000,
        "disallowed_clauses": ["CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP"],
    },
    "provenance": {
        "id_property": "id",
        "source_ref_property": "external_references",
        "source_name": "MITRE ATT&CK",
        "dataset_version": "v19.0",
        "id_scheme": "technique-id",
    },
    "entity_descriptions": {
        "nodes": {"Technique": "An adversary action."},
        "relationships": {"USES": "A Group uses a Technique."},
    },
}

_CAPEC_OVERLAY = {
    "connection": {
        "backend": "gremlin",
        "uri": "ws://localhost:8182/gremlin",
        "traversal_source": "g",
        "auth_env": {"user": "GREMLIN_USER", "password": "GREMLIN_PASSWORD"},
        "read_only": True,
        "timeout_ms": 5000,
    },
    "safety": {
        "read_only": True,
        "max_result_rows": 1000,
        "max_traversal_depth": 3,
        "query_timeout_ms": 5000,
        "disallowed_steps": ["addV", "addE", "drop", "property"],
    },
    "provenance": {
        "id_property": "id",
        "source_name": "MITRE CAPEC",
        "dataset_version": "v3.9",
        "id_scheme": "capec-id",
    },
    "entity_descriptions": {
        "nodes": {"AttackPattern": "A CAPEC attack pattern."},
        "relationships": {"ChildOf": "A more specific variant of a parent."},
    },
}


def _write_overlay(registry_dir: Path, dataset: str, overlay: dict) -> None:
    overlay_dir = registry_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    with open(overlay_dir / f"{dataset}.overlay.json", "w", encoding="utf-8") as f:
        json.dump(overlay, f)


def test_attack_source_card_resolves_manifest_and_exports(tmp_path: Path) -> None:
    config = BuildConfig.from_data_dir(tmp_path)
    paths = config.paths()

    canonical_dir = paths.graph_canonical_dir
    canonical_dir.mkdir(parents=True)
    manifest = {
        "schema_version": "1.0",
        "canonical": {
            "nodes_jsonl": str(canonical_dir / "nodes.jsonl"),
            "relationships_jsonl": str(canonical_dir / "relationships.jsonl"),
            "schema_json": str(canonical_dir / "schema.json"),
        },
        "exports": {
            "neo4j": {"nodes_csv": str(paths.graph_neo4j_export_dir / "nodes.csv")},
            "gremlin": {"nodes_jsonl": str(paths.graph_gremlin_export_dir / "nodes.jsonl")},
        },
    }
    manifest_path = canonical_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    schema = {
        "schema_version": "1.0",
        "node_labels": ["Technique", "Tactic"],
        "relationship_types": ["USES"],
    }
    with open(canonical_dir / "schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f)

    _write_overlay(paths.source_registry_dir, "attack", _ATTACK_OVERLAY)

    card = build_attack_source_card(config, manifest_path)
    assert card.dataset == "attack"
    assert card.runtime_backend == "neo4j"
    assert card.schema_version == "1.0"
    assert "Technique" in card.node_labels
    assert card.exports["gremlin"]["nodes_jsonl"].endswith("nodes.jsonl")

    card_path = write_attack_source_card(config, manifest_path)
    assert card_path.exists()


def test_capec_source_card_resolves_manifest_and_exports(tmp_path: Path) -> None:
    config = BuildConfig.from_data_dir(tmp_path)
    paths = config.paths()

    canonical_dir = paths.capec_graph_canonical_dir
    canonical_dir.mkdir(parents=True)
    manifest = {
        "schema_version": "1.0",
        "exports": {
            "neo4j": {"nodes_csv": str(paths.capec_graph_neo4j_export_dir / "nodes.csv")},
            "gremlin": {"nodes_jsonl": str(paths.capec_graph_gremlin_export_dir / "nodes.jsonl")},
        },
    }
    manifest_path = canonical_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    schema = {
        "schema_version": "1.0",
        "dataset": "capec",
        "node_labels": ["AttackPattern", "Category"],
        "relationship_types": ["ChildOf", "MAPS_TO"],
    }
    with open(canonical_dir / "schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f)

    _write_overlay(paths.source_registry_dir, "capec", _CAPEC_OVERLAY)

    card = build_capec_source_card(config, manifest_path)
    assert card.dataset == "capec"
    assert card.runtime_backend == "gremlin"
    assert "AttackPattern" in card.node_labels

    card_path = write_capec_source_card(config, manifest_path)
    assert card_path.exists()


def _make_attack_fixture(tmp_path: Path) -> tuple[BuildConfig, Path]:
    """Return (config, manifest_path) with overlay and schema written."""
    config = BuildConfig.from_data_dir(tmp_path)
    paths = config.paths()
    canonical_dir = paths.graph_canonical_dir
    canonical_dir.mkdir(parents=True)

    manifest = {
        "schema_version": "1.0",
        "exports": {
            "neo4j": {"nodes_csv": str(paths.graph_neo4j_export_dir / "nodes.csv")},
            "gremlin": {"nodes_jsonl": str(paths.graph_gremlin_export_dir / "nodes.jsonl")},
        },
    }
    manifest_path = canonical_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    schema = {
        "schema_version": "1.0",
        "node_labels": ["Technique", "Tactic"],
        "relationship_types": ["USES"],
    }
    with open(canonical_dir / "schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f)

    _write_overlay(paths.source_registry_dir, "attack", _ATTACK_OVERLAY)
    return config, manifest_path


def _make_capec_fixture(tmp_path: Path) -> tuple[BuildConfig, Path]:
    """Return (config, manifest_path) with overlay and schema written."""
    config = BuildConfig.from_data_dir(tmp_path)
    paths = config.paths()
    canonical_dir = paths.capec_graph_canonical_dir
    canonical_dir.mkdir(parents=True)

    manifest = {
        "schema_version": "1.0",
        "exports": {
            "neo4j": {"nodes_csv": str(paths.capec_graph_neo4j_export_dir / "nodes.csv")},
            "gremlin": {"nodes_jsonl": str(paths.capec_graph_gremlin_export_dir / "nodes.jsonl")},
        },
    }
    manifest_path = canonical_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    schema = {
        "schema_version": "1.0",
        "dataset": "capec",
        "node_labels": ["AttackPattern", "Category"],
        "relationship_types": ["ChildOf", "MAPS_TO"],
        "relationship_natures": ["ChildOf"],
        "allowed_edge_patterns": {"ChildOf": [["AttackPattern", "AttackPattern"]]},
    }
    with open(canonical_dir / "schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f)

    _write_overlay(paths.source_registry_dir, "capec", _CAPEC_OVERLAY)
    return config, manifest_path


def test_attack_card_authored_sections_populated(tmp_path: Path) -> None:
    config, manifest_path = _make_attack_fixture(tmp_path)
    card = build_attack_source_card(config, manifest_path)
    assert card.connection, "connection section must be non-empty"
    assert card.safety, "safety section must be non-empty"
    assert card.provenance, "provenance section must be non-empty"


def test_attack_card_no_literal_secrets(tmp_path: Path) -> None:
    config, manifest_path = _make_attack_fixture(tmp_path)
    card_dict = build_attack_source_card(config, manifest_path).to_dict()
    _assert_no_literal_secrets(card_dict)


def test_attack_card_connection_has_required_fields(tmp_path: Path) -> None:
    config, manifest_path = _make_attack_fixture(tmp_path)
    conn = build_attack_source_card(config, manifest_path).connection
    assert conn.get("backend") == "neo4j"
    assert "uri" in conn
    assert conn.get("read_only") is True


def test_attack_card_safety_has_disallowed_clauses(tmp_path: Path) -> None:
    config, manifest_path = _make_attack_fixture(tmp_path)
    safety = build_attack_source_card(config, manifest_path).safety
    assert "disallowed_clauses" in safety
    assert "CREATE" in safety["disallowed_clauses"]


def test_capec_card_authored_sections_populated(tmp_path: Path) -> None:
    config, manifest_path = _make_capec_fixture(tmp_path)
    card = build_capec_source_card(config, manifest_path)
    assert card.connection, "connection section must be non-empty"
    assert card.safety, "safety section must be non-empty"
    assert card.provenance, "provenance section must be non-empty"


def test_capec_card_no_literal_secrets(tmp_path: Path) -> None:
    config, manifest_path = _make_capec_fixture(tmp_path)
    card_dict = build_capec_source_card(config, manifest_path).to_dict()
    _assert_no_literal_secrets(card_dict)


def test_capec_card_safety_merges_schema_constraints(tmp_path: Path) -> None:
    config, manifest_path = _make_capec_fixture(tmp_path)
    safety = build_capec_source_card(config, manifest_path).safety
    assert "allowed_edge_patterns" in safety, "allowed_edge_patterns must be merged from schema"
    assert "relationship_natures" in safety, "relationship_natures must be merged from schema"
    assert "ChildOf" in safety["allowed_edge_patterns"]


def test_capec_card_connection_has_required_fields(tmp_path: Path) -> None:
    config, manifest_path = _make_capec_fixture(tmp_path)
    conn = build_capec_source_card(config, manifest_path).connection
    assert conn.get("backend") == "gremlin"
    assert "uri" in conn
    assert conn.get("read_only") is True


def test_overlay_absent_yields_empty_authored_sections(tmp_path: Path) -> None:
    """Overlay absence must degrade gracefully to empty dicts, not raise."""
    config = BuildConfig.from_data_dir(tmp_path)
    paths = config.paths()
    canonical_dir = paths.graph_canonical_dir
    canonical_dir.mkdir(parents=True)

    manifest = {"schema_version": "1.0", "exports": {"neo4j": {}, "gremlin": {}}}
    manifest_path = canonical_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    schema = {"schema_version": "1.0", "node_labels": [], "relationship_types": []}
    with open(canonical_dir / "schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f)

    # No overlay written — should not raise
    card = build_attack_source_card(config, manifest_path)
    assert card.connection == {}
    assert card.safety == {}
    assert card.provenance == {}
    assert card.entity_descriptions == {}


def test_rebuild_does_not_erase_authored_values(tmp_path: Path) -> None:
    """Writing the card twice must preserve authored sections from the overlay."""
    config, manifest_path = _make_attack_fixture(tmp_path)
    paths = config.paths()

    card_path = write_attack_source_card(config, manifest_path)
    first_written = json.loads(card_path.read_text())

    card_path2 = write_attack_source_card(config, manifest_path)
    second_written = json.loads(card_path2.read_text())

    assert first_written["connection"] == second_written["connection"]
    assert first_written["provenance"] == second_written["provenance"]
    assert first_written["safety"] == second_written["safety"]
