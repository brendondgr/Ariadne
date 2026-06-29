#!/usr/bin/env python3
"""Unit and live-integration tests for the CAPEC Gremlin specialist.

Unit tests use a fake (stub) connector; the live test connects to the Docker
Gremlin server and is skipped when unavailable.
"""

from __future__ import annotations

from typing import Any

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.evidence import check_contract
from utils.specialists.tests._fixtures import fixture_card
from utils.specialists.gremlin.builder import GremlinQueryBuilder
from utils.specialists.gremlin.normalizer import GremlinNormalizer
from utils.specialists.gremlin.specialist import build_gremlin_specialist
from utils.specialists.gremlin.validator import GremlinValidator
from utils.specialists.base import QuerySpecialist


# ---------------------------------------------------------------------------
# Fake connector helpers
# ---------------------------------------------------------------------------

class FakeConnector:
    """Minimal Connector protocol implementation backed by canned rows."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.connected = False
        self.closed = False

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.closed = True

    def run(self, query: str, params: dict, limits: dict) -> list[dict]:
        return list(self._rows)


# ---------------------------------------------------------------------------
# Fake elementMap-shaped rows (mimicking gremlin_python T enum keys)
# ---------------------------------------------------------------------------

try:
    from gremlin_python.process.traversal import T as GremlinT
    _T_ID = GremlinT.id
    _T_LABEL = GremlinT.label
except Exception:
    _T_ID = None
    _T_LABEL = None


def _ap_row(n: int, name: str) -> dict[str, Any]:
    """Build a fake single elementMap row for AttackPattern CAPEC-N."""
    row: dict[str, Any] = {
        "id": f"capec:attack-pattern:{n}",
        "name": name,
        "Abstraction": "Standard",
        "Status": "Draft",
    }
    if _T_ID is not None:
        row[_T_ID] = 10000 + n
    if _T_LABEL is not None:
        row[_T_LABEL] = "AttackPattern"
    else:
        row["label"] = "AttackPattern"
    return row


def _weakness_row(cwe_num: int) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": f"cwe:{cwe_num}",
        "name": f"CWE-{cwe_num}",
        "cwe_id": str(cwe_num),
    }
    if _T_ID is not None:
        row[_T_ID] = 20000 + cwe_num
    if _T_LABEL is not None:
        row[_T_LABEL] = "Weakness"
    else:
        row["label"] = "Weakness"
    return row


def _tax_row(entry_id: str, taxonomy_name: str = "ATTACK") -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": f"capec:taxonomy:{taxonomy_name}:{entry_id}",
        "name": f"T{entry_id}" if taxonomy_name == "ATTACK" else entry_id,
        "entry_id": entry_id,
        "entry_name": f"T{entry_id}",
        "taxonomy_name": taxonomy_name,
    }
    if _T_ID is not None:
        row[_T_ID] = 30000
    if _T_LABEL is not None:
        row[_T_LABEL] = "TaxonomyEntry"
    else:
        row["label"] = "TaxonomyEntry"
    return row


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def card():
    return fixture_card("capec")


@pytest.fixture()
def limits():
    return {
        "max_traversal_depth": 3,
        "max_result_rows": 1000,
        "query_timeout_ms": 5000,
    }


def _make_task(**overrides: Any) -> SpecialistTask:
    base = dict(
        sub_question_id="q-capec-1",
        source="capec",
        text="What weaknesses does CAPEC-66 exploit?",
        entities=("AttackPattern", "Weakness", "EXPLOITS_WEAKNESS"),
        limits={
            "max_traversal_depth": 3,
            "max_result_rows": 100,
            "query_timeout_ms": 5000,
        },
        join_key=None,
        seed_ids=("CAPEC-66",),
    )
    base.update(overrides)
    return SpecialistTask(**base)  # type: ignore[arg-type]


def _make_maps_to_task(**overrides: Any) -> SpecialistTask:
    base = dict(
        sub_question_id="q-capec-2",
        source="capec",
        text="Which ATT&CK techniques does CAPEC-1 map to?",
        entities=("AttackPattern", "TaxonomyEntry", "MAPS_TO"),
        limits={
            "max_traversal_depth": 3,
            "max_result_rows": 100,
            "query_timeout_ms": 5000,
        },
        join_key="attack-technique-id",
        seed_ids=("CAPEC-1",),
    )
    base.update(overrides)
    return SpecialistTask(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Unit tests — CAPEC-N derivation
# ---------------------------------------------------------------------------

class TestCAPECIdDerivation:
    def test_derives_capec_n_from_gremlin_id(self):
        from utils.specialists.gremlin.normalizer import _primary_id_from_gremlin_id
        assert _primary_id_from_gremlin_id("capec:attack-pattern:66") == "CAPEC-66"
        assert _primary_id_from_gremlin_id("capec:attack-pattern:100") == "CAPEC-100"

    def test_fallback_for_non_pattern(self):
        from utils.specialists.gremlin.normalizer import _primary_id_from_gremlin_id
        assert _primary_id_from_gremlin_id("cwe:89") == "cwe:89"


# ---------------------------------------------------------------------------
# Unit tests — normalizer with canned rows
# ---------------------------------------------------------------------------

class TestNormalizerSingle:
    def test_lookup_rows_produce_records(self, card):
        rows = [_ap_row(66, "SQL Injection"), _ap_row(1, "Accessing Functionality")]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="fake_query", card=card)  # type: ignore[arg-type]
        assert len(records) == 2
        ids = {r.primary_id for r in records}
        assert "CAPEC-66" in ids
        assert "CAPEC-1" in ids

    def test_contract_passes_on_lookup(self, card):
        rows = [_ap_row(66, "SQL Injection")]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="g.V().elementMap().limit(10)", card=card)  # type: ignore[arg-type]
        violations = check_contract(records)
        assert violations == [], violations

    def test_id_scheme_is_capec_id(self, card):
        rows = [_ap_row(66, "SQL Injection")]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert records[0].id_scheme == "capec-id"


class TestNormalizerNeighbors:
    def test_related_grouping(self, card):
        """Two weaknesses under CAPEC-66 should produce one record with two related entries."""
        rows = [
            {"ap": _ap_row(66, "SQL Injection"), "nbr": _weakness_row(89)},
            {"ap": _ap_row(66, "SQL Injection"), "nbr": _weakness_row(1286)},
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert len(records) == 1
        assert records[0].primary_id == "CAPEC-66"
        assert len(records[0].related) == 2
        related_ids = {r.get("id") for r in records[0].related}
        assert "cwe:89" in related_ids
        assert "cwe:1286" in related_ids

    def test_contract_passes_on_neighbors(self, card):
        rows = [
            {"ap": _ap_row(66, "SQL Injection"), "nbr": _weakness_row(89)},
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert check_contract(records) == []


class TestNormalizerMapsTo:
    def test_t_prefixed_join_values(self, card):
        """ATTACK taxonomy entry_id '1574.010' becomes 'T1574.010' in join_values."""
        rows = [
            {"ap": _ap_row(1, "Accessing Functionality"), "tax": _tax_row("1574.010", "ATTACK")},
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert len(records) == 1
        assert "T1574.010" in records[0].join_values

    def test_wasc_entries_not_in_join_values(self, card):
        """WASC taxonomy entries must NOT appear in join_values."""
        rows = [
            {"ap": _ap_row(66, "SQL Injection"), "tax": _tax_row("19", "WASC")},
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert len(records) == 1
        assert records[0].join_values == ()

    def test_contract_passes_on_maps_to(self, card):
        rows = [
            {"ap": _ap_row(1, "Accessing Functionality"), "tax": _tax_row("1574.010")},
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert check_contract(records) == []


# ---------------------------------------------------------------------------
# Unit tests — full specialist loop with fake connector
# ---------------------------------------------------------------------------

class TestSpecialistLoopFake:
    def _build_specialist(self, card, rows, template="capec_neighbors"):
        connector = FakeConnector(rows)
        specialist = QuerySpecialist(
            card=card,
            builder=GremlinQueryBuilder(),
            validator=GremlinValidator(),
            connector=connector,
            normalizer=GremlinNormalizer(),
            max_retries=1,
        )
        return specialist, connector

    def test_neighbor_task_succeeds(self, card):
        rows = [
            {"ap": _ap_row(66, "SQL Injection"), "nbr": _weakness_row(89)},
            {"ap": _ap_row(66, "SQL Injection"), "nbr": _weakness_row(1286)},
        ]
        specialist, connector = self._build_specialist(card, rows)
        task = _make_task()
        result = specialist.run(task)
        assert result.ok, f"errors: {result.error}; traces: {result.traces}"
        assert len(result.records) == 1
        assert result.records[0].primary_id == "CAPEC-66"
        assert len(result.records[0].related) == 2
        assert connector.connected
        assert connector.closed

    def test_maps_to_task_join_values(self, card):
        rows = [
            {"ap": _ap_row(1, "Accessing Functionality"), "tax": _tax_row("1574.010")},
        ]
        specialist, _ = self._build_specialist(card, rows)
        task = _make_maps_to_task()
        result = specialist.run(task)
        assert result.ok, result.error
        assert any("T1574.010" in r.join_values for r in result.records)

    def test_lookup_task_produces_records(self, card):
        rows = [_ap_row(66, "SQL Injection")]
        connector = FakeConnector(rows)
        specialist = QuerySpecialist(
            card=card,
            builder=GremlinQueryBuilder(),
            validator=GremlinValidator(),
            connector=connector,
            normalizer=GremlinNormalizer(),
            max_retries=1,
        )
        task = _make_task(
            entities=("AttackPattern",),
            seed_ids=("CAPEC-66",),
        )
        result = specialist.run(task)
        assert result.ok, result.error
        assert result.records[0].primary_id == "CAPEC-66"

    def test_wrong_source_fails(self, card):
        rows = []
        specialist, _ = self._build_specialist(card, rows)
        task = _make_task(source="attack")
        result = specialist.run(task)
        assert not result.ok
        assert result.error is not None


# ---------------------------------------------------------------------------
# Live integration test (skip if Gremlin unreachable)
# ---------------------------------------------------------------------------

def _gremlin_reachable(uri: str = "ws://localhost:6455/gremlin") -> bool:
    try:
        from gremlin_python.driver import client as gc
        from gremlin_python.driver.serializer import GraphSONSerializersV3d0
        c = gc.Client(uri, "g", message_serializer=GraphSONSerializersV3d0())
        c.submit("g.V().limit(1)").all().result(timeout=3)
        c.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def live_card():
    from utils.config import load_env
    load_env()
    from utils.planner.cards import load_source_cards
    cards = load_source_cards("data")
    return cards["capec"]


@pytest.fixture(scope="module")
def live_config():
    from utils.config import load_env
    load_env()
    from utils.specialists.config import SpecialistConfig
    return SpecialistConfig.from_env()


@pytest.mark.live
class TestLiveGremlin:
    """Live tests against the Docker Gremlin stack — skipped when unreachable."""

    def _skip_if_unavailable(self, config):
        uri = config.endpoint_for("gremlin")
        if not _gremlin_reachable(uri):
            pytest.skip(f"Gremlin not reachable at {uri}")

    def test_capec66_exploits_weakness(self, live_card, live_config):
        """CAPEC-66 EXPLOITS_WEAKNESS should return CWE-89 and CWE-1286."""
        self._skip_if_unavailable(live_config)
        specialist = build_gremlin_specialist(live_card, live_config)
        task = SpecialistTask(
            sub_question_id="live-q1",
            source="capec",
            text="What weaknesses does CAPEC-66 exploit?",
            entities=("AttackPattern", "Weakness", "EXPLOITS_WEAKNESS"),
            limits={
                "max_traversal_depth": 3,
                "max_result_rows": 50,
                "query_timeout_ms": 8000,
            },
            join_key=None,
            seed_ids=("CAPEC-66",),
        )
        result = specialist.run(task)
        assert result.ok, f"error: {result.error}\ntraces: {result.traces}"
        assert result.records, "expected at least one record"

        # CAPEC-66 must be the anchor.
        capec_ids = {r.primary_id for r in result.records}
        assert "CAPEC-66" in capec_ids

        # The two known weaknesses should appear in related.
        all_related_ids = {
            rel.get("id") for rec in result.records for rel in rec.related
        }
        assert "cwe:89" in all_related_ids, f"expected CWE-89, got {all_related_ids}"
        assert "cwe:1286" in all_related_ids, f"expected CWE-1286, got {all_related_ids}"

        # Contract must pass.
        assert check_contract(result.records) == []

    def test_capec1_maps_to_attack(self, live_card, live_config):
        """CAPEC-1 MAPS_TO should return at least one T-prefixed join value."""
        self._skip_if_unavailable(live_config)
        specialist = build_gremlin_specialist(live_card, live_config)
        task = SpecialistTask(
            sub_question_id="live-q2",
            source="capec",
            text="Which ATT&CK techniques does CAPEC-1 map to?",
            entities=("AttackPattern", "TaxonomyEntry", "MAPS_TO"),
            limits={
                "max_traversal_depth": 3,
                "max_result_rows": 50,
                "query_timeout_ms": 8000,
            },
            join_key="attack-technique-id",
            seed_ids=("CAPEC-1",),
        )
        result = specialist.run(task)
        assert result.ok, f"error: {result.error}\ntraces: {result.traces}"
        assert result.records, "expected at least one record"

        all_join_values = [v for r in result.records for v in r.join_values]
        # T1574.010 is the confirmed mapping for CAPEC-1.
        assert any(jv.startswith("T") for jv in all_join_values), (
            f"expected T-prefixed join values, got: {all_join_values}"
        )
        assert "T1574.010" in all_join_values, (
            f"expected T1574.010 in join values, got: {all_join_values}"
        )

        # Contract must pass.
        assert check_contract(result.records) == []
