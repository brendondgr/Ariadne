"""View and edit the env-backed LLM and connection settings.

Reads resolve through ``PlannerConfig``/``SpecialistConfig.from_env()`` so the
service always reports what the agents would actually use. Writes go through
``utils.config.set_env_values()``, which rewrites the central ``.env`` in place
(preserving comments/ordering) **and** mirrors the new values into
``os.environ`` — so an edit takes effect on the next query without a restart.
The Neo4j password is write-only: it is accepted on update but never returned.
"""

from __future__ import annotations

import os
from pathlib import Path

from utils.config import set_env_values
from utils.evaluation.llm_judge.config import EvalConfig
from utils.orchestration.config import OrchestrationConfig
from utils.orchestration.main import pipeline_timeout_s
from utils.planner.config import PlannerConfig
from utils.specialists.config import SpecialistConfig
from utils.synthesis.config import SynthesisConfig

from ..models import (
    ConfigResponse,
    ConfigUpdateRequest,
    ConnectionConfig,
    LLMConfig,
    LLMGroup,
    LLMGroupUpdate,
    OrchestrationGroup,
)

# Single source of truth mapping update fields -> env var names, per agent.
_LLM_ENV_KEYS: dict[str, dict[str, str]] = {
    "planner": {
        "enabled": "PLANNER_LLM_ENABLED",
        "base_url": "PLANNER_LLM_BASE_URL",
        "model": "PLANNER_LLM_MODEL",
        "timeout_s": "PLANNER_LLM_TIMEOUT_S",
        "max_tokens": "PLANNER_LLM_MAX_TOKENS",
    },
    "specialist": {
        "enabled": "SPECIALIST_LLM_ENABLED",
        "base_url": "SPECIALIST_LLM_BASE_URL",
        "model": "SPECIALIST_LLM_MODEL",
        "timeout_s": "SPECIALIST_LLM_TIMEOUT_S",
        "max_tokens": "SPECIALIST_LLM_MAX_TOKENS",
    },
    "synthesis": {
        "enabled": "SYNTHESIS_LLM_ENABLED",
        "base_url": "SYNTHESIS_LLM_BASE_URL",
        "model": "SYNTHESIS_LLM_MODEL",
        "timeout_s": "SYNTHESIS_LLM_TIMEOUT_S",
        "max_tokens": "SYNTHESIS_LLM_MAX_TOKENS",
    },
    "eval": {
        "enabled": "EVAL_LLM_ENABLED",
        "base_url": "EVAL_LLM_BASE_URL",
        "model": "EVAL_LLM_MODEL",
        "timeout_s": "EVAL_LLM_TIMEOUT_S",
        "max_tokens": "EVAL_LLM_MAX_TOKENS",
    },
}

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


def _group(cfg: PlannerConfig | SpecialistConfig | SynthesisConfig | EvalConfig) -> LLMGroup:
    return LLMGroup(
        enabled=cfg.llm_enabled,
        base_url=cfg.llm_base_url,
        model=cfg.llm_model,
        timeout_s=cfg.llm_timeout_s,
        max_tokens=cfg.llm_max_tokens,
    )


def _orchestration_group() -> OrchestrationGroup:
    orch = OrchestrationConfig.from_env()
    return OrchestrationGroup(
        checkpointer=orch.checkpointer,
        recursion_limit=orch.recursion_limit,
        pipeline_timeout_s=pipeline_timeout_s(),
    )


def read_config() -> ConfigResponse:
    """Return the currently-resolved LLM and connection settings (password redacted)."""
    planner = PlannerConfig.from_env()
    specialist = SpecialistConfig.from_env()
    return ConfigResponse(
        llm=LLMConfig(
            planner=_group(planner),
            specialist=_group(specialist),
            synthesis=_group(SynthesisConfig.from_env()),
            eval=_group(EvalConfig.from_env()),
        ),
        connection=ConnectionConfig(
            neo4j_uri=planner.neo4j_uri,
            neo4j_user=planner.neo4j_user,
            neo4j_password_set=bool(os.environ.get("NEO4J_PASSWORD")),
            gremlin_uri=planner.gremlin_uri,
        ),
        orchestration=_orchestration_group(),
    )


def _to_env_str(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _collect_group_updates(agent: str, group: LLMGroupUpdate | None, out: dict[str, str]) -> None:
    if group is None:
        return
    keys = _LLM_ENV_KEYS[agent]
    for field, env_key in keys.items():
        value = getattr(group, field)
        if value is not None:
            out[env_key] = _to_env_str(value)


def collect_updates(request: ConfigUpdateRequest) -> dict[str, str]:
    """Flatten a partial update request into ``{ENV_VAR: value}`` pairs."""
    updates: dict[str, str] = {}
    _collect_group_updates("planner", request.planner, updates)
    _collect_group_updates("specialist", request.specialist, updates)
    _collect_group_updates("synthesis", request.synthesis, updates)
    _collect_group_updates("eval", request.eval, updates)
    if request.orchestration is not None:
        for field, env_key in _ORCH_ENV_KEYS.items():
            value = getattr(request.orchestration, field)
            if value is not None:
                updates[env_key] = _to_env_str(value)
    if request.connection is not None:
        for field, env_key in _CONNECTION_ENV_KEYS.items():
            value = getattr(request.connection, field)
            # Skip empty password so a blank field never clobbers the stored one.
            if value is None or (field == "neo4j_password" and value == ""):
                continue
            updates[env_key] = _to_env_str(value)
    return updates


def apply_update(
    request: ConfigUpdateRequest, env_file: str | Path | None = None
) -> ConfigResponse:
    """Persist a partial settings update and return the new resolved config."""
    updates = collect_updates(request)
    if updates:
        set_env_values(updates, env_file=env_file)
    return read_config()
