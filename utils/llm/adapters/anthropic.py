#!/usr/bin/env python3
"""Anthropic Messages API.

Four differences break OpenAI habits, and three of them fail loudly enough to
find. The fourth does not: ``max_tokens`` is **required**, so a caller that omits
it gets a 400 rather than a default, which is why the client always passes one.

  * the system prompt is a top-level ``system=`` field, not a message;
  * auth is ``x-api-key`` plus a required ``anthropic-version`` header, not Bearer;
  * content comes back as a list of typed blocks, not a string;
  * the stop reason is ``stop_reason`` with different vocabulary
    (``max_tokens``, not ``length``).
"""

from __future__ import annotations

from typing import Any

from utils.llm.config import LLMSettings
from utils.llm.types import FINISH_LENGTH, ChatResult, Message, ModelInfo, Usage

from .base import split_system

#: Pinned rather than floating. An unpinned version header is a silent breaking
#: change on somebody else's deploy schedule.
API_VERSION = "2023-06-01"


class AnthropicAdapter:
    name = "anthropic"

    def _headers(self, settings: LLMSettings) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": settings.api_key,
            "anthropic-version": API_VERSION,
        }

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
            "model": settings.model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in rest],
        }
        if system:
            payload["system"] = system
        # Anthropic's temperature is 0..1 like OpenAI's, so 0 maps straight
        # through and the project's greedy-decoding posture is preserved.
        payload["temperature"] = temperature
        if sampling:
            # `seed` and vLLM's thinking-budget channels have no Anthropic
            # equivalent; passing them would 400. Only `top_p` survives.
            if "top_p" in sampling:
                payload["top_p"] = sampling["top_p"]
            budget = _thinking_budget(sampling)
            if budget:
                # Extended thinking requires temperature to be unset, and the
                # budget must leave room for the answer inside max_tokens.
                payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
                payload.pop("temperature", None)
        url = settings.base_url.rstrip("/") + "/messages"
        return url, self._headers(settings), payload

    def parse_chat(self, body: dict[str, Any]) -> ChatResult:
        blocks = body.get("content") or []
        text = "".join(
            str(b.get("text") or "")
            for b in blocks
            if isinstance(b, dict) and b.get("type") == "text"
        )
        raw_usage = body.get("usage") or {}
        prompt = int(raw_usage.get("input_tokens") or 0)
        completion = int(raw_usage.get("output_tokens") or 0)
        stop = str(body.get("stop_reason") or "")
        return ChatResult(
            content=text,
            # Normalize Anthropic's `max_tokens` stop reason onto the project's
            # `length`, so `ChatResult.truncated` means the same thing everywhere.
            finish_reason=FINISH_LENGTH if stop == "max_tokens" else stop,
            usage=Usage(prompt, completion, prompt + completion),
            model=str(body.get("model") or ""),
            raw=body,
        )

    def models_request(self, settings: LLMSettings) -> tuple[str, dict[str, str]] | None:
        return settings.base_url.rstrip("/") + "/models", self._headers(settings)

    def parse_models(self, body: dict[str, Any]) -> list[ModelInfo]:
        entries = body.get("data")
        if not isinstance(entries, list):
            return []
        models: list[ModelInfo] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("id") or "").strip()
            if not model_id:
                continue
            models.append(
                ModelInfo(
                    id=model_id,
                    display_name=str(entry.get("display_name") or model_id),
                    context_window=_as_int(entry.get("max_input_tokens")),
                    max_output_tokens=_as_int(entry.get("max_tokens")),
                    family="anthropic",
                    source="server-reported",
                    meta={"capabilities": entry.get("capabilities") or {}},
                )
            )
        return models


def _as_int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None


def _thinking_budget(sampling: dict[str, Any]) -> int:
    """Read the budget out of the vLLM-shaped sampling block, if present."""
    for key in ("chat_template_kwargs", "extra_body"):
        block = sampling.get(key)
        if isinstance(block, dict) and block.get("thinking_budget"):
            return int(block["thinking_budget"])
    return 0
