#!/usr/bin/env python3
"""Analyst-intent classification — the planner's first step.

The proposal charges the planner with four jobs: *read the source cards,
**classify the analyst's intent**, identify required entities/relationships, and
emit a machine-readable plan*. This module is that second job made explicit.

Classification is a small, closed taxonomy (:class:`Intent`) where **every label
changes what the plan does** — it is a routing signal, not a decoration:

* ``correlation`` expects two sources joined on a canonical key (the flagship
  CAPEC→ATT&CK cross-source question).
* ``remediation`` pulls the ATT&CK ``mitigates`` side.
* ``traversal`` is a neighbour / hierarchy / chain walk on one source.
* ``enumeration`` is a broad filtered scan.
* ``definitional`` resolves a named entity by name (the dossier / name-lookup
  path) rather than by id.
* ``lookup`` is a single entity fetched by id.
* ``unsupported`` is the honest "no recognizable, in-scope intent" bucket.

Like the drafter, classification lives behind a small protocol with a
deterministic default (this module) and an optional LLM refinement
(``llm_intent.py``) that degrades cleanly back to the deterministic result. The
label only *biases* the draft; the deterministic gate remains the sole authority
on whether a plan ships, so a mis-classification can never emit an unsafe plan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:  # cards are only used for the lookup-vs-unsupported fallback
    from .cards import SourceCardView


class Intent:
    """The closed intent taxonomy (string constants, JSON-friendly)."""

    DEFINITIONAL = "definitional"
    LOOKUP = "lookup"
    ENUMERATION = "enumeration"
    CORRELATION = "correlation"
    REMEDIATION = "remediation"
    TRAVERSAL = "traversal"
    UNSUPPORTED = "unsupported"

    #: Canonical ordering (also the tie-break priority — most specific first).
    ALL: tuple[str, ...] = (
        CORRELATION,
        REMEDIATION,
        TRAVERSAL,
        ENUMERATION,
        LOOKUP,
        DEFINITIONAL,
        UNSUPPORTED,
    )

    @classmethod
    def is_valid(cls, label: str) -> bool:
        return label in cls.ALL


@dataclass(frozen=True)
class IntentClassification:
    """One classified intent with its evidence, for the plan and the UI.

    ``cues`` are the concrete phrases/tokens that fired (so the analyst sees
    *why*), ``rationale`` is the human sentence, and ``source`` records which
    classifier produced it (``deterministic`` | ``llm`` | ``fallback``).
    """

    label: str
    confidence: float
    rationale: str = ""
    cues: list[str] = field(default_factory=list)
    source: str = "deterministic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": round(float(self.confidence), 3),
            "rationale": self.rationale,
            "cues": list(self.cues),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "IntentClassification | None":
        if not data:
            return None
        return cls(
            label=str(data.get("label", Intent.UNSUPPORTED)),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            rationale=str(data.get("rationale", "")),
            cues=[str(c) for c in data.get("cues", [])],
            source=str(data.get("source", "deterministic")),
        )


class IntentClassifier(Protocol):
    """Classifies an analyst request into one :class:`Intent` label.

    ``cards`` are optional: the deterministic classifier only consults them to
    decide *lookup vs unsupported* when no distinctive cue fired.
    """

    def classify(
        self, request: str, cards: "dict[str, SourceCardView] | None" = None
    ) -> IntentClassification: ...


# -- deterministic cue rules -------------------------------------------------
#
# Each rule is a compiled pattern over the raw request. Rules are evaluated in
# ``Intent.ALL`` priority order (most specific first): the first rule that fires
# wins, so a cross-source "map to ... mitigations" reads as correlation, not
# remediation. ``definitional`` reuses the specialists' committed heuristic so
# the planner and the specialists agree on what "what is X" means.

_CORRELATION_RE = re.compile(
    r"\b(?:maps?\s+to|mapp?ed\s+to|mapp?ings?|related\s+to|correspond\w*|"
    r"associate\w*|link(?:ed|s)?\s+to|cross[-\s]source|"
    r"between\b.+?\band\b|both\b.+?\band\b)\b",
    re.IGNORECASE,
)
_REMEDIATION_RE = re.compile(
    r"\b(?:mitigat\w*|remediat\w*|defen[sc]\w*|counter(?:measure)?\w*|"
    r"protect\w*|prevent\w*|controls?)\b",
    re.IGNORECASE,
)
_TRAVERSAL_RE = re.compile(
    # Explicit structural / hierarchy words only. Membership phrasings
    # ("belong to tactic", "part of category") read as enumeration ("give me
    # the set"), so they are deliberately NOT traversal cues.
    r"\b(?:parents?|child(?:ren)?|sub-?techniques?|hierarch\w*|neighbou?rs?|"
    r"ancestor\w*|descend\w*|chains?|related\s+patterns?)\b",
    re.IGNORECASE,
)
_ENUMERATION_RE = re.compile(
    r"\b(?:list|all|every|each|which|enumerate|how\s+many|scan|"
    r"show\s+(?:me\s+)?all)\b",
    re.IGNORECASE,
)
#: MITRE id shapes — an id in the text is a strong single-entity lookup signal.
_ID_RE = re.compile(
    r"\b(?:T\d{4}(?:\.\d{3})?|TA\d{4}|[MSG]\d{4}|DS\d{4}|CAPEC-\d+|CWE-\d+)\b",
    re.IGNORECASE,
)
#: A CAPEC mention paired with an ATT&CK mention is itself a correlation cue.
#: The ATT&CK marker is deliberately NOT the bare word "attack" — that appears in
#: the CAPEC term "attack pattern" and would flag every CAPEC-internal question
#: as cross-source. Only ATT&CK-specific vocabulary counts.
_CAPEC_RE = re.compile(r"\bcapec\b", re.IGNORECASE)
_ATTACK_RE = re.compile(r"\batt&ck\b|\btechniques?\b|\btactics?\b", re.IGNORECASE)

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9]+")


def _card_identifier_tokens(cards: "dict[str, SourceCardView]") -> set[str]:
    """Lowercase word tokens of every card node-label / relationship-type name.

    Used only for the lookup-vs-unsupported fallback, so a request that shares
    no vocabulary with any live source is honestly labelled ``unsupported``
    instead of a guessed ``lookup``.
    """
    tokens: set[str] = set()
    for card in cards.values():
        for name in list(card.node_labels) + list(card.relationship_types):
            for part in re.split(r"[^a-zA-Z0-9]+", re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)):
                if len(part) >= 3:
                    tokens.add(part.lower())
    return tokens


class DeterministicIntentClassifier:
    """Card-free cue rules with a card-aware lookup/unsupported fallback."""

    def classify(
        self, request: str, cards: "dict[str, SourceCardView] | None" = None
    ) -> IntentClassification:
        text = request or ""

        # Correlation: an explicit cross-source phrase, or a CAPEC mention paired
        # with an ATT&CK mention.
        corr_cues = [m.group(0).strip() for m in _CORRELATION_RE.finditer(text)]
        if _CAPEC_RE.search(text) and _ATTACK_RE.search(text):
            corr_cues.append("mentions both CAPEC and ATT&CK")
        if corr_cues:
            return IntentClassification(
                Intent.CORRELATION, 0.9,
                "cross-source phrasing: joins two sources on a shared id",
                corr_cues,
            )

        if cues := _matches(_REMEDIATION_RE, text):
            return IntentClassification(
                Intent.REMEDIATION, 0.85,
                "asks for mitigations / defensive controls", cues,
            )

        if cues := _matches(_TRAVERSAL_RE, text):
            return IntentClassification(
                Intent.TRAVERSAL, 0.8,
                "walks a hierarchy / neighbour / chain relationship", cues,
            )

        if cues := _matches(_ENUMERATION_RE, text):
            return IntentClassification(
                Intent.ENUMERATION, 0.75,
                "asks to list / filter a set of entities", cues,
            )

        # A concrete id is a single-entity lookup — checked before the
        # definitional heuristic so "what is T1021.001?" reads as a by-id lookup,
        # while a bare "what is Phishing?" (no id) stays definitional-by-name.
        if ids := _matches(_ID_RE, text):
            return IntentClassification(
                Intent.LOOKUP, 0.8,
                "names a specific entity by id", ids,
            )

        # Definitional reuses the specialists' committed heuristic (imported
        # lazily: specialists.resolve pulls in planner.join_keys at import time).
        from utils.specialists.resolve import is_definitional_intent

        if is_definitional_intent(text):
            return IntentClassification(
                Intent.DEFINITIONAL, 0.85,
                "names an entity to define/describe rather than an id", ["what is / define"],
            )

        # No distinctive cue. If the request shares vocabulary with a live
        # source, treat it as a weak single-entity lookup; otherwise it is
        # honestly out of scope. (The gate is still the authority either way.)
        if cards:
            request_tokens = {t.lower() for t in _TOKEN_RE.findall(text) if len(t) >= 3}
            if request_tokens & _card_identifier_tokens(cards):
                return IntentClassification(
                    Intent.LOOKUP, 0.4,
                    "no distinctive cue; matches source vocabulary, treated as a lookup", [],
                )
            return IntentClassification(
                Intent.UNSUPPORTED, 0.5,
                "no recognizable intent and no live source vocabulary matched", [],
            )
        return IntentClassification(
            Intent.LOOKUP, 0.3,
            "no distinctive cue and no cards to check; defaulting to lookup", [],
        )


def _matches(pattern: re.Pattern[str], text: str) -> list[str]:
    """Return the distinct matched phrases for a pattern (empty when none)."""
    seen: list[str] = []
    for m in pattern.finditer(text):
        phrase = m.group(0).strip()
        if phrase and phrase.lower() not in {s.lower() for s in seen}:
            seen.append(phrase)
    return seen


def mentions_entity_id(text: str) -> bool:
    """True when the text names a concrete MITRE entity id (T1555, CAPEC-560, CWE-89).

    Used by the drafter's name/id-lookup rescue: a request that references a
    specific in-scope entity is routable even when no schema *label* token
    matched, whereas an off-domain request with no id stays honestly unsupported.
    """
    return bool(_ID_RE.search(text or ""))
