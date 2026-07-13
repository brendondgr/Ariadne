#!/usr/bin/env python3
"""Registry-backed structural validation of describe/expand requests.

Stronger than the query-string regexes it is designed to replace: it checks the
structured ``(anchor_label, rel, direction, target_label)`` request against the
registry's real triples, so an impossible facet fails at plan time instead of
returning a silently-empty result — including the bidirectional facets the
regex validators' documented hole let slip through.
"""

from __future__ import annotations

from dataclasses import dataclass

from utils.specialists.schema import (
    build_registry,
    describe_request_reasons,
    expand_request_reasons,
    is_valid_expand,
)
from utils.specialists.schema.tests.test_registry import _NODES, _RELS, _write_canonical


@dataclass
class _Expand:
    dataset: str
    anchor_label: str
    rel_type: str
    direction: str
    target_label: str


def _registry(tmp_path):
    _write_canonical(tmp_path, "mini", _NODES, _RELS)
    return build_registry(tmp_path)


def test_expand_accepts_a_real_facet(tmp_path):
    reg = _registry(tmp_path)
    ok = _Expand("mini", "Technique", "MITIGATES", "in", "Mitigation")
    assert expand_request_reasons(ok, reg) == []
    assert is_valid_expand(ok, reg)


def test_expand_rejects_wrong_direction(tmp_path):
    reg = _registry(tmp_path)
    # MITIGATES is inbound to Technique; outbound does not exist.
    bad = _Expand("mini", "Technique", "MITIGATES", "out", "Mitigation")
    reasons = expand_request_reasons(bad, reg)
    assert reasons and "is not a relationship" in reasons[0]
    assert not is_valid_expand(bad, reg)


def test_expand_rejects_unknown_relationship(tmp_path):
    reg = _registry(tmp_path)
    bad = _Expand("mini", "Technique", "DETECTS", "in", "DetectionStrategy")
    assert not is_valid_expand(bad, reg)


def test_expand_rejects_bad_direction_token(tmp_path):
    reg = _registry(tmp_path)
    bad = _Expand("mini", "Technique", "MITIGATES", "sideways", "Mitigation")
    assert any("direction must be" in r for r in expand_request_reasons(bad, reg))


def test_expand_accepts_a_bidirectional_facet_the_regexes_missed(tmp_path):
    # The CanFollow self-edge is exactly the bidirectional shape the query-string
    # validators could not see; the registry check validates it structurally.
    reg = _registry(tmp_path)
    assert is_valid_expand(_Expand("mini", "Pattern", "CanFollow", "in", "Pattern"), reg)
    assert is_valid_expand(_Expand("mini", "Pattern", "CanFollow", "out", "Pattern"), reg)


def test_describe_label_check(tmp_path):
    reg = _registry(tmp_path)
    assert describe_request_reasons("mini", "Technique", reg) == []
    assert describe_request_reasons("mini", None, reg) == []  # by-title is always admissible
    assert describe_request_reasons("mini", "Bogus", reg)  # unknown label rejected
