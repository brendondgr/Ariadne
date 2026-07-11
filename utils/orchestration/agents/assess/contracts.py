#!/usr/bin/env python3
"""The sufficiency verdict the ``assess`` node writes into pipeline state.

``Assessment`` is a small, frozen, JSON-serializable contract — it rides in
``PipelineState['assessment']`` and (Step 7) is surfaced as a stream event, so
it stays flat and stable like the other pipeline contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Assessment:
    """Whether the accumulated evidence answers the request — and if not, why.

    * ``sufficient`` — stop the loop and synthesize when True.
    * ``gaps`` — natural-language "what's missing" strings that seed the
      re-plan (deterministic: declared-join and novelty gaps; LLM: the critic's
      prose).
    * ``missing_entities`` — concrete join-key values discovered but not yet
      resolved across sources; the re-planner chases these into the other side.
    * ``hop`` — the hop this verdict was produced on.
    * ``hop_capped`` — True when sufficiency was *forced* by the hop cap rather
      than earned by the predicate (termination guarantee, surfaced honestly).
    * ``mode`` — which judge ran: ``"deterministic"``, ``"llm"``, or
      ``"deterministic (llm fallback)"`` when the critic was requested but
      unavailable.
    * ``reason`` — a one-line human summary for the trace / UI.
    """

    sufficient: bool
    gaps: list[str] = field(default_factory=list)
    missing_entities: list[str] = field(default_factory=list)
    hop: int = 1
    hop_capped: bool = False
    mode: str = "deterministic"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sufficient": self.sufficient,
            "gaps": list(self.gaps),
            "missing_entities": list(self.missing_entities),
            "hop": self.hop,
            "hop_capped": self.hop_capped,
            "mode": self.mode,
            "reason": self.reason,
        }
