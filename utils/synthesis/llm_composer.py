#!/usr/bin/env python3
"""OpenAI-compatible LLM composer (the hybrid LLM path).

Posts the federated evidence bundle to a configurable OpenAI-compatible
endpoint and parses the reply into a ``SynthesizedAnswer`` draft of structured
claims-with-citations. The prompt shows the model *only* retrieved records and
requires every claim to cite them — but nothing here is trusted: the draft
flows through the same deterministic ``verify_answer`` pass as the mechanical
composer, which cuts anything the evidence does not support and enforces
abstention on honest empties.

On any transport, HTTP, or parse failure it raises ``ComposerUnavailable`` so
the hybrid factory can fall back to the deterministic composer.
"""

from __future__ import annotations

import json
import logging

from utils.specialists.federation import FederatedEvidence

from .config import SynthesisConfig
from .contracts import Abstention, Claim, SynthesizedAnswer

logger = logging.getLogger("ariadne.synthesis.llm")


class ComposerUnavailable(Exception):
    """Raised when the LLM endpoint cannot produce a usable draft."""


_SYSTEM_PROMPT = """\
You are the synthesis agent for a federated graph-database system. You are \
given the ONLY evidence that exists: records retrieved from live graph \
sources, with provenance. You write the analyst-facing answer as structured, \
checkable claims. A deterministic verifier will check every claim against the \
records; any claim it cannot ground WILL be cut.

Rules you MUST follow:
- Every claim MUST cite records from EVIDENCE RECORDS via (source, primary_id).
- Every identifier a claim asserts MUST appear in "entity_ids" and MUST come \
from the cited records (their primary ids, join values, or related ids). \
Never introduce an identifier that is not in the evidence.
- Use kind "correlation" ONLY for identifiers listed under CROSS-SOURCE JOIN \
VALUES; use kind "fact" otherwise.
- For every sub-question under EMPTY SUB-QUESTIONS, add an abstention that \
plainly states the sources don't establish it. Do NOT write claims about \
those sub-questions and do NOT guess.
- Never state more than the records show. If the evidence is thin, say less.

Output ONLY a single JSON object (no prose, no markdown fences) with this shape:
{
  "headline": "<one-sentence summary of what the evidence establishes>",
  "final_answer": "<a direct, natural-language answer to the ANALYST REQUEST, \
written for a human analyst, grounded ONLY in the evidence records — 1-4 \
sentences; if the evidence does not answer the question, say so plainly>",
  "claims": [
    {"text": "<one checkable sentence>",
     "citations": [{"source": "<dataset>", "primary_id": "<id>"}],
     "entity_ids": ["<every identifier the sentence asserts>"],
     "kind": "fact" | "correlation",
     "sub_question_id": "<originating sub-question id or empty>"}
  ],
  "abstentions": [
    {"sub_question_id": "<id>", "source": "<dataset>",
     "statement": "<the sources don't establish this, stated plainly>"}
  ]
}
"""

# Bound the evidence context: per-record related entries and total records per
# result are capped so the prompt stays within the model's context window.
_MAX_RECORDS_PER_RESULT = 50
_MAX_RELATED_PER_RECORD = 30
_MAX_FACETS_PER_RECORD = 20
_MAX_PROP_CHARS = 600
# Bulky citation arrays carry no evidentiary value for the composer — dropped
# with an explicit marker rather than silently, so a long value is never mistaken
# for the whole property set.
_SKIP_PROPERTIES = frozenset({"external_references"})


def _bounded_properties(properties) -> dict:
    """A prompt-safe view of a record's properties (the description survives whole,
    long strings are marked-truncated, bulky arrays are dropped with a marker)."""
    out: dict = {}
    dropped: list[str] = []
    for key, value in (properties or {}).items():
        if key in _SKIP_PROPERTIES:
            dropped.append(key)
            continue
        if isinstance(value, str):
            out[key] = value[:_MAX_PROP_CHARS] + ("…" if len(value) > _MAX_PROP_CHARS else "")
        elif isinstance(value, bool) or isinstance(value, (int, float)) or value is None:
            out[key] = value
        elif isinstance(value, list):
            out[key] = [str(v) for v in value[:10]]
            if len(value) > 10:
                out[key].append(f"…(+{len(value) - 10} more)")
    if dropped:
        out["_omitted_properties"] = sorted(dropped)
    return out


def _record_line(record) -> str:
    entry = {
        "primary_id": record.primary_id,
        "label": record.label,
        "name": record.name,
        "join_values": list(record.join_values),
        # The node's own properties — description and attributes — were dropped
        # here before, so the composer wrote answers blind to what a node *is*.
        "properties": _bounded_properties(record.properties),
        # The bounded facet block: adjacency counts by (rel, direction, neighbour
        # label), incl. honest zeros, so the composer can assert presence AND
        # absence ("has no sub-techniques") from the same summary.
        "facets": [
            {
                "rel": f.get("rel"),
                "direction": f.get("direction"),
                "neighbour_label": f.get("label"),
                "count": f.get("count"),
            }
            for f in (record.facets or [])[:_MAX_FACETS_PER_RECORD]
        ],
        # Related neighbours now keep their edge semantics (type/direction) — the
        # normalizers computed them and this layer used to strip them out.
        "related": [
            {k: v for k, v in rel.items() if k in ("id", "entry_id", "name", "type", "direction", "label")}
            for rel in record.related[:_MAX_RELATED_PER_RECORD]
        ],
    }
    return json.dumps(entry, ensure_ascii=False)


def build_evidence_context(evidence: FederatedEvidence) -> str:
    """The user-message body: request + retrieved records + joins + empties.

    Shared by the claims composer and the prose narrator so both reason over the
    exact same evidence framing (pure; testable without HTTP).
    """
    blocks: list[str] = []
    empties: list[str] = []
    for result in evidence.results:
        task = result.task
        if result.records:
            shown = result.records[:_MAX_RECORDS_PER_RESULT]
            lines = "\n".join(f"    {_record_line(r)}" for r in shown)
            more = (
                f"\n    ... {len(result.records) - len(shown)} more record(s) omitted"
                if len(result.records) > len(shown)
                else ""
            )
            blocks.append(
                f"- sub_question {task.sub_question_id} (source={task.source}): "
                f"{task.text}\n  records:\n{lines}{more}"
            )
        elif result.ok:
            empties.append(
                f"- sub_question {task.sub_question_id} (source={task.source}): "
                f"{task.text}"
            )

    context = [
        f"ANALYST REQUEST:\n{evidence.request}",
        "",
        "EVIDENCE RECORDS (the only facts that exist):",
        "\n".join(blocks) if blocks else "  (none)",
        "",
        "CROSS-SOURCE JOIN VALUES (identifiers corroborated by 2+ sources):",
        ", ".join(evidence.cross_source_join_values()) or "  (none)",
        "",
        "EMPTY SUB-QUESTIONS (ran cleanly, zero records — MUST abstain):",
        "\n".join(empties) if empties else "  (none)",
    ]
    return "\n".join(context)


def build_messages(evidence: FederatedEvidence) -> list[dict[str, str]]:
    """Build the chat messages for one composition (pure; testable without HTTP)."""
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": build_evidence_context(evidence)},
    ]


def extract_json_object(text: str) -> dict:
    """Extract the first balanced top-level JSON object from model output."""
    if not text:
        raise ComposerUnavailable("empty model response")
    start = text.find("{")
    if start == -1:
        raise ComposerUnavailable("no JSON object in model response")
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
                    raise ComposerUnavailable(f"invalid JSON in response: {exc}") from exc
    raise ComposerUnavailable("unbalanced JSON object in model response")


def parse_answer(data: dict, evidence: FederatedEvidence) -> SynthesizedAnswer:
    """Turn the model's JSON into an (unverified) ``SynthesizedAnswer`` draft."""
    claims = [Claim.from_dict(c) for c in data.get("claims", []) or []]
    abstentions = [
        Abstention.from_dict(a) for a in data.get("abstentions", []) or []
    ]
    return SynthesizedAnswer(
        request=evidence.request,
        headline=str(data.get("headline", "") or ""),
        narrative=str(data.get("final_answer", "") or ""),
        claims=claims,
        abstentions=abstentions,
        composer="llm",
    )


class OpenAICompatibleComposer:
    """Composes answers via a configurable OpenAI-compatible chat endpoint."""

    name = "llm"

    def __init__(self, config: SynthesisConfig) -> None:
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
            raise ComposerUnavailable(f"request failed: {exc}") from exc
        if resp.status_code != 200:
            raise ComposerUnavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ComposerUnavailable(f"unexpected response shape: {exc}") from exc
        if not content:
            raise ComposerUnavailable("model returned no content (raise max_tokens?)")
        return content

    def compose(self, evidence: FederatedEvidence) -> SynthesizedAnswer:
        messages = build_messages(evidence)
        content = self._post(messages)
        data = extract_json_object(content)
        answer = parse_answer(data, evidence)
        logger.info(
            "LLM composed %d claim(s), %d abstention(s)",
            len(answer.claims),
            len(answer.abstentions),
        )
        return answer
