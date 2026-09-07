#!/usr/bin/env python3
"""OpenAI Chat Completions — the shape every Ariadne call site already used.

Covers OpenAI proper, vLLM, llama.cpp, Ollama's ``/v1``, LM Studio, DeepSeek and
any proxy speaking ``POST /chat/completions``. For an endpoint with no API key
this produces a byte-identical request to the one the hand-rolled clients sent
before this module existed, which is what lets the refactor land without moving
a graded number.
"""

from __future__ import annotations

from typing import Any

from utils.llm.config import LLMSettings
from utils.llm.types import ChatResult, Message, ModelInfo, Usage

from .base import bearer


class OpenAICompatAdapter:
    name = "openai-compatible"

    def chat_request(
        self,
        settings: LLMSettings,
        messages: list[Message],
        *,
        max_tokens: int,
        temperature: float,
        sampling: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        payload: dict[str, Any] = {
            "model": settings.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # The caller's sampling block (seed, top_p, thinking budget) is spread
        # last so an explicit choice wins over the defaults above.
        if sampling:
            payload.update(sampling)
        headers = {"Content-Type": "application/json", **bearer(settings)}
        return settings.chat_endpoint, headers, payload

    def parse_chat(self, body: dict[str, Any]) -> ChatResult:
        choices = body.get("choices") or []
        # An empty `choices` is the shape a server returns while it is still
        # loading weights. Treat it as no content rather than indexing into it.
        first = choices[0] if choices else {}
        message = first.get("message") or {}
        raw_usage = body.get("usage") or {}
        return ChatResult(
            # `content` is null (not "") on a length stop from several servers.
            content=message.get("content") or "",
            finish_reason=first.get("finish_reason") or "",
            usage=Usage(
                prompt_tokens=int(raw_usage.get("prompt_tokens") or 0),
                completion_tokens=int(raw_usage.get("completion_tokens") or 0),
                total_tokens=int(raw_usage.get("total_tokens") or 0),
            ),
            model=str(body.get("model") or ""),
            raw=body,
        )

    def models_request(self, settings: LLMSettings) -> tuple[str, dict[str, str]] | None:
        return settings.models_endpoint, {"Accept": "application/json", **bearer(settings)}

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
            # vLLM reports the real serving window here; OpenAI reports nothing
            # at all and never has. `max_model_len` present means server-reported,
            # absent means we genuinely do not know — not that it is unlimited.
            context = entry.get("max_model_len") or (entry.get("meta") or {}).get("n_ctx_train")
            models.append(
                ModelInfo(
                    id=model_id,
                    display_name=model_id,
                    context_window=int(context) if isinstance(context, (int, float)) else None,
                    family=str(entry.get("owned_by") or ""),
                    source="server-reported",
                    meta={k: v for k, v in entry.items() if k not in {"id", "object"}},
                )
            )
        return models
