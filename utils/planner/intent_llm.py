#!/usr/bin/env python3
"""OpenAI-compatible LLM intent classifier (the hybrid classifier path).

Mirrors ``llm_drafter.py`` / ``drafter_factory.py``: an optional LLM classifier
that refines the deterministic label, wrapped by a hybrid that falls back to the
deterministic classifier on *any* transport/HTTP/parse failure or an
out-of-taxonomy label. The classifier only biases the draft, so a fallback is
never fatal — the deterministic result is always a valid answer.

Enabled by ``PLANNER_INTENT_LLM_ENABLED`` (default off) and reuses the drafter's
LLM endpoint config (``PLANNER_LLM_BASE_URL`` / ``PLANNER_LLM_MODEL``).
"""

from __future__ import annotations

import dataclasses
import logging

from .config import PlannerConfig
from .intent import (
    DeterministicIntentClassifier,
    Intent,
    IntentClassification,
    IntentClassifier,
)
from .llm_drafter import DrafterUnavailable, extract_json_object
from utils.llm_sampling import sampling_params

logger = logging.getLogger("ariadne.planner.intent")


class ClassifierUnavailable(Exception):
    """Raised when the LLM endpoint cannot produce a usable classification."""


_SYSTEM_PROMPT = """\
You classify a cybersecurity analyst's graph-database question into EXACTLY ONE \
intent label. The label routes the question, so pick the most specific one.

Labels:
- correlation: correlates two sources on a shared id (e.g. which CAPEC patterns \
map to ATT&CK techniques). Prefer this whenever the question spans CAPEC AND \
ATT&CK.
- remediation: asks for mitigations / defensive controls for a technique.
- traversal: walks a hierarchy / neighbour / chain (parent, child, sub-technique).
- enumeration: lists or filters a set of entities ("list all techniques that ...").
- definitional: asks what a named entity is / to describe it (by name, not id).
- lookup: fetches one specific entity by its id (e.g. T1555, CAPEC-560).
- unsupported: no recognizable, in-scope intent.

Output ONLY a single JSON object (no prose, no markdown fences):
{"label": "<one label>", "confidence": <0..1>, "rationale": "<one sentence>", \
"cues": ["<phrase that decided it>", ...]}
"""


class LLMIntentClassifier:
    """Classifies intent via a configurable OpenAI-compatible chat endpoint."""

    def __init__(self, config: PlannerConfig) -> None:
        self._config = config

    @property
    def endpoint(self) -> str:
        return self._config.llm_base_url.rstrip("/") + "/chat/completions"

    def _post(self, request: str) -> str:
        import requests

        payload = {
            "model": self._config.llm_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"ANALYST REQUEST:\n{request}"},
            ],
            **sampling_params(max_tokens=self._config.llm_max_tokens),
        }
        try:
            resp = requests.post(
                self.endpoint, json=payload, timeout=self._config.llm_timeout_s
            )
        except requests.RequestException as exc:
            raise ClassifierUnavailable(f"request failed: {exc}") from exc
        if resp.status_code != 200:
            raise ClassifierUnavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ClassifierUnavailable(f"unexpected response shape: {exc}") from exc
        if not content:
            raise ClassifierUnavailable("model returned no content (raise max_tokens?)")
        return content

    def classify(self, request: str, cards=None) -> IntentClassification:
        content = self._post(request or "")
        try:
            data = extract_json_object(content)
        except DrafterUnavailable as exc:  # reuse the balanced-JSON parser
            raise ClassifierUnavailable(str(exc)) from exc
        label = str(data.get("label", "")).strip().lower()
        if not Intent.is_valid(label):
            raise ClassifierUnavailable(f"out-of-taxonomy label: {label!r}")
        confidence = data.get("confidence", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.0
        return IntentClassification(
            label=label,
            confidence=confidence,
            rationale=str(data.get("rationale", "")),
            cues=[str(c) for c in data.get("cues", []) if str(c).strip()],
            source="llm",
        )


class HybridIntentClassifier:
    """Tries the LLM classifier, falling back to deterministic on any failure."""

    def __init__(self, primary: IntentClassifier, fallback: IntentClassifier) -> None:
        self._primary = primary
        self._fallback = fallback
        self.last_used: str = ""

    def classify(self, request: str, cards=None) -> IntentClassification:
        try:
            result = self._primary.classify(request, cards)
            self.last_used = type(self._primary).__name__
            return result
        except ClassifierUnavailable as exc:
            logger.info("LLM classifier unavailable (%s); using deterministic fallback", exc)
            result = self._fallback.classify(request, cards)
            self.last_used = type(self._fallback).__name__
            # Record that the label came from the deterministic fallback, not the LLM.
            return dataclasses.replace(result, source="fallback")


def select_intent_classifier(config: PlannerConfig) -> IntentClassifier:
    """Return the configured classifier (hybrid LLM when enabled, else deterministic)."""
    deterministic = DeterministicIntentClassifier()
    if config.intent_llm_enabled:
        logger.info(
            "LLM intent classifier enabled: %s (model=%s)",
            config.llm_base_url, config.llm_model,
        )
        return HybridIntentClassifier(LLMIntentClassifier(config), deterministic)
    return deterministic
