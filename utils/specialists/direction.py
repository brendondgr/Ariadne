#!/usr/bin/env python3
"""Which end of the edge did the caller actually seed?

A two-label template encodes a direction: ``(Group)-[:USES]->(Technique)``
filtered on ``Group.attack_id`` answers *which techniques does this group use*.
The development catalogue only ever asked that way, so the templates only ever
served it, and the blind holdout — whose author asked *which groups use this
technique* — scored 0.00 on the category. The query was not wrong; it was
answering the other question, against a filter no technique id can satisfy.

Nothing about that is specific to ATT&CK. The template names both labels, the
seeds identify one of them, and which one is a question the learned identifier
schemes already answer. This module asks it:

    resolve_anchor(("T1047",), {"Group": "g", "Technique": "t"}, "attack")
    → Technique.attack_id, alias ``t``

**One candidate or nothing.** If the seeds fit two of the template's labels, or
none, the answer is ``None`` and the caller keeps its declared default. An
ambiguous anchor resolved by guessing is how a system starts answering a
question nobody asked, which is the failure this module exists to end.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from utils.specialists.schema import get_registry
from utils.specialists.schema.idscheme import CONSISTENT
from utils.specialists.schema.registry import SchemaRegistry


@dataclass(frozen=True)
class AnchorBinding:
    """The label the seeds identify, and where to filter it."""

    label: str
    alias: str
    property: str

    def expression(self) -> str:
        """The filter target, e.g. ``g.attack_id``."""
        return f"{self.alias}.{self.property}"


def resolve_anchor(
    seed_ids: Sequence[str],
    aliases: Mapping[str, str],
    dataset: str,
    registry: SchemaRegistry | None = None,
) -> AnchorBinding | None:
    """The one label among ``aliases`` whose identifiers all the seeds fit.

    ``aliases`` maps each label the template names to the alias it is bound to
    in the query. Returns ``None`` when the schema licenses no repair (nothing
    fits) or more than one (an ambiguity), so the caller emits exactly what it
    emitted before.
    """
    if not seed_ids or not aliases or not dataset:
        return None
    registry = registry or get_registry()
    schema = registry.dataset(dataset)
    if schema is None:
        return None

    hits: list[AnchorBinding] = []
    for label, alias in aliases.items():
        properties = schema.label_id_schemes.get(label) or {}
        for prop in sorted(properties):
            if all(
                schema.value_verdict(label, prop, seed) == CONSISTENT for seed in seed_ids
            ):
                hits.append(AnchorBinding(label, alias, prop))
                break  # one property per label is enough to place the anchor
    if len(hits) != 1:
        return None
    return hits[0]


def anchor_expression(
    seed_ids: Sequence[str],
    aliases: Mapping[str, str],
    dataset: str,
    default: str,
    registry: SchemaRegistry | None = None,
) -> str:
    """:func:`resolve_anchor`'s filter expression, or ``default`` unchanged.

    The default is what the template emitted before this module existed, so a
    dataset the registry cannot read leaves every query byte-identical.
    """
    anchor = resolve_anchor(seed_ids, aliases, dataset, registry)
    return anchor.expression() if anchor is not None else default
