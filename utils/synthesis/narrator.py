#!/usr/bin/env python3
"""The prose narrator: a short natural-language answer to the analyst's question.

Separate from the claims composer on purpose. Asking a model to regenerate the
full structured claims-with-citations JSON over a large evidence bundle makes it
over-generate and truncate (or return nothing), so that path is unreliable at
scale. The narrator instead asks for *only* a few sentences of plain prose that
directly answer the question, grounded in the same evidence — small, bounded
output that models handle reliably.

The narrative is the readable answer shown above the verified claim table; the
claim table remains the trust surface. On any transport/HTTP/empty failure this
raises ``ComposerUnavailable`` so the caller keeps the deterministic narrative.
"""

from __future__ import annotations

import logging

from utils.specialists.federation import FederatedEvidence

from .config import SynthesisConfig
from .llm_composer import ComposerUnavailable, build_evidence_context

logger = logging.getLogger("ariadne.synthesis.narrator")

_NARRATOR_SYSTEM = """\
You are a cybersecurity analyst assistant for a federated graph system that \
joins MITRE ATT&CK (techniques, mitigations) and CAPEC (attack patterns). You \
are given the ANALYST REQUEST and the ONLY evidence that exists: records \
retrieved from the live graphs.

Write a clear, natural-language answer to the request for a human analyst:
- 2 to 5 sentences of plain prose. No JSON, no bullet lists, no markdown.
- Ground every statement in the evidence. Name the relevant ATT&CK/CAPEC \
identifiers where it helps, but NEVER invent an identifier that is not in the \
evidence.
- When many identifiers share a relationship, summarise (e.g. "18 techniques \
are corroborated across both sources, including …") rather than listing them all.
- If the evidence does not answer part of the request, say so plainly.
Output only the answer prose.
"""


def build_narrator_messages(evidence: FederatedEvidence) -> list[dict[str, str]]:
    """Chat messages for one narration (pure; testable without HTTP)."""
    return [
        {"role": "system", "content": _NARRATOR_SYSTEM},
        {"role": "user", "content": build_evidence_context(evidence)},
    ]


def compose_narrative(evidence: FederatedEvidence, config: SynthesisConfig) -> str:
    """Return a short prose answer from the LLM, or raise ``ComposerUnavailable``."""
    import requests

    endpoint = config.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.llm_model,
        "messages": build_narrator_messages(evidence),
        "temperature": 0,
        "max_tokens": config.llm_max_tokens,
    }
    try:
        resp = requests.post(endpoint, json=payload, timeout=config.llm_timeout_s)
    except requests.RequestException as exc:
        raise ComposerUnavailable(f"request failed: {exc}") from exc
    if resp.status_code != 200:
        raise ComposerUnavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ComposerUnavailable(f"unexpected response shape: {exc}") from exc
    text = (content or "").strip()
    if not text:
        raise ComposerUnavailable("model returned no content (raise max_tokens?)")
    logger.info("LLM narrated a %d-char answer", len(text))
    return text
