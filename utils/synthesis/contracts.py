#!/usr/bin/env python3
"""Contracts for the synthesis layer: claims, citations, verdicts, abstentions.

The composer (deterministic or LLM) never emits free prose — it emits
``Claim`` objects whose ``citations`` point at concrete retrieved records and
whose ``entity_ids`` name the identifiers the sentence asserts. That structure
is what makes verification *mechanical*: the verifier resolves every citation
against the actual ``EvidenceRecord``s and checks every named identifier
appears in the cited records, without having to parse prose.

Everything here is a pure JSON-serialisable dataclass, matching the style of
``utils.specialists.contracts`` (the schema synthesis reads from).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Citation:
    """One pointer from a claim to a concrete retrieved evidence record."""

    source: str          # registry dataset key, e.g. "attack"
    primary_id: str      # the record's join-relevant identifier, e.g. "T1047"
    record_id: str = ""  # backend node/edge id from provenance (optional)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "primary_id": self.primary_id,
            "record_id": self.record_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Citation":
        return cls(
            source=str(data.get("source", "")),
            primary_id=str(data.get("primary_id", "")),
            record_id=str(data.get("record_id", "") or ""),
        )


@dataclass(frozen=True)
class Claim:
    """One checkable sentence of the answer.

    ``kind`` is ``"fact"`` for single-source statements and ``"correlation"``
    for cross-source statements (which must additionally be backed by the
    federation's join index). ``entity_ids`` are the identifiers the sentence
    asserts; every one must be grounded in the cited records or the claim is
    cut.
    """

    text: str
    citations: tuple[Citation, ...] = ()
    entity_ids: tuple[str, ...] = ()
    kind: str = "fact"           # "fact" | "correlation"
    sub_question_id: str = ""    # originating sub-question, when known

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "citations": [c.to_dict() for c in self.citations],
            "entity_ids": list(self.entity_ids),
            "kind": self.kind,
            "sub_question_id": self.sub_question_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Claim":
        return cls(
            text=str(data.get("text", "")),
            citations=tuple(
                Citation.from_dict(c) for c in data.get("citations", []) or []
            ),
            entity_ids=tuple(str(e) for e in data.get("entity_ids", []) or []),
            kind=str(data.get("kind", "fact") or "fact"),
            sub_question_id=str(data.get("sub_question_id", "") or ""),
        )


@dataclass(frozen=True)
class Abstention:
    """An honest "the sources don't establish this", with the query as proof.

    Emitted when a specialist ran cleanly (``ok=True``) and returned zero
    records: the correct answer is the absence itself, demonstrated by the
    exact query that was executed — never a plausible-sounding invention.
    """

    sub_question_id: str
    source: str
    statement: str
    query: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub_question_id": self.sub_question_id,
            "source": self.source,
            "statement": self.statement,
            "query": self.query,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Abstention":
        return cls(
            sub_question_id=str(data.get("sub_question_id", "")),
            source=str(data.get("source", "")),
            statement=str(data.get("statement", "")),
            query=str(data.get("query", "")),
        )


@dataclass(frozen=True)
class ClaimVerdict:
    """The verifier's ruling on one claim."""

    verdict: str                              # "supported" | "unsupported"
    reasons: list[str] = field(default_factory=list)

    @property
    def supported(self) -> bool:
        return self.verdict == "supported"

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "reasons": list(self.reasons)}


@dataclass
class VerificationReport:
    """Per-claim verdicts plus the roll-up metrics goals.md asks for."""

    verdicts: list[ClaimVerdict] = field(default_factory=list)
    # Abstentions the verifier had to add because the composer omitted them
    # (the deterministic guard the LLM path cannot skip past).
    repaired_abstentions: int = 0

    @property
    def supported_count(self) -> int:
        return sum(1 for v in self.verdicts if v.supported)

    @property
    def unsupported_count(self) -> int:
        return len(self.verdicts) - self.supported_count

    @property
    def unsupported_claim_rate(self) -> float:
        return self.unsupported_count / len(self.verdicts) if self.verdicts else 0.0

    @property
    def ok(self) -> bool:
        return self.unsupported_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdicts": [v.to_dict() for v in self.verdicts],
            "claim_count": len(self.verdicts),
            "supported_count": self.supported_count,
            "unsupported_count": self.unsupported_count,
            "unsupported_claim_rate": self.unsupported_claim_rate,
            "repaired_abstentions": self.repaired_abstentions,
            "ok": self.ok,
        }


@dataclass
class SynthesizedAnswer:
    """The synthesis agent's output: claims, abstentions, and (after the
    verification pass) the per-claim verdicts.

    ``verification`` is ``None`` for an unverified draft; the API seam and the
    golden suites only ever render verified answers. ``rendered_claims`` is the
    prose surface: verified-supported claims only — unsupported claims stay in
    ``claims``/``verification`` as flagged, auditable, but never shown as fact.
    """

    request: str
    headline: str = ""
    claims: list[Claim] = field(default_factory=list)
    abstentions: list[Abstention] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    composer: str = "deterministic"      # "deterministic" | "llm"
    fallback_reason: str | None = None   # set when the LLM path fell back
    verification: VerificationReport | None = None

    def rendered_claims(self) -> list[Claim]:
        """Claims safe to show as fact: verified and supported.

        An unverified draft renders no claims at all — the answer must prove
        itself before it speaks.
        """
        if self.verification is None:
            return []
        return [
            claim
            for claim, verdict in zip(self.claims, self.verification.verdicts)
            if verdict.supported
        ]

    def flagged_claims(self) -> list[tuple[Claim, ClaimVerdict]]:
        """Claims the verifier cut, paired with the reasons — the audit trail."""
        if self.verification is None:
            return []
        return [
            (claim, verdict)
            for claim, verdict in zip(self.claims, self.verification.verdicts)
            if not verdict.supported
        ]

    def to_dict(self) -> dict[str, Any]:
        verdicts = self.verification.verdicts if self.verification else []
        claims = []
        for i, claim in enumerate(self.claims):
            entry = claim.to_dict()
            entry["verdict"] = verdicts[i].to_dict() if i < len(verdicts) else None
            claims.append(entry)
        return {
            "request": self.request,
            "headline": self.headline,
            "claims": claims,
            "rendered_claims": [c.to_dict() for c in self.rendered_claims()],
            "abstentions": [a.to_dict() for a in self.abstentions],
            "notes": list(self.notes),
            "composer": self.composer,
            "fallback_reason": self.fallback_reason,
            "verification": self.verification.to_dict() if self.verification else None,
        }
