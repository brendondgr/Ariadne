#!/usr/bin/env python3
"""The model registry (Era 2, Step 2): what a test may call, and proof of what answered.

    from utils.llm.registry import load, require_identity

    reg = load()                        # utils/llm/models.yaml
    spec = reg["qwen38-27b"]
    identity = require_identity(spec)   # raises IdentityMismatch on a swapped model

**Why identity is checked by token id.** The relay's aliases have pointed at
four different models over this project's life, and since 2026-11-14 the
response envelope's ``model`` field names the *other* model. The tokenizer does
not lie: a plain reply ends on the family's end-of-turn token. So a model is
identified by asking it to say "ok" with ``return_token_ids`` and reading the
last id. A reply ending in a tool call ends on a different token, which is why
this is a separate probe rather than something read off each row.

A model whose identity cannot be checked (a decision model, an unknown id) is
reported as ``verified=None``, never as verified.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from utils.llm.client import complete_raw
from utils.llm.types import LLMUnavailable

REGISTRY_PATH = Path(__file__).with_name("models.yaml")
KINDS = ("llm", "decision", "reranker", "nli", "embedder")
#: ``open``: the operator has it running for us. ``closed``: listed for the
#: record, not to be called (runners refuse it without probing).
STATUSES = ("open", "closed")

#: The probe sends a real completion; 2,048 tokens because a reasoning model
#: given less can spend it all thinking and return nothing.
IDENTITY_MAX_TOKENS = 2048
IDENTITY_PROMPT = "Reply with the word ok."


class IdentityMismatch(RuntimeError):
    """The model behind an endpoint is not the one the registry names."""


@dataclass(frozen=True)
class ModelSpec:
    name: str
    kind: str
    endpoint: str
    alias: str | None = None
    stop_token_id: int | None = None
    family: str | None = None
    size: str | None = None
    licence: str | None = None
    context_window: int | None = None
    reasoning_param: str | None = None
    reasoning_values: tuple[str, ...] = ()
    reasoning_default: str | None = None
    native_tool_calls: bool = False
    grammar_constrained: bool = False
    #: Name of an environment variable holding an API key; never the key itself.
    api_key_env: str | None = None
    notes: str = ""
    status: str = "open"
    #: Concurrent requests the operator has said the server takes; None = unknown.
    max_concurrency: int | None = None
    max_tokens: int = 16384
    long_max_tokens: int = 32768
    connect_timeout_s: float = 3.0
    read_timeout_s: float = 600.0

    @property
    def headers(self) -> dict[str, str]:
        key = os.environ.get(self.api_key_env, "") if self.api_key_env else ""
        return {"Authorization": f"Bearer {key}"} if key else {}

    def reasoning_extra(self, level: str | None = None) -> dict[str, Any]:
        """The request field that sets the thinking level, or ``{}``."""
        if not self.reasoning_param:
            if level:
                raise ValueError(f"{self.name} has no reasoning control; got level {level!r}")
            return {}
        value = level or self.reasoning_default
        if value is None:
            return {}
        if self.reasoning_values and value not in self.reasoning_values:
            raise ValueError(f"{self.name}: {self.reasoning_param}={value!r} not in {self.reasoning_values}")
        return {self.reasoning_param: value}


@dataclass(frozen=True)
class Identity:
    """The outcome of one identity probe."""

    model: str
    #: True: the expected tokenizer answered. False: another one did.
    #: None: this model cannot be checked this way.
    verified: bool | None
    expected_token_id: int | None = None
    last_token_id: int | None = None
    envelope_model: str = ""
    checked_at: float = field(default_factory=time.time)
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "verified": self.verified,
            "expected_token_id": self.expected_token_id,
            "last_token_id": self.last_token_id,
            "envelope_model": self.envelope_model,
            "checked_at": round(self.checked_at, 3),
            "reason": self.reason,
        }


class Registry(dict[str, ModelSpec]):
    """``name -> ModelSpec``, plus the defaults block it was loaded with."""

    def __init__(self, specs: dict[str, ModelSpec], defaults: dict[str, Any], path: Path) -> None:
        super().__init__(specs)
        self.defaults = defaults
        self.path = path

    @property
    def default(self) -> ModelSpec:
        """The model every step uses unless told otherwise (``defaults.default_model``)."""
        name = self.defaults.get("default_model")
        if not name:
            raise KeyError(f"{self.path} names no defaults.default_model")
        return self[name]

    def open_models(self) -> list[str]:
        return [n for n, s in self.items() if s.status == "open"]

    def __missing__(self, key: str) -> ModelSpec:
        raise KeyError(f"no model {key!r} in {self.path}; known: {', '.join(sorted(self))}")


def _spec(name: str, entry: dict[str, Any], defaults: dict[str, Any]) -> ModelSpec:
    kind = entry.get("kind")
    if kind not in KINDS:
        raise ValueError(f"{name}: kind must be one of {KINDS}, got {kind!r}")
    endpoint = entry.get("endpoint")
    if not endpoint:
        raise ValueError(f"{name}: endpoint is required")
    identity = entry.get("identity") or {}
    reasoning = entry.get("reasoning") or {}
    tools = entry.get("tool_calls") or {}
    status = entry.get("status") or "open"
    if status not in STATUSES:
        raise ValueError(f"{name}: status must be one of {STATUSES}, got {status!r}")
    if kind == "llm" and not entry.get("alias"):
        raise ValueError(f"{name}: an llm needs the alias it is reached by")
    return ModelSpec(
        name=name,
        kind=kind,
        endpoint=str(endpoint),
        alias=entry.get("alias"),
        stop_token_id=identity.get("stop_token_id"),
        family=identity.get("family"),
        size=entry.get("size"),
        licence=entry.get("licence"),
        context_window=entry.get("context_window"),
        reasoning_param=reasoning.get("param"),
        reasoning_values=tuple(reasoning.get("values") or ()),
        reasoning_default=reasoning.get("default"),
        native_tool_calls=bool(tools.get("native")),
        grammar_constrained=bool(tools.get("grammar_constrained")),
        api_key_env=entry.get("api_key_env"),
        notes=str(entry.get("notes") or "").strip(),
        status=status,
        max_concurrency=entry.get("max_concurrency"),
        max_tokens=int(entry.get("max_tokens") or defaults.get("max_tokens") or 16384),
        long_max_tokens=int(entry.get("long_max_tokens") or defaults.get("long_max_tokens") or 32768),
        connect_timeout_s=float(defaults.get("connect_timeout_s") or 3.0),
        read_timeout_s=float(defaults.get("read_timeout_s") or 600.0),
    )


def load(path: str | Path | None = None) -> Registry:
    """Read and validate a registry file (default ``utils/llm/models.yaml``)."""
    p = Path(path) if path else REGISTRY_PATH
    raw = yaml.safe_load(p.read_text()) or {}
    defaults = raw.get("defaults") or {}
    if (defaults.get("max_tokens") or 0) < 2048:
        raise ValueError("defaults.max_tokens must be >= 2048 (reasoning models truncate to empty)")
    if defaults.get("fallback"):
        raise ValueError("defaults.fallback must be null: fallback is opt-in per call, never a default")
    specs = {name: _spec(name, entry or {}, defaults) for name, entry in (raw.get("models") or {}).items()}
    dm = defaults.get("default_model")
    for spec in specs.values():
        if spec.kind == "llm" and spec.status == "open" and spec.stop_token_id is None:
            raise ValueError(f"{spec.name}: an open llm needs identity.stop_token_id (probe it first)")
    if dm is not None and (dm not in specs or specs[dm].status != "open"):
        raise ValueError(f"defaults.default_model {dm!r} must name an open model")
    return Registry(specs, defaults, p)


#: Process-wide cache: one probe per model per ``max_age_s``.
_IDENTITY_CACHE: dict[tuple[str, str, str | None], Identity] = {}


def check_identity(spec: ModelSpec, *, max_age_s: float = 0.0) -> Identity:
    """Probe ``spec``'s endpoint and compare the tokenizer's end-of-turn id.

    Raises :class:`LLMUnavailable` when the endpoint cannot be reached; a
    mismatch is returned as ``verified=False``, not raised (see
    :func:`require_identity`).
    """
    if spec.kind != "llm" or spec.stop_token_id is None:
        return Identity(spec.name, None, reason=f"{spec.kind} model: no token-id identity check")
    key = (spec.name, spec.endpoint, spec.alias)
    cached = _IDENTITY_CACHE.get(key)
    if cached and max_age_s and time.time() - cached.checked_at <= max_age_s:
        return cached
    payload: dict[str, Any] = {
        "model": spec.alias,
        "max_tokens": IDENTITY_MAX_TOKENS,
        "temperature": 0.0,
        "return_token_ids": True,
        "messages": [{"role": "user", "content": IDENTITY_PROMPT}],
    }
    payload.update(spec.reasoning_extra())
    raw = complete_raw(spec.endpoint, payload, headers=spec.headers, stream=False,
                       connect_timeout_s=spec.connect_timeout_s, read_timeout_s=300.0)
    last = raw.token_ids[-1] if raw.token_ids else None
    if last is None:
        ident = Identity(spec.name, None, spec.stop_token_id, None, raw.envelope_model,
                         reason="the server returned no token ids (return_token_ids unsupported?)")
    elif last == spec.stop_token_id:
        ident = Identity(spec.name, True, spec.stop_token_id, last, raw.envelope_model)
    else:
        ident = Identity(spec.name, False, spec.stop_token_id, last, raw.envelope_model,
                         reason=(f"expected end-of-turn id {spec.stop_token_id} ({spec.family}), "
                                 f"got {last}: another model is behind {spec.alias!r}"))
    _IDENTITY_CACHE[key] = ident
    return ident


def require_identity(spec: ModelSpec, *, max_age_s: float = 0.0, allow_unverifiable: bool = False) -> Identity:
    """:func:`check_identity`, raising :class:`IdentityMismatch` unless verified."""
    ident = check_identity(spec, max_age_s=max_age_s)
    if ident.verified is False:
        raise IdentityMismatch(f"{spec.name}: {ident.reason}")
    if ident.verified is None and not allow_unverifiable:
        raise IdentityMismatch(f"{spec.name}: identity cannot be verified ({ident.reason})")
    return ident


def clear_identity_cache() -> None:
    _IDENTITY_CACHE.clear()


__all__ = [
    "IDENTITY_MAX_TOKENS",
    "REGISTRY_PATH",
    "Identity",
    "IdentityMismatch",
    "LLMUnavailable",
    "ModelSpec",
    "Registry",
    "check_identity",
    "clear_identity_cache",
    "load",
    "require_identity",
]
