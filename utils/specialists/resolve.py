#!/usr/bin/env python3
"""Shared resolve-to-schema (briefing §2.3, "shared code, different data").

Resolving a filtered task against a source card is the *same* code for both
specialists — only the card fed in changes. It maps the task's entities to real
card labels/edges, pulls concrete identifiers out of the task text, pairs an
ATT&CK id with its STIX type (legacy-id disambiguation, §8), and surfaces the
canonical join target so the language-specific builder can construct a bounded
query from grounded parameters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from utils.planner.join_keys import get_join_key

from .concepts import concept_terms
from .contracts import SpecialistTask

# ATT&CK identifier shapes. Order matters: longer/letter-prefixed forms first so
# e.g. "TA0006" is read as a Tactic, not a Technique "T0006", and "DET0103" /
# "DC0084" are not mistaken for other prefixes.
_ATTACK_ID_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Technique", r"\bT\d{4}(?:\.\d{3})?\b"),
    ("Tactic", r"\bTA\d{4}\b"),
    ("Mitigation", r"\bM\d{4}\b"),
    ("Group", r"\bG\d{4}\b"),
    ("Software", r"\bS\d{4}\b"),
    ("DetectionStrategy", r"\bDET\d{4}\b"),
    ("DataComponent", r"\bDC\d{4}\b"),
    ("Campaign", r"\bC\d{4}\b"),
)

_TECHNIQUE_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")
_CAPEC_RE = re.compile(r"\bCAPEC[-\s]?(\d+)\b", re.IGNORECASE)
_CWE_RE = re.compile(r"\bCWE[-\s]?(\d+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ResolvedTask:
    """A task grounded against a specific source card."""

    task: SpecialistTask
    dataset: str
    labels: tuple[str, ...] = ()
    relationships: tuple[str, ...] = ()
    unknown_entities: tuple[str, ...] = ()
    seed_ids: tuple[str, ...] = ()
    attack_ids: tuple[str, ...] = ()
    capec_ids: tuple[str, ...] = ()
    join_key: str | None = None
    join_endpoint: Any | None = None
    stix_types: dict[str, str] = field(default_factory=dict)
    # Anchor terms for concepts the text names (committed vocabulary in
    # ``concepts.py``, never model output) — lets a builder scope a query to a
    # fuzzy concept like "credential theft".
    concept_terms: tuple[str, ...] = ()

    @property
    def has_join(self) -> bool:
        return self.join_key is not None and self.join_endpoint is not None

    def primary_label(self) -> str | None:
        """The most specific resolved label to anchor a query on, if any."""
        return self.labels[0] if self.labels else None


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return tuple(seen)


def extract_attack_ids(text: str) -> tuple[str, ...]:
    """Return every ATT&CK technique id (``T####[.###]``) mentioned in ``text``."""
    return _dedupe([m.group(0).upper() for m in _TECHNIQUE_RE.finditer(text or "")])


def extract_capec_ids(text: str) -> tuple[str, ...]:
    """Return every CAPEC id mentioned, normalised to ``CAPEC-N``."""
    return _dedupe([f"CAPEC-{m.group(1)}" for m in _CAPEC_RE.finditer(text or "")])


def extract_cwe_ids(text: str) -> tuple[str, ...]:
    """Return every CWE id mentioned, normalised to ``CWE-N``."""
    return _dedupe([f"CWE-{m.group(1)}" for m in _CWE_RE.finditer(text or "")])


def _extract_attack_seed_ids(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for _label, pattern in _ATTACK_ID_PATTERNS:
        found.extend(m.group(0).upper() for m in re.finditer(pattern, text or ""))
    return _dedupe(found)


def card_stix_types(card: Any) -> dict[str, str]:
    """Map each ATT&CK label to its STIX type example from the card properties."""
    out: dict[str, str] = {}
    node_props = card.node_properties or {}
    for label, props in node_props.items():
        stix = (props or {}).get("stix_type") if isinstance(props, dict) else None
        example = stix.get("example") if isinstance(stix, dict) else None
        if example:
            out[label] = str(example)
    return out


def resolve(task: SpecialistTask, card: Any) -> ResolvedTask:
    """Ground ``task`` against ``card`` (the shared resolve-to-schema step).

    ``card`` is a ``utils.planner.cards.SourceCardView`` (duck-typed: exposes
    ``dataset``, ``has_label``/``has_relationship``, ``node_properties``,
    ``provenance``). The function never touches a database — it only reconciles
    the task with the card's introspected structure.
    """
    labels = [e for e in task.entities if card.has_label(e)]
    relationships = [e for e in task.entities if card.has_relationship(e)]
    unknown = [e for e in task.entities if not card.has_label(e) and not card.has_relationship(e)]

    text = task.text or ""
    attack_ids = list(extract_attack_ids(text))
    capec_ids = list(extract_capec_ids(text))

    if card.dataset == "attack":
        native = list(_extract_attack_seed_ids(text))
    elif card.dataset == "capec":
        # CWE ids are CAPEC-native anchors too: the graph's Weakness vertices
        # seed the CWE -> CAPEC -> ATT&CK chain template.
        native = [*capec_ids, *extract_cwe_ids(text)]
    else:
        native = []
    # Seed ids the planner already attached win first, then text-extracted ones.
    seed_ids = _dedupe([*task.seed_ids, *native])

    join_key = task.join_key
    join_endpoint = None
    if join_key:
        declared = get_join_key(join_key)
        if declared is not None:
            join_endpoint = declared.endpoint_for(card.dataset)

    return ResolvedTask(
        task=task,
        dataset=card.dataset,
        labels=_dedupe(labels),
        relationships=_dedupe(relationships),
        unknown_entities=_dedupe(unknown),
        seed_ids=seed_ids,
        attack_ids=_dedupe(attack_ids),
        capec_ids=_dedupe(capec_ids),
        join_key=join_key,
        join_endpoint=join_endpoint,
        stix_types=card_stix_types(card),
        concept_terms=concept_terms(text),
    )
