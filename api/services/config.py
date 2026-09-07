"""View and edit the LLM and connection settings behind the workbench.

Reads resolve through :func:`utils.llm.config.resolve` so the service always
reports what the agents would actually use, and writes go through
``utils.config.set_env_values`` / ``unset_env_values``, which rewrite the central
``.env`` in place (preserving comments and ordering) **and** mirror into
``os.environ`` — so an edit takes effect on the next query without a restart.

Two things are write-only and never returned: the Neo4j password and the LLM API
key. ``*_set`` booleans report whether each is configured.

**Why one LLM group.** This module used to expose four sibling groups —
planner, specialist, synthesis, eval — and the settings modal rendered all four.
That was confusing rather than flexible. The chat pane actually ran on a *fifth*
group the modal never showed (``CONVERSATION_LLM_*``, silently inheriting
synthesis), and of the four on screen, ``SPECIALIST_LLM_ENABLED`` is inert unless
the experiment-only query-builder flag is on and ``EVAL_LLM_*`` only affects the
offline judge. So an operator could fill in an endpoint, flip toggles, and have
no way to tell which one made the model answer.

Now there is one group, ``ARIADNE_LLM_*``, that every stage follows, plus
per-stage overrides for the operator who genuinely wants a second endpoint (the
judge on another GPU, a cheap local model for routing and a hosted one for the
visible answer). A stage reverts to following the default by *unsetting* its
keys, never by having the default's current values written into it — that would
pin a moving target the next time the default changed.
"""

from __future__ import annotations

import os
from pathlib import Path

from utils.config import set_env_values, unset_env_values
from utils.llm.config import (
    FIELD_SUFFIX,
    STAGES,
    LLMSettings,
    env_key,
    resolve,
)
from utils.orchestration.config import OrchestrationConfig
from utils.orchestration.main import pipeline_timeout_s
from utils.planner.config import PlannerConfig

from ..models import (
    ConfigResponse,
    ConfigUpdateRequest,
    ConnectionConfig,
    LLMConfig,
    LLMGroup,
    LLMGroupUpdate,
    OrchestrationGroup,
)

_CONNECTION_ENV_KEYS = {
    "neo4j_uri": "NEO4J_URI",
    "neo4j_user": "NEO4J_USER",
    "neo4j_password": "NEO4J_PASSWORD",
    "gremlin_uri": "GREMLIN_URI",
}

_ORCH_ENV_KEYS = {
    "checkpointer": "ORCH_CHECKPOINTER",
    "recursion_limit": "ORCH_RECURSION_LIMIT",
    "pipeline_timeout_s": "PIPELINE_TIMEOUT_S",
}


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


def _group(settings: LLMSettings) -> LLMGroup:
    """Serialize resolved settings, with the API key redacted to a boolean."""
    return LLMGroup(
        enabled=settings.enabled,
        provider=settings.provider.value,
        base_url=settings.base_url,
        model=settings.model,
        api_key_set=settings.api_key_set,
        timeout_s=settings.timeout_s,
        max_tokens=settings.max_tokens,
        thinking_budget=settings.thinking_budget,
        inherited=sorted(settings.inherited),
    )


def _orchestration_group() -> OrchestrationGroup:
    orch = OrchestrationConfig.from_env()
    return OrchestrationGroup(
        checkpointer=orch.checkpointer,
        recursion_limit=orch.recursion_limit,
        pipeline_timeout_s=pipeline_timeout_s(),
    )


def read_config() -> ConfigResponse:
    """Return the resolved LLM and connection settings (secrets redacted)."""
    planner = PlannerConfig.from_env()
    return ConfigResponse(
        llm=LLMConfig(
            default=_group(resolve(None)),
            stages={stage: _group(resolve(stage)) for stage in STAGES},
        ),
        connection=ConnectionConfig(
            neo4j_uri=planner.neo4j_uri,
            neo4j_user=planner.neo4j_user,
            neo4j_password_set=bool(os.environ.get("NEO4J_PASSWORD")),
            gremlin_uri=planner.gremlin_uri,
        ),
        orchestration=_orchestration_group(),
    )


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #


def _to_env_str(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _collect_llm_group(
    group: LLMGroupUpdate | None,
    stage: str | None,
    sets: dict[str, str],
    unsets: set[str],
) -> None:
    """Flatten one group's update into env sets and unsets."""
    if group is None:
        return

    # `inherit` first, so a field named in both is set rather than cleared — the
    # explicit value is the more specific instruction.
    for field_name in group.inherit:
        if field_name in FIELD_SUFFIX:
            unsets.add(env_key(field_name, stage))

    for field_name in FIELD_SUFFIX:
        value = getattr(group, field_name, None)
        if value is None:
            continue
        # An empty API key means "leave the stored one alone", never "clear it";
        # clearing goes through `inherit`. Same rule as neo4j_password.
        if field_name == "api_key" and value == "":
            continue
        key = env_key(field_name, stage)
        sets[key] = _to_env_str(value)
        unsets.discard(key)


def collect_updates(
    request: ConfigUpdateRequest,
) -> tuple[dict[str, str], set[str]]:
    """Flatten an update request into ``({ENV_VAR: value}, {ENV_VAR to clear})``."""
    sets: dict[str, str] = {}
    unsets: set[str] = set()

    _collect_llm_group(request.llm, None, sets, unsets)
    for stage, group in (request.llm_stages or {}).items():
        if stage not in STAGES:
            raise ValueError(f"Unknown LLM stage: {stage!r} (expected one of {STAGES})")
        _collect_llm_group(group, stage, sets, unsets)

    if request.orchestration is not None:
        for field_name, key in _ORCH_ENV_KEYS.items():
            value = getattr(request.orchestration, field_name)
            if value is not None:
                sets[key] = _to_env_str(value)

    if request.connection is not None:
        for field_name, key in _CONNECTION_ENV_KEYS.items():
            value = getattr(request.connection, field_name)
            # Skip an empty password so a blank field never clobbers the stored one.
            if value is None or (field_name == "neo4j_password" and value == ""):
                continue
            sets[key] = _to_env_str(value)

    return sets, unsets


def validate_update(request: ConfigUpdateRequest) -> list[str]:
    """Field errors this update would produce, checked against resolved values.

    The per-model validator already catches an update that carries both
    ``max_tokens`` and ``thinking_budget``. This catches the partial case — an
    operator lowering ``max_tokens`` below a budget that is already stored —
    which the request alone cannot see.
    """
    sets, unsets = collect_updates(request)
    errors: list[str] = []

    # Apply the update to a copy of the environment and re-resolve, so the check
    # runs against what the settings WOULD become rather than what they are.
    saved = dict(os.environ)
    try:
        for key, value in sets.items():
            os.environ[key] = value
        for key in unsets:
            os.environ.pop(key, None)
        for scope in (None, *STAGES):
            resolved = resolve(scope, clamp=False)
            label = scope or "default"
            errors += [
                f"{label}.{err.field}: {err.message}" for err in resolved.validate()
            ]
    finally:
        os.environ.clear()
        os.environ.update(saved)
    return errors


def apply_update(
    request: ConfigUpdateRequest, env_file: str | Path | None = None
) -> ConfigResponse:
    """Persist a partial settings update and return the new resolved config."""
    sets, unsets = collect_updates(request)
    # Unset first: a field named in both was already removed from `unsets`, so
    # ordering only matters for keys being genuinely cleared.
    if unsets:
        unset_env_values(sorted(unsets), env_file=env_file)
    if sets:
        set_env_values(sets, env_file=env_file)
    return read_config()
