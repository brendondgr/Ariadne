#!/usr/bin/env python3
"""The anchor resolver — a deterministic id/title ladder that returns ambiguity.

The universal ``describe`` primitive takes *one* anchor node — cited by id or by
title — and the old system decided whether you got a description at all by
whether your phrasing matched a regex. That is the single most arbitrary failure
mode in the pipeline. This resolver replaces it with a deterministic ladder:

    planner seed id  ->  exact id in the text  ->  known name / alias  ->  fuzzy name

The first tier that produces a candidate wins. When a tier produces **more than
one distinct** candidate — the text cites two ids, or two Title-Case entities —
the resolver returns an :class:`AmbiguousAnchor` carrying every candidate, so the
ambiguity can propagate to the planner as a disambiguation prompt instead of
being silently collapsed to the first match. A tier that produces nothing falls
through to the next; a total miss returns ``None``.

Alias resolution (``G0016`` → "APT29" / "Cozy Bear" / "The Dukes") depends on an
alias index whose authoritative source is an open product question (plan §2). The
resolver accepts an optional injected ``alias_index`` (lower-cased alias → the
canonical title) and works without one, degrading to the fuzzy-name tier. It does
not build a canonical alias index in the hot path — that is deliberately out of
scope here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import (
    _ATTACK_ID_PATTERNS,
    _dedupe,
    _extract_attack_seed_ids,
    _extract_name_terms,
    _schema_word_set,
    extract_attack_ids,
    extract_capec_ids,
    extract_cwe_ids,
)

# Anchor kinds.
KIND_ID = "id"
KIND_TITLE = "title"

# id-prefix -> label inference, reusing the resolve module's committed patterns.
_ID_LABEL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (label, re.compile(pattern)) for label, pattern in _ATTACK_ID_PATTERNS
)
_CAPEC_ID_RE = re.compile(r"^CAPEC[-\s]?\d+$", re.IGNORECASE)
_CWE_ID_RE = re.compile(r"^CWE[-\s]?\d+$", re.IGNORECASE)


@dataclass(frozen=True)
class ResolvedAnchor:
    """A single node identity to describe: an id or a title, plus how we got it."""

    kind: str
    value: str
    dataset: str
    label: str | None = None
    via: str = "exact-id"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "dataset": self.dataset,
            "label": self.label,
            "via": self.via,
        }


@dataclass(frozen=True)
class AmbiguousAnchor:
    """More than one candidate at the winning tier — resolve, don't guess."""

    dataset: str
    candidates: tuple[ResolvedAnchor, ...]
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "reason": self.reason,
            "candidates": [c.to_dict() for c in self.candidates],
        }


def infer_label(id_value: str, dataset: str) -> str | None:
    """Infer a node label from an identifier's shape (best effort, may be None)."""
    value = (id_value or "").strip()
    if _CAPEC_ID_RE.match(value):
        return "AttackPattern"
    if _CWE_ID_RE.match(value):
        return "Weakness"
    for label, pattern in _ID_LABEL_PATTERNS:
        if pattern.search(value):
            return label
    return None


def _native_ids(task: Any, dataset: str) -> tuple[str, ...]:
    """Ids the text names, in the dataset's native priority (mirrors ``resolve``)."""
    text = task.text or ""
    if dataset == "attack":
        return _extract_attack_seed_ids(text)
    if dataset == "capec":
        # CAPEC ids first, else the CWE Weakness anchors, else ATT&CK ids
        # (TaxonomyEntry seeds for the reverse MAPS_TO join) — priority, not union.
        return extract_capec_ids(text) or extract_cwe_ids(text) or extract_attack_ids(text)
    return ()


def _one_or_ambiguous(
    anchors: list[ResolvedAnchor], dataset: str, reason: str
) -> ResolvedAnchor | AmbiguousAnchor | None:
    """Collapse a tier's candidates: none -> None, one -> it, many -> ambiguous."""
    unique: list[ResolvedAnchor] = []
    seen: set[tuple[str, str]] = set()
    for anchor in anchors:
        key = (anchor.kind, anchor.value.upper())
        if key not in seen:
            seen.add(key)
            unique.append(anchor)
    if not unique:
        return None
    if len(unique) == 1:
        return unique[0]
    return AmbiguousAnchor(dataset=dataset, candidates=tuple(unique), reason=reason)


def resolve_anchor(
    task: Any,
    card: Any,
    *,
    alias_index: dict[str, str] | None = None,
) -> ResolvedAnchor | AmbiguousAnchor | None:
    """Resolve the single anchor a ``describe`` request should target.

    ``task`` exposes ``text`` and ``seed_ids``; ``card`` is a ``SourceCardView``
    (``dataset``, ``node_labels``/``relationship_types`` for name filtering).
    Returns a :class:`ResolvedAnchor`, an :class:`AmbiguousAnchor`, or ``None``.
    """
    dataset = getattr(card, "dataset", "")

    # 1. The planner already attached seed ids — the highest-authority anchor.
    seeds = tuple(task.seed_ids or ())
    if seeds:
        anchors = [
            ResolvedAnchor(KIND_ID, s.upper(), dataset, infer_label(s, dataset), "seed")
            for s in seeds
        ]
        result = _one_or_ambiguous(anchors, dataset, "the task carries multiple seed ids")
        if result is not None:
            return result

    # 2. Exact ids named in the text, in the dataset's native priority.
    ids = _native_ids(task, dataset)
    if ids:
        anchors = [
            ResolvedAnchor(KIND_ID, i.upper(), dataset, infer_label(i, dataset), "exact-id")
            for i in ids
        ]
        result = _one_or_ambiguous(anchors, dataset, "the text names multiple ids")
        if result is not None:
            return result

    # 3/4. Named entities. Prefer a known name/alias hit; else a fuzzy name anchor
    #      the describe compiler matches with a case-insensitive CONTAINS.
    names = _extract_name_terms(task.text or "", _schema_word_set(card))
    if names:
        if alias_index:
            canon = _dedupe(
                [alias_index[n.lower()] for n in names if n.lower() in alias_index]
            )
            if canon:
                anchors = [
                    ResolvedAnchor(KIND_TITLE, c, dataset, None, "alias") for c in canon
                ]
                result = _one_or_ambiguous(
                    anchors, dataset, "aliases resolve to multiple entities"
                )
                if result is not None:
                    return result
        anchors = [
            ResolvedAnchor(KIND_TITLE, n, dataset, None, "fuzzy") for n in _dedupe(names)
        ]
        return _one_or_ambiguous(anchors, dataset, "the text names multiple entities")

    # 5. Nothing to anchor on.
    return None
