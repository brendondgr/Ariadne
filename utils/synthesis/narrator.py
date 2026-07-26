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
from typing import Any

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
- When many identifiers share a relationship, state the total and name a \
representative few (e.g. "TrickBot uses 55 techniques, including T1055, T1027, \
…"); the complete list is carried in the structured claims, so you need not \
list every id in the prose. Never say a set is empty or that only "a few" exist \
when the evidence lists more — report the true count.
- A related entity may carry a role (e.g. an abstraction ancestor tagged \
"standard" or "meta"). When it does, state which id plays which role — do not \
merely say both exist. NEVER claim the evidence "does not contain" or "does not \
name" identifiers that are present in a record's related set: if they are \
listed, name them.
- If the evidence does not answer part of the request, say so plainly — but \
NEVER invent the reason. The only permitted explanations for a missing part are \
the ones written under "SUB-QUESTIONS THAT DID NOT RUN OR FAILED", "DEPENDENT-HOP \
SEEDING" and "EMPTY SUB-QUESTIONS". Do NOT say a query "returned zero results" \
unless it is listed as empty; do NOT say a source "does not cover" the request \
unless it is listed as not supported; do NOT describe a timeout or a skipped hop \
as an absence of data. If a hop was NOT seeded, say the join could not be made — \
not that the relationship does not exist.
- NEVER assert that something does not exist for a source that was not queried.
- NEVER state a count you did not read off the evidence (record counts, a \
record's "facets" count, or the length of its "related" list). Do not add, \
estimate, or infer totals.
- Do NOT assign identifiers to tactics, phases, or categories, and do not \
characterise what they "correspond to", unless the evidence carries that \
relationship explicitly. Unsupported framing is a fabrication even when the \
identifiers themselves are real.
- When a record carries the attribute the question asks about (e.g. Abstraction, \
Status, a name), state its value verbatim from the record's properties.
Output only the answer prose.
"""


#: Appended when the narrator is given the verified claims to render. Without it
#: the narrator re-derives the answer from raw evidence *in parallel with* the
#: deterministic composer, which is why its prose could enumerate less than the
#: claims already had (a 55-id enumeration claim rendered as "including three")
#: and could assert what no claim supported. With it the claims are the spine and
#: the model's only job is to read them aloud.
_CLAIM_RENDER_RULES = """\

You are ALSO given VERIFIED CLAIMS: the deterministic, citation-checked answer \
that has already been established from this evidence. Those claims — not your \
own reading of the records — are the answer.
- Render EVERY verified claim. The prose must state every identifier the claims \
assert; if a claim enumerates 55 ids, the prose reports all 55 (list them; a long \
list is correct, and "including" or "such as" is not).
- Add NOTHING the claims do not assert. You may use the evidence records for a \
name, a description, or an attribute value that makes a claim readable, but you \
may not introduce a fact, an identifier, a count, or a relationship that no claim \
carries.
- Do not re-analyse, re-count, or second-guess the claims. If a claim states a \
count, use that count verbatim.
- Your job is to make the established answer read as fluent analyst prose — \
ordering, grouping by claim, and connective language are yours; the facts are not.
"""


def _claims_block(answer: Any) -> str:
    """The verified claims rendered for the narrator, or an empty string."""
    claims = []
    try:
        rendered = answer.rendered_claims()
    except Exception:  # noqa: BLE001 — narration must never sink on a bad answer
        return ""
    for claim in rendered:
        text = (claim.text or "").strip()
        if text:
            claims.append(f"- {text}")
    abstentions = [
        f"- (abstention) {a.statement}"
        for a in (getattr(answer, "abstentions", None) or [])
        if getattr(a, "statement", "")
    ]
    if not claims and not abstentions:
        return ""
    return "\n".join(
        ["", "VERIFIED CLAIMS (the established answer — render all of it, add nothing):"]
        + claims
        + abstentions
    )


def build_narrator_messages(
    evidence: FederatedEvidence, answer: Any | None = None
) -> list[dict[str, str]]:
    """Chat messages for one narration (pure; testable without HTTP).

    When ``answer`` is given, its verified claims are supplied as the spine and the
    system prompt switches from "read the evidence" to "render this answer".
    """
    block = _claims_block(answer) if answer is not None else ""
    system = _NARRATOR_SYSTEM + (_CLAIM_RENDER_RULES if block else "")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": build_evidence_context(evidence) + block},
    ]


def compose_narrative(
    evidence: FederatedEvidence, config: SynthesisConfig, answer: Any | None = None
) -> str:
    """Return a short prose answer from the LLM, or raise ``ComposerUnavailable``."""
    import requests

    endpoint = config.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.llm_model,
        "messages": build_narrator_messages(evidence, answer),
        "temperature": 0,
        "max_tokens": config.llm_max_tokens,
        "thinking_token_budget": config.thinking_budget(),
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
