#!/usr/bin/env python3
"""Google Gemini (the ``generativeLanguage`` REST surface).

The failure mode to design against here is silence. Gemini returns **200 with an
empty candidate list** when a prompt is blocked by a safety filter, so a caller
that indexes ``candidates[0]`` crashes on a policy decision, and one that reads
``.get("candidates", [])`` reports "the model said nothing" for something the
operator could have fixed. :meth:`GeminiAdapter.parse_chat` surfaces the
``promptFeedback.blockReason`` as the finish reason instead.

Other departures: the container is ``contents`` not ``messages``, the assistant
role is spelled ``model``, the system prompt is a separate
``systemInstruction``, generation knobs live under ``generationConfig`` with
``maxOutputTokens`` rather than ``max_tokens``, and listed model names are
prefixed (``models/gemini-3.7-flash``) while the id you send back is bare.
"""

from __future__ import annotations

from typing import Any

from utils.llm.config import LLMSettings
from utils.llm.types import FINISH_LENGTH, ChatResult, Message, ModelInfo, Usage

from .base import split_system


class GeminiAdapter:
    name = "gemini"

    def _headers(self, settings: LLMSettings) -> dict[str, str]:
        return {"Content-Type": "application/json", "x-goog-api-key": settings.api_key}

    def chat_request(
        self,
        settings: LLMSettings,
        messages: list[Message],
        *,
        max_tokens: int,
        temperature: float,
        sampling: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        system, rest = split_system(messages)
        payload: dict[str, Any] = {
            "contents": [
                {
                    # Gemini's assistant role is "model"; sending "assistant"
                    # is rejected.
                    "role": "model" if m.role == "assistant" else "user",
                    "parts": [{"text": m.content}],
                }
                for m in rest
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if sampling and "top_p" in sampling:
            payload["generationConfig"]["topP"] = sampling["top_p"]
        # `seed` has no REST equivalent and unsupported keys are ignored rather
        # than rejected, so sending it would look like it worked. Dropped.
        model = settings.model.removeprefix("models/")
        url = f"{settings.base_url.rstrip('/')}/models/{model}:generateContent"
        return url, self._headers(settings), payload

    def parse_chat(self, body: dict[str, Any]) -> ChatResult:
        candidates = body.get("candidates") or []
        if not candidates:
            # 200 with no candidates == blocked prompt. Name it, so the operator
            # sees a policy decision rather than an unexplained empty answer.
            feedback = body.get("promptFeedback") or {}
            reason = str(feedback.get("blockReason") or "no candidates returned")
            return ChatResult(content="", finish_reason=f"blocked: {reason}", raw=body)

        first = candidates[0]
        parts = ((first.get("content") or {}).get("parts")) or []
        text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))
        raw_usage = body.get("usageMetadata") or {}
        finish = str(first.get("finishReason") or "")
        return ChatResult(
            content=text,
            # Normalize MAX_TOKENS onto the project's `length` so `.truncated`
            # holds the same meaning across providers.
            finish_reason=FINISH_LENGTH if finish == "MAX_TOKENS" else finish,
            usage=Usage(
                prompt_tokens=int(raw_usage.get("promptTokenCount") or 0),
                completion_tokens=int(raw_usage.get("candidatesTokenCount") or 0),
                total_tokens=int(raw_usage.get("totalTokenCount") or 0),
            ),
            model=str(body.get("modelVersion") or ""),
            raw=body,
        )

    def models_request(self, settings: LLMSettings) -> tuple[str, dict[str, str]] | None:
        return settings.base_url.rstrip("/") + "/models", self._headers(settings)

    def parse_models(self, body: dict[str, Any]) -> list[ModelInfo]:
        entries = body.get("models")
        if not isinstance(entries, list):
            return []
        models: list[ModelInfo] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            # "models/gemini-3.7-flash" -> "gemini-3.7-flash": the dropdown value
            # must be the bare id, which is what generateContent takes.
            name = str(entry.get("name") or "").removeprefix("models/").strip()
            if not name:
                continue
            actions = entry.get("supportedGenerationMethods") or entry.get("supported_actions") or []
            # The catalogue mixes embedding and chat models with no marker; an
            # unfiltered list offers embedding-001 in a chat picker.
            if actions and "generateContent" not in actions:
                continue
            models.append(
                ModelInfo(
                    id=name,
                    display_name=str(entry.get("displayName") or name),
                    context_window=_as_int(entry.get("inputTokenLimit")),
                    max_output_tokens=_as_int(entry.get("outputTokenLimit")),
                    family="gemini",
                    source="server-reported",
                    meta={"description": entry.get("description") or ""},
                )
            )
        return models


def _as_int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None
