#!/usr/bin/env python3
"""OpenAI-compatible LLM drafter (the hybrid LLM path).

Posts a strict JSON-plan prompt to a configurable OpenAI-compatible endpoint
(default ``http://localhost:9090/v1`` / ``default-model``) and parses the reply
into a ``Plan``. It is grounded: the prompt shows only the **live** sources as
routable, names the **down** sources that must be marked unsupported, and lists
the declared canonical join keys — so the model drafts against ground truth.

The drafter never tries to grade itself; on any transport, HTTP, or parse
failure it raises ``DrafterUnavailable`` so the caller can fall back to the
deterministic drafter. The deterministic gate still decides whether the parsed
plan ships.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from .cards import SourceCardView
from .config import PlannerConfig
from .discovery import LiveSourceView
from .join_keys import CANONICAL_JOIN_KEYS
from .schema import Plan

if TYPE_CHECKING:
    from .intent import IntentClassification

logger = logging.getLogger("ariadne.planner.llm")


class DrafterUnavailable(Exception):
    """Raised when the LLM endpoint cannot produce a usable draft."""


_SYSTEM_PROMPT = """\
You are the routing planner for a federated graph-database system. You do not \
query databases; you only emit a machine-readable PLAN that routes an analyst \
request to live graph sources.

Rules you MUST follow:
- Route a sub-question ONLY to a source listed under LIVE SOURCES.
- Every entity you name in a sub-question MUST be a node label or relationship \
type listed for that source. Never invent labels, relationships, or sources.
- Every sub-question MUST include a "limits" object, using values no larger \
than that source's stated bounds.
- If part of the request needs a DOWN source or data no live source holds, add \
it to "unsupported" with a reason and set "partial": true. Never fabricate a \
path to look helpful.
- A DEFINITIONAL question that names an entity by its human name rather than an \
id (e.g. "What is Phishing?", "Define User Training") IS answerable: route a \
sub-question to the live source(s) whose schema could hold that entity, keep the \
entity name in the sub-question "text", and use the source's most general node \
label as its "entities". Do NOT mark such a question unsupported merely because \
the name is not itself a label — the specialist resolves entities by name.
- Only declare a "join" using a key from DECLARED JOIN KEYS, and only between \
two live sources that both expose it.
- State any interpretation you had to choose in "assumptions".

Output ONLY a single JSON object (no prose, no markdown fences) with this shape:
{
  "sub_questions": [
    {"id": "q1", "source": "<dataset>", "text": "<what to retrieve>",
     "entities": ["<Label or REL>", ...],
     "limits": {"max_traversal_depth": <int>, "max_result_rows": <int>, "query_timeout_ms": <int>},
     "join_key": "<declared key or null>", "rationale": "<why this source>"}
  ],
  "joins": [{"key": "<declared key>", "sources": ["<a>", "<b>"], "on": "<note>"}],
  "unsupported": [{"description": "<what>", "reason": "<why>"}],
  "assumptions": ["<assumption>"],
  "rationale": "<overall source-selection rationale>",
  "partial": <true|false>
}
"""


def _source_block(card: SourceCardView, live: bool) -> str:
    limits = card.limits()
    node_glosses = (card.entity_descriptions or {}).get("nodes", {})
    labels = ", ".join(sorted(card.node_labels))
    rels = ", ".join(sorted(card.relationship_types))
    gloss_lines = "\n".join(
        f"    - {label}: {node_glosses[label]}"
        for label in sorted(card.node_labels)
        if label in node_glosses
    )
    status = "LIVE" if live else "DOWN"
    return (
        f"- {card.dataset} [{status}] (backend={card.runtime_backend})\n"
        f"    node_labels: {labels}\n"
        f"    relationship_types: {rels}\n"
        f"    limit bounds: {limits}\n"
        f"    glosses:\n{gloss_lines}"
    )


def build_messages(
    request: str,
    cards: dict[str, SourceCardView],
    live_view: LiveSourceView,
    feedback: list[str] | None = None,
    intent: "IntentClassification | None" = None,
) -> list[dict[str, str]]:
    """Build the chat messages for one draft (pure; testable without HTTP)."""
    live_blocks, down_blocks = [], []
    for ds in sorted(cards):
        block = _source_block(cards[ds], live_view.is_live(ds))
        (live_blocks if live_view.is_live(ds) else down_blocks).append(block)

    join_lines = "\n".join(
        f"- {key.name}: {key.description}" for key in CANONICAL_JOIN_KEYS
    )
    context = [
        "LIVE SOURCES (routable):",
        "\n".join(live_blocks) if live_blocks else "  (none live)",
        "",
        "DOWN SOURCES (must be marked unsupported if needed):",
        "\n".join(down_blocks) if down_blocks else "  (none down)",
        "",
        "DECLARED JOIN KEYS:",
        join_lines or "  (none)",
    ]
    if intent is not None:
        # A prior classifier already named the intent; give it to the model as a
        # hint (e.g. a "correlation" intent should declare a cross-source join).
        context += [
            "",
            f"CLASSIFIED INTENT: {intent.label} (confidence {intent.confidence:.2f})"
            + (f" — cues: {', '.join(intent.cues)}" if intent.cues else ""),
        ]
    context += ["", f"ANALYST REQUEST:\n{request}"]
    if feedback:
        context += [
            "",
            "YOUR PREVIOUS DRAFT WAS REJECTED. Fix exactly these problems:",
            "\n".join(f"- {r}" for r in feedback),
        ]
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(context)},
    ]


def extract_json_object(text: str) -> dict:
    """Extract the first balanced top-level JSON object from model output."""
    if not text:
        raise DrafterUnavailable("empty model response")
    start = text.find("{")
    if start == -1:
        raise DrafterUnavailable("no JSON object in model response")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = text[start : i + 1]
                try:
                    return json.loads(blob)
                except json.JSONDecodeError as exc:
                    raise DrafterUnavailable(f"invalid JSON in response: {exc}") from exc
    raise DrafterUnavailable("unbalanced JSON object in model response")


class OpenAICompatibleDrafter:
    """Drafts plans via a configurable OpenAI-compatible chat endpoint."""

    def __init__(self, config: PlannerConfig) -> None:
        self._config = config

    @property
    def endpoint(self) -> str:
        return self._config.llm_base_url.rstrip("/") + "/chat/completions"

    def _post(self, messages: list[dict[str, str]]) -> str:
        import requests

        payload = {
            "model": self._config.llm_model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self._config.llm_max_tokens,
        }
        try:
            resp = requests.post(
                self.endpoint, json=payload, timeout=self._config.llm_timeout_s
            )
        except requests.RequestException as exc:
            raise DrafterUnavailable(f"request failed: {exc}") from exc
        if resp.status_code != 200:
            raise DrafterUnavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise DrafterUnavailable(f"unexpected response shape: {exc}") from exc
        if not content:
            raise DrafterUnavailable("model returned no content (raise max_tokens?)")
        return content

    def draft(
        self,
        request: str,
        cards: dict[str, SourceCardView],
        live_view: LiveSourceView,
        feedback: list[str] | None = None,
        intent: "IntentClassification | None" = None,
    ) -> Plan:
        messages = build_messages(request, cards, live_view, feedback, intent)
        content = self._post(messages)
        data = extract_json_object(content)
        data["request"] = request
        plan = Plan.from_dict(data)
        logger.info(
            "LLM drafted %d sub-question(s), %d unsupported",
            len(plan.sub_questions),
            len(plan.unsupported),
        )
        return plan
