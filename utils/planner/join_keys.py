#!/usr/bin/env python3
"""Declared canonical join keys for cross-source planning.

The planner may only propose a cross-source join on a **declared, canonical**
key that is actually present in both source cards. If the key is not declared,
or the required labels/edges are absent from either card, the planner does not
invent a join — it marks the cross-source part unsupported (briefing §1.2).

The single declared bridge for the demonstration sources is the ATT&CK
technique id: a CAPEC ``AttackPattern`` ``MAPS_TO`` a ``TaxonomyEntry`` whose
``entry_id`` (taxonomy ``ATTACK``, e.g. ``1574.010``) corresponds to an ATT&CK
``Technique``/``SubTechnique`` ``attack_id`` (``T1574.010``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid an import cycle; cards imports nothing from here
    from .cards import SourceCardView


@dataclass(frozen=True)
class JoinKeyEndpoint:
    """How one source exposes the canonical join key."""

    dataset: str
    labels: tuple[str, ...]  # any of these labels carries the key
    property: str            # the property holding the key value
    via_edge: str | None = None  # edge that must exist to reach the key
    note: str = ""


@dataclass(frozen=True)
class JoinKey:
    """A declared canonical join key bridging two sources."""

    name: str
    description: str
    endpoints: tuple[JoinKeyEndpoint, JoinKeyEndpoint]

    def endpoint_for(self, dataset: str) -> JoinKeyEndpoint | None:
        for endpoint in self.endpoints:
            if endpoint.dataset == dataset:
                return endpoint
        return None


# The full registry of canonical join keys. Adding a new cross-source bridge is
# a deliberate, reviewed edit here — never something the planner fabricates.
CANONICAL_JOIN_KEYS: tuple[JoinKey, ...] = (
    JoinKey(
        name="attack-technique-id",
        description=(
            "ATT&CK technique id bridges CAPEC and ATT&CK: CAPEC AttackPattern "
            "-[MAPS_TO]-> TaxonomyEntry(taxonomy=ATTACK).entry_id  <->  ATT&CK "
            "Technique/SubTechnique.attack_id (with the 'T' prefix)."
        ),
        endpoints=(
            JoinKeyEndpoint(
                dataset="capec",
                labels=("TaxonomyEntry",),
                property="entry_id",
                via_edge="MAPS_TO",
                note="taxonomy_name == 'ATTACK'; entry_id form '####[.###]'",
            ),
            JoinKeyEndpoint(
                dataset="attack",
                labels=("Technique", "SubTechnique"),
                property="attack_id",
                via_edge=None,
                note="attack_id form 'T####[.###]'",
            ),
        ),
    ),
)


def is_declared(name: str) -> bool:
    """Return True when ``name`` is a declared canonical join key."""
    return any(key.name == name for key in CANONICAL_JOIN_KEYS)


def get_join_key(name: str) -> JoinKey | None:
    """Return the declared join key by name, or None."""
    for key in CANONICAL_JOIN_KEYS:
        if key.name == name:
            return key
    return None


def _endpoint_present(endpoint: JoinKeyEndpoint, card: "SourceCardView") -> bool:
    """A card carries the key when it has one of the labels and (if required)
    the bridging edge in its introspected structure."""
    if card.dataset != endpoint.dataset:
        return False
    if not any(card.has_label(label) for label in endpoint.labels):
        return False
    if endpoint.via_edge is not None and not card.has_relationship(endpoint.via_edge):
        return False
    return True


def resolve_join_key(card_a: "SourceCardView", card_b: "SourceCardView") -> JoinKey | None:
    """Return a declared join key bindable across both cards, else None.

    The key binds only when the two cards are **distinct** sources that together
    cover both of the key's endpoints, and each card exposes its endpoint's
    required labels and bridging edge in the cards' **introspected** structure.
    An undeclared, same-dataset, or half-present key returns None so the planner
    marks the join unsupported.
    """
    if card_a.dataset == card_b.dataset:
        return None
    for key in CANONICAL_JOIN_KEYS:
        datasets = {endpoint.dataset for endpoint in key.endpoints}
        if datasets != {card_a.dataset, card_b.dataset}:
            continue
        ep_a = key.endpoint_for(card_a.dataset)
        ep_b = key.endpoint_for(card_b.dataset)
        if ep_a is None or ep_b is None:
            continue
        if _endpoint_present(ep_a, card_a) and _endpoint_present(ep_b, card_b):
            return key
    return None
