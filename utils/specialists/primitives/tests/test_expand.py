#!/usr/bin/env python3
"""Tests for the ``expand`` primitive: paged, identity-only, honest about truncation.

The rule under test is **never truncate silently**: every result carries the real
total and an explicit truncated flag. A small facet returns all its members
untruncated; an oversized facet returns one page, ``truncated=True`` and the true
``total`` — never a bare short list.
"""

from __future__ import annotations

from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.cypher.normalizer import CypherNormalizer
from utils.specialists.gremlin.builder import GremlinQueryBuilder
from utils.specialists.gremlin.normalizer import GremlinNormalizer
from utils.specialists.primitives.expand import ExpandRequest, paginate


def _req(**kw) -> ExpandRequest:
    base = dict(
        dataset="attack", anchor_id="T1059", anchor_label="Technique",
        rel_type="HAS_SUBTECHNIQUE", direction="out", target_label="SubTechnique",
    )
    base.update(kw)
    return ExpandRequest(**base)


def _members(n: int) -> list[dict]:
    return [{"id": f"T1059.{i:03d}", "name": f"sub {i}", "label": "SubTechnique"} for i in range(n)]


# -- paginate() pure function ------------------------------------------------


def test_small_facet_returns_all_members_untruncated() -> None:
    result = paginate(_members(3), _req(page=0, page_size=50))
    assert result.total == 3
    assert len(result.members) == 3
    assert result.truncated is False


def test_oversized_facet_pages_and_flags_truncation() -> None:
    result = paginate(_members(858), _req(page=0, page_size=50))
    assert result.total == 858            # the honest total, not the page size
    assert len(result.members) == 50
    assert result.truncated is True
    assert result.members[0]["id"] == "T1059.000"


def test_last_page_is_not_truncated() -> None:
    result = paginate(_members(13), _req(page=2, page_size=5))
    assert result.total == 13
    assert len(result.members) == 3        # members 10, 11, 12
    assert result.truncated is False


def test_pre_sliced_server_page_keeps_the_true_total() -> None:
    # The Cypher backend slices server-side and hands back the page + true total.
    page = _members(50)
    result = paginate(page, _req(page=0, page_size=50), total=858, pre_sliced=True)
    assert result.total == 858 and len(result.members) == 50 and result.truncated is True


def test_request_skip_end_and_dict() -> None:
    r = _req(page=3, page_size=25)
    assert r.skip() == 75 and r.end() == 100
    assert r.to_dict()["rel_type"] == "HAS_SUBTECHNIQUE"


# -- Cypher expand -----------------------------------------------------------


def test_cypher_expand_query_is_typed_and_paged() -> None:
    draft = CypherQueryBuilder().expand(_req(direction="in", rel_type="MITIGATES", target_label="Mitigation"))
    assert "(n)<-[:MITIGATES]-(m:Mitigation)" in draft.query
    # Slice the node collection, THEN build member maps — so properties_json (the
    # description blob) is materialized only for the bounded page.
    assert "nodes[$skip..$end]" in draft.query and "size(nodes) AS total" in draft.query
    assert "x.properties_json" in draft.query
    assert draft.params["skip"] == 0 and draft.template == "expand"


def test_cypher_expand_carries_bounded_description() -> None:
    import json

    req = _req(page=0, page_size=5)
    long_desc = "Antivirus solutions " * 60  # > 400 chars
    row = {"members": [
        {"id": "M1049", "name": "Antivirus/Antimalware", "label": "Mitigation",
         "props": json.dumps({"description": long_desc})},
    ], "total": 1}
    result = CypherNormalizer().normalize_expand([row], req)
    desc = result.members[0]["description"]
    assert desc.startswith("Antivirus solutions") and desc.endswith("…") and len(desc) <= 401


def test_gremlin_expand_query_projects_description() -> None:
    req = ExpandRequest("capec", "CAPEC-459", "AttackPattern", "HAS_MITIGATION", "out", "Mitigation")
    draft = GremlinQueryBuilder().expand(req)
    assert '"description"' in draft.query and 'values("description")' in draft.query


def test_gremlin_expand_carries_bounded_description() -> None:
    req = ExpandRequest("capec", "CAPEC-459", "AttackPattern", "HAS_MITIGATION", "out", "Mitigation")
    rows = [{"id": "capec:attack-pattern:459:mitigation:1", "name": "", "label": "Mitigation",
             "description": "Use SHA-256 or SHA-512. " * 40}]
    result = GremlinNormalizer().normalize_expand(rows, req)
    desc = result.members[0]["description"]
    assert desc.startswith("Use SHA-256") and desc.endswith("…") and len(desc) <= 401


def test_cypher_expand_rejects_an_unsafe_identifier() -> None:
    import pytest

    with pytest.raises(ValueError):
        CypherQueryBuilder().expand(_req(rel_type="DROP; MATCH"))


def test_cypher_normalize_expand_uses_server_total() -> None:
    req = _req(page=0, page_size=5)
    row = {"members": _members(5), "total": 13}
    result = CypherNormalizer().normalize_expand([row], req)
    assert result.total == 13 and len(result.members) == 5 and result.truncated is True
    assert CypherNormalizer().normalize_expand([], req).total == 0  # empty is honest, not an error


# -- Gremlin expand ----------------------------------------------------------


def test_gremlin_expand_query_uses_the_facet_step() -> None:
    req = ExpandRequest("capec", "CAPEC-98", "AttackPattern", "CAN_PRECEDE", "out", "AttackPattern")
    draft = GremlinQueryBuilder().expand(req)
    assert '.out("CAN_PRECEDE").hasLabel("AttackPattern")' in draft.query
    assert 'has("id", within(ids))' in draft.query
    assert draft.params["ids"] == ["capec:attack-pattern:98"]


def test_gremlin_normalize_expand_paginates_and_keeps_composite_ids() -> None:
    req = ExpandRequest("capec", "CAPEC-66", "AttackPattern", "HAS_MITIGATION", "out", "Mitigation", page=0, page_size=2)
    # Mitigation members carry composite ids — they must NOT collapse to CAPEC-66.
    rows = [
        {"id": "capec:attack-pattern:66:mitigation:0", "name": "", "label": "Mitigation"},
        {"id": "capec:attack-pattern:66:mitigation:1", "name": "", "label": "Mitigation"},
        {"id": "capec:attack-pattern:66:mitigation:2", "name": "", "label": "Mitigation"},
    ]
    result = GremlinNormalizer().normalize_expand(rows, req)
    assert result.total == 3 and len(result.members) == 2 and result.truncated is True
    ids = [m["id"] for m in result.members]
    assert ids == ["capec:attack-pattern:66:mitigation:0", "capec:attack-pattern:66:mitigation:1"]
    assert all(m != "CAPEC-66" for m in ids)


def test_gremlin_normalize_expand_converts_clean_pattern_ids() -> None:
    req = ExpandRequest("capec", "CAPEC-98", "AttackPattern", "CAN_PRECEDE", "out", "AttackPattern")
    rows = [{"id": "capec:attack-pattern:89", "name": "Pharming", "label": "AttackPattern"}]
    result = GremlinNormalizer().normalize_expand(rows, req)
    assert result.members[0]["id"] == "CAPEC-89"
