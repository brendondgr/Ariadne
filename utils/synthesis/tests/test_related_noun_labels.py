#!/usr/bin/env python3
"""A relationship noun must not assert a kind the neighbour is not.

EXP-2026-08-010 caught the composer writing, of a piece of software:

    S0512 (FatDuke) has 2 used techniques: G0016, C0023

G0016 is a Group and C0023 a Campaign. The identifiers were correct and
retrieved; only the noun was false — which is the worst shape this failure can
take, because a reader has no way to tell that the label is the part that lied.

The cause is that ATT&CK's ``USES`` joins Group->Software, Campaign->Software
and Software->Technique alike, while ``_REL_NOUNS`` maps it to one noun. This
was the last known fabrication source in an otherwise deterministic path.
"""

from __future__ import annotations

import pytest

from utils.synthesis.composer import _related_noun


class _Record:
    """Only ``related`` is read, so a stub keeps the fixture honest about that."""

    def __init__(self, related: list[dict]) -> None:
        self.related = related


def _rel(pairs: list[tuple[str, str]], rel_type: str = "USES") -> _Record:
    return _Record([{"id": i, "label": l, "type": rel_type} for i, l in pairs])


# -- the defect --------------------------------------------------------------


def test_software_neighbours_are_not_called_techniques() -> None:
    noun = _related_noun(_rel([("S0002", "Software"), ("S0004", "Software")]), 2)
    assert "technique" not in noun
    assert noun == "pieces of software"


def test_a_mixed_neighbour_set_falls_back_rather_than_picking_one() -> None:
    """The exact FatDuke case: a Group and a Campaign over the same edge.

    No single noun is true of both, so the flat one is the only honest option.
    """
    noun = _related_noun(_rel([("G0016", "Group"), ("C0023", "Campaign")]), 2)
    assert "technique" not in noun
    assert noun == "related item(s)"


def test_group_neighbours_are_called_groups() -> None:
    assert _related_noun(_rel([("G0007", "Group"), ("G0016", "Group")]), 2) == "groups"


# -- what must not have changed ----------------------------------------------


@pytest.mark.parametrize(
    ("pairs", "count", "expected"),
    [
        ([("T1083", "Technique")], 1, "used technique"),
        ([("T1083", "Technique"), ("T1027.001", "SubTechnique")], 2, "used techniques"),
        ([("T1027.001", "SubTechnique")], 1, "used technique"),
    ],
)
def test_the_relationship_noun_survives_when_it_is_true(
    pairs: list[tuple[str, str]], count: int, expected: str
) -> None:
    assert _related_noun(_rel(pairs), count) == expected


def test_an_unconstrained_relationship_is_untouched() -> None:
    """CAPEC's hierarchy roles are AttackPattern->AttackPattern throughout.

    They carry no entry in `_NOUN_EXPECTS`, so they keep the wording the
    recorded CAPEC answers were produced with.
    """
    assert _related_noun(_rel([("CAPEC-1", "AttackPattern")], "CHILD_OF"), 1) == "ChildOf parent"
    assert _related_noun(_rel([("CAPEC-1", "AttackPattern")], "PEER_OF"), 2) == "PeerOf peers"


def test_unlabelled_neighbours_keep_the_relationship_noun() -> None:
    """Several normalizers emit related entries with no label at all.

    An absent label is not evidence against the noun, so those must not be
    demoted — every template that reports through them would change wording.
    """
    record = _Record([{"id": "T1083", "type": "USES"}])
    assert _related_noun(record, 1) == "used technique"


def test_a_label_with_no_spelled_plural_still_reads_as_a_word() -> None:
    assert _related_noun(_rel([("x", "Analytic")], "HAS_ANALYTIC"), 3) == "Analytics"
