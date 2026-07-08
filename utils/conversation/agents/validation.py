#!/usr/bin/env python3
"""The post-extraction Validation agent (bounded sufficiency-retry gate).

After graph extraction, decide whether the grounded evidence sufficiently
answers the resolved question. If not — and we are under the retry cap — return
new search parameters + a reason and loop back into extraction. Otherwise pass
to the Answer agent.

Boundedness & determinism:

* The retry cap (``max_validation_iters``) is enforced here: once that many
  extraction attempts have completed, the verdict is forced to ``pass`` so the
  loop always terminates.
* Deterministic fallback (LLM off/failing) is ``pass``. We never loop without an
  explicit LLM judgment — this keeps LLM-off builds reproducible and cannot spin.
"""

from __future__ import annotations

from typing import Any

from utils.conversation.agents._common import extract_json_object
from utils.conversation.config import ConversationConfig
from utils.conversation.llm import ConversationLLM, LLMUnavailable
from utils.synthesis.contracts import SynthesizedAnswer

VERDICT_PASS = "pass"
VERDICT_INSUFFICIENT = "insufficient"

_SYSTEM = (
    "You are the validation gate for a cybersecurity knowledge-graph assistant. "
    "You are given the analyst's question and the grounded answer produced from "
    "the graphs. Decide whether the grounded answer sufficiently and completely "
    "answers the question. Do not judge on style — only on whether the necessary "
    "facts are present. If something important is missing, list concrete follow-up "
    "search focuses that a graph query could retrieve.\n\n"
    "Respond with a single JSON object: "
    '{"sufficient": true|false, "missing": ["..."], "reason": "<short reason>"}.'
)


def _grounded_summary(answer: SynthesizedAnswer | None) -> str:
    if answer is None:
        return "(no answer produced)"
    parts: list[str] = []
    if answer.narrative:
        parts.append(answer.narrative)
    for claim in answer.rendered_claims():
        parts.append(f"- {claim.text}")
    return "\n".join(parts) if parts else "(no grounded claims)"


def evaluate_sufficiency(
    question: str,
    answer: SynthesizedAnswer | None,
    config: ConversationConfig,
    client: ConversationLLM | None = None,
) -> tuple[str, str, list[str]]:
    """Return ``(verdict, reason, missing)`` for one extraction result."""
    client = client or ConversationLLM(config.llm)
    if not client.enabled:
        return VERDICT_PASS, "validation LLM disabled — accepting evidence", []

    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Grounded answer:\n{_grounded_summary(answer)}"
            ),
        },
    ]
    try:
        data = extract_json_object(client.complete(messages, max_tokens=300))
    except (LLMUnavailable, ValueError):
        return VERDICT_PASS, "validation LLM unavailable — accepting evidence", []

    sufficient = bool(data.get("sufficient", True))
    reason = str(data.get("reason", "")).strip() or "validation decision"
    missing = [str(m).strip() for m in (data.get("missing") or []) if str(m).strip()]
    if sufficient:
        return VERDICT_PASS, reason, []
    return VERDICT_INSUFFICIENT, reason, missing


def make_validation_node(
    config: ConversationConfig, client: ConversationLLM | None = None
):
    """Build the LangGraph node that gates extraction and bounds the retry loop."""

    def validation_node(state: dict[str, Any]) -> dict[str, Any]:
        attempts = int(state.get("validation_iterations", 0)) + 1
        question = state.get("resolved_question") or state.get("question", "")

        # Hard cap: after this many attempts, always accept and move on.
        if attempts >= config.max_validation_iters:
            return {
                "validation_iterations": attempts,
                "validation_verdict": VERDICT_PASS,
                "validation_reason": "retry cap reached — accepting best evidence",
                "validation_missing": [],
                "trace": [
                    {"node": "validation", "verdict": VERDICT_PASS, "capped": True}
                ],
            }

        verdict, reason, missing = evaluate_sufficiency(
            question, state.get("answer"), config, client
        )
        out: dict[str, Any] = {
            "validation_iterations": attempts,
            "validation_verdict": verdict,
            "validation_reason": reason,
            "validation_missing": missing,
            "trace": [
                {"node": "validation", "verdict": verdict, "attempt": attempts}
            ],
        }
        if verdict == VERDICT_INSUFFICIENT:
            out["extraction_params"] = {"focus": missing, "reason": reason}
        return out

    return validation_node
