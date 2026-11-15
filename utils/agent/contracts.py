#!/usr/bin/env python3
"""The agent contract (Era 2, Step 3; plan v2 §4): one request, one envelope, every path.

A caller -- a person, a script, a parent agent, an MCP client -- sends an
:class:`AgentRequest` and gets back an :class:`AnswerEnvelope`. It never sees
the loop's internals unless it reads the run log. Every path that answers a
question (the deterministic fast path, the agent loop) returns this envelope,
and every envelope validates against :data:`ENVELOPE_SCHEMA`.

The four exits, as the operator described them:

| Situation | ``status`` | What the caller gets |
|---|---|---|
| enough information | ``answered`` (``partial`` if a ceiling was hit) | the exact sets, text, citations |
| not enough in the graph | ``insufficient`` | what was searched, found empty, and why |
| doesn't know where to go next | ``needs_clarification`` (interactive) else ``insufficient`` | the questions, or the open alternatives |
| not expressible with the tools | ``not_expressible`` | which part, and which operator is missing |

plus ``error`` for a run that broke. The cross-field rules (an answered
envelope has an answer, a paused one has a clarification, every other exit has
a reason) are enforced by the model validator and stated in the schema's
description, because JSON Schema alone cannot say them clearly.

pydantic v2 models: typed like the dataclasses elsewhere in the codebase, and
they give the JSON Schema for free. ``extra="forbid"`` everywhere, so a field
nobody defined cannot ride along unnoticed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

STATUSES = ("answered", "partial", "insufficient", "needs_clarification", "not_expressible", "error")
Status = Literal["answered", "partial", "insufficient", "needs_clarification", "not_expressible", "error"]
Path_ = Literal["fast", "loop"]
Mode = Literal["fast", "auto", "thorough"]

#: Keys whose values depend on the clock, not on what the run did. Comparisons of
#: two envelopes (the crash test, the recorded-answer regression) exclude them.
CLOCK_KEYS = ("seconds", "created", "ts", "checked_at")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# The request
# --------------------------------------------------------------------------- #


class Budget(_Strict):
    steps: int = Field(6, ge=1, le=50, description="model calls the loop may make")
    seconds: float = Field(60.0, gt=0, description="wall-clock budget for the whole run")


class Caller(_Strict):
    kind: Literal["person", "script", "agent", "mcp"] = "script"
    id: str | None = None


class AgentRequest(_Strict):
    question: str = Field(min_length=1)
    graph: str | list[str] = Field(description="a source key, or a list of them for federation")
    mode: Mode = "auto"
    interactive: bool = Field(False, description="may the run pause to ask the caller?")
    budget: Budget = Field(default_factory=Budget)
    caller: Caller = Field(default_factory=Caller)

    @property
    def graphs(self) -> list[str]:
        return [self.graph] if isinstance(self.graph, str) else list(self.graph)


# --------------------------------------------------------------------------- #
# The envelope
# --------------------------------------------------------------------------- #


class AnswerSet(_Strict):
    handle: str = Field(description="server-side handle, e.g. set:7")
    kind: str = Field(description="the node label the set holds")
    total: int = Field(ge=0, description="exact size of the set")
    complete: bool = Field(description="false when a ceiling cut the set short")
    ids: list[str] = Field(default_factory=list, description="every member's identifier")


class Answer(_Strict):
    text: str
    sets: list[AnswerSet] = Field(default_factory=list)


class CitationRef(_Strict):
    id: str
    source: str
    query_hash: str | None = None


class Confidence(_Strict):
    score: float | None = Field(None, ge=0.0, le=1.0)
    threshold: float | None = Field(None, ge=0.0, le=1.0)
    calibrated_on: str | None = None


class Trace(_Strict):
    steps: int = Field(0, ge=0, description="model calls made")
    tools: list[str] = Field(default_factory=list, description="tool names, in call order")
    served_model: str | None = Field(None, description="registry name and verified token id, e.g. gemma4-31b/106")
    seconds: float = Field(0.0, ge=0)
    repairs: int = Field(0, ge=0, description="logged reply repairs over the run")


class ClarifyOption(_Strict):
    label: str = Field(min_length=1)
    detail: str = ""


class ClarifyQuestion(_Strict):
    header: str = Field(min_length=1, max_length=40)
    question: str = Field(min_length=1)
    options: list[ClarifyOption] = Field(min_length=2, max_length=4)


class Clarification(_Strict):
    resume: str = Field(description="the run id to pass to resume()")
    questions: list[ClarifyQuestion] = Field(min_length=1, max_length=4)
    why: str = ""


class AnswerEnvelope(_Strict):
    """What every path returns. See the module docstring for the four exits."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"description": (
            "Rules beyond the field types: status answered|partial requires answer; "
            "status needs_clarification requires clarification (and no other status may carry one); "
            "status insufficient|not_expressible|error requires reason."
        )},
    )

    run_id: str
    status: Status
    path: Path_
    answer: Answer | None = None
    citations: list[CitationRef] = Field(default_factory=list)
    confidence: Confidence | None = None
    trace: Trace = Field(default_factory=Trace)
    clarification: Clarification | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _exits(self) -> "AnswerEnvelope":
        if self.status in ("answered", "partial") and self.answer is None:
            raise ValueError(f"status {self.status} requires an answer")
        if (self.status == "needs_clarification") != (self.clarification is not None):
            raise ValueError("clarification is set exactly when status is needs_clarification")
        if self.status in ("insufficient", "not_expressible", "error") and not self.reason:
            raise ValueError(f"status {self.status} requires a reason")
        if self.clarification is not None and self.clarification.resume != self.run_id:
            raise ValueError("clarification.resume must be this run's id")
        return self

    def comparable(self) -> dict[str, Any]:
        """The envelope as a dict without clock keys, for byte-level comparison."""
        return strip_clock(self.model_dump(mode="json"))


def strip_clock(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_clock(v) for k, v in obj.items() if k not in CLOCK_KEYS}
    if isinstance(obj, list):
        return [strip_clock(v) for v in obj]
    return obj


def validate_envelope(data: dict[str, Any]) -> AnswerEnvelope:
    """Validate a dict (from JSON, an API, a log) as an envelope. Raises on failure."""
    return AnswerEnvelope.model_validate(data)


def envelope_from_synthesis(answer: Any, run_id: str, *, served_model: str | None = None,
                            seconds: float = 0.0) -> AnswerEnvelope:
    """The fast path's envelope: today's pipeline answer (``SynthesizedAnswer`` or its dict).

    Only claims the verifier supported are shown (a dict without verdicts, as in
    the recorded answers, is taken as already rendered). The era-1 pipeline has
    no server-side handles, so ``answer.sets`` is empty until Step 5 adds them;
    the claims' citations carry the identifiers instead.
    """
    d = answer.to_dict() if hasattr(answer, "to_dict") else dict(answer)
    claims = [c for c in d.get("claims") or []
              if not isinstance(c.get("verdict"), dict) or c["verdict"].get("supported", True)]
    seen: set[tuple[str, str]] = set()
    cites = []
    for c in claims:
        for ref in c.get("citations") or []:
            key = (str(ref.get("primary_id") or ""), str(ref.get("source") or ""))
            if key[0] and key not in seen:
                seen.add(key)
                cites.append(CitationRef(id=key[0], source=key[1]))
    trace = Trace(steps=0, served_model=served_model, seconds=seconds)
    if claims:
        text = (d.get("narrative") or d.get("headline") or " ".join(c.get("text", "") for c in claims)).strip()
        return AnswerEnvelope(run_id=run_id, status="answered", path="fast",
                              answer=Answer(text=text or claims[0].get("text", "")),
                              citations=cites, trace=trace)
    statements = [a.get("statement", "") for a in d.get("abstentions") or [] if a.get("statement")]
    reason = "; ".join(statements) or d.get("fallback_reason") or "no verified claims"
    return AnswerEnvelope(run_id=run_id, status="insufficient", path="fast", trace=trace, reason=reason)


ENVELOPE_SCHEMA: dict[str, Any] = AnswerEnvelope.model_json_schema()
REQUEST_SCHEMA: dict[str, Any] = AgentRequest.model_json_schema()
SCHEMA_DIR = Path(__file__).with_name("schemas")


def write_schemas(directory: Path = SCHEMA_DIR) -> list[Path]:
    """Write the JSON Schemas a non-Python caller reads. A test keeps them current."""
    directory.mkdir(parents=True, exist_ok=True)
    out = []
    for name, schema in (("envelope", ENVELOPE_SCHEMA), ("request", REQUEST_SCHEMA)):
        p = directory / f"{name}.schema.json"
        p.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        out.append(p)
    return out


__all__ = [
    "CLOCK_KEYS",
    "ENVELOPE_SCHEMA",
    "REQUEST_SCHEMA",
    "STATUSES",
    "AgentRequest",
    "Answer",
    "AnswerEnvelope",
    "AnswerSet",
    "Budget",
    "Caller",
    "CitationRef",
    "Clarification",
    "ClarifyOption",
    "ClarifyQuestion",
    "Confidence",
    "Trace",
    "envelope_from_synthesis",
    "strip_clock",
    "validate_envelope",
    "write_schemas",
]
