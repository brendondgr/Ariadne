#!/usr/bin/env python3
"""Learn, from the canonical snapshot, what an identifier *looks like* per label.

A query that filters ``Group.attack_id`` against ``T1550.002`` cannot match
anything. Nothing in the repository could say so, because the only knowledge of
which identifier belongs to which label lived in hand-written regexes
(``utils/specialists/resolve/resolver.py``) that name ATT&CK and CAPEC
explicitly. This module derives the same knowledge from the data instead, so a
source nobody has seen yet gets it without a line of new code.

**A scheme is a value's shape.** Case-fold the value and collapse every maximal
run of digits to ``#``; keep everything else verbatim. ``T1550.002`` becomes
``t#.#``, ``G0082`` becomes ``g#``, ``capec:attack-pattern:1`` becomes
``capec:attack-pattern:#``. Collapsing the *length* of a digit run rather than
preserving it is deliberate: ``CAPEC-9`` and ``CAPEC-1000`` are the same kind of
identifier and must not learn as two.

**Three answers, not two.** ``admits`` returns ``consistent``, ``mismatch`` or
``undetermined``, and only ``mismatch`` is ever actionable. A property whose
values are opaque — UUIDs, hostnames, anything with more distinct shapes than
:data:`MAX_SCHEMES` — is recorded as *open*: it admits everything, because
nothing has been learned about it. That is the honest answer for a telemetry
source keyed by GUID, and it is why this machinery cannot manufacture a false
mismatch on data it does not understand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

# Verdicts. Only MISMATCH is actionable; see the module docstring.
CONSISTENT = "consistent"
MISMATCH = "mismatch"
UNDETERMINED = "undetermined"

# The pseudo-property under which a node's own canonical id is learned. Both
# datasets need it: CAPEC's analyst-facing identifier *is* the node id, while
# ATT&CK's is the ``attack_id`` property and its node id is an opaque STIX UUID.
ID_PROPERTY = "id"

# Above this many distinct schemes a property is opaque, not structured. The cap
# is a statement about kinds of identifier, not about cardinality: ATT&CK has
# eleven labelled id families in total, so a single property exhibiting two dozen
# shapes is free text or a UUID, either way unlearnable.
MAX_SCHEMES = 24

# Values longer than this, or carrying whitespace, are prose rather than
# identifiers and are not learned at all.
MAX_VALUE_LEN = 64

_DIGIT_RUN = re.compile(r"\d+")


def scheme_of(value: Any) -> str | None:
    """The shape of ``value``, or ``None`` when it is not identifier-like.

    ``None`` means "do not learn from this and do not judge against it" — an
    empty string, a non-string, prose, or anything carrying whitespace.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > MAX_VALUE_LEN:
        return None
    if any(char.isspace() for char in text):
        return None
    return _DIGIT_RUN.sub("#", text.casefold())


@dataclass(frozen=True, order=True)
class PropertySchemes:
    """Every identifier shape observed for one ``(label, property)`` pair.

    ``is_open`` marks a property that exceeded :data:`MAX_SCHEMES` while
    learning. An open property admits every value, because the alternative —
    judging against a truncated sample — would report a mismatch that is really
    an absence of evidence.
    """

    label: str
    property: str
    schemes: frozenset[str] = field(default_factory=frozenset)
    is_open: bool = False

    def admits(self, value: Any) -> str:
        """Can ``value`` inhabit this property? ``consistent`` / ``mismatch`` / ``undetermined``."""
        if self.is_open or not self.schemes:
            return UNDETERMINED
        scheme = scheme_of(value)
        if scheme is None:
            return UNDETERMINED
        return CONSISTENT if scheme in self.schemes else MISMATCH


class SchemeLearner:
    """Accumulates schemes per ``(label, property)``, capped and order-free."""

    def __init__(self) -> None:
        self._seen: dict[tuple[str, str], set[str]] = {}
        self._open: set[tuple[str, str]] = set()

    def observe(self, label: str, prop: str, value: Any) -> None:
        key = (label, prop)
        if key in self._open:
            return
        scheme = scheme_of(value)
        if scheme is None:
            return
        bucket = self._seen.setdefault(key, set())
        bucket.add(scheme)
        if len(bucket) > MAX_SCHEMES:
            # Opaque: forget the sample rather than judge against a truncation.
            self._open.add(key)
            self._seen.pop(key, None)

    def observe_node(self, node: Mapping[str, Any]) -> None:
        """Learn from one canonical node: its id, then its string properties."""
        label = node.get("label")
        if not label:
            return
        self.observe(label, ID_PROPERTY, node.get("id"))
        properties = node.get("properties")
        if isinstance(properties, Mapping):
            for key, value in properties.items():
                self.observe(label, key, value)

    def result(self) -> dict[str, dict[str, PropertySchemes]]:
        learned: dict[str, dict[str, PropertySchemes]] = {}
        for (label, prop), schemes in self._seen.items():
            learned.setdefault(label, {})[prop] = PropertySchemes(
                label=label, property=prop, schemes=frozenset(schemes)
            )
        for label, prop in self._open:
            learned.setdefault(label, {})[prop] = PropertySchemes(
                label=label, property=prop, is_open=True
            )
        return learned


def learn_schemes(nodes: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, PropertySchemes]]:
    """Walk canonical nodes into ``{label: {property: PropertySchemes}}``."""
    learner = SchemeLearner()
    for node in nodes:
        learner.observe_node(node)
    return learner.result()


def combine_verdicts(verdicts: Iterable[str]) -> str:
    """Fold verdicts from several sources: any consistent wins, mismatch needs unanimity.

    A value that fits *somewhere* is not a defect, and an empty fold is
    ``undetermined`` — nothing was checked, so nothing is known.
    """
    seen = list(verdicts)
    if not seen:
        return UNDETERMINED
    if CONSISTENT in seen:
        return CONSISTENT
    if UNDETERMINED in seen:
        return UNDETERMINED
    return MISMATCH
