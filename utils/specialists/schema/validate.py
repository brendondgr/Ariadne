#!/usr/bin/env python3
"""Registry-backed structural validation of the universal primitive requests.

Validating a generated query *string* with regexes was always the weaker check —
both legacy validators have a documented hole that bidirectional patterns slip
through (``.outE(``/``.inE(`` never match the ``.out(``/``.in(`` step regex, and
``-[r]-`` carries no relationship type for ``_REL_TYPE_RE`` to see). Validating a
*structured request* against the canonical registry — "does ``(Technique,
MITIGATES, in, Mitigation)`` exist in this schema?" — is strictly stronger: it
fails at plan time instead of returning a silently-empty result, and it is the
natural check once the model emits anchors and facet selections rather than query
shapes.

These are pure functions over a :class:`SchemaRegistry`; the caller supplies the
registry (so they stay hermetic and never touch a live database).
"""

from __future__ import annotations

from typing import Any

from .registry import SchemaRegistry


def describe_request_reasons(
    dataset: str, anchor_label: str | None, registry: SchemaRegistry
) -> list[str]:
    """Why (if at all) a ``describe`` anchor label is not real for ``dataset``.

    A describe by title carries no inferred label (``anchor_label is None``) and
    is always structurally admissible — the name filter resolves the label at
    query time. A describe by id whose inferred label is unknown to the dataset
    is a boundary error worth failing early.
    """
    if anchor_label is None:
        return []
    if not registry.has_label(anchor_label, dataset=dataset):
        known = sorted(registry.dataset(dataset).labels()) if registry.dataset(dataset) else []
        return [f"anchor label {anchor_label!r} is not in the {dataset!r} schema (known: {known})"]
    return []


def expand_request_reasons(request: Any, registry: SchemaRegistry) -> list[str]:
    """Why (if at all) an ``ExpandRequest`` is not a real facet of its anchor.

    Structurally validates the ``(anchor_label, rel_type, direction,
    target_label)`` tuple against the registry's observed triples — the exact
    check ``describe`` used to build the facet block, run in reverse. An expand
    whose facet the schema does not carry is rejected here rather than executed
    into an empty result.
    """
    reasons: list[str] = []
    dataset = getattr(request, "dataset", "")
    anchor_label = getattr(request, "anchor_label", "")
    rel_type = getattr(request, "rel_type", "")
    direction = getattr(request, "direction", "")
    target_label = getattr(request, "target_label", "")

    if direction not in ("out", "in"):
        reasons.append(f"direction must be 'out' or 'in', got {direction!r}")
    if anchor_label and not registry.has_label(anchor_label, dataset=dataset):
        reasons.append(f"anchor label {anchor_label!r} is not in the {dataset!r} schema")
    if not registry.facet_exists(
        anchor_label, rel_type, direction, target_label or None, dataset=dataset
    ):
        reasons.append(
            f"facet ({anchor_label}, {rel_type}, {direction}, {target_label}) "
            f"is not a relationship the {dataset!r} schema carries"
        )
    return reasons


def is_valid_expand(request: Any, registry: SchemaRegistry) -> bool:
    """True when ``request`` names a facet the schema actually carries."""
    return not expand_request_reasons(request, registry)
