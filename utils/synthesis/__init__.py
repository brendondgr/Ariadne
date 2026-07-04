#!/usr/bin/env python3
"""Synthesis agent for Ariadne — the answer layer that proves itself.

The synthesis agent turns a ``FederatedEvidence`` bundle into the analyst-facing
answer as structured *claims with citations*, then a deterministic verifier
checks every claim against the actual evidence records that were retrieved.
Claims the evidence does not support are cut from the rendered prose and kept
flagged in the verification report. When a source honestly returned nothing,
the answer *abstains* — "the sources don't establish this" — with the executed
query attached as proof, never a plausible-sounding invention.

Layering (briefing Step 6): the specialists' gates catch malformed or dangerous
queries and their retry loop fixes visible failures; this package catches the
queries that ran cleanly but do not actually support the sentence the agent
wrote — each layer catches what the previous one structurally cannot.
"""

from __future__ import annotations

from .composer import DeterministicComposer
from .config import SynthesisConfig
from .contracts import (
    Abstention,
    Citation,
    Claim,
    ClaimVerdict,
    SynthesizedAnswer,
    VerificationReport,
)
from .verifier import verify_answer

__all__ = [
    "Abstention",
    "Citation",
    "Claim",
    "ClaimVerdict",
    "DeterministicComposer",
    "SynthesisConfig",
    "SynthesizedAnswer",
    "VerificationReport",
    "verify_answer",
]
