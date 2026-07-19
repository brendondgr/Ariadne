#!/usr/bin/env python3
"""OpenAI-compatible LLM judge (the opt-in LLM-as-judge path).

Posts a verified answer plus the evidence it was built from to a configurable
OpenAI-compatible endpoint and parses back numeric scores for faithfulness,
groundedness, and evidence sufficiency. This is an *estimate layer* on top of
the deterministic verifier — it never overrides the reproducible metrics; the
report labels its numbers as LLM-derived and non-reproducible.

On any transport, HTTP, or parse failure it raises ``JudgeUnavailable`` so the
hybrid factory can fall back to the deterministic proxy judge. The prompt is
built purely (testable without HTTP).
"""

from __future__ import annotations

import json
import logging

from utils.specialists.federation import FederatedEvidence
from utils.synthesis.contracts import SynthesizedAnswer

from .config import EvalConfig
from .contracts import JudgeVerdict

logger = logging.getLogger("ariadne.evaluation.judge")


class JudgeUnavailable(Exception):
    """Raised when the LLM judge endpoint cannot produce a usable verdict."""


_SYSTEM_PROMPT = """\
You are an evaluation judge for a federated graph-database question-answering \
system. You are given an analyst QUESTION, the prose ANSWER shown to the analyst, \
the verified CLAIMS backing it (each already cites evidence records), any \
ABSTENTIONS, and the EVIDENCE RECORDS that were actually retrieved. Judge the \
prose ANSWER (the claims and evidence are the ground truth it must stay faithful \
to). Rate it on three dimensions, each a number from 0.0 to 1.0:

- faithfulness: does every statement follow from the evidence, with nothing \
invented or overstated?
- groundedness: is every identifier and fact traceable to a cited record?
- evidence_sufficiency: does the answer make appropriate use of the retrieved \
evidence (neither ignoring available records nor over-claiming beyond them)? \
An honest abstention when no evidence exists is fully sufficient.

Output ONLY a single JSON object (no prose, no markdown fences):
{"faithfulness": <0..1>, "groundedness": <0..1>, \
"evidence_sufficiency": <0..1>, "reasons": ["<short note>"]}
"""

_MAX_RECORDS_PER_RESULT = 40
_MAX_RELATED_PER_RECORD = 20


def _record_line(record) -> str:
    entry = {
        "primary_id": record.primary_id,
        "label": record.label,
        "name": record.name,
        "join_values": list(record.join_values),
        "related": [
            {k: v for k, v in rel.items() if k in ("id", "entry_id", "name")}
            for rel in record.related[:_MAX_RELATED_PER_RECORD]
        ],
    }
    return json.dumps(entry, ensure_ascii=False)


def build_messages(
    answer: SynthesizedAnswer, evidence: FederatedEvidence
) -> list[dict[str, str]]:
    """Build the chat messages for one judgment (pure; testable without HTTP)."""
    claim_lines = [
        json.dumps(
            {
                "text": c.text,
                "entity_ids": list(c.entity_ids),
                "kind": c.kind,
                "citations": [
                    {"source": cit.source, "primary_id": cit.primary_id}
                    for cit in c.citations
                ],
            },
            ensure_ascii=False,
        )
        for c in answer.rendered_claims()
    ]
    abstention_lines = [
        f"- ({a.source}) {a.statement}" for a in answer.abstentions
    ]
    evidence_blocks: list[str] = []
    for result in evidence.results:
        if not result.records:
            continue
        shown = result.records[:_MAX_RECORDS_PER_RESULT]
        lines = "\n".join(f"    {_record_line(r)}" for r in shown)
        more = (
            f"\n    ... {len(result.records) - len(shown)} more omitted"
            if len(result.records) > len(shown)
            else ""
        )
        evidence_blocks.append(
            f"- {result.task.sub_question_id} (source={result.task.source}):\n"
            f"{lines}{more}"
        )

    context = [
        f"QUESTION:\n{answer.request}",
        "",
        "ANSWER (prose shown to the analyst):",
        answer.narrative.strip() or "  (none)",
        "",
        "ANSWER CLAIMS (verified, with citations):",
        "\n".join(claim_lines) if claim_lines else "  (none)",
        "",
        "ABSTENTIONS:",
        "\n".join(abstention_lines) if abstention_lines else "  (none)",
        "",
        "EVIDENCE RECORDS (the only facts that exist):",
        "\n".join(evidence_blocks) if evidence_blocks else "  (none)",
    ]
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(context)},
    ]


def extract_json_object(text: str) -> dict:
    """Extract the first balanced top-level JSON object from model output."""
    if not text:
        raise JudgeUnavailable("empty model response")
    start = text.find("{")
    if start == -1:
        raise JudgeUnavailable("no JSON object in model response")
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
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as exc:
                    raise JudgeUnavailable(f"invalid JSON in response: {exc}") from exc
    raise JudgeUnavailable("unbalanced JSON object in model response")


def _clamp01(value) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))


def parse_verdict(
    data: dict,
    question_id: str,
    unsupported_claim_rate: float,
    conflict_count: int = 0,
) -> JudgeVerdict:
    """Turn the model's JSON into a ``JudgeVerdict`` (unsupported rate and
    conflict count stay deterministic — the LLM never sets them)."""
    reasons = data.get("reasons") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    return JudgeVerdict(
        question_id=question_id,
        source="llm",
        faithfulness=_clamp01(data.get("faithfulness")),
        groundedness=_clamp01(data.get("groundedness")),
        evidence_sufficiency=_clamp01(data.get("evidence_sufficiency")),
        unsupported_claim_rate=unsupported_claim_rate,
        conflict_count=conflict_count,
        reasons=[str(r) for r in reasons][:5],
    )


class OpenAICompatibleJudge:
    """Judges answers via a configurable OpenAI-compatible chat endpoint."""

    name = "llm"

    def __init__(self, config: EvalConfig) -> None:
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
            raise JudgeUnavailable(f"request failed: {exc}") from exc
        if resp.status_code != 200:
            raise JudgeUnavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise JudgeUnavailable(f"unexpected response shape: {exc}") from exc
        if not content:
            raise JudgeUnavailable("model returned no content (raise max_tokens?)")
        return content

    def judge(
        self,
        question_id: str,
        answer: SynthesizedAnswer,
        evidence: FederatedEvidence,
    ) -> JudgeVerdict:
        report = answer.verification
        unsupported_rate = report.unsupported_claim_rate if report else 0.0
        conflict_count = report.conflict_count if report else 0
        messages = build_messages(answer, evidence)
        content = self._post(messages)
        data = extract_json_object(content)
        verdict = parse_verdict(data, question_id, unsupported_rate, conflict_count)
        logger.info(
            "LLM judged %s: faith=%.2f ground=%.2f suff=%.2f",
            question_id,
            verdict.faithfulness,
            verdict.groundedness,
            verdict.evidence_sufficiency,
        )
        return verdict
