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
        # Neighbour ids are canonicalised like the anchor's — a raw ``cwe:89``
        # matches no gold assertion and reads as a different entity downstream.
        related_ids = {r.get("id") for r in records[0].related}
        assert "CWE-89" in related_ids
        assert "CWE-1286" in related_ids

    def test_contract_passes_on_neighbors(self, card):
        rows = [
            {"ap": _ap_row(66, "SQL Injection"), "nbr": _weakness_row(89)},
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert check_contract(records) == []


class TestNormalizerHierarchy:
    def test_ancestors_carry_role_name_and_abstraction(self, card):
        """Walk-up rows must keep parent=standard / grandparent=meta roles, not
        flatten both to bare ids (the C-ABS defect)."""
        gp = _ap_row(248, "Command Injection")
        gp["Abstraction"] = "Meta"
        rows = [{
            "ap": _ap_row(7, "Blind SQL Injection"),
            "parent": _ap_row(66, "SQL Injection"),   # Abstraction=Standard
            "grandparent": gp,                          # Abstraction=Meta
        }]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert len(records) == 1
        rel = {r["id"]: r for r in records[0].related}
        assert rel["CAPEC-66"]["role"] == "standard"
        assert rel["CAPEC-66"]["name"] == "SQL Injection"
        assert rel["CAPEC-66"]["abstraction"] == "Standard"
        assert rel["CAPEC-248"]["role"] == "meta"
        assert rel["CAPEC-248"]["abstraction"] == "Meta"

    def test_contract_passes_on_hierarchy(self, card):
        rows = [{
            "ap": _ap_row(7, "Blind SQL Injection"),
            "parent": _ap_row(66, "SQL Injection"),
            "grandparent": _ap_row(248, "Command Injection"),
        }]
        records = GremlinNormalizer().normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
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
        assert "CWE-89" in all_related_ids, f"expected CWE-89, got {all_related_ids}"
        assert "CWE-1286" in all_related_ids, f"expected CWE-1286, got {all_related_ids}"

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


# ---------------------------------------------------------------------------
# NEW templates — routing, normalizer, non-regression
# ---------------------------------------------------------------------------

# -- Helpers ------------------------------------------------------------------

def _make_resolved(task: SpecialistTask, *, join_endpoint: Any = None) -> Any:
    """Build a ResolvedTask directly for routing tests (no live card needed)."""
    from utils.specialists.resolve import ResolvedTask
    return ResolvedTask(
        task=task,
        dataset="capec",
        seed_ids=task.seed_ids,
        join_key=task.join_key,
        join_endpoint=join_endpoint,
    )


def _fake_join_endpoint():
    """Return a truthy sentinel so has_join evaluates True."""
    class _EP:
        dataset = "capec"
    return _EP()


# -- Template: capec_facets (native multi-facet expansion) --------------------

class TestCapecFacets:
    """A CAPEC anchor's own edges answer the question — no cross-source bridge."""

    def _resolved(self, *, relationships, entities, labels=(), join_key="attack-technique-id"):
        from utils.specialists.resolve import ResolvedTask

        task = SpecialistTask(
            sub_question_id="q-facets",
            source="capec",
            text="Explain the mitigations and weaknesses of CAPEC-459.",
            entities=tuple(entities),
            join_key=join_key,
            seed_ids=("CAPEC-459",),
        )
        return ResolvedTask(
            task=task, dataset="capec", seed_ids=("CAPEC-459",),
            relationships=tuple(relationships), labels=tuple(labels),
            join_key=join_key, join_endpoint=_fake_join_endpoint(),
        )

    def test_multi_native_facet_beats_spurious_join(self):
        """Regression: 'mitigations and weaknesses of CAPEC-459' expanded both native
        edges instead of bridging to ATT&CK (which had no MAPS_TO edge → 0 records)."""
        resolved = self._resolved(
            relationships=("EXPLOITS_WEAKNESS", "HAS_MITIGATION"),
            entities=("EXPLOITS_WEAKNESS", "HAS_MITIGATION", "Mitigation"),
            labels=("Mitigation",),
        )
        draft = GremlinQueryBuilder().build(resolved)
        assert draft.template == "capec_facets"
        assert 'out("EXPLOITS_WEAKNESS")' in draft.query
        assert 'out("HAS_MITIGATION")' in draft.query
        assert ".union(" in draft.query and "MAPS_TO" not in draft.query

    def test_mapping_intent_still_routes_to_maps_to(self):
        """A genuine bridge question (names MAPS_TO/TaxonomyEntry) keeps the join."""
        resolved = self._resolved(
            relationships=("HAS_MITIGATION", "MAPS_TO"),
            entities=("AttackPattern", "HAS_MITIGATION", "MAPS_TO", "Mitigation", "TaxonomyEntry"),
            labels=("AttackPattern", "Mitigation", "TaxonomyEntry"),
        )
        draft = GremlinQueryBuilder().build(resolved)
        assert draft.template == "capec_maps_to"

    def test_label_only_request_maps_to_native_edge(self):
        """A plan that named only the neighbour label ('Mitigation') still expands
        the native HAS_MITIGATION edge (single facet -> capec_neighbors)."""
        resolved = self._resolved(
            relationships=(), entities=("Mitigation",), labels=("Mitigation",), join_key=None,
        )
        draft = GremlinQueryBuilder().build(resolved)
        assert draft.template == "capec_neighbors"
        assert 'out("HAS_MITIGATION")' in draft.query

    def test_capec_facets_passes_validator(self, card):
        resolved = self._resolved(
            relationships=("EXPLOITS_WEAKNESS", "HAS_MITIGATION"),
            entities=("EXPLOITS_WEAKNESS", "HAS_MITIGATION", "Mitigation"),
            labels=("Mitigation",),
        )
        draft = GremlinQueryBuilder().build(resolved)
        validator = GremlinValidator()
        reasons = (
            validator.structural_reasons(draft.query)
            + validator.violates_read_only(draft.query, card)
            + validator.schema_reasons(draft.query, card)
        )
        assert reasons == [], f"validator rejected: {reasons}"


# -- Template: capec_hierarchy_chain -----------------------------------------

class TestCapecHierarchyChain:
    """Two ChildOf entities in task.entities + seeds → capec_hierarchy_chain."""

    def _hierarchy_task(self, **overrides: Any) -> SpecialistTask:
        base = dict(
            sub_question_id="q-hier-1",
            source="capec",
            text="What is the parent and grandparent of CAPEC-66?",
            entities=("AttackPattern", "ChildOf", "ChildOf"),
            limits={"max_traversal_depth": 3, "max_result_rows": 50, "query_timeout_ms": 5000},
            join_key=None,
            seed_ids=("CAPEC-66",),
        )
        base.update(overrides)
        return SpecialistTask(**base)  # type: ignore[arg-type]

    def test_routes_to_hierarchy_chain(self):
        task = self._hierarchy_task()
        resolved = _make_resolved(task)
        builder = GremlinQueryBuilder()
        draft = builder.build(resolved)
        assert draft.template == "capec_hierarchy_chain"

    def test_query_contains_two_childof_hops(self):
        from utils.graph_loader.stores.gremlin import gremlin_edge_label
        child_of_edge = gremlin_edge_label("ChildOf")
        task = self._hierarchy_task()
        resolved = _make_resolved(task)
        draft = GremlinQueryBuilder().build(resolved)
        assert draft.query.count(f'.out("{child_of_edge}")') == 2
        assert '"ap"' in draft.query
        assert '"parent"' in draft.query
        assert '"grandparent"' in draft.query

    def test_query_passes_validator(self, card):
        task = self._hierarchy_task()
        resolved = _make_resolved(task)
        draft = GremlinQueryBuilder().build(resolved)
        validator = GremlinValidator()
        reasons = (
            validator.structural_reasons(draft.query)
            + validator.violates_read_only(draft.query, card)
            + validator.schema_reasons(draft.query, card)
        )
        assert reasons == [], f"validator rejected: {reasons}"

    def test_normalizer_hierarchy_rows(self, card):
        """Rows with ap/parent/grandparent → one record with two related entries."""
        rows = [
            {
                "ap": _ap_row(66, "SQL Injection"),
                "parent": _ap_row(100, "Overflow Buffers"),
                "grandparent": _ap_row(92, "Forced Integer Overflow"),
            },
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert len(records) == 1
        rec = records[0]
        assert rec.primary_id == "CAPEC-66"
        related_ids = {r["id"] for r in rec.related}
        assert "CAPEC-100" in related_ids
        assert "CAPEC-92" in related_ids
        assert rec.join_values == ()

    def test_normalizer_hierarchy_deduplicates_ancestors(self, card):
        """Same parent/grandparent across two rows should not duplicate related."""
        rows = [
            {
                "ap": _ap_row(66, "SQL Injection"),
                "parent": _ap_row(100, "Overflow Buffers"),
                "grandparent": _ap_row(92, "Forced Integer Overflow"),
            },
            {
                "ap": _ap_row(66, "SQL Injection"),
                "parent": _ap_row(100, "Overflow Buffers"),
                "grandparent": _ap_row(92, "Forced Integer Overflow"),
            },
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert len(records) == 1
        assert len(records[0].related) == 2

    def test_normalizer_hierarchy_contract(self, card):
        rows = [
            {
                "ap": _ap_row(66, "SQL Injection"),
                "parent": _ap_row(100, "Overflow Buffers"),
                "grandparent": _ap_row(92, "Forced Integer Overflow"),
            },
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert check_contract(records) == []


# -- Template: cwe_chain ------------------------------------------------------

class TestCweChain:
    """CWE-seeded + join_key → cwe_chain."""

    def _cwe_task(self, **overrides: Any) -> SpecialistTask:
        base = dict(
            sub_question_id="q-cwe-1",
            source="capec",
            text="Which ATT&CK techniques exploit CWE-89?",
            entities=("Weakness", "AttackPattern", "TaxonomyEntry", "EXPLOITS_WEAKNESS", "MAPS_TO"),
            limits={"max_traversal_depth": 3, "max_result_rows": 50, "query_timeout_ms": 5000},
            join_key="attack-technique-id",
            seed_ids=("CWE-89",),
        )
        base.update(overrides)
        return SpecialistTask(**base)  # type: ignore[arg-type]

    def test_routes_to_cwe_chain(self):
        task = self._cwe_task()
        resolved = _make_resolved(task, join_endpoint=_fake_join_endpoint())
        draft = GremlinQueryBuilder().build(resolved)
        assert draft.template == "cwe_chain"

    def test_cwe_id_converted_to_gremlin_form(self):
        task = self._cwe_task()
        resolved = _make_resolved(task, join_endpoint=_fake_join_endpoint())
        draft = GremlinQueryBuilder().build(resolved)
        assert "cweIds" in draft.params
        assert "cwe:89" in draft.params["cweIds"]

    def test_query_passes_validator(self, card):
        task = self._cwe_task()
        resolved = _make_resolved(task, join_endpoint=_fake_join_endpoint())
        draft = GremlinQueryBuilder().build(resolved)
        validator = GremlinValidator()
        reasons = (
            validator.structural_reasons(draft.query)
            + validator.violates_read_only(draft.query, card)
            + validator.schema_reasons(draft.query, card)
        )
        assert reasons == [], f"validator rejected: {reasons}"

    def test_normalizer_cwe_chain_rows(self, card):
        """Rows with w/ap/tax → one record per ap, related CWEs, T-prefixed join_values."""
        rows = [
            {
                "w": _weakness_row(89),
                "ap": _ap_row(66, "SQL Injection"),
                "tax": _tax_row("1190.001", "ATTACK"),
            },
            {
                "w": _weakness_row(89),
                "ap": _ap_row(66, "SQL Injection"),
                "tax": _tax_row("1059", "ATTACK"),
            },
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert len(records) == 1
        rec = records[0]
        assert rec.primary_id == "CAPEC-66"
        related_ids = {r["id"] for r in rec.related}
        assert "CWE-89" in related_ids
        assert "T1190.001" in rec.join_values
        assert "T1059" in rec.join_values

    def test_normalizer_cwe_chain_multiple_aps(self, card):
        """Multiple attack patterns under one CWE → one record each."""
        rows = [
            {
                "w": _weakness_row(89),
                "ap": _ap_row(66, "SQL Injection"),
                "tax": _tax_row("1190", "ATTACK"),
            },
            {
                "w": _weakness_row(89),
                "ap": _ap_row(110, "SQL Injection via SOAP Parameter Tampering"),
                "tax": _tax_row("1190", "ATTACK"),
            },
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert len(records) == 2
        primary_ids = {r.primary_id for r in records}
        assert "CAPEC-66" in primary_ids
        assert "CAPEC-110" in primary_ids

    def test_normalizer_cwe_chain_wasc_not_in_join_values(self, card):
        """WASC entries in tax must not produce join_values."""
        rows = [
            {
                "w": _weakness_row(89),
                "ap": _ap_row(66, "SQL Injection"),
                "tax": _tax_row("19", "WASC"),
            },
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert len(records) == 1
        assert records[0].join_values == ()

    def test_normalizer_cwe_chain_contract(self, card):
        rows = [
            {
                "w": _weakness_row(89),
                "ap": _ap_row(66, "SQL Injection"),
                "tax": _tax_row("1190", "ATTACK"),
            },
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert check_contract(records) == []


# -- Template: capec_reverse_maps ---------------------------------------------

class TestCapecReverseMaps:
    """T-prefixed seed + join_key → capec_reverse_maps; rows shape matches maps_to path."""

    def _reverse_task(self, **overrides: Any) -> SpecialistTask:
        base = dict(
            sub_question_id="q-rev-1",
            source="capec",
            text="Which CAPEC patterns map to T1190?",
            entities=("TaxonomyEntry", "AttackPattern", "MAPS_TO"),
            limits={"max_traversal_depth": 3, "max_result_rows": 50, "query_timeout_ms": 5000},
            join_key="attack-technique-id",
            seed_ids=("T1190",),
        )
        base.update(overrides)
        return SpecialistTask(**base)  # type: ignore[arg-type]

    def test_routes_to_capec_reverse_maps(self):
        task = self._reverse_task()
        resolved = _make_resolved(task, join_endpoint=_fake_join_endpoint())
        draft = GremlinQueryBuilder().build(resolved)
        assert draft.template == "capec_reverse_maps"

    def test_t_prefix_stripped_to_entry_id(self):
        task = self._reverse_task()
        resolved = _make_resolved(task, join_endpoint=_fake_join_endpoint())
        draft = GremlinQueryBuilder().build(resolved)
        assert "entryIds" in draft.params
        assert "1190" in draft.params["entryIds"]

    def test_subtechnique_seed_stripped_correctly(self):
        task = self._reverse_task(seed_ids=("T1574.010",))
        resolved = _make_resolved(task, join_endpoint=_fake_join_endpoint())
        draft = GremlinQueryBuilder().build(resolved)
        assert "1574.010" in draft.params["entryIds"]

    def test_query_passes_validator(self, card):
        task = self._reverse_task()
        resolved = _make_resolved(task, join_endpoint=_fake_join_endpoint())
        draft = GremlinQueryBuilder().build(resolved)
        validator = GremlinValidator()
        reasons = (
            validator.structural_reasons(draft.query)
            + validator.violates_read_only(draft.query, card)
            + validator.schema_reasons(draft.query, card)
        )
        assert reasons == [], f"validator rejected: {reasons}"

    def test_normalizer_reverse_maps_rows_use_maps_to_path(self, card):
        """Rows with ap+tax from capec_reverse_maps feed the existing maps_to normalizer."""
        rows = [
            {"ap": _ap_row(66, "SQL Injection"), "tax": _tax_row("1190", "ATTACK")},
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert len(records) == 1
        assert records[0].primary_id == "CAPEC-66"
        assert "T1190" in records[0].join_values

    def test_normalizer_reverse_maps_contract(self, card):
        rows = [
            {"ap": _ap_row(66, "SQL Injection"), "tax": _tax_row("1190", "ATTACK")},
        ]
        normalizer = GremlinNormalizer()
        records = normalizer.normalize(rows, resolved=None, query="q", card=card)  # type: ignore[arg-type]
        assert check_contract(records) == []


# -- Non-regression tests -----------------------------------------------------

class TestNonRegressionRouting:
    """Existing routes must not be displaced by the new branches."""

    def test_capec_seeded_maps_to_still_routes_capec_maps_to(self):
        """A CAPEC-seeded maps_to task routes capec_maps_to (not reverse or cwe)."""
        task = _make_maps_to_task()  # seed_ids=("CAPEC-1",), join_key="attack-technique-id"
        from utils.specialists.resolve import ResolvedTask
        resolved = ResolvedTask(
            task=task,
            dataset="capec",
            seed_ids=task.seed_ids,
            join_key=task.join_key,
            join_endpoint=_fake_join_endpoint(),
        )
        draft = GremlinQueryBuilder().build(resolved)
        assert draft.template == "capec_maps_to"

    def test_single_childof_neighbor_still_routes_capec_neighbors(self):
        """A task with exactly one ChildOf entity still routes capec_neighbors."""
        task = _make_task(
            entities=("AttackPattern", "ChildOf"),
            seed_ids=("CAPEC-66",),
            join_key=None,
        )
        from utils.specialists.resolve import ResolvedTask
        resolved = ResolvedTask(
            task=task,
            dataset="capec",
            seed_ids=task.seed_ids,
            relationships=("ChildOf",),
            join_key=None,
            join_endpoint=None,
        )
        draft = GremlinQueryBuilder().build(resolved)
        assert draft.template == "capec_neighbors"


# ---------------------------------------------------------------------------
# capec_dossier: single-entity deep dive (full node + typed 1-hop)
# ---------------------------------------------------------------------------


class TestCapecDossier:
    def test_routing_describe_on_describe_intent(self, card, limits):
        from utils.specialists.resolve import resolve

        task = _make_task(
            text="Tell me more about CAPEC-98.",
            entities=("AttackPattern",),
            join_key=None,
            seed_ids=("CAPEC-98",),
        )
        resolved = resolve(task, card)
        draft = GremlinQueryBuilder().build(resolved)
        assert draft.template == "describe"
        # A bare CAPEC number does not say which kind it names -- CAPEC-98 is an
        # attack pattern, CAPEC-118 a category, CAPEC-284 a view -- so the anchor
        # offers all three namespaces and lets the graph disambiguate. Asserting
        # the single attack-pattern id here was the contract that made every
        # View and Category question search for a vertex that does not exist.
        assert draft.params["ids"] == [
            "capec:attack-pattern:98",
            "capec:view:98",
            "capec:category:98",
        ]
        assert GremlinValidator().validate(draft, card, limits).ok

    def test_bare_seed_id_also_routes_to_describe(self, card):
        """A bare id lookup with no 'tell me about' verb still routes to describe.

        describe subsumes the old capec_lookup/capec_dossier split — there is
        no longer a "lean lookup vs rich dossier" distinction, so a bare id and
        a describe-verb id both take the same full-record path.
        """
        from utils.specialists.resolve import resolve

        task = _make_task(text="CAPEC-98", entities=("AttackPattern",), join_key=None, seed_ids=("CAPEC-98",))
        draft = GremlinQueryBuilder().build(resolve(task, card))
        assert draft.template == "describe"

    def test_normalizer_describe_builds_full_properties_and_facets(self, card):
        from utils.specialists.resolve import resolve

        rows = [
            {
                "node": {"id": "capec:attack-pattern:98", "label": "AttackPattern", "name": "Phishing",
                         "description": "A social engineering technique."},
                "out": [
                    {"rel": "CAN_PRECEDE", "label": "AttackPattern"},
                ],
                "in": [
                    {"rel": "CHILD_OF", "label": "AttackPattern"},
                ],
            }
        ]
        task = _make_task(text="Tell me more about CAPEC-98.", entities=("AttackPattern",), join_key=None, seed_ids=("CAPEC-98",))
        rec = GremlinNormalizer().normalize(rows, resolve(task, card), "FAKE", card)[0]
        assert rec.primary_id == "CAPEC-98"
        # properties carries the full parsed vertex — no allow-list.
        assert rec.properties["description"] == "A social engineering technique."
        assert "neighbor_total" not in rec.properties
        # facets carries the folded {rel, direction, label, count} block. The
        # registry also folds in the plausible-but-unobserved reverse-direction
        # facets as honest zeros, so key on (rel, direction) to grab the observed ones.
        by_rel = {(f["rel"], f["direction"]): f for f in rec.facets}
        assert by_rel[("CAN_PRECEDE", "out")]["label"] == "AttackPattern"
        assert by_rel[("CAN_PRECEDE", "out")]["count"] == 1
        assert by_rel[("CHILD_OF", "in")]["count"] == 1
        # describe returns facet counts, not individual neighbours.
        assert rec.related == []


# ---------------------------------------------------------------------------
# capec_dossier_by_name: seedless definitional name lookup ("What is Phishing?")
# ---------------------------------------------------------------------------


class TestCapecDossierByName:
    def test_routing_describe_by_name_on_definitional_question(self, card, limits):
        from utils.specialists.resolve import resolve

        # A name matching no catalogue entry, so this still exercises the regex
        # path the test is about. "Phishing" sat here until 2026-08-31 and now
        # resolves exactly to CAPEC-98, taking the by-id path — see
        # test_exact_name_takes_the_id_path below. Note the replacement must
        # contain no complete entity name at all: "Phishing Variant Alpha" still
        # resolves, because "Phishing" is itself a complete name inside it.
        task = _make_task(
            text="What is Marbled Lattice?",
            entities=(),
            join_key=None,
            seed_ids=(),
        )
        resolved = resolve(task, card)
        draft = GremlinQueryBuilder().build(resolved)
        assert draft.template == "describe_by_name"
        # Anchors AttackPattern by case-insensitive name, same describe projection.
        assert 'TextP.regex(' in draft.query
        assert '.project("node","out","in")' in draft.query
        assert GremlinValidator().validate(draft, card, limits).ok

    def test_exact_name_takes_the_id_path(self, card, limits):
        """An exactly-resolving name is anchored by id, not by substring.

        Measured 2026-08-31: the regex path returns **four** records for "What
        is Phishing?" — Phishing, Spear Phishing, Mobile Phishing and Voice
        Phishing — because the pattern matches any name containing the word.
        Resolving the name first returns the one entity that was asked about.
        """
        from utils.specialists.resolve import resolve

        task = _make_task(text="What is Phishing?", entities=(), join_key=None, seed_ids=())
        draft = GremlinQueryBuilder().build(resolve(task, card))
        assert draft.template == "describe"
        # Gremlin binds the canonical node id, not the analyst-facing spelling.
        assert "98" in str(draft.params.get("ids", ()))
        assert GremlinValidator().validate(draft, card, limits).ok

    def test_multiword_name_pattern_has_no_groovy_breaking_escape(self, card, limits):
        # A multi-word name must not embed backslash escapes: re.escape emits
        # '\ ' for the spaces, which the Gremlin server's Groovy parser rejects.
        # Non-alphanumerics become '.' wildcards, which still match the separator.
        from utils.specialists.resolve import resolve

        task = _make_task(text="What is Denial of Service?", entities=(), join_key=None, seed_ids=())
        draft = GremlinQueryBuilder().build(resolve(task, card))
        assert "\\" not in draft.query
        assert "(Denial.of.Service)" in draft.query
        assert GremlinValidator().validate(draft, card, limits).ok

    def test_name_dossier_row_normalizes_via_shape_dispatch(self, card):
        """A name-lookup dossier row (no seed) still keys on the node's own id."""
        from utils.specialists.resolve import resolve

        rows = [
            {
                "node": {"id": "capec:attack-pattern:98", "label": "AttackPattern",
                         "name": "Phishing", "description": "A social engineering technique."},
                "out": [],
                "in": [],
            }
        ]
        task = _make_task(text="What is Phishing?", entities=(), join_key=None, seed_ids=())
        rec = GremlinNormalizer().normalize(rows, resolve(task, card), "FAKE", card)[0]
        assert rec.primary_id == "CAPEC-98"
        assert rec.properties["description"] == "A social engineering technique."

    def test_seedless_non_definitional_still_scans(self, card):
        """A seedless question with no definitional intent keeps the bare scan."""
        from utils.specialists.resolve import resolve

        task = _make_task(
            text="List attack patterns", entities=("AttackPattern",), join_key=None, seed_ids=()
        )
        draft = GremlinQueryBuilder().build(resolve(task, card))
        assert draft.template == "capec_scan"


class TestCapecAnchorResolution:
    """CAPEC-284 is a View, and the anchor used to search for an AttackPattern.

    Two defects in one place. The visible one was ``hasLabel("AttackPattern")``
    on the anchor; the load-bearing one was `_capec_gremlin_id`, which turned
    ``CAPEC-284`` into ``capec:attack-pattern:284`` while the view is stored as
    ``capec:view:284``. Removing only the label filter would have left the lookup
    missing in exactly the same way.
    """

    def test_a_bare_capec_id_offers_every_namespace_it_could_name(self):
        from utils.specialists.gremlin.builder import _capec_candidate_ids

        assert _capec_candidate_ids(["CAPEC-284"]) == [
            "capec:attack-pattern:284",
            "capec:view:284",
            "capec:category:284",
        ]

    def test_a_cwe_id_is_never_a_candidate(self):
        """cwe:284 sits beside capec:view:284 in the same store.

        Resolving by number alone would let a question about CAPEC-284 be
        answered by an unrelated weakness that happens to share its number.
        """
        from utils.specialists.gremlin.builder import _capec_candidate_ids

        assert not any("cwe:" in c for c in _capec_candidate_ids(["CAPEC-284"]))

    def test_ids_already_in_urn_form_pass_through(self):
        from utils.specialists.gremlin.builder import _capec_candidate_ids

        assert _capec_candidate_ids(["capec:view:284"]) == ["capec:view:284"]

    def test_duplicate_seeds_do_not_duplicate_candidates(self):
        from utils.specialists.gremlin.builder import _capec_candidate_ids

        assert len(_capec_candidate_ids(["CAPEC-98", "CAPEC-98"])) == 3

    def test_the_seeded_describe_anchor_carries_no_label_filter(self, card):
        """Identity is the id, which is unique store-wide.

        A label on this anchor cannot add precision and can only exclude the
        right vertex.
        """
        from utils.specialists.resolve import resolve

        task = _make_task(
            text="What kind of CAPEC view is CAPEC-284?",
            entities=("View",),
            join_key=None,
            seed_ids=("CAPEC-284",),
        )
        draft = GremlinQueryBuilder().build(resolve(task, card))
        assert draft.template == "describe"
        assert 'hasLabel("AttackPattern")' not in draft.query
        assert 'g.V().has("id", within(ids))' in draft.query
        assert "capec:view:284" in draft.params["ids"]

    def test_the_label_free_anchor_still_declares_what_it_binds(self, card):
        """Without the declaration the binding audit calls the draft unchecked.

        Dropping hasLabel is invisible to the Gremlin binding parser, and an
        unchecked draft is one that filters on values nothing verified.
        """
        from utils.specialists.binding import extract_bindings
        from utils.specialists.resolve import resolve

        task = _make_task(
            text="What kind of CAPEC view is CAPEC-284?",
            entities=("View",),
            join_key=None,
            seed_ids=("CAPEC-284",),
        )
        draft = GremlinQueryBuilder().build(resolve(task, card))
        bindings = extract_bindings(draft)
        assert bindings, "a label-free anchor must declare its bindings"
        assert {b.label for b in bindings} == {"AttackPattern", "View", "Category"}
        assert {b.property for b in bindings} == {"id"}

    def test_the_name_anchored_describe_reaches_views_and_categories(self, card):
        """With no id the label IS the scope, so it is widened, not dropped."""
        from utils.specialists.resolve import resolve

        task = _make_task(
            text='What is "Detailed Abstractions"?',
            entities=("View",),
            join_key=None,
            seed_ids=(),
        )
        draft = GremlinQueryBuilder().build(resolve(task, card))
        if draft.template == "describe_by_name":
            for kind in ("AttackPattern", "View", "Category"):
                assert f'"{kind}"' in draft.query

    def test_the_weakness_and_taxonomy_anchors_are_untouched(self, card):
        """_cwe_chain and _capec_reverse_maps anchor elsewhere on purpose."""
        import inspect

        from utils.specialists.gremlin import builder as mod

        for fn in (mod.GremlinQueryBuilder._cwe_chain,
                   mod.GremlinQueryBuilder._capec_reverse_maps):
            src = inspect.getsource(fn)
            assert 'hasLabel("Weakness")' in src or 'hasLabel("TaxonomyEntry")' in src


class TestContainmentRouting:
    """A containment question used to fall through to ``describe``.

    ``_resolve_neighbor_rels`` knew only the seven edges that leave an
    AttackPattern, so a Category's own membership edge was invisible: asked what
    CAPEC-156 contains, the system described the category and reported its
    status. The bank asks in the source's vocabulary (``HAS_MEMBER``, container
    to member) while the graph stores ``MEMBER_OF`` and ``IN_VIEW`` running
    member to container -- same edge, opposite convention, and ``HAS_MEMBER``
    exists nowhere in the graph.
    """

    def _draft(self, entities, seeds):
        from pathlib import Path

        from utils.planner.cards import load_source_cards
        from utils.specialists.resolve import resolve

        card = load_source_cards(Path("data"))["capec"]
        task = SpecialistTask(sub_question_id="q1", source="capec", text="q",
                              entities=entities, seed_ids=seeds)
        return GremlinQueryBuilder().build(resolve(task, card))

    def test_a_category_question_traverses_member_of_inward(self):
        d = self._draft(("Category", "MEMBER_OF", "AttackPattern"), ("CAPEC-156",))
        assert d.template == "capec_neighbors"
        assert (d.meta["rel"], d.meta["direction"]) == ("MEMBER_OF", "in")

    def test_a_view_question_traverses_in_view_inward(self):
        # The container's kind picks the edge: a View's membership is IN_VIEW.
        d = self._draft(("View", "MEMBER_OF", "Category"), ("CAPEC-1000",))
        assert (d.meta["rel"], d.meta["direction"]) == ("IN_VIEW", "in")

    def test_the_same_edge_read_from_the_member_reverses(self):
        d = self._draft(("AttackPattern", "MEMBER_OF", "View"), ("CAPEC-580",))
        assert (d.meta["rel"], d.meta["direction"]) == ("IN_VIEW", "out")
        d = self._draft(("AttackPattern", "MEMBER_OF", "Category"), ("CAPEC-66",))
        assert (d.meta["rel"], d.meta["direction"]) == ("MEMBER_OF", "out")

    def test_containment_carries_no_target_label(self):
        """_REL_TARGET_LABEL maps MEMBER_OF to Category.

        Applied when reading the edge from the container's side it filtered the
        members -- which are AttackPatterns -- down to Categories, and returned
        nothing. A View's members are both kinds in any case, so no single label
        is correct here.
        """
        d = self._draft(("Category", "MEMBER_OF", "AttackPattern"), ("CAPEC-156",))
        assert "hasLabel(" not in d.query
        assert '.in("MEMBER_OF")' in d.query

    def test_a_plain_lookup_still_describes(self):
        assert self._draft(("AttackPattern",), ("CAPEC-98",)).template == "describe"

    def test_a_compound_question_is_not_captured_by_its_second_hop(self):
        """"Peers of CAPEC-12, and what categories contain each of those?"

        Names ``('PeerOf', 'MEMBER_OF')``. Routing on the containment hop
        answers the wrong one, and it measurably did: 0.3333 through describe,
        0.0000 through the containment traversal, because CAPEC-12 is in no
        category and the peers were never fetched.
        """
        d = self._draft(("AttackPattern", "PeerOf", "MEMBER_OF", "Category"), ("CAPEC-12",))
        assert d.template == "describe"

    def test_containment_still_routes_when_it_is_the_only_relation(self):
        d = self._draft(("Category", "MEMBER_OF", "AttackPattern"), ("CAPEC-156",))
        assert d.template == "capec_neighbors"

    def test_an_undeterminable_direction_falls_through_rather_than_guessing(self):
        # The membership edge is named but no end identifies a container, so
        # there is no edge to choose and no direction to read it in. describe is
        # the honest outcome; a fixed ".out" would have been a guess.
        d = self._draft(("AttackPattern", "MEMBER_OF"), ("CAPEC-66",))
        assert d.template == "describe"

    def test_a_named_facet_still_wins_when_containment_is_unresolvable(self):
        # Weakness maps to EXPLOITS_WEAKNESS, which is a real AttackPattern
        # facet, so this must keep routing there rather than being swallowed.
        d = self._draft(("AttackPattern", "MEMBER_OF", "Weakness"), ("CAPEC-66",))
        assert (d.meta["rel"], d.meta["direction"]) == ("EXPLOITS_WEAKNESS", "out")
