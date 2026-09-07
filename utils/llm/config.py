#!/usr/bin/env python3
"""The single source of truth for how Ariadne talks to a language model.

Before this module the project had **five** independent LLM config groups —
``PLANNER_LLM_*``, ``SPECIALIST_LLM_*``, ``SYNTHESIS_LLM_*``, ``EVAL_LLM_*`` and
``CONVERSATION_LLM_*`` — each with its own enabled/base_url/model/timeout/
max_tokens, plus a sixth de-facto group in the global ``LLM_THINKING_BUDGET``.
Configuring the workbench meant knowing which of them the chat pane actually
reached (the answer was ``CONVERSATION_LLM_*``, which silently inherited
``SYNTHESIS_LLM_*``, and which the settings modal did not show at all).

There is now one group, ``ARIADNE_LLM_*``. Every stage resolves from it unless
that stage explicitly overrides a field:

    <STAGE>_LLM_<FIELD>   ->   ARIADNE_LLM_<FIELD>   ->   built-in default

The per-stage names are kept rather than deleted for two reasons. They are what
roughly twenty scripts under ``scripts/`` and every arm in
``docs/research/experiments/`` pin, so removing them would invalidate the
reproducibility record; and they are the mechanism behind the workbench's
per-stage endpoint overrides, which is how an operator points the judge at a
second GPU. What makes the configuration *single* is that they default to
inheriting and live in one collapsed section of one modal — not that they are
unreachable.

Two invariants this module owns
-------------------------------

**The thinking budget is one value and it is bounded.** A reasoning model given
room spends it: the record has 4,134 tokens of answer behind 16,106 characters
of preamble, and 42,602 characters when unbounded. A budget at or above
``max_tokens`` does not merely waste the allowance, it is the configuration that
returns empty content — which reaches a caller as a silent "LLM unavailable"
fallback rather than an error. So a positive ``thinking_budget`` must be
strictly less than ``max_tokens``. :meth:`LLMSettings.validate` reports that as
a field error for the API and the UI to render; :func:`resolve` clamps as a last
resort for a hand-edited ``.env`` and says so in the log, because a value that
quietly becomes something else is how runs have been lost here before.

**Nothing is derived silently.** ``SynthesisConfig.thinking_budget()`` used to
fall back to ``max_tokens // 2``, so changing the token cap moved the budget
without anyone asking. A default that changes when an unrelated field changes is
a second source wearing a disguise. ``0`` means "send no cap", which is what
every recorded run predating the cap did, and it stays the default.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, replace
from enum import Enum

from utils.config import env_bool, env_int, env_str

logger = logging.getLogger("ariadne.llm.config")

# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #


class LLMProvider(str, Enum):
    """A backend kind, which decides message shape, auth header and token field.

    ``OPENAI_COMPATIBLE`` is the project default and covers every local server —
    vLLM, llama.cpp, Ollama's ``/v1``, LM Studio, DeepSeek — plus any proxy that
    speaks ``POST /chat/completions``. It is what every existing Ariadne call
    site has always used, so leaving the provider unset changes nothing.
    """

    OPENAI_COMPATIBLE = "openai-compatible"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"

    @classmethod
    def parse(cls, value: str | None, default: "LLMProvider | None" = None) -> "LLMProvider":
        """Parse a provider name, tolerating spelling variants; never raises."""
        fallback = default or cls.OPENAI_COMPATIBLE
        if not value:
            return fallback
        normalized = value.strip().lower().replace("_", "-")
        aliases = {
            "openai-compat": cls.OPENAI_COMPATIBLE,
            "compatible": cls.OPENAI_COMPATIBLE,
            "local": cls.OPENAI_COMPATIBLE,
            "vllm": cls.OPENAI_COMPATIBLE,
            "llamacpp": cls.OPENAI_COMPATIBLE,
            "llama-cpp": cls.OPENAI_COMPATIBLE,
            "lmstudio": cls.OPENAI_COMPATIBLE,
            "lm-studio": cls.OPENAI_COMPATIBLE,
            "deepseek": cls.OPENAI_COMPATIBLE,
            "claude": cls.ANTHROPIC,
            "google": cls.GEMINI,
            "google-genai": cls.GEMINI,
        }
        if normalized in aliases:
            return aliases[normalized]
        for member in cls:
            if member.value == normalized:
                return member
        logger.warning("Unknown LLM provider %r; falling back to %s", value, fallback.value)
        return fallback

    def requires_api_key(self) -> bool:
        """Whether a call to this provider is refused without credentials.

        The local kinds are deliberately excluded: an OpenAI-compatible server on
        localhost normally takes no key, and demanding one would make the default
        configuration invalid.
        """
        return self in {LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.GEMINI}

    def default_base_url(self) -> str:
        """The vendor endpoint for a hosted provider, else the local default."""
        return {
            LLMProvider.OPENAI: "https://api.openai.com/v1",
            LLMProvider.ANTHROPIC: "https://api.anthropic.com/v1",
            LLMProvider.GEMINI: "https://generativelanguage.googleapis.com/v1beta",
            LLMProvider.OLLAMA: "http://localhost:11434/v1",
        }.get(self, DEFAULT_BASE_URL)


#: Default endpoint/model, unchanged from what every per-stage group used before
#: this module existed, so an unset ``ARIADNE_LLM_*`` resolves identically.
DEFAULT_BASE_URL = "http://localhost:9090/v1"
DEFAULT_MODEL = "default-model"
DEFAULT_TIMEOUT_S = 30.0
DEFAULT_MAX_TOKENS = 4096
#: 0 means "send no thinking cap" — the behaviour of every run predating the cap.
DEFAULT_THINKING_BUDGET = 0
#: A local server that is not running must fail fast; generation legitimately
#: takes minutes. One number cannot be both, so they are two.
DEFAULT_CONNECT_TIMEOUT_S = 5.0

#: The stages that have a real read site, in the order the UI lists them.
STAGES: tuple[str, ...] = ("planner", "specialist", "synthesis", "conversation", "eval")

#: Per-stage env prefixes. ``eval`` is spelled ``EVAL`` rather than ``EVALUATOR``
#: because that is the name already on disk in every recorded protocol.
_STAGE_PREFIX: dict[str, str] = {
    "planner": "PLANNER",
    "specialist": "SPECIALIST",
    "synthesis": "SYNTHESIS",
    "conversation": "CONVERSATION",
    "eval": "EVAL",
}

#: The primary group's prefix.
PRIMARY_PREFIX = "ARIADNE"

#: Config field -> env suffix. The suffix is shared by the primary group and
#: every stage, so ``ARIADNE_LLM_MODEL`` and ``SYNTHESIS_LLM_MODEL`` are the same
#: knob at two scopes.
FIELD_SUFFIX: dict[str, str] = {
    "enabled": "ENABLED",
    "provider": "PROVIDER",
    "base_url": "BASE_URL",
    "model": "MODEL",
    "api_key": "API_KEY",
    "timeout_s": "TIMEOUT_S",
    "max_tokens": "MAX_TOKENS",
    "thinking_budget": "THINKING_BUDGET",
}

#: ``max_tokens`` and ``thinking_budget`` move together. A stage that overrode
#: only one of them would run a budget sized against somebody else's token cap,
#: which is precisely the invariant this module exists to hold, so overriding
#: either carries both.
COUPLED_FIELDS: frozenset[str] = frozenset({"max_tokens", "thinking_budget"})

#: Fields whose value is a secret and must never be echoed back over the API.
SECRET_FIELDS: frozenset[str] = frozenset({"api_key"})


def env_key(field_name: str, stage: str | None = None) -> str:
    """The env var name for ``field_name``, at the primary or a stage scope."""
    suffix = FIELD_SUFFIX[field_name]
    prefix = PRIMARY_PREFIX if stage is None else _STAGE_PREFIX[stage]
    return f"{prefix}_LLM_{suffix}"


def stage_env_keys(stage: str) -> dict[str, str]:
    """``{field: ENV_VAR}`` for one stage — what the API sets and unsets."""
    return {name: env_key(name, stage) for name in FIELD_SUFFIX}


def primary_env_keys() -> dict[str, str]:
    """``{field: ENV_VAR}`` for the primary ``ARIADNE_LLM_*`` group."""
    return {name: env_key(name) for name in FIELD_SUFFIX}


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FieldError:
    """One rejected field, in the shape the API turns into a 422."""

    field: str
    message: str


@dataclass(frozen=True)
class LLMSettings:
    """One fully-resolved LLM endpoint.

    ``inherited`` names the fields this object took from the primary group rather
    than from its own stage. The UI renders a stage row as ``inherit`` versus
    ``custom`` from it, and the API reports it so an operator can see what a
    stage is *actually* using rather than what it was configured with.
    """

    enabled: bool = False
    provider: LLMProvider = LLMProvider.OPENAI_COMPATIBLE
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key: str = ""
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_tokens: int = DEFAULT_MAX_TOKENS
    thinking_budget: int = DEFAULT_THINKING_BUDGET
    connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S
    #: Which stage this resolved for; ``None`` for the primary group itself.
    stage: str | None = None
    #: Field names inherited from the primary group (i.e. not stage-overridden).
    inherited: frozenset[str] = field(default_factory=frozenset)

    # -- derived ---------------------------------------------------------- #

    @property
    def chat_endpoint(self) -> str:
        """The OpenAI-compatible chat URL. Kept for the existing call sites."""
        return self.base_url.rstrip("/") + "/chat/completions"

    @property
    def models_endpoint(self) -> str:
        """The OpenAI-compatible model-listing URL."""
        return self.base_url.rstrip("/") + "/models"

    @property
    def api_key_set(self) -> bool:
        """Whether a key is configured — the only thing the API may reveal."""
        return bool(self.api_key)

    def is_inherited(self, field_name: str) -> bool:
        return field_name in self.inherited

    # -- validation ------------------------------------------------------- #

    def validate(self) -> list[FieldError]:
        """Return field errors, empty when the settings are coherent.

        Reporting rather than repairing is deliberate. The API turns these into a
        422 with a named field and the modal disables Save; a value the server
        silently rewrites is indistinguishable, downstream, from a value the
        operator chose.
        """
        errors: list[FieldError] = []

        if not self.base_url.startswith(("http://", "https://")):
            errors.append(FieldError("base_url", "base_url must start with http:// or https://"))
        if not self.model.strip():
            errors.append(FieldError("model", "model must not be empty"))
        if self.timeout_s <= 0:
            errors.append(FieldError("timeout_s", "timeout_s must be greater than 0"))
        if self.max_tokens < 1:
            errors.append(FieldError("max_tokens", "max_tokens must be at least 1"))
        if self.thinking_budget < 0:
            errors.append(
                FieldError("thinking_budget", "thinking_budget must not be negative")
            )
        elif self.thinking_budget and self.thinking_budget >= self.max_tokens:
            # The invariant this module exists for. A budget that consumes the
            # whole allowance leaves nothing for the answer, and the model
            # returns empty content rather than an error.
            errors.append(
                FieldError(
                    "thinking_budget",
                    f"thinking_budget ({self.thinking_budget}) must be less than "
                    f"max_tokens ({self.max_tokens}); use 0 to send no cap",
                )
            )
        if self.provider.requires_api_key() and not self.api_key:
            errors.append(
                FieldError("api_key", f"{self.provider.value} requires an API key")
            )
        return errors

    def clamped(self) -> "LLMSettings":
        """Return a copy with the budget forced below ``max_tokens``.

        The last-resort path for a hand-edited ``.env`` that the API never saw.
        It logs, because silently substituting a different number is the failure
        mode the validation above exists to avoid.
        """
        if self.thinking_budget and self.thinking_budget >= self.max_tokens:
            safe = max(0, self.max_tokens - 1)
            logger.warning(
                "%s thinking budget %d >= max_tokens %d; clamping to %d. "
                "A budget that consumes the whole allowance returns empty content.",
                self.stage or "primary",
                self.thinking_budget,
                self.max_tokens,
                safe,
            )
            return replace(self, thinking_budget=safe)
        return self

    def redacted(self) -> "LLMSettings":
        """A copy with the API key removed, safe to serialize outward."""
        return replace(self, api_key="")


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #


def _raw(field_name: str, stage: str | None) -> str | None:
    """The raw env value at one scope, or ``None`` when unset/empty."""
    value = os.environ.get(env_key(field_name, stage))
    if value is None or value.strip() == "":
        return None
    return value


def _stage_overrides(stage: str) -> set[str]:
    """Which fields this stage sets for itself.

    ``max_tokens`` and ``thinking_budget`` are coupled: setting either counts as
    setting both, so a stage can never pair its own token cap with the primary's
    budget (or the reverse), which would break the ``budget < max_tokens``
    invariant in a way neither scope's validation would catch.
    """
    present = {name for name in FIELD_SUFFIX if _raw(name, stage) is not None}
    if present & COUPLED_FIELDS:
        present |= COUPLED_FIELDS
    return present


def resolve(
    stage: str | None = None,
    *,
    defaults: LLMSettings | None = None,
    clamp: bool = True,
) -> LLMSettings:
    """Resolve one endpoint from the environment.

    Lookup order per field is ``<STAGE>_LLM_<FIELD>`` -> ``ARIADNE_LLM_<FIELD>``
    -> the built-in default, so with nothing set every stage resolves to exactly
    the values the per-stage configs used before this module existed.

    Args:
        stage: One of :data:`STAGES`, or ``None`` for the primary group.
        defaults: Base values to fall back to instead of the module defaults.
            Used by callers whose historical default differs — the specialist's
            2048 max tokens, the judge's 32000 — so this refactor does not move
            a number any recorded run depends on.
        clamp: Force the thinking budget below ``max_tokens`` when a hand-edited
            ``.env`` violates it. Callers that want to *report* the violation
            instead (the API) pass ``False`` and use :meth:`LLMSettings.validate`.

    Returns:
        The resolved settings, with ``inherited`` naming the fields that came
        from the primary group rather than from ``stage``.
    """
    if stage is not None and stage not in _STAGE_PREFIX:
        raise ValueError(f"Unknown LLM stage: {stage!r} (expected one of {STAGES})")

    base = defaults or LLMSettings()
    overrides = _stage_overrides(stage) if stage is not None else set()

    def pick(field_name: str) -> str | None:
        """The winning raw value: the stage's if it overrides, else the primary's."""
        if stage is not None and field_name in overrides:
            own = _raw(field_name, stage)
            if own is not None:
                return own
            # Reached only via the coupled-field widening: the partner field was
            # set and this one was not, so the stage still owns it and takes the
            # primary's value as its own rather than inheriting the label.
        return _raw(field_name, None)

    def as_bool(field_name: str, fallback: bool) -> bool:
        raw = pick(field_name)
        return fallback if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}

    def as_float(field_name: str, fallback: float) -> float:
        raw = pick(field_name)
        if raw is None:
            return fallback
        try:
            return float(raw)
        except ValueError:
            logger.warning("%s is not a number (%r); using %s", env_key(field_name, stage), raw, fallback)
            return fallback

    def as_int(field_name: str, fallback: int) -> int:
        raw = pick(field_name)
        if raw is None:
            return fallback
        try:
            return int(raw)
        except ValueError:
            logger.warning("%s is not an integer (%r); using %s", env_key(field_name, stage), raw, fallback)
            return fallback

    def as_str(field_name: str, fallback: str) -> str:
        raw = pick(field_name)
        return fallback if raw is None else raw

    provider = LLMProvider.parse(pick("provider"), base.provider)
    # A hosted provider selected without an explicit URL gets its vendor endpoint
    # rather than localhost:9090, which would otherwise fail with a confusing
    # connection error rather than a missing-key one.
    url_fallback = base.base_url
    if pick("base_url") is None and provider is not base.provider:
        url_fallback = provider.default_base_url()

    settings = LLMSettings(
        enabled=as_bool("enabled", base.enabled),
        provider=provider,
        base_url=as_str("base_url", url_fallback),
        model=as_str("model", base.model),
        api_key=as_str("api_key", base.api_key),
        timeout_s=as_float("timeout_s", base.timeout_s),
        max_tokens=as_int("max_tokens", base.max_tokens),
        thinking_budget=as_int("thinking_budget", base.thinking_budget),
        connect_timeout_s=base.connect_timeout_s,
        stage=stage,
        inherited=frozenset(FIELD_SUFFIX) - overrides if stage is not None else frozenset(),
    )
    return settings.clamped() if clamp else settings


def resolve_all(*, clamp: bool = True) -> dict[str, LLMSettings]:
    """Resolve the primary group and every stage — what ``GET /api/config`` returns."""
    resolved = {"primary": resolve(None, clamp=clamp)}
    for stage in STAGES:
        resolved[stage] = resolve(stage, clamp=clamp)
    return resolved
