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

from ..concepts import concept_terms
from ..contracts import SpecialistTask

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
    # Deterministic name anchors for a *named* entity ("User Training") when no
    # id is present — quoted phrases and Title-Case runs from the task text,
    # card-filtered so a schema word is never mistaken for an entity name. Lets a
    # builder emit a name-anchored dossier for a definitional question.
    name_terms: tuple[str, ...] = ()

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


# -- name-term extraction ---------------------------------------------------
# A named entity ("User Training") carries no id, so the id regexes above find
# nothing. These helpers deterministically lift name anchors from the task text.
# Priority: quoted phrases, then Title-Case runs, then filtered single tokens.
# Card label/relationship words are excluded so a schema mention ("Mitigation")
# is never read as a name; multi-word runs are kept whole, so "Software
# Configuration" survives even though "Software" is itself a label word.

_NAME_STOPWORDS = frozenset(
    """a an and are as at be by for from has have in into is it its of on or that the
    their to was were which who whom with you your they them then this these those""".split()
)

_NAME_SCAFFOLD = frozenset(
    """identify find finds retrieve retrieves relevant associated related detail details
    describe describes description descriptions overview overviews explain explains
    definition definitions define defines elaborate elaborates learn dive full record
    records profile profiles picture exactly respectively provide provides give gives
    given show shows list lists please deep entity entities node nodes information about
    tell more what whats which who whom please give""".split()
)

_QUOTED_NAME_RE = re.compile(r"['\"‘’“”]([^'\"‘’“”]{2,})['\"‘’“”]")
# A Title-Case run may span a lowercase within-name connector ("Phishing for
# Information", "Denial of Service") so the whole entity name stays one term.
# "and"/"or" are deliberately excluded: they separate entities ("User Training
# and Software Configuration" must split), not join a single name.
_NAME_CONNECTORS = r"(?:the|of|for|to|in|on|with|a|an|by|from)"
_TITLECASE_RUN_RE = re.compile(
    rf"[A-Z][A-Za-z0-9]*(?:\s+(?:{_NAME_CONNECTORS}\s+)?[A-Z][A-Za-z0-9]*)*"
)
_ANY_ID_RE = re.compile(
    r"\b(?:TA|DET|DC|T|M|G|S|C)\d{3,}(?:\.\d+)?\b|\bCAPEC[-\s]?\d+\b|\bCWE[-\s]?\d+\b",
    re.IGNORECASE,
)

_MIN_NAME_LEN = 4
_MAX_NAME_TERMS = 4


def _schema_word_set(card: Any) -> set[str]:
    """Lowercased word tokens of every card label and relationship type."""
    words: set[str] = set()
    names = list(getattr(card, "node_labels", ()) or ()) + list(
        getattr(card, "relationship_types", ()) or ()
    )
    for name in names:
        spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name)).replace("_", " ")
        for w in spaced.split():
            if w:
                words.add(w.lower())
    return words


def _acceptable_name(candidate: str, schema_words: set[str]) -> bool:
    """A candidate is a plausible entity name (not scaffolding or a schema word)."""
    cand = candidate.strip()
    if not cand or _ANY_ID_RE.search(cand):
        return False
    lowers = [w.lower() for w in cand.split()]
    if not lowers:
        return False
    # An all-scaffolding/stopword phrase names nothing.
    if all(w in _NAME_STOPWORDS or w in _NAME_SCAFFOLD for w in lowers):
        return False
    if len(lowers) == 1:
        w = lowers[0]
        if len(w) < _MIN_NAME_LEN:
            return False
        if w in _NAME_STOPWORDS or w in _NAME_SCAFFOLD or w in schema_words:
            return False
    return True


def _extract_name_terms(text: str, schema_words: set[str]) -> tuple[str, ...]:
    """Deterministic name anchors from ``text`` (see module note above)."""
    if not text:
        return ()
    terms: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        cand = candidate.strip().strip(".,;:?!()[]{}")
        low = cand.lower()
        if not cand or low in seen or not _acceptable_name(cand, schema_words):
            return
        seen.add(low)
        terms.append(cand)

    for m in _QUOTED_NAME_RE.finditer(text):
        add(m.group(1))
    if not terms:
        for m in _TITLECASE_RUN_RE.finditer(text):
            add(m.group(0))
    if not terms:
        for w in re.findall(r"[A-Za-z][A-Za-z0-9]+", text):
            add(w)
    return tuple(terms[:_MAX_NAME_TERMS])


def definitional_name_terms(text: str) -> tuple[str, ...]:
    """The entity name(s) a question asks about, for messaging.

    Card-agnostic (no schema filter) so the synthesis layer can name an
    unresolved entity in an honest abstention without a card in hand.
    Unconditional: once ``describe`` returns everything for any anchor, gating
    name extraction on a "what is X" regex is redundant — the resolver already
    knows whether a name resolved, so this just lifts the name terms the text
    carries (empty when the text names no entity).
    """
    return _extract_name_terms(text, set())


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
        # Prioritized CAPEC-native anchors: CAPEC ids first; else CWE ids (the
        # Weakness vertices seeding the CWE -> CAPEC -> ATT&CK chain); else
        # ATT&CK technique ids (the TaxonomyEntry anchors seeding the reverse
        # MAPS_TO join). Priority, not union, so a text naming both a pattern
        # and a technique anchors on the pattern.
        native = (
            list(capec_ids)
            or list(extract_cwe_ids(text))
            or list(attack_ids)
        )
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
        name_terms=_extract_name_terms(text, _schema_word_set(card)),
    )
